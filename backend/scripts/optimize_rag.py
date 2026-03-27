import random

import random

_orig_randrange = random.randrange
_orig_inst_randrange = random.Random.randrange

def _safe_inst_randrange(self, *args, **kwargs):
    try:
        if len(args) == 2 and args[0] == args[1]:
            return args[0] - 1 if args[0] > 0 else 0
        return _orig_inst_randrange(self, *args, **kwargs)
    except ValueError as e:
        if "empty range" in str(e):
            return 0
        raise

random.Random.randrange = _safe_inst_randrange

def _safe_randrange(*args, **kwargs):
    try:
        if len(args) == 2 and args[0] == args[1]:
            return args[0] - 1 if args[0] > 0 else 0
        return _orig_randrange(*args, **kwargs)
    except ValueError as e:
        if "empty range" in str(e):
            return 0
        raise

random.randrange = _safe_randrange

import dspy
import json
import asyncio
import os
import logging
from dspy.teleprompt import BootstrapFewShot
from src.infrastructure.dspy_utils import YandexGPTLM
from src.infrastructure.dspy_program import RAGModule, overlap_metric, WinnerSelectionSignature
from src.application.rag_service import RAGService
from src.config import Config
from src.api.dependencies import (
    get_xmlriver_client, get_ranker, get_yandex_gpt_client, 
    get_chunker, get_source_processor, get_metric_service
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optimizer")
# ---------------------------------------------------------
from dspy.teleprompt import MIPROv2

class RescueMIPRO(MIPROv2):
    """Кастомный MIPROv2, который подменяет этап генерации инструкций, если он падает."""
    def _propose_instructions(self, *args, **kwargs):
        # Suppress Yandex SDK noise
        logging.getLogger("yandex_cloud_ml_sdk").setLevel(logging.WARNING)
        logging.getLogger("yandex_ai_studio_sdk").setLevel(logging.WARNING)
        logging.getLogger("grpc").setLevel(logging.WARNING)
        
        logger.info("RescueMIPRO: Attempting to propose instructions...")
        try:
            result = super()._propose_instructions(*args, **kwargs)
            # Log sizes for debugging
            if isinstance(result, dict):
                sizes = {k: len(v) for k, v in result.items()}
                logger.info(f"Proposed instruction candidate sizes: {sizes}")
            return result
        except Exception as e:
            logger.warning(f"RescueMIPRO: Proposer failed ({e}), using manual high-quality candidates.")
            # Возвращаем dict {predictor_idx: [candidates]}, как ожидает MIPROv2
            program = args[0] if args else None
            num_predictors = len(program.predictors()) if program else 1
            fallback = [
                "Prioritize search results with clear geographical markers (address, phone) and high domain authority.",
                "Extract URLs that precisely match the semantic intent of the query and business type.",
                "Select sources that are recognized as official business listings or maps data.",
            ]
            return {i: fallback for i in range(num_predictors)}

    def _get_param_distributions(self, program, instruction_candidates, demo_candidates):
        """
        Исправление бага DSPy 3.1.3: строим distributions только по реальным предикторам программы.
        """
        from optuna.distributions import CategoricalDistribution
        
        num_predictors = len(program.predictors())
        param_distributions = {}
        
        # instruction_candidates может быть dict {int: [str]} или список [str]
        if isinstance(instruction_candidates, dict):
            # ВАЖНО: берем все ключи, которые есть в candidates, но только до количества предикторов
            keys = sorted(instruction_candidates.keys())
        else:
            keys = list(range(num_predictors))
        
        for i in range(num_predictors):
            # Сопоставляем предикторы i с ключами k
            k = keys[i] if i < len(keys) else i
            
            if isinstance(instruction_candidates, dict):
                cands = instruction_candidates.get(k, instruction_candidates.get(0, []))
            else:
                cands = instruction_candidates
            
            # Логируем для отладки ValueError: 'X' not in range(Y)
            logger.debug(f"P({i}) using dist range({len(cands)}) from key {k}")
            
            param_distributions[f"{i}_predictor_instruction"] = CategoricalDistribution(
                range(len(cands))
            )
            if demo_candidates and i < len(demo_candidates):
                param_distributions[f"{i}_predictor_demos"] = CategoricalDistribution(
                    range(len(demo_candidates[i]))
                )
        
        return param_distributions
# ---------------------------------------------------------

def optimize(test_mode=False):
    # 1. Setup LM
    lm = YandexGPTLM(
        model="yandexgpt-lite/latest",
        folder_id=Config.YANDEX_FOLDER_ID,
        api_key=Config.YANDEX_API_KEY
    )
    dspy.settings.configure(lm=lm)

    # 2. Setup RAGService & Module
    from src.infrastructure.clients.xmlriver import XMLRiverClient
    from src.infrastructure.clients.yandex_gpt import YandexGPTClient
    from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
    from src.domain.services.chunker import Chunker
    from src.domain.services.ranker import ChunkRanker
    from src.domain.services.source_processor import SourceProcessor
    from src.domain.services.metrics import MetricService

    search_client = XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)
    emb_client = YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    gpt_client = YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    chunker = Chunker()
    ranker = ChunkRanker(embedding_client=emb_client)
    processor = SourceProcessor(chunker=chunker, ranker=ranker)
    metrics = MetricService()
    
    service = RAGService(search_client, ranker, gpt_client, chunker, processor, metrics)
    # ПЕРЕДАЕМ LM
    program = RAGModule(service, lm=lm)

    # 3. Load Dataset (Gold Data)
    with open("backend/scripts/gold_data.json", "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    
    trainset = [
        dspy.Example(query=c['query'], expected_urls=c['expected_urls']).with_inputs('query')
        for c in gold_data
    ]
    
    if test_mode:
        logger.info("TEST MODE: Using only 2 examples and 2 trials.")
        trainset = trainset[:2]

    # 4. Stage 1: Chunker Optimization (Optuna)
    import optuna
    
    def objective(trial):
        chunk_size = trial.suggest_int("chunk_size", 200, 1000, step=50)
        chunk_overlap = trial.suggest_int("chunk_overlap", 20, 200, step=20)
        
        scores = []
        for ex in trainset[:5] if not test_mode else trainset: # Use small subset for speed in Stage 1
            pred = program.forward(ex.query, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            scores.append(overlap_metric(ex, pred))
        
        return sum(scores) / len(scores) if scores else 0

    logger.info("Stage 1: Optimizing Chunker Parameters...")
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=5 if test_mode else 15)
    
    best_params = study.best_params
    logger.info(f"Best Chunker Params: {best_params}")
    
    # Save rag_config.json
    os.makedirs("config", exist_ok=True)
    with open("config/rag_config.json", "w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=4)

    # 5. Stage 2: Prompt Optimization (RescueMIPRO)
    # Apply best chunking params to the program permanentely for Stage 2
    service.chunker.chunk_size = best_params["chunk_size"]
    service.chunker.overlap = best_params["chunk_overlap"]

    # Suppress gRPC logging noise from Yandex SDK
    logging.getLogger("yandex_cloud_ml_sdk").setLevel(logging.WARNING)
    logging.getLogger("yandex_ai_studio_sdk").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)

    # Use tqdm for better progress visualization in sequential mode
    from tqdm import tqdm
    def _run_seq(self, wrapped, data):
        results = []
        pbar = tqdm(data, desc=f"Eval Examples", leave=False, colour='cyan')
        for d in pbar:
            results.append(wrapped(d))
        return results
    dspy.utils.parallelizer.ParallelExecutor.execute = _run_seq
    dspy.utils.parallelizer.ParallelExecutor._execute_parallel = _run_seq

    teleprompter = RescueMIPRO(
        metric=overlap_metric,
        prompt_model=lm,
        task_model=lm,
        num_candidates=7,
        auto=None
    )
    
    logger.info(f"Stage 2: Starting prompt optimization with {len(trainset)} examples...")
    
    # Настройки
    num_trials = 2 if test_mode else 10
    minibatch_size = 1
    
    try:
        optimized_program = teleprompter.compile(
            program, 
            trainset=trainset,
            num_trials=num_trials,
            max_bootstrapped_demos=0, 
            max_labeled_demos=0,
            minibatch_size=minibatch_size,
            requires_permission_to_run=False
        )
    except KeyboardInterrupt:
        logger.warning("\n[!] Optimization interrupted. Saving best found.")
        optimized_program = program
    except Exception as e:
        import traceback
        logger.error(f"Stage 2 failed: {e}\n{traceback.format_exc()}")
        optimized_program = program

    # 6. Save Prompts
    winner_instr = WinnerSelectionSignature.__doc__.strip()
    try:
        if hasattr(optimized_program, 'select_winners'):
             winner_instr = optimized_program.select_winners.predictor.signature.instructions
    except Exception:
        pass

    prod_prompts = {
        "WINNER_SELECTION": winner_instr
    }
    
    os.makedirs("config", exist_ok=True)
    with open("config/prompts_prod.json", "w", encoding="utf-8") as f:
        json.dump(prod_prompts, f, indent=4, ensure_ascii=False)
    
    logger.info("Optimization complete. Results saved to config/prompts_prod.json and config/rag_config.json")

if __name__ == "__main__":
    import sys
    is_test = "--test" in sys.argv
    optimize(test_mode=is_test)

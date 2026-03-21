import asyncio
import logging
from typing import Optional, Any, List, Dict, Tuple
from yandex_cloud_ml_sdk import YCloudML
from src.domain.exceptions import ExternalAPIException
from src.core.constants import YandexModelNames
from src.core import prompts
from src.domain.models import SearchResult

# чтоб логи были
logger = logging.getLogger(__name__)

class YandexGPTClient:
    def __init__(self, folder_id: str, api_key: str, model_name: str = YandexModelNames.GPT_LITE.value):
        self.folder_id = folder_id
        self.api_key = api_key
        self.model_name = model_name
        self.sdk = YCloudML(folder_id=folder_id, auth=api_key)

    async def generate_answer(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # тут ретраи если яндекс прилетел с ошибкой
        model = self.sdk.models.completions(self.model_name)
        
        max_retries = 3
        last_error = ""
        
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, lambda: model.run(prompt))
                
                if hasattr(result, "alternatives") and result.alternatives:
                    return str(result.alternatives[0].text)
                
                last_error = "Invalid response structure"
            except Exception as e:
                last_error = str(e)
                if "StatusCode.INTERNAL" in last_error or "StatusCode.UNAVAILABLE" in last_error:
                    logger.warning(f"gpt retry {attempt+1}: {last_error}")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                break
                
        raise ExternalAPIException("YandexGPT", 500, f"Error: {last_error}")

    async def score_passage(self, query: str, passage: str) -> int:
        # оцениваем насколько кусок подходит под запрос
        prompt = prompts.RELEVANCE_SCORE.format(query=query, passage=passage)
        try:
            response = await self.generate_answer(prompt)
            import re
            match = re.search(r'\d+', response)
            if match:
                score = int(match.group())
                return min(max(score, 1), 10)
            return 1
        except Exception:
            return -1

    async def select_winners(self, query: str, candidates: List[SearchResult]) -> List[SearchResult]:
        # выбираем 5 самых норм сорсов
        if not candidates:
            return []

        formatted_candidates = "\n".join([
            f"[{i}] Title: {c.title}\nSnippet: {c.snippet}" 
            for i, c in enumerate(candidates)
        ])

        prompt = prompts.WINNER_SELECTION.format(query=query, candidates=formatted_candidates)

        try:
            response = await self.generate_answer(prompt)
            import re
            indices = [int(idx) for idx in re.findall(r'\d+', response)]
            
            winners: List[SearchResult] = []
            seen_indices = set()
            for idx in indices:
                if 0 <= idx < len(candidates) and idx not in seen_indices:
                    winners.append(candidates[idx])
                    seen_indices.add(idx)
                    if len(winners) >= 5:
                        break
            
            return winners if winners else candidates[:5]
        except Exception:
            logger.warning("winner choice failed")
            return candidates[:5]

    async def rephrase_query(self, query: str, history: List[Dict[str, str]]) -> str:
        # переделываем вопрос шоб поиск лучше отработал
        if not history:
            return query

        conversation = "\n".join([
            f"{h['role']}: {h['content']}" 
            for h in history[-5:] 
            if isinstance(h, dict) and "role" in h and "content" in h
        ])
        prompt = prompts.QUERY_REPHRASE.format(history=conversation, query=query)

        try:
            rephrased = await self.generate_answer(prompt)
            return rephrased.strip().strip('"').strip("'")
        except Exception:
            return query

    async def verify_answer(self, query: str, context: str, answer: str) -> Tuple[bool, str]:
        # проверяем не врет ли нейронка
        prompt = prompts.GROUNDING_VERIFICATION.format(query=query, context=context, answer=answer)

        try:
            verification = await self.generate_answer(
                prompt, 
                system_prompt=prompts.VERIFIER_SYSTEM
            )
            is_grounded = "GROUNDED: YES" in verification.upper()
            feedback = verification.split("ERRORS:")[-1].strip() if "ERRORS:" in verification else ""
            return is_grounded, feedback
        except Exception:
            return True, ""

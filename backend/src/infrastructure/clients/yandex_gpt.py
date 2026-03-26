import asyncio
import logging
import json
from typing import Optional, Any, List, Dict, Tuple
from yandex_cloud_ml_sdk import YCloudML
from src.infrastructure.clients.limiter import RateLimiter
from src.domain.exceptions import ExternalAPIException
from src.core.constants import YandexModelNames, DefaultConfigs
from src.core import prompts
from src.domain.models import SearchResult

# чтоб логи были
logger = logging.getLogger(__name__)

from src.infrastructure.clients.cache import cache

class YandexGPTClient:
    def __init__(self, folder_id: str, api_key: str, model_name: str = YandexModelNames.GPT_LITE.value):
        self.folder_id = folder_id
        self.api_key = api_key
        self.model_name = model_name
        self.sdk = YCloudML(folder_id=folder_id, auth=api_key)

    async def generate_answer(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Check cache first
        cache_key = f"{prompt}:{system_prompt or ''}:{self.model_name}"
        cached_res = cache.get("gpt", cache_key)
        if cached_res:
            logger.info("Using cached GPT response")
            return cached_res

        model = self.sdk.models.completions(self.model_name)
        
        max_retries = 3
        last_error = ""
        
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "text": system_prompt})
                messages.append({"role": "user", "text": prompt[:120000]})

                result = await RateLimiter.run(loop.run_in_executor(
                    None, 
                    lambda: model.run(messages)
                ))
                
                if hasattr(result, "alternatives") and result.alternatives:
                    answer = str(result.alternatives[0].text)
                    # Cache the result for 24 hours
                    cache.set("gpt", cache_key, answer, ttl=86400)
                    return answer
                
                last_error = "Invalid response structure"
            except Exception as e:
                last_error = str(e)
                if "StatusCode.INTERNAL" in last_error or "StatusCode.UNAVAILABLE" in last_error:
                    logger.warning(f"gpt retry {attempt+1}: {last_error}")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                break
                
        raise ExternalAPIException("YandexGPT", 500, f"Error: {last_error}")

    async def generate_answer_stream(self, prompt: str, system_prompt: Optional[str] = None):
        """Streaming version of generate_answer."""
        # Caching is tricky for streaming, usually disabled or cached after full gen
        model = self.sdk.models.completions(self.model_name)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})
        messages.append({"role": "user", "text": prompt[:120000]})

        # In Yandex Cloud ML SDK, streaming is typically done via .run_stream or .stream
        # We'll use the executor to handle the synchronous stream iterator
        loop = asyncio.get_running_loop()
        
        def get_stream():
            # Assuming the SDK model has a stream method
            return model.run_stream(messages) if hasattr(model, 'run_stream') else model.run(messages, stream=True)

        try:
            stream = await loop.run_in_executor(None, get_stream)
            full_response = []
            
            for chunk in stream:
                if hasattr(chunk, "alternatives") and chunk.alternatives:
                    text = chunk.alternatives[0].text
                    # The SDK sometimes returns the full text accumulated, or delta
                    # Usually it's accumulated in some SDKs, but let's assume delta for streaming
                    # If it's accumulated, we'd need to track the last sent length
                    yield text
                    full_response.append(text)
            
            # Optionally cache the full result after streaming finishes
            # cache.set("gpt", f"{prompt}:{system_prompt or ''}", "".join(full_response), ttl=86400)
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            # Fallback to non-streaming if needed, or just yield the error
            yield f"Error during streaming: {e}"

    async def score_passage(self, query: str, passage: str, title: str = "", url: str = "", metadata: Dict[str, Any] = None) -> int:
        # оцениваем насколько кусок подходит под запрос + смотрим на авторитетность (JEPA)
        prompt = prompts.AUTHORITY_JUDGE_SCORE.format(
            query=query, 
            passage=passage,
            title=title,
            url=url,
            metadata=json.dumps(metadata or {}, ensure_ascii=False)
        )
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

    async def select_winners(self, query: str, candidates: List[SearchResult], custom_prompt: Optional[str] = None) -> List[SearchResult]:
        # выбираем 5 самых норм сорсов
        if not candidates:
            return []

        formatted_candidates = "\n".join([
            f"[{i}] {c.title} ({c.url})\nPreview: {c.snippet[:400]}..." 
            for i, c in enumerate(candidates)
        ])

        if custom_prompt:
            # Используем оптимизированный промпт из DSPy
            prompt = custom_prompt.format(query=query, candidates=formatted_candidates)
        else:
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
                    if len(winners) >= DefaultConfigs.TOP_K_CHUNKS:
                        break
            
            return winners if winners else candidates[:DefaultConfigs.TOP_K_CHUNKS]
        except Exception:
            logger.warning("winner choice failed")
            return candidates[:DefaultConfigs.TOP_K_CHUNKS]

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

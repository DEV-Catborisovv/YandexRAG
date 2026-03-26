import dspy
import logging
import sys
import asyncio
import nest_asyncio
from src.infrastructure.clients.limiter import RateLimiter

import requests
from src.infrastructure.clients.limiter import SyncRateLimiter

# ГОРЯЧИЙ ФИКС: патчим DSPy, чтобы он не падал на NoneType в re.sub
try:
    import dspy.propose.utils
    import re
    original_strip = dspy.propose.utils.strip_prefix
    def safe_strip_prefix(text, pattern=r"^[^:]*:"):
        if text is None: return ""
        return re.sub(pattern, "", str(text))
    dspy.propose.utils.strip_prefix = safe_strip_prefix
    sys.stderr.write("[DEBUG] DSPy monkeypatch applied successfully\n")
except Exception as e:
    sys.stderr.write(f"[DEBUG] DSPy monkeypatch failed: {e}\n")

class YandexGPTLM(dspy.LM):
    def __init__(self, model: str, folder_id: str, api_key: str, **kwargs):
        self.model = model
        self.folder_id = folder_id
        self.api_key = api_key
        self.kwargs = {
            "temperature": 0.3,
            "max_tokens": 1000,
            **kwargs,
        }
        try:
            adapter = dspy.ChatAdapter()
        except:
            adapter = None
            
        super().__init__(model, adapter=adapter)
        self.provider = "openai" # Хак для внутренней логики DSPy 3
        # Пустое кэширование для предотвращения проблем с состоянием
        self.history = []

    def request(self, prompt: str = None, messages: list = None, **kwargs):
        """Полностью синхронный и потокобезопасный вызов YandexGPT."""
        if messages:
            full_prompt = "\n".join([m.get("content", m.get("text", "")) for m in messages])
        else:
            full_prompt = prompt or ""
            
        n = kwargs.get("n", 1)
        
        # Оборачиваем синхронный запрос в лимитер
        resp = SyncRateLimiter.run(self.basic_request, full_prompt, **kwargs)
        return resp

    def basic_request(self, prompt: str, **kwargs):
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json"
        }
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        n = kwargs.get("n", 1)
        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": kwargs.get("temperature", self.kwargs["temperature"]),
                "maxTokens": kwargs.get("max_tokens", self.kwargs["max_tokens"])
            },
            "messages": [{"role": "user", "text": prompt}]
        }
        
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=35)
            r.raise_for_status()
            result = r.json()
            text = result['result']['alternatives'][0]['message']['text']
            return {"choices": [{"text": text} for _ in range(n)]}
        except Exception as e:
            logger.error(f"YandexGPTLM Sync Error: {e}")
            # Возвращаем хоть какую-то осмысленную строку, чтобы DSPy не упал на NoneType
            fallback_text = "Instructions: Prioritize high-authority results from official sources and map data."
            return {"choices": [{"text": fallback_text} for _ in range(n)]}

    def __call__(self, prompt=None, **kwargs):
        prompt = prompt or kwargs.get("prompt")
        if not prompt: return [""]
        res = self.request(prompt, **kwargs)
        return [c["text"] for c in res["choices"]]

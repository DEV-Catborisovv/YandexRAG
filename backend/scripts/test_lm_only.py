import dspy
import os
import sys
import litellm
from src.infrastructure.dspy_utils import YandexGPTLM
from src.config import Config

def test_prefixes():
    print("--- LITELLM DIVERSE TEST ---")
    os.environ["YANDEX_API_KEY"] = Config.YANDEX_API_KEY
    os.environ["YANDEX_FOLDER_ID"] = Config.YANDEX_FOLDER_ID
    
    prefixes = ["yandex/yandexgpt-lite", "yandex_cloud/yandexgpt-lite", "yandexgpt-lite"]
    for p in prefixes:
        try:
            print(f"Testing prefix: {p}")
            # Мы используем mock_response, чтобы проверить только валидацию провайдера в LiteLLM
            resp = litellm.completion(
                model=p,
                messages=[{"role": "user", "content": "Hello"}],
                mock_response="Ok"
            )
            print(f"  SUCCESS: {p} is recognized!")
        except Exception as e:
            print(f"  FAILED: {p} -> {str(e)[:100]}")
    print("--- END LITELLM TEST ---\n")

def test_predictor():
    print("--- PREDICTOR TEST ---")
    lm = YandexGPTLM(
        model="yandexgpt-lite/latest",
        folder_id=Config.YANDEX_FOLDER_ID,
        api_key=Config.YANDEX_API_KEY
    )
    dspy.settings.configure(lm=lm, adapter=dspy.ChatAdapter())
    
    class SimpleSignature(dspy.Signature):
        """Translate to English."""
        sentence = dspy.InputField()
        translation = dspy.OutputField()
        
    predictor = dspy.Predict(SimpleSignature, lm=lm)
    print("Calling predictor...")
    try:
        response = predictor(sentence="Привет")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Predictor failed: {e}")
    print("--- END PREDICTOR TEST ---")

if __name__ == "__main__":
    test_prefixes()
    test_predictor()

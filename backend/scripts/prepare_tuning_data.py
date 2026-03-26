import json
import argparse
from typing import List, Dict

def prepare_jsonl(input_file: str, output_file: str):
    """
    Конвертирует список ответов Алисы в формат JSONL для Yandex AI Studio.
    Ожидаемый формат входного файла (JSON):
    [
        {"query": "Вопрос", "answer": "Ответ Алисы", "context": "Текст сайтов (опционально)"},
        ...
    ]
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in data:
                # Для Fine-tuning обычно используем формат сообщений
                messages = [
                    {"role": "system", "text": "Вы — голосовой помощник Яндекс Алиса. Отвечайте на вопросы на основе предоставленных сайтов дружелюбно и понятно."},
                    {"role": "user", "text": f"Вопрос: {item['query']}\n\nКонтекст:\n{item.get('context', '')}"},
                    {"role": "assistant", "text": item['answer']}
                ]
                json_line = {"messages": messages}
                f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
        
        print(f"Готово! Сохранено в {output_file}. Всего примеров: {len(data)}")
    except Exception as e:
        print(f"Ошибка при подготовке данных: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Подготовка данных для Fine-tuning")
    parser.add_argument("--input", default="alice_data.json", help="Путь к файлу с ответами")
    parser.add_argument("--output", default="tuning_data.jsonl", help="Где сохранить результат")
    args = parser.parse_args()
    
    prepare_jsonl(args.input, args.output)

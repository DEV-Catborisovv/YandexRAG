import sys
import argparse
import uvicorn
import os
import argparse

# запускаем наш сервак
# порты и прочее можно через аргументы менять если надо

def main():
    parser = argparse.ArgumentParser(description="YandexRAG API")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)), help="порт")
    parser.add_argument("--reload", action="store_true", help="авторелоад для разработки")
    
    args = parser.parse_args()

    print(f"Starting YandexRAG API server on port {args.port}...")
    
    # стартуем ювикорн
    uvicorn.run(
        "src.app:app", 
        host="0.0.0.0", 
        port=args.port, 
        reload=args.reload
    )


if __name__ == "__main__":
    main()

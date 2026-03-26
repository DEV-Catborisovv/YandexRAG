FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (essentials)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -m nltk.downloader punkt punkt_tab || true

COPY . .

# Expose port
EXPOSE 8000

# Run the app
CMD ["python", "main.py", "--port", "8000"]

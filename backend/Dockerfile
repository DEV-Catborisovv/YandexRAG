FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for lxml and newspaper4k
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data (optional but good for newspaper4k)
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')" || true

COPY . .

# Expose port
EXPOSE 8000

# Run the app
CMD ["python", "main.py", "--port", "8000"]

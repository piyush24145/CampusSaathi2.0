FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY ai-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence transformer model into container image so startup is instantaneous
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY ai-service/ .

EXPOSE 10000
EXPOSE 8000
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]

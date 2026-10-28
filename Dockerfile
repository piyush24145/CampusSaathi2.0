# -------------------------------------------------------------------
# Google Cloud Run Optimized Dockerfile for CampusSathi AI Service
# -------------------------------------------------------------------
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Configure Cloud Run environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HF_HOME=/app/cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Install minimal build tools and clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first (saves ~1.2 GB image size and avoids CUDA bloat)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
COPY ai-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and cache embedding model during build to eliminate HF runtime downloads & rate limits
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy data and ai-service source code
COPY data/ /app/data/
COPY ai-service/ /app/

# Pre-seed sample college notices into ChromaDB during build
RUN python -c "from app.seeder import seed_sample_notices_if_empty; seed_sample_notices_if_empty()"

# Expose standard Cloud Run port
EXPOSE 8080

# Start Uvicorn bound to Cloud Run PORT environment variable
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]

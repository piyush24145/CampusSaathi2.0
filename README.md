# 🎓 CampusSathi AI - Smart College Campus Assistant

CampusSathi AI is an intelligent college campus assistant featuring Retrieval-Augmented Generation (RAG), multi-notice PDF processing, and voice interaction.

---

## 🏗️ Architecture

- **Frontend (`frontend/`)**: React 19 + Vite SPA (Deployed on **Vercel**)
- **AI Service / Backend (`ai-service/`)**: FastAPI + LangChain + ChromaDB + OpenRouter (Deployed on **Google Cloud Run**)
- **Data (`data/`)**: Sample campus notices and circulars for vector indexing.

---

## 🚀 Deployment Guide

### 1. Deploy Backend on Google Cloud Run (Recommended)

Google Cloud Run provides **2,000,000 free requests/month**, zero cold-start timeouts, customizable RAM (2 GiB), and no aggressive free-tier rate limits.

#### Quick Option A: Deploy via Google Cloud Console UI
1. Go to [Google Cloud Run Console](https://console.cloud.google.com/run).
2. Click **Create Service**.
3. Select **"Continuously deploy from a repository"** -> Connect your GitHub repo.
4. Set Build Type to **Dockerfile** (Root `/Dockerfile`).
5. Choose Region (e.g. `asia-south1 (Mumbai)` or `us-central1`).
6. Under **Authentication**, check **"Allow unauthenticated invocations"**.
7. Under **Container Settings**:
   - **Port**: `8080`
   - **Memory**: `2 GiB` (minimum 1 GiB)
   - **CPU**: `1`
8. Under **Environment Variables**, add:
   - `OPENROUTER_API_KEY`: `your_openrouter_api_key_here`
   - `OPENROUTER_MODEL`: `meta-llama/llama-3.3-70b-instruct:free` (optional)
   - `GNANI_API_KEY`: `your_gnani_api_key_here` (optional)
9. Click **Create**. Once deployed, copy your Cloud Run service URL (e.g., `https://campussathi-ai-xxxx-uc.a.run.app`).

#### Quick Option B: Deploy via Google Cloud CLI (`gcloud`)
```bash
gcloud run deploy campussathi-ai \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --port 8080 \
  --set-env-vars "OPENROUTER_API_KEY=your_openrouter_api_key_here"
```
*(Windows users can also double-click `deploy-cloudrun.bat`!)*

👉 For complete step-by-step instructions with rate-limit mitigation details, see [CLOUD_RUN_DEPLOYMENT.md](file:///c:/Users/piyus/Desktop/CampusSathi-AI/CLOUD_RUN_DEPLOYMENT.md).

---

### 2. Deploy Frontend on Vercel

1. Go to [Vercel Dashboard](https://vercel.com/) and click **Add New...** -> **Project**.
2. Import your GitHub repository.
3. Configure the following:
   - **Root Directory**: `frontend`
   - **Framework Preset**: **Vite**
4. Under **Environment Variables**, add:
   - `VITE_API_URL`: Your Google Cloud Run URL (e.g., `https://campussathi-ai-xxxx-uc.a.run.app`)
5. Click **Deploy**.

> **Instant Connection:** You can also connect the frontend directly in the running web app by clicking the **"Connect Backend"** pill (⚙️) on the top-right header and pasting your Cloud Run URL!

---

## 💻 Local Development

### AI Service (Backend):
```bash
cd ai-service
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 🛡️ Built-in Rate Limit & Stability Features

- **Baked Embedding Model**: Embedding model weights (`sentence-transformers/all-MiniLM-L6-v2`) are downloaded during container build, eliminating runtime Hugging Face rate limits.
- **Intelligent OpenRouter Failover**: If the primary free model hits HTTP 429 rate limit or 503 overload, it automatically fails over across verified free models (`meta-llama/llama-3.3-70b-instruct:free`, `google/gemini-2.0-flash-exp:free`, `mistralai/mistral-7b-instruct:free`, `openrouter/free`).
- **Auto-Seeded Sample Notices**: ChromaDB is automatically populated with sample notices on first startup so questions work immediately out-of-the-box.
- **CPU-Optimized Container**: Uses lightweight PyTorch CPU build, reducing Docker image size from ~2.5 GB to ~600 MB for rapid deployments.

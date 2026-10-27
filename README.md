# 🎓 CampusSathi AI - Smart College Campus Assistant

CampusSathi AI is an intelligent college campus assistant featuring Retrieval-Augmented Generation (RAG), PDF notice processing, and voice interaction.

---

## 🏗️ Architecture

- **Frontend (`frontend/`)**: React 19 + Vite SPA (Deployed on **Vercel**)
- **AI Service / Backend (`ai-service/`)**: FastAPI + LangChain + ChromaDB + OpenRouter (Deployed on **Render**)
- **Data (`data/`)**: Sample campus notices and documents for vector indexing.

---

## 🚀 Deployment Guide (No Docker Required)

### 1. Deploy Backend on Render (Native Python)

1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the following settings:
   - **Name**: `campussathi-ai-service` (or any name you prefer)
   - **Language / Runtime**: `Python 3`
   - **Root Directory**: `ai-service`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python -c "import chromadb.utils.embedding_functions as ef; ef.DefaultEmbeddingFunction()(['warmup'])"
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
4. Under **Environment Variables**, add:
   - `PYTHON_VERSION`: `3.11.9`
   - `OPENROUTER_API_KEY`: `your_openrouter_api_key_here`
   - `OPENROUTER_MODEL`: `mistralai/mistral-small-24b-instruct-2501` (optional)
   - `GNANI_API_KEY`: `your_gnani_api_key_here` (optional)
5. Click **Deploy Web Service**.
6. Once deployed, copy your Render service URL (e.g., `https://campussathi-ai-service.onrender.com`).

> **Tip:** You can also deploy instantly using the included `render.yaml` Blueprint by choosing **New +** -> **Blueprint** in Render.

---

### 2. Deploy Frontend on Vercel

1. Go to [Vercel Dashboard](https://vercel.com/) and click **Add New...** -> **Project**.
2. Import your GitHub repository.
3. In the configuration window:
   - Set **Root Directory** to `frontend` (Click *Edit* and select `frontend`).
   - Framework Preset will automatically detect **Vite**.
4. Expand **Environment Variables** and add:
   - `VITE_API_URL`: Your Render backend URL (e.g., `https://campussathi-ai-service.onrender.com`)
5. Click **Deploy**.

---

## 💻 Local Development

### AI Service (Backend):
```bash
cd ai-service
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

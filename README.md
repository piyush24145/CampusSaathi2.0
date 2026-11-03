# 🎓 CampusSathi AI - Smart College Campus Assistant
Powered by **Gnani AI** (Prisma STT, Timbre TTS & Evon Reasoning Model)

CampusSathi AI is an intelligent college campus assistant featuring Retrieval-Augmented Generation (RAG), multi-notice PDF processing, and native Indian voice interaction.

---

## 🏗️ Architecture

- **AI Service / Backend (`ai-service/`)**: FastAPI + LangChain + ChromaDB + Gnani AI Ecosystem (Prisma v3.0, Timbre v2.5, Evon v3.3)
- **Frontend (`frontend/`)**: React 19 + Vite SPA (Deployed on **Vercel**)
- **Data (`data/`)**: Sample campus notices and circulars for vector indexing.

---

## 🤖 Gnani AI Ecosystem Integration

| Component | Model | Role |
| :--- | :--- | :--- |
| **Speech-to-Text** | **Gnani Prisma v3.0** | Real-time voice query transcription with Indian accent & code-mixed language support (`indic-auto`) |
| **Text-to-Speech** | **Gnani Timbre v3.0** | Expressive natural voice synthesis (`Shivani`) with inline audio tags (`<pauses>`) & SSE streaming |
| **Reasoning LLM** | **Gnani Evon v3.3 (30B-A3B)** | Sovereign Indic reasoning model via Hugging Face (`gnani/gnani-evon-v3.3-30B-A3B`) |

---

## 💻 Local Development

### 1. AI Service (Backend):
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

### 2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 🔑 Environment Variables (`ai-service/.env`)

```env
# Gnani AI Voice Platform
GNANI_API_KEY=your_gnani_api_key_here

# Gnani Evon (Hugging Face)
HUGGINGFACE_API_KEY=your_huggingface_token_here

# Auth & Google OAuth
JWT_SECRET_KEY=your_jwt_secret_key_here
GOOGLE_CLIENT_ID=your_google_client_id_here
```

---

## 🛡️ Built-in Stability Features

- **Gnani Prisma v3.0 Automatic Language Identification**: Automatically handles English, Hindi, and regional code-mixed speech.
- **Gnani Timbre Streaming WAV Reconstruction**: Reconstructs chunked audio headers for smooth playback on any browser.
- **Baked Embedding Model**: Embedding model weights (`sentence-transformers/all-MiniLM-L6-v2`) are cached locally, eliminating runtime network bottlenecks.
- **Auto-Seeded Sample Notices**: ChromaDB is automatically populated with sample notices on first startup so questions work immediately out-of-the-box.
- **CPU-Optimized Container**: Uses lightweight PyTorch CPU build, reducing Docker image size from ~2.5 GB to ~600 MB for rapid deployments.

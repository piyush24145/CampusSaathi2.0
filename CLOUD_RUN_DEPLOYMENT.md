# 🚀 CampusSathi AI - Google Cloud Run Deployment Guide
Powered by **Gnani AI** (Prisma STT, Timbre TTS & Evon Reasoning Model)

Yeh guide aapko CampusSathi AI ke backend (FastAPI + ChromaDB + LangChain + Gnani AI) ko **Google Cloud Run** par deploy karne ka step-by-step tarika batata hai taaki **Render ke rate limits, slow cold starts, aur memory crashes se 100% chutkara mil sake**.

---

## 🌟 Google Cloud Run Kyu Render se Behtar Hai?

| Feature | Render Free Tier | Google Cloud Run |
|---|---|---|
| **Monthly Free Requests** | Bahut kam / Rate limits lagte hain | **2,000,000 (20 Lakh) Requests bilkul FREE** |
| **RAM (Memory)** | Max 512 MB (PyTorch OOM crash karta hai) | **1 GiB - 2 GiB allocate kar sakte hain** |
| **Cold Starts** | 45-60 seconds (so jata hai) | **1-3 seconds (fast auto-scaling)** |
| **HuggingFace Rate Limits** | Startup pe model download karta tha | **Docker image me pehle se baked hai (0 download)** |
| **Gnani AI Integration** | High latency on slow hosts | **Fast Indian regional edge (asia-south1)** |

---

## 🛠️ Step-by-Step Deployment Guide

Aap do tarike se deploy kar sakte hain:
- **Tarika 1 (Sabse Aasan):** Google Cloud Console UI se (Bina kisi terminal/command ke)
- **Tarika 2 (Fastest):** Google Cloud CLI (`gcloud`) se (Sirf 1 command)

---

### 🔹 Tarika 1: Google Cloud Console UI Se Deploy Karna (Recommended)

1. **Google Cloud Console me Login karein:**
   - [console.cloud.google.com](https://console.cloud.google.com/) par jayein aur apna project select/create karein.

2. **Cloud Run Service Create karein:**
   - Search bar me **Cloud Run** search karein aur open karein.
   - **Create Service** button par click karein.

3. **Source Code Select karein:**
   - **"Continuously deploy from a repository"** par click karein.
   - **"Set up with Cloud Build"** select karein.
   - Provider: **GitHub** choose karein aur apna GitHub account connect karein.
   - Repository: Apna **`CampusSaathi-AI`** repository select karein.
   - Branch: `main` (ya jo bhi aapki active branch ho).
   - Build Type: **`Dockerfile`**
   - Source location: `/Dockerfile` (root Dockerfile) select karein.
   - Click **Save**.

4. **Service Configuration Settings (BOHOT ZAROORI):**
   - **Service name**: `campussathi-ai` (ya jo aap chahein)
   - **Region**: `asia-south1 (Mumbai)` ya `us-central1`
   - **Authentication**:
     - ✅ **"Allow unauthenticated invocations"** par tick karein (Isko tick karna zaroori hai taaki frontend bina login API access kar sake).

5. **Container & Resource Settings:**
   - **"Container, Networking, Security"** (ya Container Settings) expand karein:
     - **Container Port**: `8080` (Default)
     - **CPU**: `1`
     - **Memory**: **`2 GiB`** *(Minimum 1 GiB rakhein taaki PyTorch / Embeddings smoothly chalein)*
     - **Request timeout**: `300` seconds

6. **Environment Variables Add karein:**
   - **Environment Variables** tab me jayein aur yeh keys add karein:
     - `GNANI_API_KEY`: *(Apni Gnani API Key dalein)*
     - `HUGGINGFACE_API_KEY`: *(Apna Hugging Face Token dalein)*
     - `JWT_SECRET_KEY`: *(Apna JWT Secret dalein)*
     - `GOOGLE_CLIENT_ID`: *(Apna Google Client ID dalein)*

7. **Deploy karein:**
   - Niche **"Create"** button par click karein.
   - Cloud Build automatic image banayega (PyTorch CPU, model caching, sample notices seed sab apne aap ho jayega).
   - 3-5 minute me deploy complete ho jayega aur aapko **Service URL** mil jayega (e.g. `https://campussathi-ai-xxxx-uc.a.run.app`).

---

### 🔹 Tarika 2: Google Cloud CLI (`gcloud`) Se Deploy Karna (Sirf 1 Command)

Agar aapke system me `gcloud` CLI installed hai:

1. Terminal me login karein:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. Direct deploy command chalayein (Project ke root folder se):
   ```bash
   gcloud run deploy campussathi-ai \
     --source . \
     --region asia-south1 \
     --platform managed \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 1 \
     --port 8080 \
     --set-env-vars "GNANI_API_KEY=your_gnani_key,HUGGINGFACE_API_KEY=your_hf_token"
   ```

3. Command complete hote hi terminal par aapka **Live URL** aa jayega:
   ```
   Service URL: https://campussathi-ai-xxxx-uc.a.run.app
   ```

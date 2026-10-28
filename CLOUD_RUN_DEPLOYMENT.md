# 🚀 CampusSathi AI - Google Cloud Run Deployment Guide

Yeh guide aapko CampusSathi AI ke backend (FastAPI + ChromaDB + LangChain + OpenRouter) ko **Google Cloud Run** par deploy karne ka step-by-step tarika batata hai taaki **Render ke rate limits, slow cold starts, aur memory crashes se 100% chutkara mil sake**.

---

## 🌟 Google Cloud Run Kyu Render se Behtar Hai?

| Feature | Render Free Tier | Google Cloud Run |
|---|---|---|
| **Monthly Free Requests** | Bahut kam / Rate limits lagte hain | **2,000,000 (20 Lakh) Requests bilkul FREE** |
| **RAM (Memory)** | Max 512 MB (PyTorch OOM crash karta hai) | **1 GiB - 2 GiB allocate kar sakte hain** |
| **Cold Starts** | 45-60 seconds (so jata hai) | **1-3 seconds (fast auto-scaling)** |
| **HuggingFace Rate Limits** | Startup pe model download karta tha | **Docker image me pehle se baked hai (0 download)** |
| **OpenRouter 429 Failover** | Direct crash hota tha | **Automatic multi-model fallback & backoff** |

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
     - `OPENROUTER_API_KEY`: *(Apni OpenRouter API Key dalein)*
     - `OPENROUTER_MODEL`: `meta-llama/llama-3.3-70b-instruct:free` *(Optional - agar blank chhodenge toh bhi automatic smart fallback chalega)*
     - `GNANI_API_KEY`: *(Apni Gnani API Key dalein - optional)*

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
     --set-env-vars "OPENROUTER_API_KEY=your_openrouter_api_key_here"
   ```

   *(Windows users direct `deploy-cloudrun.bat` double click karke bhi chala sakte hain!)*

3. Command complete hote hi terminal par aapka **Live URL** aa jayega:
   ```
   Service URL: https://campussathi-ai-xxxx-uc.a.run.app
   ```

---

## 🔗 Frontend (Vercel) Se Connect Karna

Jab Cloud Run ka URL mil jaye:

### Option A: Vercel Settings Me Permanent Connect Karna
1. [vercel.com](https://vercel.com/) dashboard me jayein.
2. Apne **CampusSathi** project par click karein -> **Settings** -> **Environment Variables**.
3. Naya variable add karein:
   - **Key**: `VITE_API_URL`
   - **Value**: Aapka Cloud Run URL (e.g. `https://campussathi-ai-xxxx-uc.a.run.app`)
4. Save karein aur **Redeploy** karein.

### Option B: Instant UI Connect (Bina Vercel Redeploy Ke)
1. Apni live frontend website open karein.
2. Top right me **"Connect Backend"** / Server status pill par click karein.
3. Apna Cloud Run URL paste karein aur **"⚡ Test Connection"** dabayein.
4. "Connected successfully!" aate hi **"💾 Save & Connect"** par click karein. Instant connect ho jayega!

---

## 🛡️ Rate Limits & Crash Protection (Kya Naya Kiya Hai?)

1. **Pre-baked Embedding Model**:
   - Hugging Face `sentence-transformers/all-MiniLM-L6-v2` ko Docker build ke waqt hi container image ke andar download kar diya gaya hai.
   - Container start hone par **Hugging Face ko koi call nahi jati**, isliye unauthenticated rate limit ka 0% chance hai!

2. **Automatic OpenRouter Model Failover (HTTP 429 Prevention)**:
   - Agar OpenRouter ka primary free model rate-limit (429) ya overloaded (503) ho jata hai, toh backend crash hone ke bajaye **automatically next free model** par switch kar leta hai:
     - `meta-llama/llama-3.3-70b-instruct:free`
     - `google/gemini-2.0-flash-exp:free`
     - `mistralai/mistral-7b-instruct:free`
     - `openrouter/free`
     - `qwen/qwen-2.5-72b-instruct:free`
   - Student ko hamesha answer milta hai aur request fail nahi hoti!

3. **Auto-Seeded Sample Notices**:
   - Deploy hone ke baad ChromaDB khali nahi rehta.
   - Exam Schedule, Hostel Allotment, aur Library Rules ke sample notices pehle se vector database me indexed milte hain!

4. **PyTorch CPU Optimization**:
   - Docker image ka size 2.5 GB se ghatakar sirf **~600 MB** kar diya gaya hai, jisse build aur container startup lightning-fast ho jata hai.

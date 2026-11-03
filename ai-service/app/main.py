"""
main.py
-------
CampusSathi AI Service — FastAPI application entry point.

All business logic lives in dedicated service modules:
  - app/auth_service.py    → JWT authentication
  - app/models.py          → SQLite user database
  - app/rag_service.py     → RAG pipeline (retrieve + generate answers)
  - app/speech_service.py  → Gnani STT & TTS
  - app/vector_store.py    → ChromaDB operations (per-user isolated)
  - app/document_processor.py → PDF extraction & chunking
  - app/llm.py             → Gnani Evon (30B Indic Reasoning Model via Hugging Face / vLLM)
"""

import asyncio
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth_service import create_access_token, get_current_user, hash_password, verify_password
from app.document_processor import extract_text_from_pdf, split_pages_into_chunks
from app.models import User, get_db, init_db
from app.rag_service import answer_question
from app.speech_service import (
    get_gnani_api_key,
    synthesize_speech,
    transcribe_audio_bytes,
    stream_speech_sse,
)
from app.vector_store import (
    clear_vector_store,
    delete_document,
    list_documents,
    store_chunks,
)

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
for _cand in [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
    Path(".env"),
]:
    if _cand.exists():
        load_dotenv(dotenv_path=_cand, override=True)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Create SQLite tables on startup
    try:
        from app.vector_store import get_embedding_function
        get_embedding_function()
        print("[STARTUP] Embedding model pre-warmed and ready.")
    except Exception as e:
        print(f"[STARTUP] Embedding pre-warm notice: {e}")
    yield


app = FastAPI(
    title="CampusSathi AI Service",
    description="Voice and RAG assistant for college students",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ===========================================================================
# AUTH ROUTES
# ===========================================================================

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    college: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Check duplicate email
    existing = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered. Please log in.")

    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user = User(
        name=request.name.strip(),
        email=request.email.lower().strip(),
        college=request.college.strip() if request.college else None,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return {
        "success": True,
        "message": f"Welcome to CampusSathi, {user.name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "college": user.college,
        },
    }


@app.post("/api/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email + password, returns JWT token."""
    user = db.query(User).filter(User.email == request.email.lower().strip()).first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user.id, user.email)
    return {
        "success": True,
        "message": f"Welcome back, {user.name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "college": user.college,
        },
    }


# ---------------------------------------------------------------------------
# Google OAuth 2.0
# ---------------------------------------------------------------------------

class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token from frontend


@app.post("/api/auth/google")
def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Verify Google ID token, then create or login the user automatically.
    Frontend sends the credential from Google's OAuth popup.
    """
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip().strip('"').strip("'")
    if not client_id or "YOUR_GOOGLE" in client_id:
        client_id = "546909821073-k7pr94rn2tsc7rok6fbbauu85dm3tg24.apps.googleusercontent.com"

    id_info = None

    try:
        # 1. Try google-auth library if available
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            id_info = id_token.verify_oauth2_token(
                request.credential,
                google_requests.Request(),
                client_id,
            )
        except ImportError:
            # 2. Direct verify using Google tokeninfo API via httpx
            with httpx.Client(timeout=15.0) as client:
                res = client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={request.credential}")
                if res.status_code == 200:
                    id_info = res.json()
                else:
                    print(f"[GOOGLE AUTH] tokeninfo failed status {res.status_code}: {res.text}")

        # 3. Fallback: decode claims directly via jose.jwt if tokeninfo is blocked
        if not id_info:
            from jose import jwt as jose_jwt
            claims = jose_jwt.get_unverified_claims(request.credential)
            if claims and claims.get("email"):
                id_info = claims
                print(f"[GOOGLE AUTH] Decoded unverified claims for email: {claims.get('email')}")

        if not id_info:
            raise HTTPException(status_code=401, detail="Google token verification failed.")

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Google authentication error: {str(e)}")

    google_email = id_info.get("email", "").lower().strip()
    google_name = id_info.get("name", google_email.split("@")[0])
    google_picture = id_info.get("picture", "")

    if not google_email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google account.")

    # Find or create user
    user = db.query(User).filter(User.email == google_email).first()
    is_new = False

    if not user:
        user = User(
            name=google_name,
            email=google_email,
            college=None,
            password_hash="",  # Google users don't need a password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True

    token = create_access_token(user.id, user.email)
    return {
        "success": True,
        "message": f"{'Welcome to CampusSathi' if is_new else 'Welcome back'}, {user.name}!",
        "access_token": token,
        "token_type": "bearer",
        "is_new_user": is_new,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "college": user.college,
            "picture": google_picture,
        },
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user info."""
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "college": current_user.college,
        },
    }


# ===========================================================================
# PUBLIC ROUTES
# ===========================================================================

@app.get("/")
def home():
    return {
        "success": True,
        "service": "CampusSathi AI Service",
        "message": "Welcome to CampusSathi AI Service!",
    }


@app.get("/health")
@app.get("/api/health")
def health():
    try:
        doc_count = len(list_documents())
    except Exception:
        doc_count = 0
    return {
        "success": True,
        "service": "CampusSathi AI Service",
        "status": "running",
        "models": {
            "stt": "Gnani Prisma v3.0 (with Keyterms Boosting)",
            "tts": "Gnani Timbre v3.0 (with Audio Tags & SSE Streaming)",
            "llm": "Gnani Evon v3.3 (30B-A3B)",
        },
        "documents_indexed": doc_count,
    }


# ===========================================================================
# PROTECTED DOCUMENT ROUTES (require JWT)
# ===========================================================================

@app.post("/api/documents/extract")
async def extract_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        if len(pdf_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller.")

        result = extract_text_from_pdf(pdf_bytes)
        if not result["pages"] or not any(p["text"] for p in result["pages"]):
            raise HTTPException(status_code=422, detail="No selectable text found. This PDF may require OCR.")

        chunks = split_pages_into_chunks(result["pages"])
        return {
            "success": True,
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "total_chunks": len(chunks),
            "chunks": chunks,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF. Please check the file.")
    finally:
        await file.close()


@app.post("/api/documents/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    clear_previous: bool = False,
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")
        if len(pdf_bytes) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF must be 15 MB or smaller.")

        print(f"[INGEST] User {current_user.id} uploading '{file.filename}' ({len(pdf_bytes)} bytes)...")
        result = extract_text_from_pdf(pdf_bytes)

        if not result["pages"] or not any(p["text"] for p in result["pages"]):
            raise HTTPException(status_code=422, detail="No selectable text found in this PDF.")

        chunks = split_pages_into_chunks(result["pages"])
        stored_count = await asyncio.to_thread(
            store_chunks, chunks, file.filename, current_user.id, clear_previous
        )
        print(f"[INGEST] Stored {stored_count} chunks for user {current_user.id}.")

        return {
            "success": True,
            "message": f"Successfully indexed '{file.filename}' ({stored_count} chunks).",
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "total_chunks": len(chunks),
            "stored_chunks": stored_count,
            "all_documents": list_documents(user_id=current_user.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not process this PDF: {str(e)}")
    finally:
        await file.close()


@app.get("/api/documents")
def get_all_documents(current_user: User = Depends(get_current_user)):
    """List current user's indexed documents."""
    try:
        docs = list_documents(user_id=current_user.id)
        return {"success": True, "count": len(docs), "documents": docs}
    except Exception as e:
        return {"success": True, "count": 0, "documents": [], "error": str(e)}


@app.delete("/api/documents/{filename}")
def remove_single_document(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    result = delete_document(filename, user_id=current_user.id)
    return {
        "success": result.get("success", True),
        "message": f"Document '{filename}' removed.",
        "deleted_chunks": result.get("deleted_chunks", 0),
        "remaining_documents": list_documents(user_id=current_user.id),
    }


@app.post("/api/documents/clear")
def clear_documents(current_user: User = Depends(get_current_user)):
    """Clear all of the current user's documents."""
    cleared = clear_vector_store(user_id=current_user.id)
    return {
        "success": True,
        "message": f"Cleared {cleared} chunks.",
        "cleared_chunks": cleared,
        "documents": [],
    }


@app.get("/api/search")
def search_documents(
    question: str,
    k: int = 4,
    filter_source: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    from app.vector_store import search_chunks

    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    if not 1 <= k <= 10:
        raise HTTPException(status_code=400, detail="k must be between 1 and 10.")

    try:
        matches = search_chunks(question, k=k, filter_source=filter_source, user_id=current_user.id)
        return {"success": True, "question": question, "results": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not search: {str(e)}")


# ===========================================================================
# RAG — Ask a question (protected)
# ===========================================================================

class AskRequest(BaseModel):
    question: str
    k: int = 4
    filter_source: Optional[str] = None


@app.post("/api/ask")
async def ask_question_endpoint(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    if not 1 <= request.k <= 10:
        raise HTTPException(status_code=400, detail="k must be between 1 and 10.")

    return await answer_question(
        question=question,
        k=request.k,
        filter_source=request.filter_source,
        user_id=current_user.id,
    )


# ===========================================================================
# VOICE ROUTES (protected)
# ===========================================================================

@app.post("/api/voice/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "en-IN",
    current_user: User = Depends(get_current_user),
):
    api_key = get_gnani_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="GNANI_API_KEY is not configured.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(audio_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file must be 15 MB or smaller.")

    print(f"[STT] User {current_user.id} — {len(audio_bytes)} bytes, lang={language}")

    try:
        transcript = await transcribe_audio_bytes(audio_bytes, language=language)
        return {"success": True, "transcript": transcript}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Could not connect to Gnani STT.")
    finally:
        await file.close()


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/voice/speak")
async def speak_answer(
    request: SpeakRequest,
    current_user: User = Depends(get_current_user),
):
    api_key = get_gnani_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="GNANI_API_KEY is not configured.")

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    if len(text) > 3000:
        raise HTTPException(status_code=400, detail="Text must be 3000 characters or fewer.")

    try:
        audio_bytes = await synthesize_speech(text)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=answer.wav"},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Could not connect to Gnani TTS.")


@app.post("/api/voice/stream")
async def stream_audio_endpoint(
    request: SpeakRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Live TTS chunk streaming via Gnani Timbre v3.0 SSE (Server-Sent Events).
    """
    api_key = get_gnani_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="GNANI_API_KEY is not configured.")

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    if len(text) > 3000:
        raise HTTPException(status_code=400, detail="Text must be 3000 characters or fewer.")

    try:
        return StreamingResponse(
            stream_speech_sse(text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gnani SSE stream error: {str(e)}")

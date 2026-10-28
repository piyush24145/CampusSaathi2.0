
import os
import struct
import asyncio
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from openrouter import OpenRouter
from pydantic import BaseModel

from typing import Optional, List, Dict, Any

from app.vector_store import (
    store_chunks,
    search_chunks,
    get_vector_store,
    clear_vector_store,
    list_documents,
    delete_document,
)
from app.document_processor import (
    extract_text_from_pdf,
    split_pages_into_chunks,
)

# Load environment variables from ai-service/.env
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fast non-blocking boot so Google Cloud Run / health checks pass immediately
    try:
        from app.seeder import seed_sample_notices_if_empty
        # Seed sample notices in background thread if database is empty
        asyncio.create_task(asyncio.to_thread(seed_sample_notices_if_empty))
    except Exception as e:
        print(f"[STARTUP WARNING] Could not schedule background seeder: {e}")
    yield

app = FastAPI(
    title="CampusSathi AI Service",
    description="Voice and RAG assistant for college students on Google Cloud Run",
    version="2.0.0",
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

# --------------------------------------------------
# 1. Home endpoint
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "success": True,
        "service": "CampusSathi AI Service",
        "message": "Welcome to CampusSathi AI Service!",
    }


# --------------------------------------------------
# 2. Health check endpoint
# --------------------------------------------------

@app.get("/health")
@app.get("/api/health")
def health():
    try:
        docs = list_documents()
        doc_count = len(docs)
    except Exception:
        doc_count = 0

    return {
        "success": True,
        "service": "CampusSathi AI Service",
        "status": "running",
        "documents_indexed": doc_count,
    }


# --------------------------------------------------
# 3. Extract text and chunks from a PDF
# --------------------------------------------------

@app.post("/api/documents/extract")
async def extract_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file.",
        )

    try:
        pdf_bytes = await file.read()

        if not pdf_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        if len(pdf_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="PDF must be 10 MB or smaller.",
            )

        result = extract_text_from_pdf(pdf_bytes)

        if not result["pages"] or not any(
            page["text"] for page in result["pages"]
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "No selectable text found. "
                    "This PDF may require OCR."
                ),
            )

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
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF. Please check the file.",
        )

    finally:
        await file.close()


# --------------------------------------------------
# 4. Ingest PDF chunks into ChromaDB
# --------------------------------------------------

@app.post("/api/documents/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    clear_previous: bool = True,
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file.",
        )

    try:
        pdf_bytes = await file.read()

        if not pdf_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF is empty.",
            )

        if len(pdf_bytes) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="PDF must be 15 MB or smaller.",
            )

        print(f"[INGEST] Processing '{file.filename}' ({len(pdf_bytes)} bytes)...")
        result = extract_text_from_pdf(pdf_bytes)
        print(f"[INGEST] Extracted {result['total_pages']} page(s) from '{file.filename}'")

        if not result["pages"] or not any(
            page["text"] for page in result["pages"]
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "No selectable text found in this PDF. "
                    "Scanned images may require OCR."
                ),
            )

        chunks = split_pages_into_chunks(result["pages"])
        print(f"[INGEST] Generated {len(chunks)} text chunks. Replacing prior notice with new document...")

        # Always clear previous documents so only the currently uploaded PDF is active
        stored_count = await asyncio.to_thread(
            store_chunks, chunks, file.filename, clear_previous=True
        )
        print(f"[INGEST] Done! Stored {stored_count} chunks for active notice '{file.filename}'.")

        all_docs = list_documents()

        return {
            "success": True,
            "message": f"Successfully indexed '{file.filename}' ({stored_count} chunks).",
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "total_chunks": len(chunks),
            "stored_chunks": stored_count,
            "all_documents": all_docs,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process or store this PDF: {str(e)}",
        )

    finally:
        await file.close()


@app.get("/api/documents")
def get_all_documents():
    """Retrieve all currently indexed college documents with chunk counts and pages."""
    try:
        docs = list_documents()
        return {
            "success": True,
            "count": len(docs),
            "documents": docs,
        }
    except Exception as e:
        print(f"[API ERROR] /api/documents error: {e}")
        return {
            "success": True,
            "count": 0,
            "documents": [],
            "error": str(e),
        }


@app.delete("/api/documents/{filename}")
def remove_single_document(filename: str):
    """Remove a specific college notice from the vector store."""
    result = delete_document(filename)
    docs = list_documents()
    return {
        "success": result.get("success", True),
        "message": f"Document '{filename}' removed.",
        "deleted_chunks": result.get("deleted_chunks", 0),
        "remaining_documents": docs,
    }


@app.post("/api/documents/clear")
def clear_documents():
    """Clear all documents from the vector store."""
    cleared = clear_vector_store()
    return {
        "success": True,
        "message": f"Successfully cleared {cleared} chunks from vector store.",
        "cleared_chunks": cleared,
        "documents": [],
    }


# --------------------------------------------------
# 5. Search relevant document chunks
# --------------------------------------------------

@app.get("/api/search")
def search_documents(question: str, k: int = 4, filter_source: Optional[str] = None):
    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )

    if not 1 <= k <= 10:
        raise HTTPException(
            status_code=400,
            detail="k must be between 1 and 10.",
        )

    try:
        matches = search_chunks(question, k=k, filter_source=filter_source)

        return {
            "success": True,
            "question": question,
            "results": matches,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not search the document database: {str(e)}",
        )


# --------------------------------------------------
# 6. Request model for RAG question answering
# --------------------------------------------------

class AskRequest(BaseModel):
    question: str
    k: int = 4
    filter_source: Optional[str] = None


# --------------------------------------------------
# 7. RAG endpoint: Retrieve + Generate answer with citations & reliability
# --------------------------------------------------

@app.post("/api/ask")
async def ask_question(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )

    if not 1 <= request.k <= 10:
        raise HTTPException(
            status_code=400,
            detail="k must be between 1 and 10.",
        )

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "OPENROUTER_API_KEY is missing. "
                "Check your environment variables in Google Cloud Run."
            ),
        )

    current_docs = list_documents()
    if not current_docs:
        return {
            "success": True,
            "question": question,
            "answer": (
                "Abhi tak koi bhi college document ya notice upload nahi kiya gaya hai. "
                "Kripya pehle notice (PDF) upload karein, phir sawaal poochein! / "
                "No college notices have been uploaded yet. Please upload a PDF notice first."
            ),
            "sources": [],
            "is_answerable": False,
            "documents_available": [],
        }

    try:
        # Step 1: Retrieve relevant chunks across documents (or filtered by document)
        matches = await asyncio.to_thread(
            search_chunks,
            question,
            k=request.k,
            filter_source=request.filter_source,
        )

        if not matches:
            doc_names = ", ".join([d["filename"] for d in current_docs])
            return {
                "success": True,
                "question": question,
                "answer": (
                    f"Yeh jaankari uploaded documents ({doc_names}) me nahi mili. "
                    "Aap exam dates, fees, ya rules ke baare me pooch sakte hain."
                ),
                "sources": [],
                "is_answerable": False,
                "documents_available": [d["filename"] for d in current_docs],
            }

        # Step 2: Build formatted multi-document context with clear document & page boundaries
        context_parts = []
        for idx, item in enumerate(matches, 1):
            src = item.get("source", "Unknown Document")
            page_num = item.get("page_number", 1)
            txt = item.get("text", "")
            context_parts.append(
                f"[DOCUMENT {idx}: {src} | Page: {page_num}]\n{txt}"
            )

        context = "\n\n".join(context_parts)
        doc_names_list = [d["filename"] for d in current_docs]
        doc_list_str = ", ".join(doc_names_list)

        # Step 3: Strict grounding prompt for reliable answers and citations
        system_prompt = (
            "You are CampusSathi AI, an intelligent, reliable college student assistant.\n"
            f"Active Uploaded Documents in System: {doc_list_str}\n\n"
            "CRITICAL INSTRUCTIONS FOR ACCURACY & RELIABILITY:\n"
            "1. STRICT GROUNDING: Answer strictly using ONLY the information provided in the Document Context Excerpts. Never invent, extrapolate, or assume facts not explicitly mentioned.\n"
            "2. CITATIONS: Whenever stating a fact, date, fee, timing, or rule, explicitly attribute the statement to its specific document name and page number (e.g. `[Notice_Exam_Schedule_2026.pdf, Page 1]`).\n"
            "3. MULTIPLE DOCUMENTS: The context may contain excerpts from several distinct college notices. Keep details from different documents separate. Never confuse hostel rules with exam rules or library timings.\n"
            "4. UNANSWERABLE & OUT-OF-DOMAIN QUESTIONS:\n"
            "   - If the student's question CANNOT be answered from the provided document context (e.g., info is not in the notices, or asks for general knowledge not covered in college circulars), you MUST clearly and politely state:\n"
            "     'Yeh jaankari uploaded documents me nahi mili. / This information is not found in the uploaded documents.'\n"
            "   - Briefly inform the student what notices are currently available so they know what they can ask about. Never guess or hallucinate.\n"
            "5. TONE & LANGUAGE: Clear, student-friendly, and concise. Respond in the language used by the user (Hindi, Hinglish, or English)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Document Context Excerpts:\n{context}"
                ),
            },
        ]

        # Call OpenRouter with multi-model fallback & rate-limit backoff
        from app.llm import generate_chat_completion
        answer, model_used = await asyncio.to_thread(
            generate_chat_completion, messages, api_key
        )

        if not answer:
            raise RuntimeError("The LLM returned an empty answer.")

        # Step 4: Reliability check: Detect if answer indicates unanswerable / out-of-domain
        not_found_indicators = [
            "nahi mili",
            "uplabdh nahi",
            "not found in the uploaded",
            "not mentioned in the uploaded",
            "not available in the uploaded",
            "not in the provided",
            "document me nahi",
            "documents me nahi",
            "not mentioned in the document",
            "cannot be answered from the provided",
            "no information regarding",
            "koi jaankari nahi",
            "not available in the provided",
            "not mentioned in any of the",
        ]
        answer_lower = answer.lower()
        is_unanswerable = any(ind in answer_lower for ind in not_found_indicators)

        # Step 5: Format structured sources with readable snippet and relevance
        sources = []
        if not is_unanswerable:
            seen_sources = set()
            for item in matches:
                src_key = (
                    item.get("source"),
                    item.get("page_number"),
                    item.get("chunk_id"),
                )
                if src_key in seen_sources:
                    continue
                seen_sources.add(src_key)

                txt = item.get("text", "").strip()
                snippet = txt[:260] + ("..." if len(txt) > 260 else "")
                sources.append({
                    "source": item.get("source"),
                    "page_number": item.get("page_number"),
                    "chunk_id": item.get("chunk_id"),
                    "snippet": snippet,
                    "relevance_score": item.get("relevance_score", 0.0),
                })

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "model_used": model_used,
            "is_answerable": not is_unanswerable,
            "sources": sources,
            "documents_available": doc_names_list,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not generate an answer: {str(e)}. Check your "
                "OpenRouter API key, model availability, "
                "network connection and API configuration."
            ),
        )

# --------------------------------------------------
# 8. Gnani Speech-to-Text (Prisma)
# --------------------------------------------------

@app.post("/api/voice/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "en-IN",
):
    api_key = os.getenv("GNANI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GNANI_API_KEY missing. Check ai-service/.env",
        )

    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    print(f"\n[STT DEBUG] Received audio: {len(audio_bytes)} bytes, language={language}")
    print(f"[STT DEBUG] Audio header: {audio_bytes[:24]}")

    # Save to debug file for inspection
    try:
        with open("debug_last_recorded.wav", "wb") as df:
            df.write(audio_bytes)
        print("[STT DEBUG] Saved debug_last_recorded.wav")
    except Exception as e:
        print(f"[STT DEBUG] Could not save debug file: {e}")

    if len(audio_bytes) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Audio file must be 15 MB or smaller.",
        )

    try:
        target_lang = "indic-auto" if language in ["auto", "indic-auto", None, ""] else language
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.vachana.ai/stt/v3",
                headers={"X-API-Key-ID": api_key},
                data={
                    "language_code": target_lang,
                    "format": "transcribe",
                },
                files={
                    "audio_file": (
                        "speech.wav",
                        audio_bytes,
                        "audio/wav",
                    )
                },
            )

            # Retry on 429 Too Many Requests (rate limit or concurrency limit)
            if response.status_code == 429:
                print("[STT DEBUG] Received 429 from Gnani STT, retrying after 700ms backoff...")
                await asyncio.sleep(0.7)
                response = await client.post(
                    "https://api.vachana.ai/stt/v3",
                    headers={"X-API-Key-ID": api_key},
                    data={
                        "language_code": target_lang,
                        "format": "transcribe",
                    },
                    files={
                        "audio_file": (
                            "speech.wav",
                            audio_bytes,
                            "audio/wav",
                        )
                    },
                )

        print(f"[STT DEBUG] Gnani STT Status: {response.status_code}")
        print(f"[STT DEBUG] Gnani STT Raw Body: {response.text}")

        if response.is_error:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Gnani STT error: {response.text[:500]}",
            )

        data = response.json()

        if not data.get("success"):
            error_detail = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else data.get("error")
            raise HTTPException(
                status_code=502,
                detail=f"Gnani STT error: {error_detail or 'Service error'}",
            )

        transcript = data.get("transcript", "").strip()
        print(f"[STT DEBUG] Final Transcript: '{transcript}'")

        return {
            "success": True,
            "transcript": transcript,
        }

    except HTTPException:
        raise
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Gnani STT.",
        )
    finally:
        await file.close()


# --------------------------------------------------
# 9. Gnani Text-to-Speech (Timbre)
# --------------------------------------------------

class SpeakRequest(BaseModel):
    text: str


@app.post("/api/voice/speak")
async def speak_answer(request: SpeakRequest):
    api_key = os.getenv("GNANI_API_KEY")
    text = request.text.strip()

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GNANI_API_KEY missing. Check ai-service/.env",
        )

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty.",
        )

    if len(text) > 3000:
        raise HTTPException(
            status_code=400,
            detail="Text must be 3000 characters or fewer.",
        )

    payload = {
        "text": text,
        "voice": "Poorvi",
        "model": "timbre-v2.5",
        "language": "hi-en",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers={
                    "X-API-Key-ID": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            # If Gnani returns 429 Too Many Requests (rate limit or concurrency lock), wait briefly and retry once
            if response.status_code == 429:
                print("[TTS DEBUG] Received 429 from Gnani, retrying after 600ms backoff...")
                await asyncio.sleep(0.6)
                response = await client.post(
                    "https://api.vachana.ai/api/v1/tts/inference",
                    headers={
                        "X-API-Key-ID": api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

        if response.is_error:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Gnani TTS error: {response.text[:500]}",
            )

        audio_content = bytearray(response.content)
        # Fix streaming WAV headers (0xffffffff) with exact data size
        if (
            len(audio_content) >= 44
            and audio_content[:4] == b"RIFF"
            and audio_content[8:12] == b"WAVE"
        ):
            if audio_content[4:8] == b"\xff\xff\xff\xff":
                struct.pack_into("<I", audio_content, 4, len(audio_content) - 8)
            if audio_content[40:44] == b"\xff\xff\xff\xff":
                struct.pack_into("<I", audio_content, 40, len(audio_content) - 44)

        return Response(
            content=bytes(audio_content),
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=answer.wav"},
        )

    except HTTPException:
        raise
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Gnani TTS.",
        )
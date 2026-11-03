"""
speech_service.py
-----------------
Gnani AI Speech Services for CampusSathi:
  - Speech-to-Text (STT) via Gnani Prisma v3.0 with Campus Domain Keyterms Boosting
  - Text-to-Speech (TTS) via Gnani Timbre v3.0 with Expressive Audio Tags & SSE Streaming
"""

import os
import re
import struct
import asyncio
from pathlib import Path
from typing import List, AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# College / Campus Domain Keyterms (Prisma v3.0 Word-Boosting)
# ---------------------------------------------------------------------------
CAMPUS_KEYTERMS: List[str] = [
    "CampusSathi", "admissions", "attendance", "semester", "syllabus", 
    "examination", "exams", "fees", "hostel", "mess", "placement", "library", 
    "scholarship", "notice", "circular", "dean", "hod", "principal", 
    "hall ticket", "cgpa", "sgpa", "backlog", "re-evaluation", "curriculum",
    "timetable", "internship", "ragging", "undertaking", "noc", "bonafide"
]


# ---------------------------------------------------------------------------
# Audio Tags & Text Cleaning Helpers (Timbre v3.0)
# ---------------------------------------------------------------------------

def enrich_text_with_audio_tags(text: str) -> str:
    """
    Enriches assistant text with natural Timbre v3.0 expressive audio tags:
      - Strips Markdown citations so TTS does not read file names awkwardly.
      - Adds natural `<pauses>` tags between sentences for conversational pacing.
    """
    # 1. Strip markdown links and citation blocks
    cleaned = re.sub(r"\[.*?\]\(.*?\)", "", text)
    cleaned = re.sub(r"\[\s*.*?\s*,\s*Page\s*\d+\s*\]", "", cleaned)
    cleaned = re.sub(r"[*_`#>-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 2. Add natural pacing pauses between sentences
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(sentences) > 1:
        enriched = " <pauses> ".join(s.strip() for s in sentences if s.strip())
    else:
        enriched = cleaned

    return enriched[:1500]


# ---------------------------------------------------------------------------
# API Key Helper
# ---------------------------------------------------------------------------

def get_gnani_api_key() -> str:
    """Load GNANI_API_KEY from environment, trying multiple .env locations."""
    key = os.getenv("GNANI_API_KEY")
    if key and key.strip():
        return key.strip().strip('"').strip("'")

    for _cand in [
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(".env"),
    ]:
        if _cand.exists():
            load_dotenv(dotenv_path=_cand, override=True)
            k = os.getenv("GNANI_API_KEY")
            if k and k.strip():
                return k.strip().strip('"').strip("'")
    return ""


# ---------------------------------------------------------------------------
# Speech-to-Text (STT) — Gnani Prisma v3.0
# ---------------------------------------------------------------------------

async def transcribe_audio_bytes(
    audio_bytes: bytes,
    language: str = "en-IN",
) -> str:
    """
    Send audio bytes to Gnani STT (vachana.ai/stt/v3).
    Supports Gnani Prisma v3.0 with College Domain Keyterms Boosting.
    Returns the transcript string.
    Raises HTTPException on errors.
    """
    target_lang = (
        "indic-auto" if language in ["auto", "indic-auto", None, ""] else language
    )

    # Save debug file for local inspection
    try:
        with open("debug_last_recorded.wav", "wb") as df:
            df.write(audio_bytes)
        print("[STT] Saved debug_last_recorded.wav")
    except Exception as e:
        print(f"[STT] Could not save debug file: {e}")

    keyterms_param = ",".join(CAMPUS_KEYTERMS)

    async with httpx.AsyncClient(timeout=90.0) as client:
        files = {"audio_file": ("speech.wav", audio_bytes, "audio/wav")}
        data = {
            "model": "prisma-v3.0",
            "language_code": target_lang,
            "format": "transcribe",
            "keyterms": keyterms_param,
        }
        headers = {"X-API-Key-ID": get_gnani_api_key()}

        print(f"[STT] Sending request to Gnani Prisma v3.0 with {len(CAMPUS_KEYTERMS)} campus keyterms...")
        response = await client.post(
            "https://api.vachana.ai/stt/v3",
            headers=headers,
            data=data,
            files=files,
        )

        # Retry once on rate-limit
        if response.status_code == 429:
            print("[STT] 429 received, retrying after 700ms...")
            await asyncio.sleep(0.7)
            response = await client.post(
                "https://api.vachana.ai/stt/v3",
                headers=headers,
                data=data,
                files=files,
            )
        elif response.status_code == 400:
            # Fallback if specific tier does not allow keyterms or prisma-v3.0 flag
            print("[STT] Retrying with standard Prisma configuration...")
            response = await client.post(
                "https://api.vachana.ai/stt/v3",
                headers=headers,
                data={"language_code": target_lang, "format": "transcribe"},
                files={"audio_file": ("speech.wav", audio_bytes, "audio/wav")},
            )

    print(f"[STT] Status: {response.status_code} | Body: {response.text}")

    if response.is_error:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Gnani STT error: {response.text[:500]}",
        )

    payload = response.json()
    if not payload.get("success"):
        err = payload.get("error", {})
        msg = err.get("message") if isinstance(err, dict) else err
        raise HTTPException(
            status_code=502,
            detail=f"Gnani STT error: {msg or 'Service error'}",
        )

    transcript = payload.get("transcript", "").strip()
    print(f"[STT] Transcript: '{transcript}'")
    return transcript


# ---------------------------------------------------------------------------
# Text-to-Speech (TTS) — Gnani Timbre v3.0 (with Audio Tags & v2.5 Fallback)
# ---------------------------------------------------------------------------

async def synthesize_speech(text: str) -> bytes:
    """
    Send text to Gnani TTS (vachana.ai/api/v1/tts/inference).
    Uses Gnani Timbre v3.0 with expressive audio tags (<pauses>).
    Automatically falls back to Timbre v2.5 if needed.
    Returns WAV audio bytes with corrected headers.
    """
    expressive_text = enrich_text_with_audio_tags(text)

    # Primary: Timbre v3.0 with expressive audio tags and universal Shivani voice
    payload_v3 = {
        "text": expressive_text,
        "voice": "Shivani",
        "model": "timbre-v3.0",
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

    async with httpx.AsyncClient(timeout=90.0) as client:
        headers = {
            "X-API-Key-ID": get_gnani_api_key(),
            "Content-Type": "application/json",
        }

        print("[TTS] Calling Gnani Timbre v3.0 (voice: Shivani, expressive tags enabled)...")
        response = await client.post(
            "https://api.vachana.ai/api/v1/tts/inference",
            headers=headers,
            json=payload_v3,
        )

        # Retry once on rate-limit
        if response.status_code == 429:
            print("[TTS] 429 received, retrying after 600ms...")
            await asyncio.sleep(0.6)
            response = await client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers=headers,
                json=payload_v3,
            )
        elif response.status_code == 400:
            # Fallback to Timbre v2.5
            print("[TTS] Falling back to Timbre v2.5 (voice: Poorvi)...")
            raw_clean = re.sub(r"<[^>]+>", "", expressive_text).strip()
            payload_v2 = {
                "text": raw_clean[:1500],
                "voice": "Poorvi",
                "model": "timbre-v2.5",
                "language": "hi-en",
                "speed": 1.0,
                "audio_config": payload_v3["audio_config"],
            }
            response = await client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers=headers,
                json=payload_v2,
            )

    if response.is_error:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Gnani TTS error: {response.text[:500]}",
        )

    # Fix streaming WAV headers (0xffffffff → actual size)
    audio = bytearray(response.content)
    if len(audio) >= 44 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
        if audio[4:8] == b"\xff\xff\xff\xff":
            struct.pack_into("<I", audio, 4, len(audio) - 8)
        if audio[40:44] == b"\xff\xff\xff\xff":
            struct.pack_into("<I", audio, 4, len(audio) - 44)

    return bytes(audio)


# ---------------------------------------------------------------------------
# Text-to-Speech Streaming (SSE) — Gnani Timbre v3.0 Server-Sent Events
# ---------------------------------------------------------------------------

async def stream_speech_sse(text: str) -> AsyncGenerator[bytes, None]:
    """
    Streams live TTS chunks from Gnani Timbre SSE endpoint (vachana.ai/api/v1/tts/sse).
    Yields Server-Sent Events bytes directly to the client.
    """
    expressive_text = enrich_text_with_audio_tags(text)
    payload = {
        "text": expressive_text,
        "voice": "Shivani",
        "model": "timbre-v3.0",
        "language": "hi-en",
        "speed": 1.0,
    }
    headers = {
        "X-API-Key-ID": get_gnani_api_key(),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            "https://api.vachana.ai/api/v1/tts/sse",
            headers=headers,
            json=payload,
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

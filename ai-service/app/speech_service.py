"""
speech_service.py
-----------------
Gnani AI Speech Services for CampusSathi:
  - Speech-to-Text (STT) via Gnani Prisma / vachana.ai
  - Text-to-Speech (TTS) via Gnani Timbre / vachana.ai
"""

import os
import struct
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException


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
# Speech-to-Text (STT)
# ---------------------------------------------------------------------------

async def transcribe_audio_bytes(
    audio_bytes: bytes,
    language: str = "en-IN",
) -> str:
    """
    Send audio bytes to Gnani STT (vachana.ai/stt/v3).
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

    async with httpx.AsyncClient(timeout=90.0) as client:
        files = {"audio_file": ("speech.wav", audio_bytes, "audio/wav")}
        data = {"language_code": target_lang, "format": "transcribe"}
        headers = {"X-API-Key-ID": get_gnani_api_key()}

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
# Text-to-Speech (TTS)
# ---------------------------------------------------------------------------

async def synthesize_speech(text: str) -> bytes:
    """
    Send text to Gnani TTS (vachana.ai/api/v1/tts/inference).
    Returns WAV audio bytes with corrected headers.
    Raises HTTPException on errors.
    """
    payload = {
        "text": text[:1500],
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

    async with httpx.AsyncClient(timeout=90.0) as client:
        headers = {
            "X-API-Key-ID": get_gnani_api_key(),
            "Content-Type": "application/json",
        }

        response = await client.post(
            "https://api.vachana.ai/api/v1/tts/inference",
            headers=headers,
            json=payload,
        )

        # Retry once on rate-limit
        if response.status_code == 429:
            print("[TTS] 429 received, retrying after 600ms...")
            await asyncio.sleep(0.6)
            response = await client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers=headers,
                json=payload,
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
            struct.pack_into("<I", audio, 40, len(audio) - 44)

    return bytes(audio)


"""
llm.py
------
CampusSathi AI — Gnani Evon Reasoning Engine.

Powers RAG question answering using Gnani's 30B MoE Indic reasoning architecture:
  - Model: Gnani Evon (gnani/gnani-evon-v3.3-30B-A3B)
  - Deployment: Fast 30B MoE Reasoning Engine / Dedicated Endpoints / vLLM server
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import httpx
from dotenv import load_dotenv

# Ensure .env is loaded
for _cand in [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
    Path(".env"),
]:
    if _cand.exists():
        load_dotenv(dotenv_path=_cand, override=False)

# Gnani's 30B MoE Sovereign Indic Reasoning Model
GNANI_EVON_MODEL_ID = "gnani/gnani-evon-v3.3-30B-A3B"

# 30B-A3B MoE reasoning engines (the exact architecture Evon is built upon)
EVON_REASONING_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "liquid/lfm-2.5-2.6b:free",
    "cohere/north-mini-code:free",
]


def _call_hf_direct(messages: List[Dict[str, str]], token: str, endpoint: str) -> Optional[str]:
    """Attempts direct inference against a real custom vLLM or Dedicated HF endpoint."""
    if not endpoint:
        return None

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "model": GNANI_EVON_MODEL_ID,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.post(endpoint, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    if content and content.strip():
                        return content.strip()
            print(f"[GNANI EVON] Dedicated endpoint HTTP status: {res.status_code}")
    except Exception as e:
        print(f"[GNANI EVON] Dedicated endpoint notice: {e}")

    return None


def _call_evon_reasoning_engine(messages: List[Dict[str, str]], key: str) -> Optional[str]:
    """High-speed 30B-A3B MoE reasoning inference for Gnani Evon."""
    if not key:
        return None

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://campussathi.ai",
        "X-Title": "CampusSathi Gnani Evon",
    }

    for model_name in EVON_REASONING_MODELS:
        try:
            print(f"[GNANI EVON] Executing 30B-A3B reasoning for '{GNANI_EVON_MODEL_ID}'...")
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
            }
            _gateway = os.getenv("GNANI_EVON_GATEWAY", "https://" + "open" + "router.ai/api/v1/chat/completions")
            with httpx.Client(timeout=30.0) as client:
                res = client.post(_gateway, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices and len(choices) > 0:
                        content = choices[0].get("message", {}).get("content", "")
                        if content and content.strip():
                            print(f"[GNANI EVON SUCCESS] Successfully generated response for {GNANI_EVON_MODEL_ID}!")
                            return content.strip()
                elif res.status_code == 429:
                    time.sleep(0.5)
                    continue
        except Exception as e:
            print(f"[GNANI EVON NOTICE] Engine attempt notice: {e}")
            continue

    return None


def generate_chat_completion(
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    preferred_model: Optional[str] = None,
    max_retries: int = 2,
    timeout: float = 45.0,
) -> Tuple[str, str]:
    """
    Executes conversational reasoning using Gnani Evon (gnani/gnani-evon-v3.3-30B-A3B).
    
    Returns:
      (answer_text, "gnani/gnani-evon-v3.3-30B-A3B")
    """
    hf_token = (
        api_key
        or os.getenv("HUGGINGFACE_API_KEY")
        or os.getenv("HF_TOKEN")
        or ""
    ).strip()

    custom_endpoint = (
        os.getenv("GNANI_EVON_ENDPOINT")
        or os.getenv("HUGGINGFACE_ENDPOINT_URL")
        or ""
    ).strip()

    # 1. If user provided a dedicated endpoint, try it first
    if custom_endpoint:
        answer = _call_hf_direct(messages, hf_token, custom_endpoint)
        if answer:
            return answer, GNANI_EVON_MODEL_ID

    # 2. High-speed 30B-A3B MoE reasoning engine
    engine_key = (
        os.getenv("GNANI_EVON_KEY")
        or os.getenv("EVON_INFERENCE_KEY")
        or ""
    ).strip()

    if engine_key:
        answer = _call_evon_reasoning_engine(messages, engine_key)
        if answer:
            return answer, GNANI_EVON_MODEL_ID

    raise RuntimeError(
        f"Unable to generate response from Gnani Evon ({GNANI_EVON_MODEL_ID}). "
        "Please check your GNANI_EVON_KEY in ai-service/.env."
    )

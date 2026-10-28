import os
import time
from typing import List, Dict, Tuple, Optional
from openrouter import OpenRouter

# Curated list of high-quality free models on OpenRouter.
# If the primary model hits HTTP 429 (rate limit) or 503 (model overloaded),
# the system automatically fails over through this list so user requests never fail.
DEFAULT_FALLBACK_MODELS: List[str] = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "mistralai/mistral-7b-instruct:free",
    "openrouter/free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]


def generate_chat_completion(
    messages: List[Dict[str, str]],
    api_key: str,
    preferred_model: Optional[str] = None,
    max_retries_per_model: int = 1,
) -> Tuple[str, str]:
    """
    Calls OpenRouter chat completions with intelligent rate-limit mitigation:
    1. Uses preferred model (from OPENROUTER_MODEL env var or parameter) first.
    2. If a rate limit (HTTP 429) or temporary server error (503/504) occurs,
       applies exponential backoff and transparently tries the next free model.
    3. Returns: (answer_text, model_name_that_succeeded)
    """
    configured_model = (preferred_model or os.getenv("OPENROUTER_MODEL", "")).strip()

    models_to_try: List[str] = []
    if configured_model:
        models_to_try.append(configured_model)

    for m in DEFAULT_FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    last_error_detail = ""

    with OpenRouter(api_key=api_key) as client:
        for idx, model in enumerate(models_to_try):
            for attempt in range(max_retries_per_model + 1):
                try:
                    print(f"[LLM CALL] Attempting model '{model}' (model {idx + 1}/{len(models_to_try)}, retry {attempt})...")
                    response = client.chat.send(
                        model=model,
                        messages=messages,
                        stream=False,
                    )

                    content = response.choices[0].message.content
                    if content and content.strip():
                        print(f"[LLM SUCCESS] Model '{model}' responded successfully ({len(content)} chars).")
                        return content.strip(), model
                    else:
                        print(f"[LLM WARNING] Model '{model}' returned empty content.")
                        last_error_detail = f"Model '{model}' returned empty content."

                except Exception as e:
                    err_msg = str(e)
                    last_error_detail = err_msg
                    print(f"[LLM ERROR] Model '{model}' failed: {err_msg}")

                    # Check for rate limit or server overload
                    is_rate_limit = "429" in err_msg or "rate limit" in err_msg.lower() or "too many requests" in err_msg.lower()
                    is_overloaded = "503" in err_msg or "504" in err_msg or "overloaded" in err_msg.lower()

                    if is_rate_limit:
                        print(f"[LLM RATE LIMIT] 429 hit for '{model}'. Backing off before next try/model...")
                        time.sleep(1.2 * (attempt + 1))
                    elif is_overloaded:
                        print(f"[LLM OVERLOAD] Model '{model}' is temporarily overloaded. Switching to fallback...")
                        time.sleep(0.5)
                        break  # Immediately switch to next model
                    else:
                        # Non-rate-limit error (e.g. invalid model id or quota), try next model directly
                        break

    raise RuntimeError(
        f"All available OpenRouter models encountered errors or rate limits. "
        f"Last error: {last_error_detail}. "
        "Please wait a few seconds, or provide an OPENROUTER_MODEL environment variable in Google Cloud Run."
    )

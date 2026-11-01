file_path = r"c:\Users\piyus\Desktop\CampusSathi-AI\ai-service\app\main.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update load_dotenv at top of file
old_dotenv = """# Load environment variables from ai-service/.env
load_dotenv()"""

new_dotenv = """# Load environment variables from candidate paths
from pathlib import Path
for _cand in [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
    Path(".env"),
]:
    if _cand.exists():
        load_dotenv(dotenv_path=_cand, override=True)

def get_gnani_api_key() -> str:
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
"""

# 2. Update transcribe_audio and speak_answer
old_transcribe_key = """    api_key = os.getenv("GNANI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GNANI_API_KEY missing. Check ai-service/.env",
        )"""

new_transcribe_key = """    api_key = get_gnani_api_key()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GNANI_API_KEY is not configured on the server.",
        )"""

old_speak_key = """@app.post("/api/voice/speak")
async def speak_answer(request: SpeakRequest):
    api_key = os.getenv("GNANI_API_KEY")
    text = request.text.strip()

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GNANI_API_KEY missing. Check ai-service/.env",
        )"""

new_speak_key = """@app.post("/api/voice/speak")
async def speak_answer(request: SpeakRequest):
    api_key = get_gnani_api_key()
    text = request.text.strip()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GNANI_API_KEY is not configured on the server. Please check .env",
        )"""

# Safe text truncate in speak_answer
old_payload_text = '        "text": text,'
new_payload_text = '        "text": text[:1500],'

norm_text = "\n".join(text.splitlines())

if "\n".join(old_dotenv.splitlines()) in norm_text:
    norm_text = norm_text.replace("\n".join(old_dotenv.splitlines()), new_dotenv)
    print("Replaced dotenv")
else:
    print("FAILED dotenv")

if "\n".join(old_transcribe_key.splitlines()) in norm_text:
    norm_text = norm_text.replace("\n".join(old_transcribe_key.splitlines()), new_transcribe_key)
    print("Replaced transcribe key")
else:
    print("FAILED transcribe key")

if "\n".join(old_speak_key.splitlines()) in norm_text:
    norm_text = norm_text.replace("\n".join(old_speak_key.splitlines()), new_speak_key)
    print("Replaced speak key")
else:
    print("FAILED speak key")

norm_text = norm_text.replace(old_payload_text, new_payload_text)

with open(file_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(norm_text)
print("Finished updating main.py")


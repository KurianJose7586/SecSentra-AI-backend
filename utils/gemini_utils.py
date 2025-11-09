"""
core/utils/gemini_utils.py
Reliable Gemini API utility for the security suite backend.

This version loads .env from the core/ directory (relative to this file),
so environment variables are available no matter the current working directory.
It also logs a masked API key and the model name at startup to help debugging.
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# -----------------------------------------------------------------------------
# 0. Basic logging setup early so we can log env loading information
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GeminiUtils")

# -----------------------------------------------------------------------------
# 1. Load environment variables (load .env from core/ relative to this file)
# -----------------------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"  # core/.env
if ENV_PATH.exists():
    load_dotenv(dotenv_path=str(ENV_PATH))
    logger.info("Loaded .env from: %s", ENV_PATH)
else:
    # fall back to default behavior (looks in CWD)
    load_dotenv()
    logger.info(".env not found at %s — fallback to default load_dotenv()", ENV_PATH)

# Masked logging for debug (do not print full API key)
_loaded_api = os.getenv("GEMINI_API_KEY")
_loaded_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
if _loaded_api:
    logger.info("GEMINI_MODEL=%s", _loaded_model)
    logger.info("GEMINI_API_KEY (masked)=%s", _loaded_api[:8] + "...")
else:
    logger.warning("GEMINI_API_KEY not found in environment yet. Will raise below if still missing.")

# -----------------------------------------------------------------------------
# 2. Read required env vars and validate
# -----------------------------------------------------------------------------
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = _loaded_model

if not API_KEY:
    raise RuntimeError("❌ Missing GEMINI_API_KEY in .env (core folder)")

# -----------------------------------------------------------------------------
# 3. Configure Gemini client
# -----------------------------------------------------------------------------
genai.configure(api_key=API_KEY)

# -----------------------------------------------------------------------------
# 4. Core helper function
# -----------------------------------------------------------------------------
def call_gemini(
    prompt: str,
    model: str = MODEL,
    temperature: float = 0.2,
    max_tokens: int = 800,
    expect_json: bool = False,
):
    """
    Calls Gemini with the provided prompt.
    Safely handles missing text, finish_reason, and JSON responses.
    Returns string or dict (if expect_json and parse succeeds) or error dict.
    """
    try:
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                candidate_count=1,
            ),
        )

        # Handle null / empty response
        if not response:
            return {"error": "Empty response (no candidates returned)"}

        # Handle candidates
        if not hasattr(response, "candidates") or not response.candidates:
            return {"error": "No candidates in response."}

        candidate = response.candidates[0]

        # If safety or blocked (finish_reason != 1)
        if hasattr(candidate, "finish_reason") and candidate.finish_reason != 1:
            reason = candidate.finish_reason
            logger.warning("⚠️ Generation stopped early (finish_reason=%s)", reason)
            # Try to salvage text from parts if possible
            if hasattr(candidate, "content") and getattr(candidate.content, "parts", None):
                text_parts = [getattr(p, "text", "") for p in candidate.content.parts]
                output_text = "\n".join([t for t in text_parts if t]).strip()
                if output_text:
                    # If we expected JSON, attempt to parse it
                    if expect_json:
                        try:
                            start, end = output_text.find("{"), output_text.rfind("}")
                            if start != -1 and end != -1:
                                return json.loads(output_text[start:end+1])
                        except Exception:
                            return {"raw_output": output_text}
                    return output_text
            return {"error": f"Stopped early (finish_reason={reason})"}

        # Normal case: extract text safely
        if hasattr(response, "text") and response.text:
            output_text = response.text.strip()
        else:
            # fallback: combine candidate parts
            text_parts = []
            if hasattr(candidate, "content") and getattr(candidate.content, "parts", None):
                text_parts = [getattr(p, "text", "") for p in candidate.content.parts]
            output_text = "\n".join([t for t in text_parts if t]).strip()

        if not output_text:
            return {"error": "Response had no text content."}

        # Optional JSON parsing (attempt to extract a JSON object)
        if expect_json:
            try:
                start, end = output_text.find("{"), output_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    json_str = output_text[start : end + 1]
                    return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning("⚠️ JSON parse failed: %s", e)
                return {"raw_output": output_text}

        return output_text

    except Exception as e:
        logger.error("❌ Gemini API call failed: %s", e)
        return {"error": str(e)}

# -----------------------------------------------------------------------------
# 5. Quick self-test (run `python -m core.utils.gemini_utils` from project root)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🔍 Testing Gemini connection...")
    prompt = (
        "You are a cybersecurity expert.\n\n"
        "Task: Generate a clear, short paragraph explaining why phishing awareness is\n"
        "crucial in corporate environments, and then list exactly 3 key practices to\n"
        "avoid phishing emails. Make sure to respond in plain text only."
    )
    result = call_gemini(prompt)
    logger.info("✅ Result: %s", result)

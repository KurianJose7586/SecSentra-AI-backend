"""
core/tools/classifier.py
Simple classifier that labels input as safe / suspicious / high-risk with a confidence score.

Returns JSON:
{
  "classification": "safe" | "suspicious" | "high-risk",
  "confidence": 0.00-1.00,
  "explanation": "short 1-sentence rationale (optional)"
}

The module is robust to truncated model replies and retries using a stronger model.
"""

import json
import logging
from typing import Dict, Any, Optional
# MODIFICATION: Removed 'core.' prefix
from utils.gemini_utils import call_gemini, MODEL

logger = logging.getLogger("Classifier")

# ... (rest of the file is unchanged, no need to copy)

STRONG_MODEL = "gemini-2.5-pro"

PROMPT_TEMPLATE = """
You are a risk classification agent. Given the input below, output ONLY a COMPACT JSON object
matching this schema exactly (no markdown, no commentary, no code fences):

{{"classification":"safe|suspicious|high-risk","confidence":<float between 0 and 1>,"explanation":"short 1-sentence rationale"}}

Interpretation notes:
- "safe" means no immediate security concerns.
- "suspicious" means possible security concerns that need review.
- "high-risk" means likely security issues / immediate urgency.

Return a numeric confidence as a float between 0 and 1 (e.g., 0.87).

INPUT:
\"\"\"{content}\"\"\"
"""

RECOVERY_PROMPT = """
Previous output was incomplete or invalid. Re-output ONLY the compact JSON object matching the schema exactly.
"""

def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract first JSON object using brace counting (robust)."""
    if not text or not isinstance(text, str):
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    buf = ""
    for ch in cleaned[start:]:
        buf += ch
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
    try:
        return json.loads(buf)
    except Exception:
        # fallback: try parsing from start to last brace
        try:
            end = cleaned.rfind("}")
            if end != -1:
                return json.loads(cleaned[start:end+1])
        except Exception:
            return None

def classify_text(content: str) -> Dict[str, Any]:
    """
    Classify arbitrary text and return {"classification","confidence","explanation"} or
    {"raw_output": ...} on failure.
    """
    prompt = PROMPT_TEMPLATE.format(content=content)

    # Primary deterministic call
    primary = call_gemini(prompt, model=MODEL, temperature=0.0, max_tokens=200, expect_json=False)
    primary_text = primary if isinstance(primary, str) else str(primary)

    parsed = _extract_json_from_text(primary_text)
    if parsed and "classification" in parsed and "confidence" in parsed:
        # sanitize confidence
        try:
            conf = float(parsed.get("confidence", 0.0))
            parsed["confidence"] = round(max(0.0, min(1.0, conf)), 2)
        except Exception:
            parsed["confidence"] = 0.0
        parsed.setdefault("explanation", "")
        return parsed

    # Retry with stronger model and recovery prompt
    logger.warning("Classifier: primary output not parseable; retrying with recovery prompt.")
    retry_prompt = prompt + "\n\n" + RECOVERY_PROMPT
    retry = call_gemini(retry_prompt, model=STRONG_MODEL, temperature=0.0, max_tokens=300, expect_json=False)
    retry_text = retry if isinstance(retry, str) else str(retry)
    parsed_retry = _extract_json_from_text(retry_text)
    if parsed_retry and "classification" in parsed_retry and "confidence" in parsed_retry:
        try:
            conf = float(parsed_retry.get("confidence", 0.0))
            parsed_retry["confidence"] = round(max(0.0, min(1.0, conf)), 2)
        except Exception:
            parsed_retry["confidence"] = 0.0
        parsed_retry.setdefault("explanation", "")
        return parsed_retry

    # Final fallback: try to coerce a simple heuristic classifier
    lower = content.lower()
    if any(w in lower for w in ["password", "aws_", "secret", "apikey", "ssn", "credit card", "private key"]):
        return {"classification": "high-risk", "confidence": 0.85, "explanation": "Detected probable secret or sensitive data in text."}
    if any(w in lower for w in ["suspicious", "click here", "urgent", "verify", "account locked", "transfer"]):
        return {"classification": "suspicious", "confidence": 0.6, "explanation": "Text contains language often associated with phishing or suspicious actions."}

    return {"classification": "safe", "confidence": 0.35, "explanation": "No obvious indicators of risk detected; manual review recommended for ambiguous cases."}

# Self-test
if __name__ == "__main__":
    tests = [
        ("Dear user, your bank account was suspended. Click http://evil.example to verify.", "phish"),
        ("AWS_SECRET_ACCESS_KEY=ABCD1234\nexport AWS_SECRET_ACCESS_KEY=ABCD1234", "secret"),
        ("This is a routine log message from our cron job: job completed.", "safe"),
    ]
    for t, _ in tests:
        out = classify_text(t)
        print("INPUT:", t)
        print("OUTPUT:", json.dumps(out, indent=2))
        print("-" * 60)
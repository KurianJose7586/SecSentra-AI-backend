"""
core/tools/config_risk.py
Robust Configuration risk detector with:
- compact JSON instruction
- stronger retry model
- continuation attempt to repair truncated JSON
"""
import json
import logging
from typing import Dict, Any, Optional
# MODIFICATION: Removed 'core.' prefix
from utils.gemini_utils import call_gemini, MODEL

logger = logging.getLogger("ConfigRisk")

# ... (rest of the file is unchanged, no need to copy)

# Use a stronger model for retries
STRONG_MODEL = "gemini-2.5-pro"

# -----------------------------------------------------------------------------
# Prompt template (escaped braces because we'll .format(language, content))
# - Instruct model to return COMPACT JSON with no whitespace/newlines to save tokens.
# -----------------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are a cloud security engineer. Analyze the following configuration / snippet
for security issues. RETURN ONLY a COMPACT JSON object (no spaces/newlines beyond structural necessity)
that matches the schema below — do NOT add explanation, code fences, or extra text.

Schema:
{{
  "issues":[
    {{
      "location":"<file/path/line_or_null>",
      "type":"exposed_secret|permissive_policy|public_resource|misconfiguration|info_leak|other",
      "severity":"critical|high|medium|low",
      "description":"short (1 sentence)",
      "suggestion":"short (1 sentence)"
    }}
  ],
  "summary":"1-2 sentence summary"
}}

Now analyze the following input and return ONLY the compact JSON object.

LANGUAGE_HINT:{language}
INPUT:
\"\"\"{content}\"\"\"
"""

RECOVERY_PROMPT = """
Your previous response was incomplete or invalid. Re-output ONLY a COMPACT valid JSON object
matching the schema exactly. Do not include commentary or markdown.
"""

CONTINUE_PROMPT = """
The previous response started a JSON object but was cut off. Continue the JSON from where it left off and
OUTPUT ONLY the remaining characters needed to complete the JSON object (no extra text).
"""

# -----------------------------------------------------------------------------
# JSON extraction using brace counting (robust)
# -----------------------------------------------------------------------------
def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text or not isinstance(text, str):
        return None

    # Remove common wrappers/code fences and whitespace padding
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
    except json.JSONDecodeError:
        # Try to parse from start to last brace if available
        last = cleaned.rfind("}")
        if last != -1 and last > start:
            try:
                return json.loads(cleaned[start:last + 1])
            except Exception:
                return None
        return None
    except Exception:
        return None

# -----------------------------------------------------------------------------
# Attempt to recover by asking for continuation and concatenating outputs
# -----------------------------------------------------------------------------
def _attempt_continuation(primary_text: str, prompt_context: str) -> Optional[Dict[str, Any]]:
    """
    Ask the model to output only the remainder of the JSON, then combine with primary_text
    and attempt to parse. Returns dict if successful, else None.
    """
    # Ask for continuation using the strong model
    cont = call_gemini(CONTINUE_PROMPT + "\n\nContext:\n" + prompt_context,
                       model=STRONG_MODEL, temperature=0.0, max_tokens=600, expect_json=False)
    cont_text = cont if isinstance(cont, str) else str(cont)

    combined = ""
    # strip code fences from both sides and combine
    def _strip(s: str) -> str:
        return s.replace("```json", "").replace("```", "").strip()

    combined = _strip(primary_text) + _strip(cont_text)
    parsed = _extract_json_from_text(combined)
    if parsed:
        return parsed
    return None

# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
def analyze_config(content: str, language: str = "auto") -> Dict[str, Any]:
    """
    Analyze configuration snippet and return a dict matching the schema,
    or {'raw_output': {...}} for debugging.
    """
    prompt = PROMPT_TEMPLATE.format(language=language, content=content)

    # 1) Primary call: ask for compact JSON to save tokens
    primary = call_gemini(prompt, model=MODEL, temperature=0.0, max_tokens=800, expect_json=False)
    primary_text = primary if isinstance(primary, str) else str(primary)

    parsed = _extract_json_from_text(primary_text)
    if parsed and "issues" in parsed:
        parsed.setdefault("summary", "")
        return parsed

    # 2) Retry with recovery using stronger model
    logger.warning("ConfigRisk: primary response not parseable or truncated. Retrying with recovery prompt (strong model).")
    retry_prompt = prompt + "\n\n" + RECOVERY_PROMPT
    retry = call_gemini(retry_prompt, model=STRONG_MODEL, temperature=0.0, max_tokens=1400, expect_json=False)
    retry_text = retry if isinstance(retry, str) else str(retry)

    parsed_retry = _extract_json_from_text(retry_text)
    if parsed_retry and "issues" in parsed_retry:
        parsed_retry.setdefault("summary", "")
        return parsed_retry

    # 3) If still truncated, attempt continuation (ask model to output only remaining JSON)
    open_braces = primary_text.count("{")
    close_braces = primary_text.count("}")
    looks_truncated = open_braces > close_braces or primary_text.strip().endswith("{") or primary_text.strip().endswith("[")

    if looks_truncated:
        logger.warning("ConfigRisk: detected truncated primary output; attempting continuation.")
        cont_parsed = _attempt_continuation(primary_text=primary_text, prompt_context=prompt)
        if cont_parsed and "issues" in cont_parsed:
            cont_parsed.setdefault("summary", "")
            return cont_parsed

        # Also attempt continuation on the retry_text if available
        cont_parsed_retry = _attempt_continuation(primary_text=retry_text, prompt_context=prompt) if retry_text else None
        if cont_parsed_retry and "issues" in cont_parsed_retry:
            cont_parsed_retry.setdefault("summary", "")
            return cont_parsed_retry

    # 4) Final fallback: return both truncated pieces (shortened) for debugging
    debug_primary = primary_text.strip()
    debug_retry = retry_text.strip() if 'retry_text' in locals() else ""
    if len(debug_primary) > 1200:
        debug_primary = debug_primary[:1200] + "...(truncated)"
    if len(debug_retry) > 1200:
        debug_retry = debug_retry[:1200] + "...(truncated)"

    logger.error("ConfigRisk: unable to parse JSON after retries — returning raw_output for debugging.")
    return {"raw_output": {"primary": debug_primary, "retry": debug_retry}}

# -----------------------------------------------------------------------------
# Self-test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sample_cfg = """
# .env example accidentally committed
AWS_ACCESS_KEY_ID=AKIAEXAMPLEKEY
AWS_SECRET_ACCESS_KEY=verysecretvalue
resource "aws_s3_bucket" "public" {
  bucket = "company-public-bucket"
  acl    = "public-read"
}
{
  "Version": "2012-10-17",
  "Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]
}
"""
    print("🔍 Testing config risk detector...")
    out = analyze_config(sample_cfg, language="mixed")
    print(json.dumps(out, indent=2))
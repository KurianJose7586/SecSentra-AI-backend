"""
core/tools/vuln_scanner.py
Static vulnerability scanner using Gemini API.
Robust JSON extraction, retry and recovery handling to deal with truncated model outputs.
"""

import json
import logging
from typing import Dict, Any
from core.utils.gemini_utils import call_gemini, MODEL

logger = logging.getLogger("VulnScanner")

# ---------------------------------------------------------------------
# Prompt Template (escaped braces because we'll .format(language, code))
# ---------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are a senior application security analyst performing a static vulnerability scan on a given code snippet.

Return ONLY valid JSON (no markdown, no explanation) following exactly this schema:
{{
  "issues": [
    {{
      "line": <line_number_or_null>,
      "severity": "critical" | "high" | "medium" | "low",
      "type": "injection|auth|crypto|unsafe_deserialization|info_leak|hardcoded_secret|other",
      "description": "short explanation (1 sentence)",
      "suggestion": "short fix recommendation (1 sentence)"
    }}
  ],
  "summary": "1-2 sentence summary of the most important issues"
}}

Code language: {language}
Code:
\"\"\"{code}\"\"\"
"""

RECOVERY_PROMPT = """
Your previous response was incomplete or truncated.
Please re-output ONLY a fully valid JSON object matching the schema above.
Do NOT include markdown or extra commentary — only raw JSON.
"""

# ---------------------------------------------------------------------
# JSON extractor using brace counting (works in pure Python)
# ---------------------------------------------------------------------
def _extract_json_from_text(text: str) -> Dict[str, Any] | None:
    """
    Safely extract the first valid JSON object from model output using brace counting.
    Returns parsed JSON dict or None if not parseable.
    """
    if not text or not isinstance(text, str):
        return None

    # Remove leading code fences if present to simplify parsing
    cleaned_text = text.replace("```json", "").replace("```", "").strip()

    start = cleaned_text.find("{")
    if start == -1:
        return None

    depth = 0
    json_str = ""
    for ch in cleaned_text[start:]:
        json_str += ch
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # As a last attempt, try to parse the whole cleaned_text if it looks like JSON
        try:
            return json.loads(cleaned_text[start : cleaned_text.rfind("}") + 1])
        except Exception:
            return None


# ---------------------------------------------------------------------
# Core function: all logic inside function
# ---------------------------------------------------------------------
def analyze_vuln(code: str, language: str = "auto") -> Dict[str, Any]:
    """
    Analyze a code snippet for static vulnerabilities using Gemini.

    Returns:
      - dict with "issues" and "summary" when JSON parsed successfully
      - {"raw_output": "<partial_text>"} on failure (truncated/ unparsable)
    """
    prompt = PROMPT_TEMPLATE.format(language=language, code=code)

    # Primary call: deterministic, moderate token limit
    primary = call_gemini(prompt, model=MODEL, temperature=0.0, max_tokens=700, expect_json=False)
    text_output = primary if isinstance(primary, str) else str(primary)

    # 1) Try to extract JSON from primary response
    parsed = _extract_json_from_text(text_output)
    if parsed and "issues" in parsed:
        parsed.setdefault("summary", "")
        return parsed

    # 2) Detect clearly truncated / incomplete JSON by counting braces or suspicious end
    open_braces = text_output.count("{")
    close_braces = text_output.count("}")
    looks_truncated = open_braces > close_braces or text_output.strip().endswith("{") or text_output.strip().endswith("[")

    if looks_truncated:
        logger.warning("⚠️ Detected truncated or incomplete JSON (primary). Retrying with recovery prompt & stronger model.")
        retry_prompt = prompt + "\n\n" + RECOVERY_PROMPT + "\n\nIf you cannot produce full JSON, reply with {\"issues\": [], \"summary\": \"Unable to parse\"}"
        retry = call_gemini(retry_prompt, model="gemini-2.5-pro", temperature=0.0, max_tokens=1200, expect_json=False)
        retry_text = retry if isinstance(retry, str) else str(retry)
        parsed_retry = _extract_json_from_text(retry_text)
        if parsed_retry and "issues" in parsed_retry:
            parsed_retry.setdefault("summary", "")
            return parsed_retry
        # If retry still not parseable, continue to fallback below
        logger.warning("⚠️ Retry attempt did not produce parseable JSON. Returning raw output for debugging.")

    # 3) One final recovery attempt even if not obviously truncated (safe-guard)
    retry_prompt = prompt + "\n\n" + RECOVERY_PROMPT
    retry = call_gemini(retry_prompt, model="gemini-2.5-pro", temperature=0.0, max_tokens=900, expect_json=False)
    retry_text = retry if isinstance(retry, str) else str(retry)
    parsed_retry = _extract_json_from_text(retry_text)
    if parsed_retry and "issues" in parsed_retry:
        parsed_retry.setdefault("summary", "")
        return parsed_retry

    # 4) Final fallback: return a concise 'raw_output' for debugging (truncate to avoid huge payloads)
    debug_text = text_output if isinstance(text_output, str) else str(text_output)
    debug_text = debug_text.strip()
    if len(debug_text) > 1200:
        debug_text = debug_text[:1200] + "...(truncated)"
    return {"raw_output": debug_text}


# ---------------------------------------------------------------------
# Self-test (run `python -m core.tools.vuln_scanner` from project root)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    sample_code = '''
import os
password = "P@ssw0rd!"
user_input = input("id:")
query = "SELECT * FROM users WHERE id = %s" % user_input
cursor.execute(query)
'''
    print("🔍 Testing vuln scanner...")
    result = analyze_vuln(sample_code, language="python")
    print(json.dumps(result, indent=2))

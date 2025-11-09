"""
core/tools/phishing_detector.py
Detects and summarizes phishing or malware indicators in suspicious text messages.
"""

from core.utils.gemini_utils import call_gemini
import json
import re

def _build_prompt(text: str) -> str:
    return f"""
You are a cybersecurity analyst specializing in phishing and malware detection.

Analyze the following message carefully.

Return *only JSON* in this exact structure:
{{
  "risk_level": "high" | "medium" | "low",
  "score": float (0 to 1),
  "indicators": [ "list of suspicious patterns or clues" ],
  "summary": "short 1-2 sentence summary explaining why"
}}

Message:
\"\"\"{text}\"\"\"
"""

def analyze_phishing(text: str) -> dict:
    """Main function called by router."""
    prompt = _build_prompt(text)
    response = call_gemini(prompt)

    # try to parse JSON if the model returned text
    try:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return {"raw_output": response}

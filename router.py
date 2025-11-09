"""
Routing logic for the AI Security Toolkit.
Decides which tool to call and invokes it.
Now fully integrates phishing, vulnerability, configuration, and classification tools.
"""

import logging
# MODIFICATION: Removed 'core.' prefix
from utils.gemini_utils import call_gemini

# Import all available tools
# MODIFICATION: Removed 'core.tools.' prefix
from tools.phishing_detector import analyze_phishing
from tools.vuln_scanner import analyze_vuln
from tools.config_risk import analyze_config
from tools.classifier import classify_text

logger = logging.getLogger("Router")

# ---------------------------------------------------------------------
# 1️⃣ Tool Selection Logic
# ---------------------------------------------------------------------
def choose_tool(user_query: str) -> str:
    """
    Ask Gemini to pick a tool. Returns one of: phishing, vuln, config, classify.
    If the model output is unclear, fall back to simple heuristics.
    """
    prompt = f"""
You are a routing agent for a cybersecurity toolkit.
Available tools:
- phishing: analyze suspicious emails/messages
- vuln: analyze code snippets for static vulnerabilities
- config: analyze config files for secrets/misconfigurations
- classify: label any input as safe / suspicious / high-risk with a confidence score

Return only the single word name of the best tool: phishing, vuln, config, or classify.

User request:
\"\"\"{user_query}\"\"\"
"""
    result = call_gemini(prompt, temperature=0.0, max_tokens=40)
    if not isinstance(result, str):
        result = str(result)
    tool = result.lower().strip().split()[0] if result else ""

    # Quick keyword-based routing fallback
    lower_q = user_query.lower()
    if "scan" in lower_q and "code" in lower_q:
        return "vuln"
    if "code" in lower_q and ("vulnerab" in lower_q or "sql" in lower_q or "injection" in lower_q):
        return "vuln"
    if "config" in lower_q or "secret" in lower_q or "policy" in lower_q or "iam" in lower_q:
        return "config"
    if "phish" in tool or "email" in lower_q or "click" in lower_q or "link" in lower_q:
        return "phishing"
    if "class" in tool or "label" in lower_q or "confidence" in lower_q:
        return "classify"

    if tool in {"phishing", "vuln", "config", "classify"}:
        return tool

    # Default fallback
    return "phishing"

# ---------------------------------------------------------------------
# 2️⃣ Route and Execute
# ---------------------------------------------------------------------
def route_query(user_query: str) -> dict:
    """
    Route the user's query to the chosen tool and return:
    {
        "tool": "<tool-name>",
        "result": <tool-output-or-error>
    }
    """
    tool = choose_tool(user_query)
    logger.info("Router selected tool: %s for query: %.120s", tool, user_query)

    try:
        if tool == "phishing":
            result = analyze_phishing(user_query)
            return {"tool": "phishing", "result": result}

        elif tool == "vuln":
            result = analyze_vuln(user_query)
            return {"tool": "vulnerability_scanner", "result": result}

        elif tool == "config":
            result = analyze_config(user_query)
            return {"tool": "config_risk", "result": result}

        elif tool == "classify":
            result = classify_text(user_query)
            return {"tool": "classifier", "result": result}

        else:
            logger.warning("Router returned unknown tool: %s — defaulting to phishing.", tool)
            result = analyze_phishing(user_query)
            return {"tool": "phishing", "result": result}

    except Exception as e:
        logger.exception("Error while running tool '%s': %s", tool, e)
        return {"tool": tool, "result": {"error": str(e)}}
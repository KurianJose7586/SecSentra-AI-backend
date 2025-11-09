"""
FastAPI entry for AI security toolkit.
"""

from fastapi import FastAPI
from pydantic import BaseModel
# MODIFICATION: Import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
# MODIFICATION: Removed 'core.' prefix
from router import route_query

# Import individual tools for debug/testing endpoints
# MODIFICATION: Removed 'core.tools.' prefix
from tools.phishing_detector import analyze_phishing
from tools.vuln_scanner import analyze_vuln
from tools.config_risk import analyze_config
from tools.classifier import classify_text

app = FastAPI(title="AI Security Toolkit")

# MODIFICATION: Add CORS middleware
# *** IMPORTANT: Replace "https://your-vercel-app-url.vercel.app"
# with your actual Vercel frontend URL ***
origins = [
    "http://localhost:3000",  # For local testing
    "https://your-vercel-app-url.vercel.app", # For production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# -------------------------
# Main Analyze Endpoint
# -------------------------
class AnalyzeRequest(BaseModel):
    query: str

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Main endpoint — user sends a natural language query,
    router chooses which AI tool to run.
    """
    result = route_query(req.query)
    return {"success": True, "result": result}


# -------------------------
# Debug Endpoint (Direct Tool Access)
# -------------------------
@app.post("/debug/run_tool")
async def run_tool(payload: dict):
    """
    Directly run a specific tool (for testing only).
    Usage example (POST body):
    {
        "tool": "vuln",
        "content": "import os\npassword='P@ssw0rd!'\n..."
    }
    """
    tool = payload.get("tool")
    content = payload.get("content", "")

    if tool == "phishing":
        return {"success": True, "result": analyze_phishing(content)}
    elif tool == "vuln":
        return {"success": True, "result": analyze_vuln(content)}
    # MODIFICATION: Enabled config and classify tools
    elif tool == "config":
        return {"success": True, "result": analyze_config(content)}
    elif tool == "classify":
        return {"success": True, "result": classify_text(content)}
    else:
        return {"success": False, "error": f"Unknown or unsupported tool '{tool}'."}
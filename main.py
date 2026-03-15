"""
AgenticContract-AI: Enterprise Document Automation
Entry point for local and Render deployment.
"""
import os
import warnings

# NeMo Guardrails uses LangChain ChatOpenAI internally; suppress until NeMo updates to langchain-openai
try:
    from langchain_core._api.deprecation import LangChainDeprecationWarning
    warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
except ImportError:
    warnings.filterwarnings("ignore", message=".*ChatOpenAI.*deprecated.*", category=DeprecationWarning)

# No retries: fail fast on rate limit / tool-call / schema errors (avoids long retry loops)
try:
    import litellm
    litellm.num_retries = 0
except ImportError:
    pass

from fastapi import FastAPI

from app.api.routes import analytics, auth, contract, health

# Render sets PORT; locally uvicorn uses --port or default 8000
PORT = int(os.environ.get("PORT", "8000"))

app = FastAPI(
    title="AgenticContract-AI",
    description="Autonomous multi-agent contract extraction with confidence-aware self-healing",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(contract.router)
app.include_router(analytics.router)


@app.get("/")
def root() -> dict:
    return {"service": "AgenticContract-AI", "docs": "/docs", "health": "/health"}

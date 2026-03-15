"""
NeMo Guardrails: run input through config/rails (injection, PII).
Returns passed/message/detections for observability. Falls back gracefully if NeMo unavailable.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_NEMO_AVAILABLE = False
_RailsConfig = None
_LLMRails = None

try:
    from nemoguardrails import LLMRails, RailsConfig
    _NEMO_AVAILABLE = True
except ImportError:
    pass


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "rails"


def run_nemo_validation(text: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """
    Run NeMo guardrails on input text. Returns:
      passed: bool – True if input allowed, False if blocked or NeMo failed
      message: str – Short status ("allowed", "blocked", "NeMo unavailable: ...")
      detections: list[str] – e.g. ["injection", "pii"] when blocked or empty
    Does not raise; on error returns passed=False, message with reason.
    """
    if not _NEMO_AVAILABLE:
        return {"passed": False, "message": "NeMo unavailable: package not installed", "detections": []}
    config_path = _config_path()
    if not config_path.is_dir():
        return {"passed": False, "message": "NeMo unavailable: config/rails not found", "detections": []}
    try:
        from app.core.config import settings
        config = RailsConfig.from_path(str(config_path))
        if not getattr(settings, "nemo_output_rails_enabled", False):
            config.rails.output.flows = []  # input-only: saves one LLM call
        rails = LLMRails(config)
    except Exception as e:
        logger.warning("NeMo config load failed: %s", e)
        return {"passed": False, "message": f"NeMo unavailable: {e}", "detections": []}

    detections: list[str] = []
    try:
        max_chars = getattr(settings, "max_nemo_chars", 6_000)
        content = text[:max_chars]
        response = rails.generate(messages=[{"role": "user", "content": content}])
        out = (response or {}).get("content", "") if isinstance(response, dict) else str(response)
        # If NeMo returns a block message, consider it blocked
        block_phrases = ["blocked", "security policy", "refused", "cannot comply"]
        out_lower = (out or "").lower()
        if any(p in out_lower for p in block_phrases):
            detections.append("injection_or_policy")
            return {"passed": False, "message": "Input blocked by guardrails", "detections": detections}
        return {"passed": True, "message": "allowed", "detections": []}
    except Exception as e:
        logger.warning("NeMo run failed (e.g. Ollama not running): %s", e)
        return {"passed": False, "message": f"NeMo error: {e}", "detections": ["error"]}

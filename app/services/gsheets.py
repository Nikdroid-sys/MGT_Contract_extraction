"""
Push AgentRunResult to Google Sheets via Web App URL (doPost). Non-blocking; logs on failure.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import settings
from app.core.schemas import AgentRunResult

logger = logging.getLogger(__name__)


def send_run_to_gsheets(result: AgentRunResult) -> bool:
    """
    POST result JSON to GSHEETS_WEBAPP_URL. Returns True if request succeeded (2xx), else False.
    Does not raise; logs errors for observability.
    """
    url = (settings.gsheets_webapp_url or "").strip()
    if not url:
        logger.debug("GSHEETS_WEBAPP_URL not set; skipping GSheets push.")
        return False
    payload: dict[str, Any] = result.model_dump_for_gsheets()
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            logger.info("GSheets push succeeded for trace_id=%s", result.trace_id)
            return True
        logger.warning("GSheets push failed trace_id=%s status=%s body=%s", result.trace_id, resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.exception("GSheets push error trace_id=%s: %s", result.trace_id, e)
        return False

"""
Analytics route: dashboard with runs from local storage (SQLite).
Returns trace_ids and summary so the client can call GET /contract/status/{trace_id}.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services.persistence import count_runs, list_runs

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(
    _user: CurrentUser,
    limit: Annotated[int, Query(description="Max runs to return")] = 50,
    offset: Annotated[int, Query(description="Skip first N runs")] = 0,
) -> dict:
    """
    Dashboard: list recent contract runs from **local storage (SQLite)**.

    Returns:
    - **total_runs**: total count in DB
    - **runs**: list of runs with `trace_id`, `status`, `created_at`, `confidence`, `document_id`, `stages_count`
    - **source**: `"local"` (SQLite)

    Use each **trace_id** to fetch full details: `GET /contract/status/{trace_id}`.
    """
    total = count_runs()
    runs = list_runs(limit=min(limit, 100), offset=max(0, offset))
    return {
        "source": "local",
        "total_runs": total,
        "runs": runs,
        "message": "Use trace_id with GET /contract/status/{trace_id} for full run details.",
    }

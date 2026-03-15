"""
SQLite persistence for AgentRunResult. Used for /contract/status and run history.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.core.schemas import AgentRunResult

logger = logging.getLogger(__name__)

# DB in project root so it's writable on Render
_DB_PATH: Path | None = None


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path(__file__).resolve().parent.parent.parent / "runs.db"
    return _DB_PATH


def _get_connection():
    import sqlite3
    path = _get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create runs table if it doesn't exist."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                trace_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_run(result: AgentRunResult) -> None:
    """Upsert one AgentRunResult by trace_id."""
    init_db()
    data = result.model_dump_for_gsheets()
    conn = _get_connection()
    try:
        updated = (result.updated_at or result.created_at).isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (trace_id, result_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                result.trace_id,
                json.dumps(data),
                result.status.value,
                result.created_at.isoformat(),
                updated,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.exception("Failed to save run %s: %s", result.trace_id, e)
        raise
    finally:
        conn.close()


def get_run(trace_id: str) -> AgentRunResult | None:
    """Load AgentRunResult by trace_id."""
    init_db()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT result_json FROM runs WHERE trace_id = ?", (trace_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["result_json"])
        # Restore datetime fields
        for key in ("created_at", "updated_at"):
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key].replace("Z", "+00:00"))
        for s in data.get("stages") or []:
            for t in ("started_at", "ended_at"):
                if s.get(t):
                    s[t] = datetime.fromisoformat(s[t].replace("Z", "+00:00"))
        return AgentRunResult.model_validate(data)
    except Exception as e:
        logger.exception("Failed to load run %s: %s", trace_id, e)
        return None
    finally:
        conn.close()


def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    List recent runs from local SQLite for dashboard. Returns lightweight rows with trace_id, status, created_at, etc.
    Use trace_id to call GET /contract/status/{trace_id}.
    """
    init_db()
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT trace_id, result_json, status, created_at, updated_at
            FROM runs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        out = []
        for row in rows:
            data = json.loads(row["result_json"])
            artifacts = data.get("artifacts") or {}
            out.append({
                "trace_id": row["trace_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "confidence": data.get("confidence"),
                "document_id": artifacts.get("document_id"),
                "stages_count": len(data.get("stages") or []),
            })
        return out
    except Exception as e:
        logger.exception("list_runs failed: %s", e)
        return []
    finally:
        conn.close()


def count_runs() -> int:
    """Total number of runs in local storage (for dashboard summary)."""
    init_db()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()
        return row["n"] if row else 0
    finally:
        conn.close()

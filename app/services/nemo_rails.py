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


def _collect_string_leaves(
    obj: Any,
    out: list[str],
    max_total_chars: int = 2000,
    _seen: set[int] | None = None,
) -> None:
    """
    Best-effort extraction of string content from an arbitrary response object.
    Used only to detect whether NeMo returned a block decision.
    """
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return
    _seen.add(oid)

    if sum(len(s) for s in out) >= max_total_chars:
        return

    if obj is None:
        return
    if isinstance(obj, str):
        s = obj.strip()
        # Avoid capturing role labels like "assistant" when the real content is nested elsewhere.
        if s and s.lower() not in {"assistant", "user", "system"}:
            out.append(s[:200])
        return
    if isinstance(obj, (bytes, bytearray)):
        try:
            s = obj.decode("utf-8", errors="replace")
        except Exception:
            return
        if s.strip():
            out.append(s[:200])
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_string_leaves(v, out, max_total_chars=max_total_chars, _seen=_seen)
        return
    if isinstance(obj, (list, tuple, set)):
        for v in obj:
            _collect_string_leaves(v, out, max_total_chars=max_total_chars, _seen=_seen)
        return


def _extract_generation_text(response: Any, max_total_chars: int = 2000) -> str:
    """
    NeMo's rails.generate() return type can vary. We attempt to pull out the assistant text
    or, as a fallback, concatenate all string leaf values for block-phrase detection.
    """
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, (bytes, bytearray)):
        try:
            return response.decode("utf-8", errors="replace")
        except Exception:
            return str(response)

    def _find_first_string_by_keys(obj: Any, keys_lower: set[str], _seen: set[int] | None = None) -> str | None:
        if _seen is None:
            _seen = set()
        oid = id(obj)
        if oid in _seen:
            return None
        _seen.add(oid)

        if obj is None:
            return None
        if isinstance(obj, str):
            s = obj.strip()
            if not s:
                return None
            if s.lower() in {"assistant", "user", "system"}:
                return None
            return s
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in keys_lower and isinstance(v, str):
                    sv = v.strip()
                    if sv and sv.lower() not in {"assistant", "user", "system"}:
                        return sv
            for v in obj.values():
                found = _find_first_string_by_keys(v, keys_lower, _seen=_seen)
                if found:
                    return found
            return None
        if isinstance(obj, (list, tuple, set)):
            for v in obj:
                found = _find_first_string_by_keys(v, keys_lower, _seen=_seen)
                if found:
                    return found
            return None
        return None

    keys_lower = {"content", "text", "output", "assistant_message", "message"}
    found = _find_first_string_by_keys(response, keys_lower)
    if found:
        return found[:max_total_chars]

    if isinstance(response, dict) or isinstance(response, (list, tuple, set)):
        bucket: list[str] = []
        _collect_string_leaves(response, bucket, max_total_chars=max_total_chars)
        return " ".join([s.strip() for s in bucket if s and s.strip()])[:max_total_chars]

    # Fallback for objects with common attributes
    for attr in ("content", "text", "output"):
        try:
            v = getattr(response, attr, None)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass

    return str(response)


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
        rails = LLMRails(config)
    except Exception as e:
        logger.warning("NeMo config load failed: %s", e)
        return {"passed": False, "message": f"NeMo unavailable: {e}", "detections": []}

    detections: list[str] = []
    try:
        max_chars = getattr(settings, "max_nemo_chars", 6_000)
        content = text[:max_chars]
        # Run full rails so that `flow main` return values propagate into the generation output.
        response = rails.generate(messages=[{"role": "user", "content": content}])
        if isinstance(response, dict):
            top_keys = list(response.keys())
            print(f"[nemo] response_type=dict top_keys={top_keys[:12]}", flush=True)
        else:
            print(f"[nemo] response_type={type(response).__name__}", flush=True)

        nemo_status = None
        nemo_rail = None
        nemo_content = ""
        if isinstance(response, dict):
            nemo_status = response.get("status")
            nemo_rail = response.get("rail")
            nemo_content = response.get("content") or ""
        else:
            nemo_status = getattr(response, "status", None)
            nemo_rail = getattr(response, "rail", None)
            nemo_content = getattr(response, "content", "") or ""

        # Some NeMo versions expose status/rail as attributes even if `response` is dict-like.
        if nemo_status is None:
            nemo_status = getattr(response, "status", None)
        if nemo_rail is None:
            nemo_rail = getattr(response, "rail", None)
        if not nemo_content:
            nemo_content = getattr(response, "content", "") or nemo_content

        nemo_status_str = (str(nemo_status) if nemo_status is not None else "").upper()
        nemo_rail_str = str(nemo_rail) if nemo_rail is not None else ""
        nemo_content_preview = (nemo_content or "").replace("\n", " ")[:120]
        print(
            f"[nemo] rails_status={nemo_status_str or 'UNKNOWN'} rail={nemo_rail_str or 'UNKNOWN'} content_preview='{nemo_content_preview}'",
            flush=True,
        )

        out = _extract_generation_text(response, max_total_chars=2000)
        out_lower = (out or "").lower()
        out_preview = (out or "").replace("\n", " ")[:120]
        print(f"[nemo] rails.generate out_preview='{out_preview}'", flush=True)

        # If NeMo explicitly BLOCKED, hard-stop the workflow (no extractor/auditor calls).
        if nemo_status_str == "BLOCKED":
            detections.append("injection_or_policy")
            msg = f"Input blocked by NeMo guardrails (rail={nemo_rail_str or 'unknown'})."
            return {"passed": False, "message": msg, "detections": detections}

        # Fallback: detect block phrasing in any assistant text we can extract.
        block_phrases = [
            "blocked",
            "request blocked",
            "security policy",
            "refused",
            "cannot comply",
            "can't respond",
            "i can't",
            "i'm sorry",
            "malicious",
            "prompt injection",
            "request_blocked",
        ]
        if any(p in out_lower for p in block_phrases):
            if "pii" in out_lower or "privacy" in out_lower:
                detections.append("pii")
            else:
                detections.append("injection_or_policy")
            msg = f"Input blocked by NeMo guardrails: {out_preview}".strip()
            return {"passed": False, "message": msg, "detections": detections}
        return {"passed": True, "message": "allowed", "detections": []}
    except Exception as e:
        logger.warning("NeMo run failed (provider/config issue): %s", e)
        return {"passed": False, "message": f"NeMo error: {e}", "detections": ["error"]}

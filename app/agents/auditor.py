"""
Auditor agent: single "Judge" LLM call for Faithfulness, Relevancy, and Schema.
One call instead of multiple DeepEval metrics; uses auxiliary model. No retries; optional pacing.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

os.environ.setdefault("DEEPEVAL_RETRY_MAX_ATTEMPTS", "1")

# Judge prompt: one LLM call for all criteria (saves 2–3 API calls)
JUDGE_SYSTEM = """You are an expert evaluator. Given the SOURCE CONTRACT TEXT and an EXTRACTED JSON, output exactly one JSON object with these keys only:
- "faithfulness_score": number 0-1 (how well the extraction is grounded in the source; 1=fully supported)
- "relevancy_score": number 0-1 (how relevant the extraction is to the contract; 1=fully relevant)
- "schema_ok": boolean (true if the extraction has document_id, fields array with name/value/confidence, overall_confidence)
- "reason": short string (one sentence explaining the main issue if any, or "OK")

Output ONLY valid JSON, no markdown or prose."""


def _get_judge_model_and_kwargs() -> tuple[str, dict[str, Any]]:
    from app.core.llm_config import (
        get_llm_api_key,
        get_llm_base_url_for_litellm,
        get_llm_eval_temperature,
        get_llm_model_string_auxiliary,
    )
    model = get_llm_model_string_auxiliary()
    api_key = get_llm_api_key()
    base_url = get_llm_base_url_for_litellm()
    kwargs: dict[str, Any] = {"temperature": get_llm_eval_temperature(), "max_tokens": 512}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url
    return model, kwargs


def _run_judge_sync(inp: str, actual_short: str, context: list[str]) -> dict[str, Any]:
    """Single Judge LLM call; no retries."""
    try:
        import litellm
        litellm.num_retries = 0
    except ImportError:
        pass
    evaluation: dict[str, Any] = {
        "faithfulness_score": None,
        "faithfulness_reason": "",
        "answer_relevancy_score": None,
        "answer_relevancy_reason": "",
    }
    model, extra = _get_judge_model_and_kwargs()
    user_content = f"SOURCE CONTRACT (excerpt):\n{context[0][:3000] if context else ''}\n\nEXTRACTED JSON:\n{actual_short[:3000]}"
    messages = [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user_content}]
    try:
        import litellm
        print(f"[tool] judge_llm model={model} max_tokens=512", flush=True)
        response = litellm.completion(model=model, messages=messages, **extra)
        choices = getattr(response, "choices", None) or []
        msg = choices[0].message if choices else None
        raw = (getattr(msg, "content", None) or "").strip() if msg else ""
    except Exception as e:
        logger.warning("Judge call failed: %s", e)
        evaluation["faithfulness_reason"] = f"Error: {e}"
        return evaluation
    raw = re.sub(r"^```\w*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end])
            except json.JSONDecodeError:
                evaluation["faithfulness_reason"] = "Judge returned invalid JSON"
                return evaluation
        else:
            evaluation["faithfulness_reason"] = "Judge returned no JSON"
            return evaluation
    f = float(data.get("faithfulness_score", 0)) if data.get("faithfulness_score") is not None else None
    r = float(data.get("relevancy_score", 0)) if data.get("relevancy_score") is not None else None
    reason = (data.get("reason") or "").strip() or "OK"
    evaluation["faithfulness_score"] = f
    evaluation["faithfulness_reason"] = reason
    evaluation["answer_relevancy_score"] = r
    evaluation["answer_relevancy_reason"] = reason
    if f is None and r is not None:
        evaluation["faithfulness_score"] = r
    elif r is None and f is not None:
        evaluation["answer_relevancy_score"] = f
    return evaluation


def run_audit(
    input_text: str,
    extraction_dict: dict[str, Any],
    threshold: float | None = None,
) -> tuple[float, str, dict[str, Any]]:
    """
    Single Judge call: Faithfulness + Relevancy + Schema in one response. Optional jittered delay.
    """
    evaluation: dict[str, Any] = {
        "faithfulness_score": None,
        "faithfulness_reason": "",
        "answer_relevancy_score": None,
        "answer_relevancy_reason": "",
    }

    delay_min = getattr(settings, "auditor_delay_min_seconds", 10.0)
    delay_max = getattr(settings, "auditor_delay_max_seconds", 14.0)
    if delay_min > 0 and delay_max > 0:
        delay = random.uniform(delay_min, delay_max)
        logger.info("Pacing API calls to respect Free Tier quotas (delay %.1fs)...", delay)
        print("Pacing API calls to respect Free Tier quotas...", flush=True)
        time.sleep(delay)

    max_chars = getattr(settings, "max_audit_chars", 4_000)
    actual_str = json.dumps(extraction_dict, default=str, indent=0)
    inp = input_text[:max_chars]
    actual_short = actual_str[:max_chars]
    context = [input_text[:max_chars]]

    timeout_sec = max(5.0, getattr(settings, "audit_timeout_seconds", 15.0))
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_judge_sync, inp, actual_short, context)
            evaluation = future.result(timeout=timeout_sec)
    except FuturesTimeoutError:
        logger.warning("Audit timed out after %s s", timeout_sec)
        return 0.0, f"Audit timed out after {timeout_sec}s.", evaluation
    except Exception as e:
        logger.warning("Audit failed: %s", e)
        return 0.0, f"Audit failed: {e}.", evaluation

    scores = []
    if evaluation.get("faithfulness_score") is not None:
        scores.append(float(evaluation["faithfulness_score"]))
    if evaluation.get("answer_relevancy_score") is not None:
        scores.append(float(evaluation["answer_relevancy_score"]))
    if not scores:
        return 0.0, "Audit failed: no scores from Judge.", evaluation
    primary = min(scores)
    rationale = (evaluation.get("faithfulness_reason") or evaluation.get("answer_relevancy_reason") or "N/A")
    return primary, rationale, evaluation

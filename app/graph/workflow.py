"""
LangGraph workflow: validate -> extractor -> auditor -> (retry or finalize) -> end.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.schemas import (
    AgentRunResult,
    RunStatusEnum,
    ScenarioEnum,
    StageRecord,
    StageStatusEnum,
)
from app.graph.state import GraphState
from app.services.validation import validate_contract_input
from app.services.nemo_rails import run_nemo_validation
from app.agents.extractor import run_extractor
from app.agents.auditor import run_audit
from app.services.persistence import save_run
from app.services.gsheets import send_run_to_gsheets

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_stage(state: GraphState, name: str, status: StageStatusEnum, started_at: datetime, ended_at: datetime | None = None, output_summary: str | None = None, err: str | None = None) -> dict:
    stages = list(state.get("stages") or [])
    stages.append({
        "name": name,
        "status": status.value,
        "started_at": started_at,
        "ended_at": ended_at or _now(),
        "output_summary": output_summary,
        "errors": [{"message": err}] if err else None,
    })
    return {"stages": stages}


def validate_node(state: GraphState) -> dict:
    """Lightweight validation first; then NeMo guardrails (injection/PII). Store nemo_* for observability."""
    started = _now()
    input_text = (state.get("input_text") or "").strip()
    ok, msg = validate_contract_input(input_text)
    if not ok:
        return {
            **_append_stage(state, "validation", StageStatusEnum.failed, started, err=msg),
            "status": RunStatusEnum.failed.value,
            "last_error": msg,
            "nemo_passed": False,
            "nemo_message": "Skipped (lightweight validation failed)",
            "nemo_detections": [],
        }
    # Run NeMo in a thread so sync rails.generate() is not inside async context (avoids "sync generate inside async" error)
    nemo_timeout = 10.0
    with ThreadPoolExecutor(max_workers=1) as _nemo_exec:
        nemo_future = _nemo_exec.submit(run_nemo_validation, input_text, nemo_timeout)
        nemo = nemo_future.result(timeout=nemo_timeout + 2)
    nemo_passed = nemo.get("passed", False)
    nemo_message = nemo.get("message", "")
    nemo_detections = nemo.get("detections") or []
    # If NeMo explicitly blocked (injection), fail the run
    if not nemo_passed and "blocked" in nemo_message.lower():
        return {
            **_append_stage(state, "validation", StageStatusEnum.failed, started, err=nemo_message),
            "status": RunStatusEnum.failed.value,
            "last_error": nemo_message,
            "nemo_passed": False,
            "nemo_message": nemo_message,
            "nemo_detections": nemo_detections,
        }
    # NeMo passed or unavailable (we still proceed)
    return {
        **_append_stage(
            state,
            "validation",
            StageStatusEnum.success,
            started,
            output_summary="Input accepted" + (" (NeMo: " + nemo_message + ")" if nemo_message else ""),
        ),
        "nemo_passed": nemo_passed,
        "nemo_message": nemo_message,
        "nemo_detections": nemo_detections,
    }


def extractor_node(state: GraphState) -> dict:
    """Run Groq extractor; on retry, pass auditor feedback to improve extraction."""
    started = _now()
    input_text = state.get("input_text") or ""
    trace_id = state.get("trace_id") or ""
    document_id = state.get("document_id") or trace_id
    last_error = (state.get("last_error") or "").strip()
    auditor_feedback = last_error if last_error else None
    try:
        extraction = run_extractor(input_text, document_id=document_id, auditor_feedback=auditor_feedback)
        art = extraction.model_dump(mode="json")
        return {
            **_append_stage(
                state,
                "extractor",
                StageStatusEnum.success,
                started,
                output_summary=f"Extracted {len(extraction.fields)} fields",
            ),
            "artifacts": art,
            "last_error": "",
        }
    except Exception as e:
        err_msg = str(e)
        logger.exception("Extractor failed: %s", e)
        return {
            **_append_stage(state, "extractor", StageStatusEnum.failed, started, err=err_msg),
            "status": RunStatusEnum.failed.value,
            "last_error": err_msg,
        }


def auditor_node(state: GraphState) -> dict:
    """Run DeepEval (Faithfulness + Answer Relevancy); set confidence and evaluation for observability."""
    started = _now()
    input_text = state.get("input_text") or ""
    artifacts = state.get("artifacts")
    if not artifacts:
        return {
            **_append_stage(state, "auditor", StageStatusEnum.failed, started, err="No artifacts to audit"),
            "status": RunStatusEnum.failed.value,
            "confidence": 0.0,
            "confidence_rationale": "No extraction to evaluate.",
            "evaluation": {},
        }
    try:
        score, reason, evaluation = run_audit(input_text, artifacts, threshold=settings.confidence_threshold)
        return {
            **_append_stage(
                state,
                "auditor",
                StageStatusEnum.success,
                started,
                output_summary=f"score={score:.2f}",
            ),
            "confidence": score,
            "confidence_rationale": reason or "Audit completed.",
            "evaluation": evaluation,
        }
    except Exception as e:
        logger.exception("Auditor failed: %s", e)
        return {
            **_append_stage(state, "auditor", StageStatusEnum.failed, started, err=str(e)),
            "status": RunStatusEnum.failed.value,
            "confidence": 0.0,
            "confidence_rationale": str(e),
            "evaluation": {},
        }


def _route_after_auditor(state: GraphState) -> Literal["retry_prep", "finalize"]:
    """If confidence >= threshold or retries exhausted -> finalize; else retry (via retry_prep)."""
    confidence = state.get("confidence") or 0.0
    retry_count = state.get("retry_count") or 0
    status = state.get("status")
    if status == RunStatusEnum.failed.value:
        return "finalize"
    if confidence >= settings.confidence_threshold:
        return "finalize"
    if retry_count >= settings.max_extraction_retries:
        return "finalize"
    return "retry_prep"


def retry_prep_node(state: GraphState) -> dict:
    """Increment retry_count and set last_error for extractor self-correction."""
    return {
        "retry_count": (state.get("retry_count") or 0) + 1,
        "last_error": state.get("confidence_rationale") or "Low confidence; retrying extraction.",
    }


def _route_after_validate(state: GraphState) -> Literal["extractor", "finalize"]:
    """If validation failed, go to finalize; else extractor."""
    if state.get("status") == RunStatusEnum.failed.value:
        return "finalize"
    return "extractor"


def finalize_node(state: GraphState) -> dict:
    """Build AgentRunResult, persist, send to GSheets; set final_result."""
    trace_id = state.get("trace_id") or ""
    scenario = ScenarioEnum.scenario_2_contract
    status = state.get("status")
    confidence = state.get("confidence")
    retry_count = state.get("retry_count") or 0
    stages_raw = state.get("stages") or []

    if status != RunStatusEnum.completed.value and status != RunStatusEnum.needs_review.value:
        if (confidence or 0) < settings.confidence_threshold and retry_count >= settings.max_extraction_retries:
            status = RunStatusEnum.failed.value
        elif (confidence or 0) < settings.confidence_threshold:
            status = RunStatusEnum.needs_review.value
        else:
            status = status or RunStatusEnum.completed.value
    else:
        status = status or (RunStatusEnum.completed.value if (confidence or 0) >= settings.confidence_threshold else RunStatusEnum.needs_review.value)

    created_at = _now()
    stages: list[StageRecord] = []
    for s in stages_raw:
        started = s.get("started_at")
        ended = s.get("ended_at")
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if not isinstance(started, datetime):
            started = _now()
        if isinstance(ended, str) and ended:
            ended = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        else:
            ended = None
        stages.append(StageRecord(
            name=s.get("name", ""),
            status=StageStatusEnum(s.get("status", "failed")),
            started_at=started,
            ended_at=ended,
            output_summary=s.get("output_summary"),
            errors=s.get("errors"),
        ))

    # Build decision with all metrics and NeMo for observability (GSheets)
    decision: dict[str, Any] = {
        "retry_count": retry_count,
        "threshold": settings.confidence_threshold,
        "faithfulness_score": None,
        "faithfulness_reason": "",
        "answer_relevancy_score": None,
        "answer_relevancy_reason": "",
        "nemo_passed": state.get("nemo_passed"),
        "nemo_message": state.get("nemo_message") or "",
        "nemo_detections": state.get("nemo_detections") or [],
        "last_error": state.get("last_error") or "",
    }
    ev = state.get("evaluation") or {}
    decision["faithfulness_score"] = ev.get("faithfulness_score")
    decision["faithfulness_reason"] = ev.get("faithfulness_reason") or ""
    decision["answer_relevancy_score"] = ev.get("answer_relevancy_score")
    decision["answer_relevancy_reason"] = ev.get("answer_relevancy_reason") or ""

    result = AgentRunResult(
        trace_id=trace_id,
        scenario=scenario,
        status=RunStatusEnum(status),
        created_at=created_at,
        updated_at=created_at,
        stages=stages,
        confidence=confidence,
        confidence_rationale=state.get("confidence_rationale"),
        decision=decision,
        artifacts=state.get("artifacts"),
    )
    try:
        save_run(result)
    except Exception as e:
        logger.exception("Failed to save run: %s", e)
    try:
        send_run_to_gsheets(result)
    except Exception as e:
        logger.exception("GSheets send failed: %s", e)
    return {"final_result": result, "status": status}


def build_graph() -> StateGraph:
    """Build and compile the graph."""
    graph = StateGraph(GraphState)
    graph.add_node("validate", validate_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("auditor", auditor_node)
    graph.add_node("retry_prep", retry_prep_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("validate")
    graph.add_conditional_edges("validate", _route_after_validate, {"extractor": "extractor", "finalize": "finalize"})
    graph.add_edge("extractor", "auditor")
    graph.add_conditional_edges("auditor", _route_after_auditor, {"retry_prep": "retry_prep", "finalize": "finalize"})
    graph.add_edge("retry_prep", "extractor")
    graph.add_edge("finalize", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Singleton compiled graph for reuse
_compiled: StateGraph | None = None


def get_graph() -> StateGraph:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def run_contract_workflow(
    input_text: str,
    trace_id: str | None = None,
    document_id: str | None = None,
) -> AgentRunResult:
    """
    Run the full workflow synchronously. Returns the final AgentRunResult.
    trace_id: unique run id (for status polling). document_id: optional id for the document; if not set, uses trace_id.
    """
    from uuid import uuid4
    tid = trace_id or str(uuid4())
    initial: GraphState = {
        "input_text": input_text,
        "trace_id": tid,
        "document_id": document_id if (document_id and document_id.strip()) else tid,
        "stages": [],
        "retry_count": 0,
    }
    graph = get_graph()
    config = {"configurable": {"thread_id": tid}}
    try:
        result = graph.invoke(initial, config=config)
    except Exception as e:
        logger.exception("Workflow invoke failed: %s", e)
        return AgentRunResult(
            trace_id=tid,
            scenario=ScenarioEnum.scenario_2_contract,
            status=RunStatusEnum.failed,
            created_at=_now(),
            stages=[StageRecord(name="workflow", status=StageStatusEnum.failed, started_at=_now(), ended_at=_now(), errors=[{"message": str(e)}])],
            confidence=0.0,
            confidence_rationale=str(e),
        )
    out = result.get("final_result")
    if out is not None:
        return out
    # Build minimal failed result when finalize didn't run (e.g. validation failed)
    return AgentRunResult(
        trace_id=tid,
        scenario=ScenarioEnum.scenario_2_contract,
        status=RunStatusEnum.failed,
        created_at=_now(),
        stages=[StageRecord(name="validation", status=StageStatusEnum.failed, started_at=_now(), ended_at=_now(), errors=[{"message": result.get("last_error", "Unknown error")}])],
        confidence=0.0,
        confidence_rationale=result.get("last_error", "Workflow did not complete."),
    )

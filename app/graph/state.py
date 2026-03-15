"""
LangGraph state: carries input, trace id, extraction, stages, and run result.
"""
from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """State passed between nodes. total=False so keys are optional for incremental updates."""
    input_text: str
    trace_id: str
    document_id: str
    artifacts: dict[str, Any]  # ContractKeyTermsExtraction as dict
    stages: list[dict[str, Any]]  # StageRecord-like dicts
    status: str  # completed | needs_review | failed
    confidence: float
    confidence_rationale: str
    retry_count: int
    last_error: str
    final_result: Any  # AgentRunResult when done
    # NeMo guardrails (validation node)
    nemo_passed: bool
    nemo_message: str
    nemo_detections: list[str]
    # DeepEval metrics (auditor node) – full detail for observability
    evaluation: dict[str, Any]  # faithfulness_score/reason, answer_relevancy_score/reason, etc.

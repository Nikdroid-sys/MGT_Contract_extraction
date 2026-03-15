"""
Output schemas aligned with schema/*.json.
ContractKeyTermsExtraction = extractor output (artifact).
AgentRunResult = full run trace (sent to GSheets, returned by API).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- ContractKeyTermsExtraction (scenario2_contract_extraction_schema.json) ---


class ExtractedField(BaseModel):
    """One extracted key term from the contract."""
    name: str
    value: Any  # string, number, boolean, or list per schema
    confidence: float = Field(ge=0, le=1)
    evidence: str | None = None


class ContractKeyTermsExtraction(BaseModel):
    """Output of the Extractor agent; stored in AgentRunResult.artifacts."""
    document_id: str
    fields: list[ExtractedField]
    overall_confidence: float | None = Field(None, ge=0, le=1)
    needs_review: bool | None = None
    review_reasons: list[str] | None = None


# --- AgentRunResult (agent_run_result_schema.json) ---


class ScenarioEnum(str, Enum):
    scenario_1_lead = "scenario_1_lead"
    scenario_2_contract = "scenario_2_contract"
    scenario_3_research = "scenario_3_research"


class RunStatusEnum(str, Enum):
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"


class StageStatusEnum(str, Enum):
    success = "success"
    skipped = "skipped"
    retrying = "retrying"
    failed = "failed"


class StageRecord(BaseModel):
    """One stage in the pipeline (validation, extractor, auditor, etc.)."""
    name: str
    status: StageStatusEnum
    started_at: datetime
    ended_at: datetime | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    errors: list[dict[str, Any]] | None = None


class AgentRunResult(BaseModel):
    """Full run trace: correlation id, status, stages, artifacts. Sent to GSheets."""
    trace_id: str
    scenario: ScenarioEnum = ScenarioEnum.scenario_2_contract
    status: RunStatusEnum
    created_at: datetime
    stages: list[StageRecord]
    updated_at: datetime | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    confidence_rationale: str | None = None
    decision: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None  # ContractKeyTermsExtraction as dict

    def model_dump_for_gsheets(self) -> dict[str, Any]:
        """JSON-serializable dict for GSheets (datetime as ISO string)."""
        return self.model_dump(mode="json")

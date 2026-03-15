# Workflow Walkthrough — Stage-by-Stage (Including Branching)

## Overview

The pipeline is a **LangGraph** state machine with five nodes and conditional edges. State (e.g. `input_text`, `artifacts`, `confidence`, `retry_count`) is carried across nodes; branching depends on validation result, confidence score, and retry limit.

---

## Stage 1: Validate

**Node:** `validate_node`

**Input (from state):** `input_text`

**Steps:**
1. **Lightweight validation** — Check non-empty, min length (~50 chars). If fail → set `status: failed`, append failed stage, **branch to Finalize**.
2. **NeMo Guardrails** — Run input through NeMo (injection/PII). If NeMo **blocks** → set `status: failed`, **branch to Finalize**. If NeMo passes or errors (e.g. unavailable) → continue; store `nemo_passed`, `nemo_message`, `nemo_detections` in state.

**Output (to state):** `stages` (validation stage), `nemo_passed`, `nemo_message`, `nemo_detections`; optionally `status: failed`, `last_error`.

**Branching:**
- If `status == failed` → **Finalize**
- Else → **Extractor**

---

## Stage 2: Extractor

**Node:** `extractor_node`

**Input (from state):** `input_text`, `document_id`, `last_error` (auditor feedback on retries)

**Steps:**
1. Call **Extractor agent** (LLM) with contract text and optional `auditor_feedback`. LLM returns JSON (document_id, fields, overall_confidence, needs_review, review_reasons).
2. Parse/normalize JSON; validate to `ContractKeyTermsExtraction`.
3. On **success** → append extractor stage, set `artifacts`, clear `last_error`.
4. On **exception** → append failed stage, set `status: failed`, `last_error`, **downstream will go to Finalize**.

**Output (to state):** `stages`, `artifacts` (and optionally `status: failed`, `last_error`).

**Branching:** No conditional here; graph always goes **Extractor → Auditor**.

---

## Stage 3: Auditor

**Node:** `auditor_node`

**Input (from state):** `input_text`, `artifacts`

**Steps:**
1. If no `artifacts` → fail stage, set `confidence: 0`, **branch to Finalize**.
2. Optional **jittered delay** (e.g. 10–14 s) for rate limiting.
3. Call **Judge** (single LLM call): compare source contract vs extracted JSON → `faithfulness_score`, `relevancy_score`, `reason`.
4. Set `confidence` = min of the scores; set `confidence_rationale`, `evaluation`.

**Output (to state):** `stages`, `confidence`, `confidence_rationale`, `evaluation`; on error, `status: failed`.

**Branching (route_after_auditor):**
- If `status == failed` → **Finalize**
- If `confidence >= threshold` (e.g. 0.8) → **Finalize** (success path)
- If `retry_count >= max_extraction_retries` (e.g. 2) → **Finalize** (exhausted retries; may be `needs_review`)
- Else → **Retry prep** (low-confidence path)

---

## Stage 4: Retry prep (low-confidence path only)

**Node:** `retry_prep_node`

**Input (from state):** `retry_count`, `confidence_rationale`

**Steps:**
1. Increment `retry_count`.
2. Set `last_error` = `confidence_rationale` (e.g. "Faithfulness: ...; AnswerRelevancy: ...") so the Extractor can use it as **auditor feedback** on the next run.

**Output (to state):** `retry_count`, `last_error`.

**Branching:** Graph always goes **Retry prep → Extractor** (loop back). The next Extractor run receives `auditor_feedback` and can improve the extraction.

---

## Stage 5: Finalize

**Node:** `finalize_node`

**Input (from state):** All state (trace_id, status, stages, confidence, artifacts, decision, nemo_*, evaluation, etc.)

**Steps:**
1. Build **AgentRunResult** (trace_id, scenario, status, stages, confidence, decision, artifacts).
2. **Persist** to SQLite (`save_run`).
3. Optionally **POST** to GSheets if `GSHEETS_WEBAPP_URL` is set.
4. Set state `final_result` = that AgentRunResult.

**Output:** No further branching; workflow ends. API returns `final_result` to the client.

---

## Branching paths summary

| Path | Condition | Result |
|------|-----------|--------|
| **Validation fail** | Input invalid or NeMo blocks | → Finalize with `status: failed` |
| **Extractor fail** | LLM/parse error | → Auditor still runs (no artifacts) or downstream handles; then Finalize with `status: failed` |
| **High confidence** | `confidence >= threshold` | → Finalize with `status: completed` (or `needs_review` if needs_review flag) |
| **Low confidence, retries left** | `confidence < threshold` and `retry_count < max` | → Retry prep → Extractor (with feedback) → Auditor again |
| **Low confidence, no retries left** | `confidence < threshold` and `retry_count >= max` | → Finalize with `status: needs_review` (or failed) |

---

## Flow diagram (simplified)

```
     [Start]
        │
        ▼
   ┌─────────┐
   │ Validate│
   └────┬────┘
        │ fail ──────────────────────────────────────────┐
        │ pass                                            │
        ▼                                                 │
   ┌──────────┐                                           │
   │ Extractor│── fail ──────────────────────────────────┤
   └────┬─────┘                                           │
        │                                                 │
        ▼                                                 │
   ┌─────────┐                                            │
   │ Auditor │── no artifacts / error ───────────────────┤
   └────┬────┘                                            │
        │                                                 │
        ├─ confidence >= threshold ──────────────────────┤
        │                                                 │
        ├─ confidence < threshold && retries left         │
        │         │                                       │
        │         ▼                                       │
        │   ┌────────────┐                                │
        │   │ Retry prep │──► back to Extractor (loop)    │
        │   └────────────┘                                │
        │                                                 │
        └─ confidence < threshold && no retries left ────┤
                                                          │
                                                          ▼
                                                    ┌───────────┐
                                                    │ Finalize  │
                                                    └───────────┘
                                                          │
                                                          ▼
                                                      [End]
```

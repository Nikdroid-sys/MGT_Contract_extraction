# How This Demonstrates Agent-Like Behavior

This short write-up explains how the **AgenticContract-AI** system exhibits agent-like behavior along four dimensions: **decisioning**, **tools**, **memory**, and **uncertainty handling**.

---

## 1. Decisioning

The system does not simply run a fixed pipeline and return the first result. It **decides** what to do next based on runtime outcomes:

- **After validation:** Decide whether to proceed to extraction or stop and finalize (e.g. invalid input or NeMo block).
- **After the auditor:** Decide whether the extraction is good enough:
  - If **confidence ≥ threshold** → treat as done and finalize (persist, optional GSheets).
  - If **confidence < threshold** and **retries remain** → send the run through **retry_prep** and back to the **extractor** with feedback (self-healing loop).
  - If **confidence < threshold** and **retries exhausted** → finalize with a **needs_review** (or failed) outcome so a human can intervene.

So the **orchestrator (LangGraph)** acts as a decision layer: it interprets confidence and retry state and chooses the next node (finalize vs retry), rather than always taking a single path.

---

## 2. Tools

Agents use tools to accomplish tasks. Here, the “tools” are the **capabilities** invoked by the graph:

- **Validation + NeMo:** Tool for input safety (injection/PII). Output: allow or block.
- **Extractor LLM:** Tool that takes raw contract text and returns **structured JSON** (key terms, confidence, evidence). It is given a clear schema and optional **auditor feedback** on retries.
- **Auditor Judge LLM:** Tool that compares source text vs extracted JSON and returns **scores and a reason** (faithfulness, relevancy). That output drives the decision to retry or finalize.
- **Persistence / GSheets:** Tools for storing the final result (SQLite) and (optionally) logging to a sheet.

The graph **orchestrates** these tools: it calls them in sequence, passes state between them, and uses their outputs to make the branching decisions above.

---

## 3. Memory

The workflow is **stateful** across steps:

- **LangGraph state** carries: `input_text`, `trace_id`, `document_id`, `stages`, `artifacts`, `confidence`, `confidence_rationale`, `retry_count`, `last_error`, `nemo_*`, `evaluation`, etc.
- **Retry loop:** On a low-confidence outcome, **retry_prep** sets `last_error` to the auditor’s rationale. The **extractor** is called again with this as **auditor_feedback** in the prompt. So the system “remembers” why the previous attempt was deemed weak and asks the LLM to improve. That feedback is the **memory** passed from the auditor back into the extractor.
- **Checkpointing:** LangGraph uses a checkpointer (e.g. in-memory) so state is retained per run (e.g. by `thread_id`/`trace_id`). Runs can be resumed or inspected (e.g. via status/dashboard).

So the agent has **short-term memory** (state + feedback) within a run and **persistent memory** of runs (SQLite, optional GSheets).

---

## 4. Uncertainty Handling

The system explicitly models **uncertainty** and acts on it:

- **Confidence scores:** The extractor outputs per-field and overall confidence; the auditor outputs faithfulness and relevancy scores. The **primary confidence** used for routing is derived from the auditor (e.g. minimum of the two scores).
- **Threshold:** A configurable **confidence threshold** (e.g. 0.8) defines “good enough.” Below that, the outcome is treated as uncertain.
- **Retries with feedback:** Instead of blindly retrying, the system **injects the auditor’s reason** into the next extraction. So the next call is conditioned on *why* the previous one was uncertain (e.g. “parties not clearly stated”), which is classic **uncertainty-driven self-correction**.
- **Explicit outcomes:** The final status can be **completed**, **needs_review**, or **failed**. Low confidence with no retries left is surfaced as **needs_review**, so humans can handle uncertain cases rather than the system pretending high certainty.

Together, this shows **agent-like behavior**: the system uses **decisioning** (branching on confidence and retries), **tools** (validation, LLMs, persistence), **memory** (state and auditor feedback), and **uncertainty handling** (scores, threshold, retries, and needs_review) to automate contract extraction while knowing when to stop and ask for human review.

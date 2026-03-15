
# 🛡️ AgenticContract-AI: Enterprise Document Automation

### *Autonomous Multi-Agent Workflow with Confidence-Aware Self-Healing*

---

## 📖 Overview

This project implements **Scenario 2 — Document Automation Agent (Orchestrated)** from the MGT Technical Assessment.

- **Business context:** Given a contract (PDF/text), extract key terms and update a system of record (mock: SQLite + optional Google Sheets).
- **Objective:** An agent that extracts structured details from contracts and updates an internal system, with an **uncertainty loop** (confidence check → complete or needs_review).
- **Workflow:** Document input → Text extraction → LLM structured extraction → Confidence check → Route outcome (complete / needs_review / retry with feedback) → Persist state + log.

Rather than a simple linear pipeline, this solution uses a **Stateful Multi-Agent Graph** with content safety guardrails and a **self-healing loop** (default: up to 2 retries when confidence is below threshold).

---

## 🏗️ Architecture & Implementation Guide

The system follows a clean, modular architecture optimized for high-intelligence performance within the memory constraints of Render's free tier (~512MB RAM).

### **The 4-Stage Workflow**

1. **Stage 1: Validation & Safety (NeMo):** Verifies the input and checks for prompt injection/PII. Uses **GROQ_API_KEY** via `config/rails` (input capped to `MAX_NEMO_CHARS` to save tokens).
2. **Stage 2: Extraction Agent (LiteLLM):** Provider-agnostic LLM (default **Gemini 2.5 Flash**) parses text into `ContractKeyTermsExtraction`. On retry, auditor feedback is injected. Input capped to `MAX_CONTRACT_CHARS`.
3. **Stage 3: Auditor Agent (DeepEval):** Faithfulness + Answer Relevancy using the same provider/model as extractor; input capped to `MAX_AUDIT_CHARS`.
4. **Stage 4: Branching & Persistence:** **High Confidence (≥ threshold):** Routes to "Complete," persists to SQLite, and logs to Google Sheets. **Low Confidence:** Routes back to the extractor with feedback for a retry (default: up to **2** retries, `MAX_EXTRACTION_RETRIES`).

**Scenario 2 workflow mapping:** Document input (POST text/PDF) → Text extraction (PDF parser or raw) → LLM structured extraction (extractor → `ContractKeyTermsExtraction`) → Confidence check (auditor: Faithfulness + Answer Relevancy) → Route outcome (complete / needs_review / failed) → Persist state (SQLite) + log (GSheets).



---

## ☁️ Azure Equivalent Stack (For MGT Requirements)

While this version is built for zero-cost deployment on Render, it is architected to be 1:1 swappable with the **Azure AI Foundry** ecosystem:

| Open-Source Stack (This Project) | Azure Enterprise Equivalent |
| --- | --- |
| **Groq (Llama 3 70B)** | **Azure OpenAI (GPT-4o)** |
| **LangGraph** | **Azure AI Agent Service / Semantic Kernel** |
| **NeMo Guardrails** | **Azure AI Content Safety** |
| **DeepEval** | **Azure AI Foundry Evaluation SDK** |
| **SQLite (Local State)** | **Azure Cosmos DB (Stateful Thread Store)** |
| **Google Sheets (Observability)** | **Azure Monitor / Application Insights** |

---

## 🛠️ Project Structure

Professional, 2026 AI-ready layout: clear separation of API, agents, graph, services, config, and tests.

```text
MGT_assessment/
│
├── app/                          # Application package
│   ├── api/                      # FastAPI layer: Auth (JWT) & Contract endpoints
│   │   └── routes/               # Route modules: auth, contract, analytics
│   ├── agents/                   # LLM logic: Supervisor, Extractor, Auditor
│   ├── core/                     # Shared core: config, security (deps), schemas
│   ├── graph/                    # LangGraph: state definitions & workflow edges
│   ├── services/                 # Integrations: GSheets logger, NeMo rails, persistence
│   └── tools/                    # Utilities: PDF parser and other tools
│
├── config/                       # External configuration (env-agnostic)
│   └── rails/                    # NeMo Guardrails: .yml and .co files
│
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests (agents, services, tools)
│   └── integration/              # Integration tests (API, graph, E2E)
│
├── scripts/                      # Dev & deploy scripts (e.g. seed, migrate)
├── docs/                         # Additional documentation & API specs
│
├── main.py                       # Entry point (uvicorn app)
├── pyproject.toml                # UV project metadata & dependencies
├── helper.txt                    # Implementation notes & sprint plan
└── README.md                     # This guide
```

| Path | Purpose |
|------|--------|
| `app/api/` + `routes/` | `/auth/login`, `/contract/process`, `/contract/status/{trace_id}`, `/analytics/dashboard` |
| `app/agents/` | Supervisor, Extractor (Groq → `ContractKeyTermsExtraction`), Auditor (DeepEval) |
| `app/core/` | JWT deps, Pydantic schemas (`AgentRunResult`, `ContractKeyTermsExtraction`), app config |
| `app/graph/` | LangGraph state, nodes, and self-healing branch logic |
| `app/services/` | GSheets bridge, NeMo guardrails wrapper, SQLite persistence |
| `app/tools/` | PDF/text parsing for contract input |
| `config/rails/` | NeMo top-level guardrail (e.g. “is this a legal document?”) |
| `tests/` | Unit + integration coverage for agents, API, and graph |
| `scripts/` | One-off or CI scripts (e.g. Render env check) |
| `docs/` | Extra design docs or OpenAPI exports |

---

## 📊 Bonus Features Included

* **Monitoring/Tracing:** Live execution logs mirrored to a **Google Sheets Dashboard** via a custom Serverless Apps Script bridge (see `docs/GSHEETS_OBSERVABILITY_SETUP.md`).
* **Guardrails:** Real-time schema enforcement and refusal handling via **NeMo** (see below).
* **Evaluation Hooks:** Integrated **DeepEval** metrics within the graph to drive retry logic and observability (see below).
* **Dead-Letter Handling:** Automated "Failed" status if the agent cannot reach high confidence after max retries.
* **Self-healing with feedback:** On low confidence, the auditor’s rationale is passed back into the extractor prompt so the next attempt is improved (faithfulness/relevancy).

---

## 🛡️ NeMo Guardrails (Validation Node)

NeMo runs in the **validation** node and uses **GROQ_API_KEY** (OpenAI-compatible endpoint: `https://api.groq.com/openai/v1`). No Ollama or separate API key is required.

| Item | Details |
|------|--------|
| **Config** | `config/rails/config.yml` (engine: openai, model: llama-3.3-70b-versatile, `api_key_env_var: GROQ_API_KEY`) |
| **Flows** | `config/rails/flows/inputrails.co`: main flow activates **input security** (injection detection) and **privacy masking** (PII). |
| **Behaviour** | If NeMo detects prompt injection it **blocks** the run and records `nemo_passed: false`, `nemo_detections` in the result (and GSheets). If NeMo is unavailable (e.g. config error), the pipeline still runs with lightweight validation and records NeMo status for observability. |
| **Observability** | `nemo_passed`, `nemo_message`, `nemo_detections` are stored in `decision` and sent to the Google Sheet. |

---

## 📐 DeepEval Metrics (Auditor Node)

The **auditor** runs two DeepEval metrics and uses **GROQ_API_KEY** via LiteLLM (same key as NeMo and the extractor for a single-key demo).

| Metric | Purpose | Stored in |
|--------|--------|-----------|
| **FaithfulnessMetric** | Whether the extraction is factually grounded in the contract text (retrieval context). | `decision.faithfulness_score`, `decision.faithfulness_reason` |
| **AnswerRelevancyMetric** | Whether the extraction is relevant to the input (contract). | `decision.answer_relevancy_score`, `decision.answer_relevancy_reason` |

**Routing:** Primary confidence = minimum of the two scores. If either metric fails to run, the other is used. All scores and reasons are written to the observability sheet.

---

## 🚀 Run & Deployment Instructions

### **Provider-agnostic LLM (Gemini / Groq / Azure OpenAI)**

Set **one** of: **GEMINI_API_KEY**, **GROQ_API_KEY**, or **AZURE_OPENAI_API_KEY** (and **LLM_PROVIDER** + **LLM_MODEL**). Set **GSHEETS_WEBAPP_URL** for observability (see `docs/GSHEETS_OBSERVABILITY_SETUP.md`).

| Env var | Default | Purpose |
|--------|---------|--------|
| `LLM_PROVIDER` | `gemini` | `gemini`, `groq`, or `azure_openai` |
| `LLM_MODEL` | `gemini-2.5-flash` | Model id (e.g. `gemini-2.5-flash`, `llama-3.3-70b-versatile`) |
| `GEMINI_API_KEY` | — | Required when `LLM_PROVIDER=gemini` |
| `GROQ_API_KEY` | — | Required when `LLM_PROVIDER=groq`; also used by NeMo |
| `AZURE_OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=azure_openai` |
| `AZURE_OPENAI_BASE_URL` | — | Azure OpenAI endpoint when using Azure |
| `MAX_CONTRACT_CHARS` | `12000` | Cap contract text for extractor (fewer tokens) |
| `MAX_AUDIT_CHARS` | `4000` | Cap input/context for DeepEval |
| `MAX_NEMO_CHARS` | `6000` | Cap input for NeMo guardrails |
| `MAX_EXTRACTION_RETRIES` | `2` | Self-healing retry limit |
| `CONFIDENCE_THRESHOLD` | `0.8` | Min score to accept extraction |

**Switching providers:** Change `LLM_PROVIDER` and set the corresponding API key. No code changes. NeMo still uses Groq from `config/rails/config.yml` unless you edit that file.

### **Local Setup (using `uv`)**

1. **Sync Environment:** `uv sync`
2. **Configure `.env`:** Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...` (or Groq/Azure); optionally `GSHEETS_WEBAPP_URL`, `JWT_SECRET`, `AUTH_DEMO_*`.
3. **Run:** `uv run uvicorn main:app --reload --port 8080` (use `--port 8080` if 8000 is in use on Windows).

### **Render Deployment**

1. Connect your GitHub repo.
2. **Environment:** Set `LLM_PROVIDER`, `LLM_MODEL`, and the matching API key (e.g. `GEMINI_API_KEY`); optionally `GSHEETS_WEBAPP_URL`, `JWT_SECRET`, `AUTH_DEMO_*`.
3. **Build Command:** `uv sync --frozen --no-dev`
4. **Start Command:** `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Render will automatically detect `uv.lock` and optimize the build.

---

## ✅ How to run and check outputs

1. **Start the app** (see Local Setup above).
2. **Get a JWT:** `POST /auth/login` with body `{"username":"admin","password":"admin"}` (or your `.env` credentials). Copy `access_token`.
3. **Process a contract:** `POST /contract/process` with header `Authorization: Bearer <access_token>` and body `{"text": "Your contract text here (at least 50 characters)..."}`. You can also send a file (PDF) via multipart.
4. **Response:** You get an **AgentRunResult** JSON: `trace_id`, `status`, `confidence`, `stages`, `decision` (with faithfulness/answer_relevancy scores and NeMo fields), and `artifacts` (extraction).
5. **Status:** `GET /contract/status/{trace_id}` with the same Bearer token to fetch the same result from SQLite.
6. **Observability:** If `GSHEETS_WEBAPP_URL` is set, each run is POSTed to your Google Sheet; open the sheet to see all metrics and NeMo detections.

---

## 📝 "Why this is Agentic" (The Short Write-up)

* **Decisioning:** The Supervisor agent doesn't just run code; it evaluates the *quality* of the Auditor's feedback to decide if a retry is necessary.
* **Memory:** LangGraph manages a cross-step state (Thread ID), allowing the Auditor to "remember" previous extraction failures to improve the next attempt.
* **Uncertainty:** The flow is not deterministic. The path changes dynamically based on the calculated `confidence` score of the extraction.

---


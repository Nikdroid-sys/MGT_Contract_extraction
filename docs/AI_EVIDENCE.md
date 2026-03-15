# Evidence of AI Usage: Prompts/Templates and Example LLM Output

## 1. Extractor (structured extraction)

**Location:** `app/agents/extractor.py` — `EXTRACTOR_SYSTEM` and user message.

**System prompt (template):**
```
You are a legal expert. Extract key terms from the contract below.
Step 1: Extract. Step 2: Double-check your JSON against the source text for faithfulness and completeness before giving the final output.
Output ONLY valid JSON (no markdown):
{"document_id":"<string>","fields":[{"name":"<term>","value":"<value>","confidence":<0-1>,"evidence":"<short excerpt or empty>"}],"overall_confidence":<0-1>,"needs_review":<bool>,"review_reasons":["<reason if any>"]}
Extract at least: parties, effective date, term/duration, termination, liability, governing law, payment terms if present.
Use the given document_id. confidence 0-1. value may be string, number, boolean, or array of strings. For missing or inapplicable terms use empty string "" or "Not specified" for value; do not use null. Use "" for evidence when none.
```

**User message (conceptual):**
```
document_id: software_subscription_agreement_1

Contract text:
This Software Subscription Agreement ("Agreement") is made effective on 2025-11-01 between Fabrikam HR Solutions Ltd. ("Vendor") and BlueYonder Logistics, Inc. ("Customer"). The subscription term is twenty-four (24) months...
```

**Example LLM structured output (extractor):**
```json
{
  "document_id": "software_subscription_agreement_1",
  "fields": [
    { "name": "parties", "value": ["Fabrikam HR Solutions Ltd.", "BlueYonder Logistics, Inc."], "confidence": 1, "evidence": "Fabrikam HR Solutions Ltd. (\"Vendor\") and BlueYonder Logistics, Inc. (\"Customer\")" },
    { "name": "effective date", "value": "2025-11-01", "confidence": 1, "evidence": "made effective on 2025-11-01" },
    { "name": "term/duration", "value": "twenty-four (24) months, with automatic renewal for additional one (1) year terms", "confidence": 1, "evidence": "subscription term is twenty-four (24) months...renew automatically for an additional one (1) year term" },
    { "name": "termination", "value": ["Either party may terminate for material breach if not cured within thirty (30) days after written notice.", "Either party may provide written notice of non-renewal at least sixty (60) days prior to the end of the then-current term."], "confidence": 1, "evidence": "Either party may terminate for material breach...thirty (30) days...written notice of non-renewal at least sixty (60) days prior" },
    { "name": "liability", "value": "", "confidence": 0, "evidence": "" },
    { "name": "governing law", "value": "laws of the State of New York", "confidence": 1, "evidence": "This Agreement is governed by the laws of the State of New York." },
    { "name": "payment terms", "value": { "amount": "$4,500 per month", "frequency": "monthly", "invoicing_schedule": "monthly in advance", "due_date": "within fifteen (15) days of the invoice date" }, "confidence": 1, "evidence": "Customer will pay $4,500 per month. Vendor will invoice monthly in advance. Payment is due within fifteen (15) days of the invoice date." }
  ],
  "overall_confidence": 1,
  "needs_review": false,
  "review_reasons": []
}
```

---

## 2. Auditor Judge (single-call evaluation)

**Location:** `app/agents/auditor.py` — `JUDGE_SYSTEM` and user message.

**System prompt (template):**
```
You are an expert evaluator. Given the SOURCE CONTRACT TEXT and an EXTRACTED JSON, output exactly one JSON object with these keys only:
- "faithfulness_score": number 0-1 (how well the extraction is grounded in the source; 1=fully supported)
- "relevancy_score": number 0-1 (how relevant the extraction is to the contract; 1=fully relevant)
- "schema_ok": boolean (true if the extraction has document_id, fields array with name/value/confidence, overall_confidence)
- "reason": short string (one sentence explaining the main issue if any, or "OK")

Output ONLY valid JSON, no markdown or prose.
```

**User message (conceptual):**
```
SOURCE CONTRACT (excerpt):
This Software Subscription Agreement is made effective on 2025-11-01 between Fabrikam HR Solutions Ltd....

EXTRACTED JSON:
{"document_id":"software_subscription_agreement_1","fields":[{"name":"parties","value":["Fabrikam HR Solutions Ltd.","BlueYonder Logistics, Inc."],...}],"overall_confidence":1,"needs_review":false,"review_reasons":[]}
```

**Example LLM structured output (Judge):**
```json
{
  "faithfulness_score": 1,
  "relevancy_score": 1,
  "schema_ok": true,
  "reason": "OK"
}
```

**Example (low-confidence run):**
```json
{
  "faithfulness_score": 0.5,
  "relevancy_score": 0.4,
  "schema_ok": true,
  "reason": "Extraction lacks support for parties and effective date; source is too short."
}
```

---

## 3. NeMo Guardrails (input)

NeMo uses config-driven prompts (see `config/rails/`). Input is run through injection detection and optional PII masking; the LLM is invoked internally by NeMo, not by our custom prompts above. Our **custom AI usage** is the **Extractor** and **Auditor Judge** prompts and their structured JSON outputs as shown.

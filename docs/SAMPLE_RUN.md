# Sample Inputs and Outputs

Below are two representative runs: one **high-confidence (completed)** and one **low-confidence (needs_review / retry path)**.

---

## Run 1: High-confidence (completed)

**Input:** Contract text (excerpt) — software subscription agreement with clear terms.

**Request:**
curl -X 'POST' \
  'http://localhost:8080/contract/process' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3MzU3ODQ0MiwiaWF0IjoxNzczNTc0ODQyfQ.t0xMBDcbXmO9fT8f9ruOPiqxLL8obv02gGyFodetCQY' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text=string' \
  -F 'document_id=contract_01' \
  -F 'file=@contract_01_master_services_agreement.pdf;type=application/pdf'
```


**Output (simplified):**
```json
{
  "trace_id": "a30dc971-cbb3-489c-86c7-f4535bb91c99",
  "scenario": "scenario_2_contract",
  "status": "completed",
  "created_at": "2026-03-15T12:13:55.489085Z",
  "stages": [
    {
      "name": "validation",
      "status": "success",
      "started_at": "2026-03-15T12:13:26.058924Z",
      "ended_at": null,
      "input_summary": "file: contract_01_master_services_agreement.pdf",
      "output_summary": "Input accepted (NeMo: allowed)",
      "tool_calls": [
        {
          "tool": "pdf_parser",
          "input": "contract_01_master_services_agreement.pdf",
          "description": "Extract text from PDF/txt upload"
        }
      ],
      "errors": null
    },
    {
      "name": "extractor",
      "status": "success",
      "started_at": "2026-03-15T12:13:29.142275Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "Extracted 7 fields",
      "tool_calls": [
        {
          "tool": "extractor_llm",
          "description": "Extract key terms from contract via LLM",
          "document_id": "contract_01"
        }
      ],
      "errors": null
    },
    {
      "name": "auditor",
      "status": "success",
      "started_at": "2026-03-15T12:13:35.585704Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "score=1.00",
      "tool_calls": [
        {
          "tool": "deepeval_audit",
          "description": "Faithfulness + Answer Relevancy evaluation",
          "threshold": 0.8
        }
      ],
      "errors": null
    }
  ],
  "updated_at": "2026-03-15T12:13:55.489085Z",
  "confidence": 1,
  "confidence_rationale": "OK",
  "decision": {
    "retry_count": 0,
    "threshold": 0.8,
    "faithfulness_score": 1,
    "faithfulness_reason": "OK",
    "answer_relevancy_score": 1,
    "answer_relevancy_reason": "OK",
    "nemo_passed": true,
    "nemo_message": "allowed",
    "nemo_detections": [],
    "last_error": ""
  },
  "artifacts": {
    "document_id": "contract_01",
    "fields": [
      {
        "name": "parties",
        "value": [
          "Northwind Analytics LLC",
          "Contoso Retail Inc."
        ],
        "confidence": 1,
        "evidence": "(1) Northwind Analytics LLC, a Delaware limited liability company... (2) Contoso Retail Inc., a Washington corporation..."
      },
      {
        "name": "effective date",
        "value": "2026-02-15",
        "confidence": 1,
        "evidence": "as of 2026-02-15 (“Effective Date”)"
      },
      {
        "name": "term/duration",
        "value": "Initial term of twelve (12) months, automatically renewing for successive one (1) year terms unless 30 days' written notice of non-renewal is given.",
        "confidence": 1,
        "evidence": "The initial term of this Agreement begins on the Effective Date and continues for twelve (12) months (“Initial Term”). After the Initial Term, this Agreement will automatically renew for successive one (1) year terms unless either party gives written notice of non-renewal at least thirty (30) days prior to the end of the then-current term."
      },
      {
        "name": "termination",
        "value": "Either party may terminate for material breach with 15 days' cure period. Client may terminate any SOW for convenience with 30 days' written notice, paying for work performed.",
        "confidence": 1,
        "evidence": "Either party may terminate this Agreement for material breach if the breaching party does not cure within fifteen (15) days after written notice. Client may terminate any SOW for convenience with thirty (30) days’ written notice; in such case Client will pay for work performed through the termination effective date."
      },
      {
        "name": "liability",
        "value": "Except for breach of confidentiality or willful misconduct, each party’s aggregate liability will not exceed fees paid by Client under the applicable SOW in the twelve (12) months preceding the event.",
        "confidence": 1,
        "evidence": "Except for breach of confidentiality or willful misconduct, each party’s aggregate liability under this Agreement will not exceed the fees paid by Client under the applicable SOW in the twelve (12) months preceding the event giving rise to the claim."
      },
      {
        "name": "governing law",
        "value": "State of California",
        "confidence": 1,
        "evidence": "This Agreement is governed by the laws of the State of California, without regard to conflict of laws principles."
      },
      {
        "name": "payment terms",
        "value": "Fees as per SOW. Invoices due Net 30 days from invoice date (unless SOW states otherwise). Late payments accrue interest at 1.0% per month.",
        "confidence": 1,
        "evidence": "Client will pay fees set forth in the applicable SOW. Unless otherwise stated in an SOW, invoices are due Net 30 days from invoice date. Late payments accrue interest at 1.0% per month."
      }
    ],
    "overall_confidence": 1,
    "needs_review": false,
    "review_reasons": []
  }
}
```

**Interpretation:** Validation passed, extractor produced 7 fields, auditor gave score 1.0. Confidence ≥ threshold → **finalize as completed**, no retry.

---

## Run 2: Low-confidence path (retry then needs_review)

**Input:** Short or ambiguous contract snippet where key terms are missing or vague.

**Request:**
```
curl -X 'POST' \
  'http://localhost:8080/contract/process' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3MzU3ODQ0MiwiaWF0IjoxNzczNTc0ODQyfQ.t0xMBDcbXmO9fT8f9ruOPiqxLL8obv02gGyFodetCQY' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text=We agree to work together. Start date TBD. Payment as per separate SOW.' \
  -F 'document_id=text_contract' \
  -F 'file='
```

**Output (after 1 retry, then finalize because retries exhausted):**
```json
{
  "trace_id": "5b0d73b8-76f3-4ae8-ac04-70c756ecb790",
  "scenario": "scenario_2_contract",
  "status": "completed",
  "created_at": "2026-03-15T12:16:39.869592Z",
  "stages": [
    {
      "name": "validation",
      "status": "success",
      "started_at": "2026-03-15T12:16:15.719050Z",
      "ended_at": null,
      "input_summary": "text",
      "output_summary": "Input accepted (NeMo: allowed)",
      "tool_calls": null,
      "errors": null
    },
    {
      "name": "extractor",
      "status": "success",
      "started_at": "2026-03-15T12:16:15.890186Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "Extracted 7 fields",
      "tool_calls": [
        {
          "tool": "extractor_llm",
          "description": "Extract key terms from contract via LLM",
          "document_id": "text_contract"
        }
      ],
      "errors": null
    },
    {
      "name": "auditor",
      "status": "success",
      "started_at": "2026-03-15T12:16:20.871136Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "score=1.00",
      "tool_calls": [
        {
          "tool": "deepeval_audit",
          "description": "Faithfulness + Answer Relevancy evaluation",
          "threshold": 0.8
        }
      ],
      "errors": null
    }
  ],
  "updated_at": "2026-03-15T12:16:39.869592Z",
  "confidence": 1,
  "confidence_rationale": "OK",
  "decision": {
    "retry_count": 0,
    "threshold": 0.8,
    "faithfulness_score": 1,
    "faithfulness_reason": "OK",
    "answer_relevancy_score": 1,
    "answer_relevancy_reason": "OK",
    "nemo_passed": true,
    "nemo_message": "allowed",
    "nemo_detections": [],
    "last_error": ""
  },
  "artifacts": {
    "document_id": "text_contract",
    "fields": [
      {
        "name": "parties",
        "value": "Undisclosed parties",
        "confidence": 0.8,
        "evidence": "We agree to work together."
      },
      {
        "name": "effective date",
        "value": "TBD",
        "confidence": 0.95,
        "evidence": "Start date TBD."
      },
      {
        "name": "term/duration",
        "value": "Not specified",
        "confidence": 0.9,
        "evidence": ""
      },
      {
        "name": "termination",
        "value": "Not specified",
        "confidence": 0.9,
        "evidence": ""
      },
      {
        "name": "liability",
        "value": "Not specified",
        "confidence": 0.9,
        "evidence": ""
      },
      {
        "name": "governing law",
        "value": "Not specified",
        "confidence": 0.9,
        "evidence": ""
      },
      {
        "name": "payment terms",
        "value": "As per separate SOW",
        "confidence": 0.95,
        "evidence": "Payment as per separate SOW."
      }
    ],
    "overall_confidence": 0.85,
    "needs_review": true,
    "review_reasons": [
      "Contract is extremely brief and lacks many standard clauses (e.g., specific parties, duration, termination, liability, governing law)."
    ]
  }
}
```


---


sample 3
curl -X 'POST' \
  'http://localhost:8080/contract/process' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3MzU3ODQ0MiwiaWF0IjoxNzczNTc0ODQyfQ.t0xMBDcbXmO9fT8f9ruOPiqxLL8obv02gGyFodetCQY' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text=I dont want to be part of this contract this is shitty and nonsense.' \
  -F 'document_id=text_contract' \
  -F 'file='

{
  "trace_id": "3bb98742-ab07-4ec4-952f-c09773c599c6",
  "scenario": "scenario_2_contract",
  "status": "failed",
  "created_at": "2026-03-15T12:21:29.880557Z",
  "stages": [
    {
      "name": "validation",
      "status": "success",
      "started_at": "2026-03-15T12:20:31.260353Z",
      "ended_at": null,
      "input_summary": "text",
      "output_summary": "Input accepted (NeMo: allowed)",
      "tool_calls": null,
      "errors": null
    },
    {
      "name": "extractor",
      "status": "success",
      "started_at": "2026-03-15T12:20:32.593282Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "Extracted 7 fields",
      "tool_calls": [
        {
          "tool": "extractor_llm",
          "description": "Extract key terms from contract via LLM",
          "document_id": "text_contract"
        }
      ],
      "errors": null
    },
    {
      "name": "auditor",
      "status": "success",
      "started_at": "2026-03-15T12:20:35.555192Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "score=0.00",
      "tool_calls": [
        {
          "tool": "deepeval_audit",
          "description": "Faithfulness + Answer Relevancy evaluation",
          "threshold": 0.8
        }
      ],
      "errors": null
    },
    {
      "name": "extractor",
      "status": "success",
      "started_at": "2026-03-15T12:20:50.125674Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "Extracted 7 fields",
      "tool_calls": [
        {
          "tool": "extractor_llm",
          "description": "Extract key terms from contract via LLM",
          "document_id": "text_contract"
        }
      ],
      "errors": null
    },
    {
      "name": "auditor",
      "status": "success",
      "started_at": "2026-03-15T12:20:53.280962Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "score=0.00",
      "tool_calls": [
        {
          "tool": "deepeval_audit",
          "description": "Faithfulness + Answer Relevancy evaluation",
          "threshold": 0.8
        }
      ],
      "errors": null
    },
    {
      "name": "extractor",
      "status": "success",
      "started_at": "2026-03-15T12:21:10.077466Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "Extracted 7 fields",
      "tool_calls": [
        {
          "tool": "extractor_llm",
          "description": "Extract key terms from contract via LLM",
          "document_id": "text_contract"
        }
      ],
      "errors": null
    },
    {
      "name": "auditor",
      "status": "success",
      "started_at": "2026-03-15T12:21:13.215425Z",
      "ended_at": null,
      "input_summary": null,
      "output_summary": "score=0.00",
      "tool_calls": [
        {
          "tool": "deepeval_audit",
          "description": "Faithfulness + Answer Relevancy evaluation",
          "threshold": 0.8
        }
      ],
      "errors": null
    }
  ],
  "updated_at": "2026-03-15T12:21:29.880557Z",
  "confidence": 0,
  "confidence_rationale": "The provided text is not a contract and does not contain any of the requested key terms. It appears to be a rejection or refusal of a contract.",
  "decision": {
    "retry_count": 2,
    "threshold": 0.8,
    "faithfulness_score": 0,
    "faithfulness_reason": "The provided text is not a contract and does not contain any of the requested key terms. It appears to be a rejection or refusal of a contract.",
    "answer_relevancy_score": 0,
    "answer_relevancy_reason": "The provided text is not a contract and does not contain any of the requested key terms. It appears to be a rejection or refusal of a contract.",
    "nemo_passed": true,
    "nemo_message": "allowed",
    "nemo_detections": [],
    "last_error": ""
  },
  "artifacts": {
    "document_id": "text_contract",
    "fields": [
      {
        "name": "parties",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "effective date",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "term/duration",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "termination",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "liability",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "governing law",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      },
      {
        "name": "payment terms",
        "value": "Not specified",
        "confidence": 0,
        "evidence": ""
      }
    ],
    "overall_confidence": 0,
    "needs_review": true,
    "review_reasons": [
      "The provided text is not a contract and does not contain any of the requested key terms. It appears to be a rejection or refusal of a contract."
    ]
  }
}

## How to reproduce

1. **High-confidence:** Use a full contract (PDF or long text) with clear parties, dates, termination, payment.
2. **Low-confidence:** Use a very short or vague snippet (e.g. 1–2 sentences) so the Judge returns low faithfulness/relevancy; ensure `MAX_EXTRACTION_RETRIES=2` (or 1) to see the retry loop and then finalize with `needs_review`.

Use `GET /contract/status/{trace_id}` with the returned `trace_id` to fetch the full run anytime.

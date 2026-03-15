"""
Extractor agent: LiteLLM (Gemini/Groq/Azure) -> ContractKeyTermsExtraction.
Uses prompt + JSON parse for schema fidelity. Token-capped input to reduce cost.
"""
from __future__ import annotations

import json
import logging
from uuid import uuid4

from app.core.config import settings
from app.core.llm_config import (
    get_llm_api_key,
    get_llm_completion_kwargs,
    get_llm_model_string_extraction,
    get_llm_temperature,
)
from app.core.schemas import ContractKeyTermsExtraction

logger = logging.getLogger(__name__)

# System prompt: extract then self-critique (reduces need for retry loop)
EXTRACTOR_SYSTEM = """You are a legal expert. Extract key terms from the contract below.
Step 1: Extract. Step 2: Double-check your JSON against the source text for faithfulness and completeness before giving the final output.
Output ONLY valid JSON (no markdown):
{"document_id":"<string>","fields":[{"name":"<term>","value":"<value>","confidence":<0-1>,"evidence":"<short excerpt or empty>"}],"overall_confidence":<0-1>,"needs_review":<bool>,"review_reasons":["<reason if any>"]}
Extract at least: parties, effective date, term/duration, termination, liability, governing law, payment terms if present.
Use the given document_id. confidence 0-1. value may be string, number, boolean, or array of strings. For missing or inapplicable terms use empty string "" or "Not specified" for value; do not use null. Use "" for evidence when none."""


def run_extractor(
    contract_text: str,
    document_id: str | None = None,
    auditor_feedback: str | None = None,
) -> ContractKeyTermsExtraction:
    """
    Call LiteLLM (Gemini/Groq/Azure) to produce ContractKeyTermsExtraction.
    Raises on missing API key or parse failure. Input capped to max_contract_chars to save tokens.
    """
    api_key = get_llm_api_key()
    if not api_key:
        raise ValueError(
            f"Set API key for provider '{settings.llm_provider}': "
            "GEMINI_API_KEY, GROQ_API_KEY, or AZURE_OPENAI_API_KEY"
        )
    doc_id = document_id or str(uuid4())
    max_chars = getattr(settings, "max_contract_chars", 12_000)
    text = (contract_text or "")[:max_chars]
    user_content = f"document_id: {doc_id}\n\nContract text:\n{text}"
    if auditor_feedback and auditor_feedback.strip():
        user_content += f"\n\n--- Improve using this feedback:\n{auditor_feedback.strip()}\n---\nOutput improved JSON only."
    messages = [
        {"role": "system", "content": EXTRACTOR_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    model = get_llm_model_string_extraction()
    extra = get_llm_completion_kwargs()
    try:
        import litellm
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=get_llm_temperature(),
            max_tokens=2048,
            **extra,
        )
        choices = getattr(response, "choices", None) or []
        msg = choices[0].message if choices else None
        raw = (getattr(msg, "content", None) or "").strip() if msg else ""
    except Exception as e:
        logger.exception("LiteLLM extractor call failed: %s", e)
        raise
    text_out = raw.strip()
    if text_out.startswith("```"):
        lines = text_out.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text_out = "\n".join(lines)
    data = None
    try:
        data = json.loads(text_out)
    except json.JSONDecodeError as e:
        logger.warning("Extractor returned non-JSON; relaxed parse: %s", e)
        start = text_out.find("{")
        if start < 0:
            raise ValueError(f"Extractor output was not valid JSON: {e}") from e
        end = text_out.rfind("}") + 1
        if end > start:
            try:
                data = json.loads(text_out[start:end])
            except json.JSONDecodeError:
                pass
        # Salvage truncated JSON (e.g. unterminated string at e.pos)
        if data is None and getattr(e, "pos", None) is not None:
            pos = min(e.pos, len(text_out))
            segment = text_out[start:pos]
            salvage = segment.strip()
            if salvage:
                if segment.count('"') % 2 == 1:
                    salvage += '"'
                open_b = max(0, salvage.count("[") - salvage.count("]"))
                open_c = max(0, salvage.count("{") - salvage.count("}"))
                salvage += "]" * open_b + "}" * open_c
                try:
                    data = json.loads(salvage)
                except json.JSONDecodeError:
                    pass
        if data is None:
            raise ValueError(f"Extractor output was not valid JSON: {e}") from e
    if "document_id" not in data:
        data["document_id"] = doc_id
    if "fields" not in data or not isinstance(data["fields"], list):
        data["fields"] = []
    normalized = []
    for f in data["fields"]:
        if isinstance(f, dict):
            raw_value = f.get("value")
            raw_evidence = f.get("evidence")
            normalized.append({
                "name": str(f.get("name", "")),
                "value": raw_value if raw_value is not None else "",
                "confidence": float(f.get("confidence", 0.5)),
                "evidence": raw_evidence if raw_evidence is not None else "",
            })
    data["fields"] = normalized
    return ContractKeyTermsExtraction.model_validate(data)

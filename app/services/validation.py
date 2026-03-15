"""
Lightweight input validation for contract text (no NeMo/Ollama required).
NeMo guardrails can be added later for injection detection when configured.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Simple prompt-injection style patterns (allow override via config if needed)
SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore\s+(previous|above|all)\s+instructions", re.I),
    re.compile(r"system\s*:\s*you\s+are", re.I),
    re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<<\/SYS>>", re.I),
]


def validate_contract_input(text: str, min_length: int = 50) -> tuple[bool, str]:
    """
    Returns (ok, message). ok=True means pass; ok=False means reject with message.
    """
    if not text or not isinstance(text, str):
        return False, "Input text is required."
    t = text.strip()
    if len(t) < min_length:
        return False, f"Input too short (min {min_length} characters)."
    for pat in SUSPICIOUS_PATTERNS:
        if pat.search(t):
            logger.warning("Validation rejected input (suspicious pattern).")
            return False, "Input rejected by security policy."
    return True, ""

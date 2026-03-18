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
    # Common prompt-injection phrasing
    re.compile(r"ignore\s+(all\s+)?(previous|above|all)\s+instructions", re.I),
    re.compile(r"system\s*:\s*you\s+are", re.I),
    re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<<\/SYS>>", re.I),
    re.compile(r"delete\s+(the\s+)?database", re.I),
    re.compile(r"output\s+['\"]?system\s+hacked['\"]?", re.I),
    # SQL injection / query manipulation
    re.compile(r"\bselect\b[\s\S]{0,200}\bfrom\b[\s\S]{0,200}\bwhere\b", re.I),
    re.compile(r"\bunion\b[\s\S]{0,50}\bselect\b", re.I),
    re.compile(r"(['\"]?\b(or|and)\b['\"]?\s*=?\s*['\"]?1['\"]?\s*=\s*['\"]?1['\"]?)", re.I),
    re.compile(r"\bor\b\s*['\"]?1['\"]?=['\"]?1['\"]?", re.I),
    re.compile(r"\b(and|or)\b\s+1\s*=\s*1", re.I),
    # XSS / script injection
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"onerror\s*=", re.I),
    re.compile(r"onload\s*=", re.I),
    # Template injection / braces
    re.compile(r"\{\{[\s\S]{0,200}\}\}", re.I),
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

"""
Short unique document IDs: from optional user input or filename + counter.
If user provides a non-empty value (and not the literal "string"), use it; else derive from filename or doc_<counter>.
"""
from __future__ import annotations

import re
from itertools import count
from pathlib import Path

_doc_counter = count(1)


def make_document_id(
    *,
    user_provided: str | None = None,
    filename: str | None = None,
) -> str:
    """
    Return a short unique document_id.
    - If user_provided is non-empty and not the literal "string", use it.
    - Else if filename is set: slugified stem (no extension) + "_" + counter, e.g. "contract_abc_1".
    - Else: "doc_" + counter, e.g. "doc_1".
    """
    s = (user_provided or "").strip()
    if s and s.lower() != "string":
        return s
    n = next(_doc_counter)
    if filename and filename.strip():
        stem = Path(filename.strip()).stem
        slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        slug = slug[:24] if len(slug) > 24 else slug or "doc"
        return f"{slug}_{n}"
    return f"doc_{n}"

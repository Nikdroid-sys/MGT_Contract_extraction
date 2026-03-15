"""
Extract plain text from PDF or return raw text. Used by contract/process.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional PyMuPDF; fail gracefully if not available
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract text from a PDF file. Raises ValueError if file is invalid or PyMuPDF missing.
    """
    if not HAS_PYMUPDF:
        raise ValueError("PDF support not available (PyMuPDF not installed)")
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        doc = fitz.open(path)
        try:
            parts = [doc.load_page(i).get_text() for i in range(len(doc))]
            return "\n".join(parts).strip() or ""
        finally:
            doc.close()
    except Exception as e:
        logger.exception("PDF extraction failed: %s", e)
        raise ValueError(f"Could not extract text from PDF: {e}") from e


def extract_text_from_bytes(data: bytes, filename: str = "") -> str:
    """
    If data looks like PDF (magic bytes), extract text; otherwise decode as UTF-8.
    """
    if data.startswith(b"%PDF"):
        if not HAS_PYMUPDF:
            raise ValueError("PDF support not available (PyMuPDF not installed)")
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            try:
                parts = [doc.load_page(i).get_text() for i in range(len(doc))]
                return "\n".join(parts).strip() or ""
            finally:
                doc.close()
        except Exception as e:
            logger.exception("PDF extraction from bytes failed: %s", e)
            raise ValueError(f"Could not extract text from PDF: {e}") from e
    return data.decode("utf-8", errors="replace").strip()

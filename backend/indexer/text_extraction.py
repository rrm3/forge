"""Text extraction from file content, producing Markdown output.

Simplified version for forge. Supports:
* Markdown: pass-through
* PDF: pymupdf4llm (Markdown with embedded images)
* Plain text / CSV / JSON: UTF-8 decode
"""

import json
import logging

logger = logging.getLogger(__name__)


def extract_text(content_bytes: bytes, mime_type: str) -> str | None:
    """Extract text from file content based on MIME type.

    Args:
        content_bytes: Raw file content
        mime_type: MIME type (e.g. "application/pdf", "text/markdown")

    Returns:
        Extracted text as a string, or None if extraction fails
    """
    # Normalize mime type (strip charset suffixes)
    base_mime = mime_type.split(";")[0].strip().lower()

    extractors = {
        "application/pdf": _extract_pdf,
        "text/plain": _extract_text_utf8,
        "text/markdown": _extract_text_utf8,
        "text/csv": _extract_text_utf8,
        "application/json": _extract_json,
    }

    extractor = extractors.get(base_mime)
    if extractor is None:
        # Fall back to text extraction for text/* types
        if base_mime.startswith("text/"):
            extractor = _extract_text_utf8
        else:
            logger.warning(f"Unsupported mime type for extraction: {mime_type}")
            return None

    try:
        return extractor(content_bytes)
    except Exception:
        logger.exception(f"Failed to extract text from {mime_type}")
        return None


def _extract_pdf(content_bytes: bytes) -> str | None:
    """Extract Markdown from PDF using pymupdf4llm."""
    import pymupdf
    import pymupdf4llm

    doc = pymupdf.open(stream=content_bytes, filetype="pdf")
    md_text = pymupdf4llm.to_markdown(doc)

    if not md_text or not md_text.strip():
        return None

    return md_text


def _extract_text_utf8(content_bytes: bytes) -> str | None:
    """Extract text by UTF-8 decoding."""
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("utf-8", errors="replace")


def _extract_json(content_bytes: bytes) -> str | None:
    """Extract and pretty-print JSON content."""
    try:
        text = content_bytes.decode("utf-8")
        data = json.loads(text)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return content_bytes.decode("utf-8", errors="replace")

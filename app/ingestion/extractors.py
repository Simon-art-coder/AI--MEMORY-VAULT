"""
Text extraction from uploaded files.

This is fully implemented — no API key needed for any of it. Each
extractor takes raw bytes and returns plain text. Unsupported formats
raise UnsupportedFileTypeError so the API layer can return a clean 400
instead of crashing.
"""

import io

import pypdf
from docx import Document

SUPPORTED_EXTENSIONS = {"txt", "md", "pdf", "docx"}


class UnsupportedFileTypeError(Exception):
    pass


class ExtractionFailedError(Exception):
    """Raised when a supported file type is malformed and can't be read."""

    pass


def extract_text(filename: str, file_bytes: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'.{extension}' is not supported. Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    try:
        if extension in ("txt", "md"):
            return _extract_plain_text(file_bytes)
        if extension == "pdf":
            return _extract_pdf(file_bytes)
        if extension == "docx":
            return _extract_docx(file_bytes)
    except UnsupportedFileTypeError:
        raise
    except Exception as exc:
        # A malformed upload should never crash the ingestion pipeline —
        # this turns any low-level parser error into a clear, user-facing one.
        raise ExtractionFailedError(f"Could not read '{filename}': {exc}") from exc

    raise UnsupportedFileTypeError(extension)  # unreachable given the check above, kept for safety


def _extract_plain_text(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def _extract_pdf(file_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs)

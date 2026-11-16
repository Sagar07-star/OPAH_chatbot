"""Upload validation by content, plus PDF text extraction.

Extensions are not trusted: the bytes decide the type. Limits are configuration.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import settings
from ..assistant import memory

SIGNATURES = (
    ("application/pdf", b"%PDF-"),
    ("image/jpeg", b"\xff\xd8\xff"),
    ("image/png", b"\x89PNG\r\n\x1a\n"),
)
SUPPORTED_MIMES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass
class ValidatedUpload:
    filename: str
    mime: str
    size_bytes: int
    raw: bytes
    extracted_text: str | None = None
    pages: int | None = None


def detect_mime(raw: bytes) -> str | None:
    if raw.startswith(b"RIFF") and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "image/webp"
    for mime, signature in SIGNATURES:
        if raw.startswith(signature):
            return mime
    return None


def _reject(filename: str, message: str) -> HTTPException:
    return HTTPException(status_code=400, detail={
        "error": "upload_rejected", "filename": filename, "message": message,
    })


def extract_pdf(raw: bytes, filename: str) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
        from io import BytesIO
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise _reject(filename, "PDF reading isn't installed on the server (pypdf is missing).") from exc
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise _reject(filename, "This PDF is password-protected, so I can't read it.") from exc
        pages = len(reader.pages)
        if pages == 0:
            raise _reject(filename, "That PDF has no pages.")
        if pages > settings.max_pdf_pages:
            raise _reject(filename, f"That PDF has {pages} pages; this prototype reads up to "
                                    f"{settings.max_pdf_pages}. Send the first pages instead.")
        chunks: list[str] = []
        for page in reader.pages[: settings.max_pdf_pages]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                chunks.append("")
            if sum(len(c) for c in chunks) > settings.max_pdf_text_chars:
                break
        text = "\n".join(chunks).strip()[: settings.max_pdf_text_chars]
        return text, pages
    except HTTPException:
        raise
    except Exception as exc:
        raise _reject(filename, f"I couldn't read that PDF ({type(exc).__name__}). "
                               "It may be corrupt or use an unsupported encoding.") from exc


async def validate_upload(file: UploadFile) -> ValidatedUpload:
    filename = (file.filename or "upload").strip()[:180]
    declared = (file.content_type or "").split(";")[0].strip().lower()
    raw = await file.read(settings.max_pdf_bytes + 1)
    if not raw:
        raise _reject(filename, "That file is empty.")
    mime = detect_mime(raw)
    if mime is None:
        raise _reject(filename, "Only JPEG, PNG, WebP images and PDFs are accepted; "
                               "that file's content isn't one of them (whatever its name says).")
    if declared and declared in SUPPORTED_MIMES and declared != mime:
        raise _reject(filename, f"That file says {declared} but its content is {mime}.")
    limit = settings.max_pdf_bytes if mime == "application/pdf" else settings.max_image_bytes
    if len(raw) > limit:
        mb = limit // (1024 * 1024)
        raise _reject(filename, f"That file is larger than the {mb} MB limit for {mime}.")
    upload = ValidatedUpload(filename=filename, mime=mime, size_bytes=len(raw), raw=raw)
    if mime == "application/pdf":
        text, pages = extract_pdf(raw, filename)
        upload.extracted_text = text or None
        upload.pages = pages
    return upload


def store_upload(owner_key: str, upload: ValidatedUpload) -> dict:
    suffix = EXTENSIONS[upload.mime]
    target = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{suffix}"
    target.write_bytes(upload.raw)
    row = memory.save_upload(
        owner_key,
        upload.filename,
        upload.mime,
        upload.size_bytes,
        str(target),
        upload.extracted_text,
        upload.pages,
    )
    row.pop("path", None)
    row["has_text"] = bool(upload.extracted_text)
    return row

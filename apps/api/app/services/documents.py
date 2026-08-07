"""Document ingestion — the one code path every attachment goes through.

Bytes are magic-byte validated, content-addressed by SHA-256, written under
``STORAGE_ROOT`` (outside any web root) and only ever served through the signed,
time-limited route in ``app/api/routers/documents.py``.

Remote images are downloaded **once**; ``Document.url`` is provenance only and is
never re-fetched at render time (§1a, M9 FR-9.11).
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import filetype
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.errors import ValidationError
from app.models.core import Document

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}

_MAX_REMOTE_BYTES = 15 * 1024 * 1024


def _detect_mime(data: bytes) -> str:
    """Trust the file's magic bytes, never the client-supplied content type."""
    kind = filetype.guess(data)
    if kind is None:
        raise ValidationError("Tipo de ficheiro não reconhecido.")
    if kind.mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(f"Tipo de ficheiro não permitido: {kind.mime}")
    return str(kind.mime)


def _storage_path(sha256_hash: str, mime: str) -> Path:
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "application/pdf": ".pdf",
    }[mime]
    # Fan out by hash prefix so a single directory never holds 100k files.
    return Path(sha256_hash[:2]) / sha256_hash[2:4] / f"{sha256_hash}{suffix}"


def store_bytes(
    db: DbSession,
    data: bytes,
    *,
    source: str = "UPLOAD",
    url: str | None = None,
    original_filename: str | None = None,
) -> Document:
    if not data:
        raise ValidationError("Ficheiro vazio.")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError("Ficheiro demasiado grande (máx. 15 MB).")

    mime = _detect_mime(data)
    sha256_hash = hashlib.sha256(data).hexdigest()

    existing = db.scalar(select(Document).where(Document.sha256_hash == sha256_hash))
    if existing is not None:
        return existing

    relative = _storage_path(sha256_hash, mime)
    absolute = settings.storage_root / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(data)

    document = Document(
        sha256_hash=sha256_hash,
        mime_type=mime,
        byte_size=len(data),
        storage_path=str(relative),
        source=source,
        url=url,
        original_filename=original_filename,
        signed_url_expires_minutes=settings.document_url_ttl_minutes,
    )
    db.add(document)
    db.flush()
    return document


def store_from_url(db: DbSession, url: str) -> Document:
    if not url.startswith(("http://", "https://")):
        raise ValidationError("O endereço da imagem tem de começar por http:// ou https://.")
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.content
    except httpx.HTTPError as exc:
        raise ValidationError(f"Não foi possível transferir a imagem: {exc}") from exc

    if len(data) > _MAX_REMOTE_BYTES:
        raise ValidationError("Imagem remota demasiado grande.")
    return store_bytes(db, data, source="URL", url=url)


def absolute_path(document: Document) -> Path:
    path = (settings.storage_root / document.storage_path).resolve()
    root = settings.storage_root.resolve()
    if not str(path).startswith(str(root)):  # defence in depth against traversal
        raise ValidationError("Caminho de ficheiro inválido.")
    return path


def get(db: DbSession, document_id: uuid.UUID) -> Document | None:
    return db.get(Document, document_id)

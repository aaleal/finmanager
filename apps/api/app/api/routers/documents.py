"""Signed, time-limited attachment delivery.

The signature is what authorizes the read, so this route is deliberately not
behind the session dependency: `<img src>` cannot send a CSRF header. The link
expires in minutes and leaks nothing beyond the single document it names.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.api.deps import Db
from app.core.errors import Forbidden, NotFound
from app.core.security import verify_document_signature
from app.services import documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/content")
def get_content(
    document_id: uuid.UUID,
    db: Db,
    expires: int = Query(...),
    signature: str = Query(...),
) -> FileResponse:
    if not verify_document_signature(document_id, expires, signature):
        raise Forbidden("Ligação expirada ou inválida.")

    document = documents.get(db, document_id)
    if document is None:
        raise NotFound("Ficheiro não encontrado.")

    path = documents.absolute_path(document)
    if not path.exists():
        raise NotFound("Ficheiro não encontrado no armazenamento.")

    return FileResponse(
        path,
        media_type=document.mime_type,
        headers={
            "Cache-Control": "private, max-age=600",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )

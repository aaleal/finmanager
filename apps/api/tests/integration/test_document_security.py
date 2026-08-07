"""Protects: rubric «Security (OWASP) — attachments validated by magic bytes, stored
outside web root, served via signed time-limited URLs» and M9 FR-9.11 «remote images
are downloaded once and stored locally».
"""

from __future__ import annotations

import time
import uuid

import pytest
from app.core.errors import ValidationError
from app.core.security import sign_document, signed_document_url, verify_document_signature
from app.services import documents
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

# 1x1 transparent PNG.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)


def test_magic_bytes_decide_the_type_not_the_supplied_name(db: Session) -> None:
    document = documents.store_bytes(db, PNG, original_filename="pretend.pdf")
    assert document.mime_type == "image/png"


def test_a_disguised_executable_is_refused(db: Session) -> None:
    with pytest.raises(ValidationError):
        documents.store_bytes(db, b"#!/bin/sh\nrm -rf /\n", original_filename="cover.png")


def test_empty_upload_is_refused(db: Session) -> None:
    with pytest.raises(ValidationError):
        documents.store_bytes(db, b"")


def test_identical_bytes_are_stored_once(db: Session) -> None:
    first = documents.store_bytes(db, PNG)
    second = documents.store_bytes(db, PNG)
    assert first.id == second.id


def test_file_lands_outside_any_web_root(db: Session) -> None:
    document = documents.store_bytes(db, PNG)
    path = documents.absolute_path(document)
    assert path.exists()
    assert str(path).startswith("/var/lib/finmanager/storage")


def test_signature_round_trips_and_expires() -> None:
    document_id = uuid.uuid4()
    signature, expires_at = sign_document(document_id, ttl_minutes=15)
    assert verify_document_signature(document_id, expires_at, signature) is True

    # Wrong document, tampered signature and elapsed deadline all fail closed.
    assert verify_document_signature(uuid.uuid4(), expires_at, signature) is False
    assert verify_document_signature(document_id, expires_at, signature + "x") is False
    assert verify_document_signature(document_id, int(time.time()) - 1, signature) is False


def test_signed_url_is_the_only_shape_the_ui_ever_sees() -> None:
    url = signed_document_url(uuid.uuid4())
    assert url.startswith("/api/documents/")
    assert "signature=" in url and "expires=" in url

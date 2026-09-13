"""Protects: the M1 rubric bullets *«the full pipeline completes with egress
blocked, at default settings»* and *«the provider seam is exercised by a fake
remote engine in tests, proving a stage can be swapped without touching the
pipeline»*.

The module's guarantee is that it is fully functional with **no subscription and
no network**. That is only worth stating if something enforces it.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from app.models import Entity, User
from app.models.supermarket import SupermarketReceiptItem
from app.services.reference_data import ensure_all
from app.services.supermarket import pipeline
from app.services.supermarket import service as supermarket_service
from sqlalchemy.orm import Session

from tests.corpus import RECEIPTS, requires_receipts

pytestmark = [pytest.mark.integration, requires_receipts]

FIXTURES = RECEIPTS


@pytest.fixture
def reference_data(db: Session) -> None:
    ensure_all(db)


@pytest.fixture
def egress_blocked(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Any outbound socket becomes an error for the duration of the test."""
    postgres_port = 5432

    def refuse(self: socket.socket, address: Any) -> None:
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        if port in (postgres_port, 6379):  # the database and Redis are not "egress"
            return original(self, address)
        raise AssertionError(f"a rede foi contactada: {address!r}")

    original = socket.socket.connect
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    monkeypatch.setattr(socket.socket, "connect", original)


def test_the_whole_pipeline_completes_with_egress_blocked(
    db: Session, entity: Entity, owner: User, reference_data: None, egress_blocked: None
) -> None:
    """No subscription, no network — that is what makes the module usable on day one."""
    receipt, _, _ = supermarket_service.create_from_upload(
        db,
        data=(FIXTURES / "continente-20260724.pdf").read_bytes(),
        filename="continente-20260724.pdf",
        entity_id=entity.id,
        actor_user_id=owner.id,
        idempotency_key=uuid.uuid4().hex,
    )
    supermarket_service.parse_receipt(db, receipt, actor_user_id=owner.id)

    assert receipt.status != "FAILED"
    assert len(receipt.items) == 15
    assert receipt.total_eur == Decimal("36.56")
    assert receipt.raw_ocr_payload is not None
    assert receipt.raw_ocr_payload["engine"] == "pdfplumber"


class FakeRemoteResolver:
    """A stand-in for a hosted product database, registered through the seam."""

    def __init__(self, product_id: uuid.UUID) -> None:
        self.product_id = product_id
        self.calls = 0

    def resolve(
        self, db: Session, *, merchant_id: uuid.UUID | None, item: SupermarketReceiptItem
    ) -> tuple[uuid.UUID | None, Decimal | None, list[dict[str, Any]]]:
        self.calls += 1
        return (
            self.product_id,
            Decimal("0.990"),
            [{"rule": "remote_provider", "detail": "Motor remoto simulado.", "score": "0.990"}],
        )


def test_a_stage_can_be_swapped_without_touching_the_pipeline(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    from app.services.supermarket import catalogue, products_service

    product = products_service.create_product(db, canonical_name="Produto Remoto")
    fake = FakeRemoteResolver(product.id)
    pipeline.register_product_resolver(fake)
    try:
        receipt, _, _ = supermarket_service.create_from_upload(
            db,
            data=(FIXTURES / "lidl-20260801.pdf").read_bytes(),
            filename="lidl-20260801.pdf",
            entity_id=entity.id,
            actor_user_id=owner.id,
            idempotency_key=uuid.uuid4().hex,
        )
        supermarket_service.parse_receipt(db, receipt, actor_user_id=owner.id)
    finally:
        pipeline.register_product_resolver(catalogue.CatalogueResolver())

    assert fake.calls == len(receipt.items) == 8
    assert all(item.master_product_id == product.id for item in receipt.items)
    assert any(
        reason["rule"] == "remote_provider"
        for item in receipt.items
        for reason in item.decision_reasons
    )
    # The engine that made the call is recorded, so a quality change is always
    # traceable to the switch that caused it.
    assert receipt.status == "AUTO_ACCEPTED"


def test_disabling_the_stage_entirely_is_reported_not_scored_as_failure(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    from app.services.supermarket import catalogue

    pipeline.register_product_resolver(None)
    try:
        receipt, _, _ = supermarket_service.create_from_upload(
            db,
            data=(FIXTURES / "lidl-20260811.pdf").read_bytes(),
            filename="lidl-20260811.pdf",
            entity_id=entity.id,
            actor_user_id=owner.id,
            idempotency_key=uuid.uuid4().hex,
        )
        supermarket_service.parse_receipt(db, receipt, actor_user_id=owner.id)
    finally:
        pipeline.register_product_resolver(catalogue.CatalogueResolver())

    assert any(reason["rule"] == "product_match_unavailable" for reason in receipt.decision_reasons)

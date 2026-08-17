"""Protects: the M1a exit criterion (*«a Continente PDF and a Lidl PDF upload,
parse, reconcile to their printed totals, and confirm»*), plus the rubric bullets
on **idempotent re-import**, **ATCUD duplicate prevention**, the **receipt status
machine**, and *«adding an Fs article to a CONFIRMED receipt changes no printed
figure»*.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from app.core.errors import Conflict, ValidationError
from app.models import AuditLog, Entity, Merchant, ReviewTask, User
from app.models.receipts import MerchantParserProfile, Receipt
from app.seed import seed_merchants, seed_parser_profiles
from app.services.receipts import service as receipts
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "receipts"


@pytest.fixture
def reference_data(db: Session) -> None:
    seed_merchants(db)
    seed_parser_profiles(db)


def upload(db: Session, entity: Entity, owner: User, name: str, key: str | None = None) -> Receipt:
    receipt, _, created = receipts.create_from_upload(
        db,
        data=(FIXTURES / name).read_bytes(),
        filename=name,
        entity_id=entity.id,
        actor_user_id=owner.id,
        idempotency_key=key or uuid.uuid4().hex,
    )
    if created:
        receipts.parse_receipt(db, receipt, actor_user_id=owner.id)
    return receipt


def test_a_continente_pdf_parses_and_reconciles(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "continente-20260724.pdf")

    assert receipt.total_eur == Decimal("36.56")
    assert receipt.total_discount_eur == Decimal("4.00")
    assert len(receipt.items) == 15
    assert receipt.atcud_code == "JFP767JJ-035904"
    assert receipt.atcud_valid is True

    merchant = db.get(Merchant, receipt.merchant_id)
    assert merchant is not None and merchant.name == "Continente"

    totals = receipts.totals_for(db, receipt)
    assert totals.computed_total_eur == Decimal("36.56")
    assert totals.is_reconciled is True
    # The invoice-level credit is spread across the lines, never summed as promos.
    assert sum(i.invoice_allocated_discount_eur for i in receipt.items) == Decimal("4.00")


def test_a_lidl_pdf_parses_and_reconciles(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "lidl-20260801.pdf")
    assert receipt.total_eur == Decimal("7.50")
    assert receipts.totals_for(db, receipt).computed_total_eur == Decimal("7.50")
    profile = db.get(MerchantParserProfile, receipt.parser_profile_id)
    assert profile is not None and profile.parser_key == "lidl_v1"


def test_reuploading_the_same_bytes_creates_no_second_receipt(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    first = upload(db, entity, owner, "lidl-20260811.pdf")
    again, _, created = receipts.create_from_upload(
        db,
        data=(FIXTURES / "lidl-20260811.pdf").read_bytes(),
        filename="lidl-20260811.pdf",
        entity_id=entity.id,
        actor_user_id=owner.id,
        idempotency_key=uuid.uuid4().hex,
    )
    assert created is False
    assert again.id == first.id
    assert db.scalar(select(func.count()).select_from(Receipt)) == 1


def test_two_receipts_cannot_share_an_atcud(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    """The ATCUD *is* the fiscal document identity (Decision #35)."""
    original = upload(db, entity, owner, "pingodoce-24118.pdf")
    clone = Receipt(entity_id=entity.id, status="UPLOADED", atcud_code=original.atcud_code)
    db.add(clone)
    with pytest.raises(Conflict):
        receipts._guard_duplicate_atcud(db, clone)


def test_needs_review_creates_exactly_one_task_and_confirm_resolves_it(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    """The photograph is the reliable review case: its total is illegible."""
    receipt = upload(db, entity, owner, "piquete-20260811.jpeg")
    assert receipt.status == "NEEDS_REVIEW"

    tasks = db.scalars(select(ReviewTask).where(ReviewTask.subject_id == receipt.id)).all()
    assert len(tasks) == 1
    assert tasks[0].module == "receipts"

    receipts.confirm(db, receipt, actor_user_id=owner.id)
    assert receipt.status == "CONFIRMED"
    assert tasks[0].status == "CONFIRMED"


def test_an_empty_catalogue_sends_a_clean_pdf_to_review(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    """Decision #39: nothing resolves, and that is correct. The fix is data.

    ADR-0018 predicted this exact change of behaviour. While the catalogue stage
    did not exist its weight was redistributed and this receipt auto-accepted;
    now the stage runs, finds nothing, and scores a genuine zero.
    """
    receipt = upload(db, entity, owner, "pingodoce-30824.pdf")
    assert receipt.status == "NEEDS_REVIEW"
    assert all(item.master_product_id is None for item in receipt.items)
    assert any(reason["rule"] == "product_resolution" for reason in receipt.decision_reasons)


def test_the_status_machine_rejects_an_illegal_transition(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "pingodoce-37014.pdf")
    receipts.confirm(db, receipt, actor_user_id=owner.id)
    with pytest.raises(Conflict):
        receipts.transition(db, receipt, "NEEDS_REVIEW", actor_user_id=owner.id)


def test_a_confirmed_receipt_is_voided_with_a_reason_never_deleted(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "pingodoce-47748.pdf")
    receipts.confirm(db, receipt, actor_user_id=owner.id)
    with pytest.raises(ValidationError):
        receipts.void(db, receipt, reason="   ", actor_user_id=owner.id)

    receipts.void(db, receipt, reason="devolvido na loja", actor_user_id=owner.id)
    assert receipt.status == "VOID"
    assert receipt.is_deleted is False
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.record_id == receipt.id, AuditLog.action == "STATUS_CHANGE")
        )
        >= 2
    )


def test_appending_an_fs_article_to_a_confirmed_receipt_moves_no_printed_figure(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "continente-20260806.pdf")
    receipts.confirm(db, receipt, actor_user_id=owner.id)

    before = receipts.totals_for(db, receipt)
    total_before = receipt.total_eur

    item = receipts.append_fs_item(
        db,
        receipt,
        description_raw="Cabaz de fruta do vizinho",
        unit_price_pvp_eur=Decimal("7.50"),
        actor_user_id=owner.id,
    )
    receipts.recompute(receipt)
    after = receipts.totals_for(db, receipt)

    assert item.is_fs is True
    assert item.paid_price_eur == Decimal("0.00")
    assert item.line_no is None and item.merchant_section is None and item.iva_class_raw is None
    assert receipt.total_eur == total_before
    assert after.computed_total_eur == before.computed_total_eur
    assert after.is_reconciled is before.is_reconciled
    assert after.printed_item_count == before.printed_item_count
    assert after.notional_total_eur == before.notional_total_eur + Decimal("7.50")
    assert after.fs_item_count == 1


def test_an_fs_article_without_a_value_is_refused(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "lidl-20260801.pdf")
    with pytest.raises(ValidationError):
        receipts.append_fs_item(
            db,
            receipt,
            description_raw="Sem valor",
            unit_price_pvp_eur=Decimal("0.00"),
            actor_user_id=owner.id,
        )


def test_a_corrupt_file_fails_alone_and_is_retryable_from_the_stored_document(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    """One bad scan never blocks a batch, and retry never asks for a re-upload."""
    good = upload(db, entity, owner, "lidl-20260801.pdf")

    broken, _, _ = receipts.create_from_upload(
        db,
        data=b"%PDF-1.4\n corrupted beyond recovery",
        filename="broken.pdf",
        entity_id=entity.id,
        actor_user_id=owner.id,
        idempotency_key=uuid.uuid4().hex,
    )
    receipts.parse_receipt(db, broken, actor_user_id=owner.id)

    assert broken.status == "FAILED"
    assert good.status in ("NEEDS_REVIEW", "AUTO_ACCEPTED")
    assert any(r["rule"] == "parse_failed" for r in broken.decision_reasons)

    # Retry runs from the stored document, not from a new upload.
    receipts.parse_receipt(db, broken, actor_user_id=owner.id)
    assert broken.document_id is not None


def test_the_status_board_reports_the_observed_rate_never_a_target(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    upload(db, entity, owner, "continente-20260731.pdf")
    upload(db, entity, owner, "piquete-20260811.jpeg")
    board = receipts.status_counts(db, [entity.id])
    assert board["to_validate"] >= 1
    assert board["decided_receipts"] >= 2
    assert board["unresolved_lines"] >= 1  # no catalogue yet, so every line is open
    assert 0.0 <= (board["observed_auto_accept_rate"] or 0.0) <= 1.0


def test_the_photograph_goes_to_review_rather_than_pretending(
    db: Session, entity: Entity, owner: User, reference_data: None
) -> None:
    receipt = upload(db, entity, owner, "piquete-20260811.jpeg")
    assert receipt.status == "NEEDS_REVIEW"
    assert len(receipt.items) == 5
    assert receipt.confidence is not None and receipt.confidence < Decimal("0.90")

"""Protects: *«Confidence engine = pure, deterministic functions»* (brief §3
Backend/data) and the M1 rubric bullet that identical input yields byte-identical
``(status, confidence, decision_reasons)`` across runs.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.receipts.confidence import ReceiptSignals, score


def full_signals(**overrides: object) -> ReceiptSignals:
    defaults = {
        "merchant_match": Decimal("1.000"),
        "ocr_text": Decimal("0.980"),
        "arithmetic_matches": True,
        "product_match": Decimal("1.000"),
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return ReceiptSignals(**defaults)  # type: ignore[arg-type]


def test_identical_input_yields_byte_identical_output() -> None:
    first = score(full_signals())
    second = score(full_signals())
    assert first == second


def test_a_clean_receipt_auto_accepts() -> None:
    status, confidence, _ = score(full_signals())
    assert status == "AUTO_ACCEPTED"
    assert confidence >= Decimal("0.90")


def test_arithmetic_mismatch_halves_the_score_and_says_so() -> None:
    _, matching, _ = score(full_signals())
    status, mismatching, reasons = score(full_signals(arithmetic_matches=False))

    assert status == "NEEDS_REVIEW"
    assert mismatching < matching / 2 + Decimal("0.001")
    assert any(reason["rule"] == "arithmetic_mismatch" for reason in reasons)


def test_a_stage_that_did_not_run_redistributes_its_weight() -> None:
    """`None` means *not run*; `0` means *ran and found nothing*. Not the same."""
    _, not_run, not_run_reasons = score(full_signals(product_match=None))
    _, found_nothing, _ = score(full_signals(product_match=Decimal("0")))

    assert not_run > found_nothing
    assert any(r["rule"] == "product_match_unavailable" for r in not_run_reasons)


def test_an_empty_catalogue_sends_everything_to_review() -> None:
    """Decision #39: the fix is data, not thresholds."""
    status, _, _ = score(full_signals(product_match=Decimal("0")))
    assert status == "NEEDS_REVIEW"


def test_no_signals_at_all_is_review_not_a_crash() -> None:
    status, confidence, reasons = score(
        ReceiptSignals(
            merchant_match=None, ocr_text=None, arithmetic_matches=None, product_match=None
        )
    )
    assert status == "NEEDS_REVIEW"
    assert confidence == Decimal("0.000")
    assert any(reason["rule"] == "no_signals" for reason in reasons)


def test_force_review_overrides_a_perfect_score() -> None:
    status, confidence, reasons = score(
        full_signals(force_review="NIF impresso em conflito com o perfil detetado.")
    )
    assert status == "NEEDS_REVIEW"
    assert confidence >= Decimal("0.90")  # the score is still reported honestly
    assert any(reason["rule"] == "force_review" for reason in reasons)


def test_thresholds_are_injected_never_read_from_the_clock_or_the_database() -> None:
    status, _, _ = score(full_signals(), auto_accept_threshold=Decimal("0.999"))
    assert status == "NEEDS_REVIEW"
    status, _, _ = score(
        full_signals(arithmetic_matches=False), auto_accept_threshold=Decimal("0.1")
    )
    assert status == "AUTO_ACCEPTED"


def test_every_reason_is_rule_detail_score() -> None:
    _, _, reasons = score(full_signals())
    for reason in reasons:
        assert set(reason) == {"rule", "detail", "score"}
        assert isinstance(reason["rule"], str)

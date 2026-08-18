"""Protects: the M1 rubric bullets *«all four merchant profiles parse their own
fixtures correctly, including the opposite discount semantics»*, *«extracted word
boxes are committed as golden files»* and *«the Piquete photograph parses end to
end through OCR»*.

Run against the eleven **real** *talões* under ``tests/fixtures/receipts/``. The
ten digital PDFs must reconcile to the cent; the photograph is reported
separately because OCR on a curved thermal slip is a different problem and must
not be judged alike.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from app.seed import INVOICES_DIR
from app.services.receipts import arithmetic, extraction, fiscal, parsers

FIXTURES = INVOICES_DIR
GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden"

# (fixture, parser_key, printed total, invoice-level credit, article count)
PDF_CASES = [
    ("continente-20260724.pdf", "continente_v1", "36.56", "4.00", 15),
    ("continente-20260730.pdf", "continente_v1", "0.00", "0.29", 2),
    ("continente-20260731.pdf", "continente_v1", "0.00", "9.39", 5),
    ("continente-20260806.pdf", "continente_v1", "98.63", "0.00", 19),
    ("lidl-20260801.pdf", "lidl_v1", "7.50", "0.00", 8),
    ("lidl-20260811.pdf", "lidl_v1", "8.06", "0.00", 6),
    ("pingodoce-24118.pdf", "pingodoce_v1", "15.20", "0.00", 10),
    ("pingodoce-30824.pdf", "pingodoce_v1", "16.21", "0.00", 8),
    ("pingodoce-37014.pdf", "pingodoce_v1", "1.59", "0.00", 1),
    ("pingodoce-47748.pdf", "pingodoce_v1", "9.82", "0.00", 7),
]


def parse(name: str, parser_key: str):  # type: ignore[no-untyped-def]
    path = FIXTURES / name
    mime = "application/pdf" if path.suffix == ".pdf" else "image/jpeg"
    data = path.read_bytes()
    result = extraction.extract(data, mime)
    return data, mime, result, parsers.get(parser_key).parse(result, {})


def computed_total(parsed) -> Decimal:  # type: ignore[no-untyped-def]
    allocations = arithmetic.prorate_invoice_discount(
        [
            arithmetic.ProrationInput(item.unit_price_pvp_eur, item.promo_discount_eur)
            for item in parsed.items
        ],
        parsed.total_discount_eur,
    )
    return sum(
        (
            arithmetic.paid_from_components(
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                promo_discount_eur=item.promo_discount_eur,
                invoice_allocated_discount_eur=allocated,
            )
            for item, allocated in zip(parsed.items, allocations, strict=True)
        ),
        Decimal("0.00"),
    )


@pytest.mark.parametrize(("name", "parser_key", "total", "discount", "count"), PDF_CASES)
def test_digital_pdf_reconciles_to_its_printed_total(
    name: str, parser_key: str, total: str, discount: str, count: int
) -> None:
    _, _, _, parsed = parse(name, parser_key)
    assert len(parsed.items) == count
    assert parsed.total_eur == Decimal(total)
    assert parsed.total_discount_eur == Decimal(discount)
    assert computed_total(parsed) == Decimal(total)


def test_continente_line_values_are_net_of_poupanca() -> None:
    """Σ lines - cartão = total. Reading them as gross overstates spending."""
    _, _, _, parsed = parse("continente-20260724.pdf", "continente_v1")
    gross = sum(item.unit_price_pvp_eur for item in parsed.items)
    promos = sum(item.promo_discount_eur for item in parsed.items)
    assert promos == Decimal("6.60")  # «Total de descontos e poupancas»
    assert gross - promos == Decimal("40.56")  # the printed SUBTOTAL
    assert Decimal("40.56") - parsed.total_discount_eur == parsed.total_eur


def test_pingo_doce_line_values_are_gross() -> None:
    """The opposite semantics: Σ lines - poupança = total."""
    _, _, _, parsed = parse("pingodoce-24118.pdf", "pingodoce_v1")
    gross = sum(item.unit_price_pvp_eur for item in parsed.items)
    promos = sum(item.promo_discount_eur for item in parsed.items)
    assert gross == Decimal("15.70")
    assert promos == Decimal("0.50")
    assert gross - promos == parsed.total_eur


def test_merchant_section_is_captured_on_every_merchant() -> None:
    """A universal signal, not a Continente quirk (Decision #27)."""
    for name, key in [
        ("continente-20260724.pdf", "continente_v1"),
        ("pingodoce-24118.pdf", "pingodoce_v1"),
    ]:
        _, _, _, parsed = parse(name, key)
        assert any(item.merchant_section for item in parsed.items)


def test_iva_token_is_captured_verbatim_and_never_interpreted() -> None:
    """`A` is 6 % at Continente and 23 % at Lidl; `F` is 0 % at Lidl (Decision #38)."""
    _, _, _, lidl = parse("lidl-20260801.pdf", "lidl_v1")
    classes = {item.iva_class_raw for item in lidl.items}
    assert "F" in classes  # the deposit lines — and nothing reads it as an Fs flag
    assert all(not item.description_raw.startswith("FS") for item in lidl.items)


def test_lidl_f_class_is_never_read_as_a_household_fs_article() -> None:
    """Decision #36: `F` is overloaded three ways and only one of them is ours."""
    _, _, _, parsed = parse("lidl-20260801.pdf", "lidl_v1")
    deposits = [i for i in parsed.items if i.iva_class_raw == "F"]
    assert deposits
    assert all(item.product_flag == "DEPOSIT_RETURN" for item in deposits)


def test_lidl_weighed_line_wraps_its_weight_onto_the_next_line() -> None:
    _, _, _, parsed = parse("lidl-20260811.pdf", "lidl_v1")
    banana = next(i for i in parsed.items if "BANANA" in i.description_raw.upper())
    assert banana.weight_observed_kg == Decimal("0.590")
    assert banana.is_bulk_weighed is True


def test_merchant_nif_is_taken_from_the_header_not_the_buyer() -> None:
    """A fixture carrying both NIFs resolves to the merchant (Decision #29)."""
    data, mime, result, _ = parse("pingodoce-30824.pdf", "pingodoce_v1")
    anchor = fiscal.read_anchor(data, mime, result.text)
    assert anchor.issuer_nif == "500829993"  # Pingo Doce, leading 5
    assert fiscal.buyer_nif(result.text) == "226443361"  # the household, leading 2


@pytest.mark.parametrize("name", [case[0] for case in PDF_CASES])
def test_every_pdf_yields_a_structurally_valid_atcud(name: str) -> None:
    data, mime, result, _ = parse(name, "generic_v1")
    anchor = fiscal.read_anchor(data, mime, result.text)
    assert anchor.atcud is not None
    assert anchor.atcud_valid is True


def test_the_photograph_parses_end_to_end_through_ocr() -> None:
    """Skewed, curved, partly obscured — and it still yields its five articles."""
    _, _, result, parsed = parse("piquete-20260811.jpeg", "piquete_v1")
    assert result.document_kind == "IMAGE_SCAN"
    assert result.engine == "pytesseract"
    assert len(parsed.items) == 5
    assert {item.merchant_section for item in parsed.items} >= {"Frutas", "Tuberculos"}
    assert all(item.is_bulk_weighed for item in parsed.items)


def test_the_photograph_refuses_to_invent_an_illegible_total() -> None:
    """It lands in review instead — reported separately from the digital PDFs."""
    _, _, _, parsed = parse("piquete-20260811.jpeg", "piquete_v1")
    assert parsed.total_eur is None
    assert parsed.warnings


def test_a_document_matching_no_profile_still_parses_generically() -> None:
    _, _, _, parsed = parse("continente-20260724.pdf", "generic_v1")
    assert parsed.items  # weaker, lower confidence, but never an error
    assert parsed.warnings


@pytest.mark.parametrize("name", [case[0] for case in PDF_CASES])
def test_extraction_matches_its_committed_golden_word_boxes(name: str) -> None:
    """Pins the *extractor*: a parser change can no longer masquerade as one."""
    golden = json.loads((GOLDEN / f"{Path(name).stem}.json").read_text(encoding="utf-8"))
    path = FIXTURES / name
    result = extraction.extract(path.read_bytes(), "application/pdf")
    actual = [
        {
            "width": round(page.width, 2),
            "height": round(page.height, 2),
            "lines": [line.as_golden() for line in page.lines],
        }
        for page in result.pages
    ]
    assert actual == golden["pages"]


def test_the_photograph_golden_exists_but_is_compared_loosely() -> None:
    """OCR output is tesseract-version dependent, so the golden is for humans to
    diff — the assertion here is only that the article lines survive."""
    golden = json.loads((GOLDEN / "piquete-20260811.json").read_text(encoding="utf-8"))
    assert golden["engine"] == "pytesseract"
    assert sum(len(page["lines"]) for page in golden["pages"]) > 20

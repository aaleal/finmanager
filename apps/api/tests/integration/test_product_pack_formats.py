"""Protects: *«a receipt line finds its pack format by value, at the gram»*.

`pack_variants` is the product's curated vocabulary of formats, not an entity a
line points at. Three properties keep that workable without a foreign key: the
weights are unique per product, both sides round to the same gram, and appending
a format never has to send the ones already there.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.errors import ValidationError
from app.services.receipts import products_service
from app.services.receipts.normalize import extract_pack_weight_kg
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


# --- Normalisation -------------------------------------------------------------


@pytest.mark.parametrize(
    ("weight", "expected"),
    [
        (Decimal("0.5"), "500 g"),
        (Decimal("0.045"), "45 g"),
        (Decimal("1"), "1 kg"),
        (Decimal("1.5"), "1,5 kg"),
        (Decimal("10.000"), "10 kg"),
    ],
)
def test_a_format_is_named_in_the_unit_a_human_would_say_it_in(
    weight: Decimal, expected: str
) -> None:
    assert products_service.pack_variant_label(weight) == expected


def test_a_weight_is_rounded_to_the_gram_and_nothing_finer() -> None:
    assert products_service.round_to_the_gram("0.5") == Decimal("0.500")
    assert products_service.round_to_the_gram(Decimal("0.4996")) == Decimal("0.500")
    assert products_service.round_to_the_gram(0) is None
    assert products_service.round_to_the_gram("") is None
    assert products_service.round_to_the_gram("abc") is None


def test_a_parsed_token_and_a_curated_format_compare_as_equals() -> None:
    """The whole match hangs on this: `500G` off a till must equal a typed 0,5."""
    parsed = products_service.round_to_the_gram(extract_pack_weight_kg("POLPA TOMATE GULOSO 500G"))
    assert parsed == products_service.round_to_the_gram("0.5")


# --- The curated list ----------------------------------------------------------


def test_formats_are_stored_as_strings_because_jsonb_cannot_hold_a_decimal(db: Session) -> None:
    product = products_service.create_product(
        db,
        canonical_name="Polpa de Tomate",
        brand="Guloso",
        pack_variants=[{"weight_kg": Decimal("0.5")}],
    )
    db.flush()
    assert product.pack_variants == [{"label": "500 g", "weight_kg": "0.500"}]


def test_a_format_without_a_weight_is_refused() -> None:
    """A weightless format answers none of the three questions it exists for."""
    with pytest.raises(ValidationError):
        products_service.sanitize_pack_variants([{"label": "Pack família"}])


def test_two_formats_cannot_share_a_weight() -> None:
    """Unique weights are what make the by-value match unambiguous."""
    with pytest.raises(ValidationError):
        products_service.sanitize_pack_variants(
            [{"weight_kg": "0.5"}, {"weight_kg": "0.4999", "label": "meio quilo"}]
        )


def test_formats_come_back_ordered_by_weight() -> None:
    cleaned = products_service.sanitize_pack_variants(
        [{"weight_kg": "1"}, {"weight_kg": "0.25"}, {"weight_kg": "0.5"}]
    )
    assert [variant["weight_kg"] for variant in cleaned] == ["0.250", "0.500", "1.000"]


# --- Appending -----------------------------------------------------------------


def test_adding_a_format_is_idempotent_on_the_weight(db: Session) -> None:
    """Two people reviewing at once must not drop each other's formats."""
    product = products_service.create_product(db, canonical_name="Arroz Carolino")
    products_service.add_pack_variant(db, product, weight_kg=Decimal("1"))
    products_service.add_pack_variant(db, product, weight_kg=Decimal("1.0004"))
    assert product.pack_variants == [{"label": "1 kg", "weight_kg": "1.000", "barcode": None}]


def test_a_shrunk_pack_joins_the_list_and_never_replaces_the_old_one(db: Session) -> None:
    """500 g → 450 g is the shrinkflation signal; overwriting it would erase it."""
    product = products_service.create_product(db, canonical_name="Polpa de Tomate", brand="Guloso")
    products_service.add_pack_variant(db, product, weight_kg=Decimal("0.5"))
    products_service.add_pack_variant(db, product, weight_kg=Decimal("0.45"))
    assert [variant["label"] for variant in product.pack_variants] == ["450 g", "500 g"]

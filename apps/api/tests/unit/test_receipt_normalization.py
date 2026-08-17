"""Protects: *«Normalize Portuguese product text before rapidfuzz token-set
ratio; match threshold ~0.78, review band ~0.70–0.78»* (brief §3 Ingestion) and
the M1 rubric bullet that every line resolves to a `MasterProduct`.

``description_norm`` is a **matching key and is never displayed**;
``description_raw`` stays verbatim as the audit trail against paper.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.services.receipts import catalogue
from app.services.receipts.normalize import (
    extract_pack_weight_kg,
    normalize_description,
    normalize_merchant_name,
    parse_decimal,
    unit_from_token,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("POLPA TOMATE GULOSO 500G", "POLPA TOMATE GULOSO 500G"),
        ("  Poupança   Imediata  ", "POUPANCA IMEDIATA"),
        # `º` must go before NFKD folds it into a bare `o`.
        ("ºSMOOTHIE TROP.PD 75", "SMOOTHIE TROP 75"),
        ("Mascarpone Galbani", "MASCARPONE GALBANI"),
        # Store-brand markers are dropped so the same genus meets across merchants.
        ("SKYR SOL CNT EQ MORANGO 150G", "SKYR SOL MORANGO 150G"),
    ],
)
def test_normalization_strips_accents_case_and_punctuation(raw: str, expected: str) -> None:
    assert normalize_description(raw) == expected


def test_size_tokens_survive_normalization() -> None:
    """A 500 g and a 1 kg bag are the same product but not the same pack."""
    assert "500G" in normalize_description("POLPA TOMATE GULOSO 500G")
    assert "1KG" in normalize_description("SAL GROSSO CONTINENTE 1KG")


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("POLPA TOMATE GULOSO 500G", Decimal("0.5000")),
        ("SAL GROSSO CONTINENTE 1KG", Decimal("1.0000")),
        ("AGUA S/GAS CONTINENTE 50CL", Decimal("0.5000")),
        ("LEITE UHT 1L", Decimal("1.0000")),
        # A multipack's weight is the product of its factors, not one unit's.
        ("LEITE PROTEINA PISTACIO 3X250ML", Decimal("0.7500")),
        ("SEM TAMANHO NENHUM", None),
    ],
)
def test_pack_weight_is_read_from_the_description(
    description: str, expected: Decimal | None
) -> None:
    assert extract_pack_weight_kg(description) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,19", Decimal("1.19")),
        ("1.234,56", Decimal("1234.56")),
        ("(0,10)", Decimal("-0.10")),
        ("0,590", Decimal("0.590")),
        ("", None),
        ("não é um número", None),
    ],
)
def test_portuguese_decimals_are_read_correctly(raw: str, expected: Decimal | None) -> None:
    assert parse_decimal(raw) == expected


def test_merchant_names_fold_case_and_whitespace() -> None:
    """`Mercadona` and `mercadona` are one shop; so are stray-whitespace twins."""
    assert normalize_merchant_name(" Mercadona ") == normalize_merchant_name("mercadona")
    assert normalize_merchant_name("Piquete da Fruta") == "PIQUETE DA FRUTA"


@pytest.mark.parametrize(
    ("token", "expected"),
    [("KG", "KG"), ("KIL", "KG"), ("GR", "G"), ("ML", "ML"), ("UN", "UN"), (None, "UN")],
)
def test_printed_unit_tokens_map_onto_the_stored_domain(token: str | None, expected: str) -> None:
    """One Piquete talão prints `KG` and `KIL` for the same unit."""
    assert unit_from_token(token) == expected


def test_a_short_catalogue_name_is_not_a_magnet_for_a_longer_line() -> None:
    """`token_set_ratio` alone scores a subset at a flat 100 (see `_combined`)."""
    good = catalogue._combined("POLPA TOMATE GULOSO 500G", "POLPA DE TOMATE GULOSO 500G")
    bad = catalogue._combined("POLPA TOMATE GULOSO 500G", "TOMATE")

    assert good >= catalogue.AUTO_ACCEPT * 100
    assert bad < catalogue.AUTO_ACCEPT * 100


def test_alias_confidence_starts_low_and_climbs() -> None:
    assert catalogue.alias_confidence(0) == Decimal("0.600")
    assert catalogue.alias_confidence(1) == Decimal("0.850")
    assert catalogue.alias_confidence(2) == Decimal("0.950")
    assert catalogue.alias_confidence(9) == Decimal("0.990")

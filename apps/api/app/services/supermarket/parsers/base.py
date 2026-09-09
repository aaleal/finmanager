"""Parser contract and the helpers every merchant parser shares.

A merchant-specific parser is a **class, not a config blob**: configuration alone
cannot handle Continente's net line values and Pingo Doce's gross ones equally
(Decision #28). ``field_hints`` on the profile tunes a parser without a deploy;
``parser_key`` names the class registered here.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from app.core.money import ZERO
from app.services.supermarket.extraction import Extraction, Line
from app.services.supermarket.normalize import parse_decimal

MONEY = re.compile(r"^\(?-?\d{1,3}(?:[.\u00a0]\d{3})*,\d{2}\)?$")
SIGNED_MONEY = re.compile(r"-?\d{1,3}(?:[.\u00a0]\d{3})*,\d{2}")


def is_money(token: str) -> bool:
    return bool(MONEY.match(token.strip().replace("€", "")))


def money_in(text: str) -> list[Decimal]:
    return [
        value
        for value in (parse_decimal(m) for m in SIGNED_MONEY.findall(text))
        if value is not None
    ]


def last_money(text: str) -> Decimal | None:
    values = money_in(text)
    return values[-1] if values else None


@dataclass(slots=True)
class ParsedItem:
    description_raw: str
    unit_price_pvp_eur: Decimal
    line_no: int | None = None
    merchant_section: str | None = None
    quantity: Decimal = Decimal("1")
    unit: str = "UN"
    promo_discount_eur: Decimal = ZERO
    promo_type: str | None = None
    iva_class_raw: str | None = None
    weight_observed_kg: Decimal | None = None
    is_bulk_weighed: bool = False
    product_flag: str | None = None
    #: 0-1, from the extraction engine's per-word confidences where it has them.
    text_confidence: Decimal = Decimal("0.980")


@dataclass(slots=True)
class ParsedReceipt:
    """What a parser extracted, before any of it is trusted."""

    merchant_name_hint: str | None = None
    merchant_nif_hint: str | None = None
    purchased_at: dt.datetime | None = None
    purchase_date: dt.date | None = None
    total_eur: Decimal | None = None
    #: The **invoice-level** credit only — it is what drives the proration ratio.
    #: Per-item promotions live on the items and must never be added here.
    total_discount_eur: Decimal = ZERO
    item_count: int | None = None
    items: list[ParsedItem] = field(default_factory=list)
    loyalty_scheme: str | None = None
    loyalty_card_masked: str | None = None
    loyalty_accrued_eur: Decimal = ZERO
    loyalty_discount_eur: Decimal = ZERO
    payment_methods: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ReceiptParser(Protocol):
    key: str
    display_name: str

    def parse(self, extraction: Extraction, hints: dict[str, Any]) -> ParsedReceipt: ...


# --- Line helpers ------------------------------------------------------------


def normalize_line(line: Line) -> str:
    """Collapse a clustered line to plain text, undoing double-struck glyphs.

    Lidl's PDF renders ``EUR/kg`` as ``EEUURR//kkgg``: the same glyph is drawn
    twice for a bold effect and pdfplumber faithfully reports both.
    """
    return " ".join(word.text for word in line.words)


DOUBLED = re.compile(r"((\w)\2){3,}")


def undouble(text: str) -> str:
    if not DOUBLED.search(text):
        return text
    out: list[str] = []
    index = 0
    while index < len(text):
        if index + 1 < len(text) and text[index] == text[index + 1]:
            out.append(text[index])
            index += 2
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


def slice_between(
    lines: list[str], start_pattern: str, end_patterns: tuple[str, ...]
) -> tuple[int, int]:
    """Index range of the article block, ``[start, end)``."""
    start = 0
    for index, text in enumerate(lines):
        if re.search(start_pattern, text, re.IGNORECASE):
            start = index + 1
            break
    end = len(lines)
    for index in range(start, len(lines)):
        if any(re.search(pattern, lines[index], re.IGNORECASE) for pattern in end_patterns):
            end = index
            break
    return start, end


def parse_pt_date(text: str) -> dt.date | None:
    match = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", text)
    if match:
        day, month, year = (int(g) for g in match.groups())
    else:
        iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not iso:
            return None
        year, month, day = (int(g) for g in iso.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_time(text: str) -> dt.time | None:
    match = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", text)
    if not match:
        return None
    hour, minute, second = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    try:
        return dt.time(hour, minute, second)
    except ValueError:
        return None

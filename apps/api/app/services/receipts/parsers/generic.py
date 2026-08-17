"""The generic fallback — a brand-new merchant is never a dead end.

It knows nothing about any layout: any line ending in a money token becomes an
article, and the largest ``TOTAL``-ish figure becomes the printed total. That is
deliberately weak, and the receipt simply arrives with lower confidence and goes
to review. Failing to parse is not an option this profile is allowed (FR-1.15).
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from app.core.money import ZERO
from app.services.receipts.extraction import Extraction
from app.services.receipts.normalize import parse_decimal
from app.services.receipts.parsers.base import (
    ParsedItem,
    ParsedReceipt,
    last_money,
    normalize_line,
    parse_pt_date,
    parse_time,
    undouble,
)

_LINE = re.compile(r"^(?P<body>.+?)\s+(?P<value>-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+[A-Z]{1,2})?\s*$")
_TOTAL_WORDS = re.compile(r"\bTOTAL\b|\bA\s*PAGAR\b|\bIMPORTE\b", re.IGNORECASE)
_SKIP = re.compile(
    r"NIF|IVA|ATCUD|SUBTOTAL|TROCO|CART[AÃ]O|MULTIBANCO|TAXA|DESCONTO|POUPAN|TERMINAL|AUT:",
    re.IGNORECASE,
)


class GenericParser:
    key = "generic_v1"
    display_name = "Perfil genérico"

    def parse(self, extraction: Extraction, hints: dict) -> ParsedReceipt:
        lines = [undouble(normalize_line(line)) for line in extraction.lines]
        parsed = ParsedReceipt()
        parsed.warnings.append(
            "Documento lido pelo perfil genérico: nenhum perfil de comerciante correspondeu."
        )

        for line in lines[:30]:
            date = parse_pt_date(line)
            if date:
                parsed.purchase_date = date
                parsed.purchased_at = dt.datetime.combine(date, parse_time(line) or dt.time(0, 0))
                break

        totals: list[Decimal] = []
        line_no = 0
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if _TOTAL_WORDS.search(line):
                amount = last_money(line)
                if amount is not None:
                    totals.append(amount)
                continue
            if _SKIP.search(line):
                continue
            match = _LINE.match(line)
            if not match:
                continue
            body = match.group("body").strip()
            if len(body) < 3 or not any(char.isalpha() for char in body):
                continue
            line_no += 1
            parsed.items.append(
                ParsedItem(
                    line_no=line_no,
                    description_raw=body,
                    unit_price_pvp_eur=parse_decimal(match.group("value")) or ZERO,
                    text_confidence=extraction.text_confidence * Decimal("0.7"),
                )
            )

        parsed.total_eur = max(totals) if totals else None
        parsed.item_count = len(parsed.items)
        return parsed

"""Lidl — IVA class **last**, deposits follow their item, weights wrap below.

    AGUA                          0,32 C   <- class letter last, not first
      Deposito 0.10               0,10 F   <- tara; F is the 0 % IVA class
    BIO IOGURTE NATURAL 0,37 x 2  0,74 B   <- unit price x qty, inline
    BANANA                        0,70 B
      0,590 kg x 1,19 EUR/kg               <- 0,590 kg x 1,19 = 0,70

`F` here is an **IVA class letter meaning 0 %**, and the document is numbered
``FS …`` for *fatura simplificada*. Neither has anything to do with the
household's Fs flag, which is never printed — so nothing in this parser may
pattern-match on `F` or `FS` to infer one (Decision #36).
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from app.core.money import ZERO
from app.services.supermarket.extraction import Extraction
from app.services.supermarket.normalize import parse_decimal
from app.services.supermarket.parsers.base import (
    ParsedItem,
    ParsedReceipt,
    normalize_line,
    parse_pt_date,
    undouble,
)

_ITEM = re.compile(r"^(?P<body>.+?)\s+(?P<value>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<iva>[A-Z])\s*$")
_INLINE_QTY = re.compile(r"^(?P<name>.+?)\s+(?P<unit_price>\d+(?:,\d+)?)\s*[xX]\s*(?P<qty>\d+)\s*$")
_WEIGHT_LINE = re.compile(
    r"^(?P<qty>\d+(?:,\d+)?)\s*(?P<unit>kg|g)\s*[xX]\s*(?P<price>\d+(?:,\d+)?)\s*EUR\s*/\s*(?P<per>kg|g)",
    re.IGNORECASE,
)


class LidlParser:
    key = "lidl_v1"
    display_name = "Lidl PDF"

    def parse(self, extraction: Extraction, hints: dict) -> ParsedReceipt:
        lines = [undouble(normalize_line(line)) for line in extraction.lines]
        parsed = ParsedReceipt(merchant_name_hint="Lidl")

        self._read_header(parsed, lines)
        self._read_items(parsed, lines, extraction.text_confidence)
        self._read_totals(parsed, lines)
        return parsed

    def _read_header(self, parsed: ParsedReceipt, lines: list[str]) -> None:
        date = None
        for line in lines:
            if "Data de Venda" in line:
                date = parse_pt_date(line)
                break
        time = None
        for line in lines:
            # `0000137 245047/005   01.08.26  11:47`
            stamp = re.search(r"\d{2}\.\d{2}\.\d{2}\s+(\d{2}:\d{2})", line)
            if stamp:
                time = dt.time(int(stamp.group(1)[:2]), int(stamp.group(1)[3:]))
                break
        if date:
            parsed.purchase_date = date
            parsed.purchased_at = dt.datetime.combine(date, time or dt.time(0, 0))

    def _read_items(
        self, parsed: ParsedReceipt, lines: list[str], text_confidence: Decimal
    ) -> None:
        started = False
        line_no = 0

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("TOTAL") or upper.startswith("MULTIBANCO"):
                break
            if set(line) <= {"-", "=", " "}:
                started = True
                continue

            weight = _WEIGHT_LINE.match(line)
            if weight and parsed.items:
                quantity = parse_decimal(weight.group("qty")) or Decimal("1")
                factor = Decimal("0.001") if weight.group("unit").lower() == "g" else Decimal("1")
                item = parsed.items[-1]
                item.quantity = quantity
                item.unit = "KG" if factor == Decimal("1") else "G"
                item.weight_observed_kg = quantity * factor
                item.is_bulk_weighed = True
                continue

            match = _ITEM.match(line)
            if not match:
                continue
            started = True
            body = match.group("body").strip()
            value = parse_decimal(match.group("value")) or ZERO

            quantity = Decimal("1")
            inline = _INLINE_QTY.match(body)
            if inline:
                body = inline.group("name").strip()
                quantity = Decimal(inline.group("qty"))

            if not body or not started:
                continue
            line_no += 1
            parsed.items.append(
                ParsedItem(
                    line_no=line_no,
                    description_raw=body,
                    unit_price_pvp_eur=value,
                    quantity=quantity,
                    iva_class_raw=match.group("iva"),
                    product_flag="DEPOSIT_RETURN" if body.upper().startswith("DEPOSITO") else None,
                    text_confidence=text_confidence,
                )
            )

    def _read_totals(self, parsed: ParsedReceipt, lines: list[str]) -> None:
        for line in lines:
            stripped = line.strip()
            if re.match(r"^Total\b", stripped, re.IGNORECASE):
                parsed.total_eur = parse_decimal(stripped.split()[-1])
            elif re.match(r"^(MULTIBANCO|DINHEIRO|NUMERARIO|CARTAO)\b", stripped, re.IGNORECASE):
                amount = parse_decimal(stripped.split()[-1])
                if amount is not None:
                    parsed.payment_methods.append(
                        {"method": stripped.split()[0].title(), "amount_eur": str(amount)}
                    )
        parsed.item_count = len(parsed.items)

"""Pingo Doce — IVA class **first and bare**, line values **gross**.

    FRUTAS E VEGETAIS                              <- section heading
     C COGUMELOS BRANC 300G  1,000 X 0,74   0,74   <- 1 kg x €0,74/kg
     C IO PROT COC GA2X150G                 1,29
         Poupança Imediata                (0,10)   <- parenthesised saving
    DEPÓSITO VOLTA
     I ºVALOR DEPÓSITO       2 X 0,10       0,20   <- tara

Verified on all four fixtures: ``Σ line values == TOTAL`` and
``TOTAL - TOTAL POUPANÇA == TOTAL A PAGAR``. The opposite of Continente, hence a
parser of its own rather than a shared one with a flag.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from app.core.money import ZERO
from app.services.receipts.extraction import Extraction
from app.services.receipts.normalize import parse_decimal, unit_from_token
from app.services.receipts.parsers.base import (
    ParsedItem,
    ParsedReceipt,
    last_money,
    money_in,
    normalize_line,
    parse_pt_date,
    parse_time,
    slice_between,
)

_ITEM = re.compile(
    r"^(?P<iva>[A-Z])\s+(?P<body>.+?)"
    r"(?:\s+(?P<qty>\d+(?:,\d+)?)\s*[Xx]\s*(?P<unit_price>\d+(?:,\d+)?))?"
    r"\s+(?P<value>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)
_PROMO = re.compile(r"Poupan[çc]a", re.IGNORECASE)
_CARD = re.compile(r"Cart[ãa]o\s*n[ºo°]?\s*:?\s*([*\d]{6,})", re.IGNORECASE)
_SECTION_STOP = ("RESUMO", "PAGAMENTOS", "TOTAL")


class PingoDoceParser:
    key = "pingodoce_v1"
    display_name = "Pingo Doce PDF"

    def parse(self, extraction: Extraction, hints: dict) -> ParsedReceipt:
        lines = [normalize_line(line) for line in extraction.lines]
        text = "\n".join(lines)
        parsed = ParsedReceipt(merchant_name_hint="Pingo Doce")

        self._read_header(parsed, lines, text)
        start, end = slice_between(lines, r"^\s*Artigos\s*$", (r"^\s*Resumo\s*$",))
        self._read_items(parsed, lines[start:end], extraction.text_confidence)
        self._read_totals(parsed, lines)
        return parsed

    def _read_header(self, parsed: ParsedReceipt, lines: list[str], text: str) -> None:
        date = None
        for line in lines:
            if "Data de emiss" in line:
                date = parse_pt_date(line)
                break
        time = None
        # `030823 2026-07-17 10:15 0764 0064 0876` — the till's own stamp.
        for line in lines:
            stamp = re.search(r"\b\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2})\b", line)
            if stamp:
                date = date or parse_pt_date(line)
                time = parse_time(stamp.group(1))
                break
        if date:
            parsed.purchase_date = date
            parsed.purchased_at = dt.datetime.combine(date, time or dt.time(0, 0))

        match = _CARD.search(text)
        if match:
            parsed.loyalty_scheme = "Cartão Poupa Mais"
            parsed.loyalty_card_masked = match.group(1)

    def _read_items(
        self, parsed: ParsedReceipt, block: list[str], text_confidence: Decimal
    ) -> None:
        section: str | None = None
        line_no = 0

        for raw in block:
            line = raw.strip()
            if not line or set(line) <= {"-", " ", "="}:
                continue

            if _PROMO.search(line):
                amount = last_money(line)
                if amount is not None and parsed.items:
                    parsed.items[-1].promo_discount_eur += abs(amount)
                    parsed.items[-1].promo_type = "ABSOLUTE"
                continue
            if "Total Dep" in line or line.upper().startswith(_SECTION_STOP):
                continue

            match = _ITEM.match(line)
            if match is None:
                if not money_in(line) and len(line) < 60:
                    section = line.strip()
                continue

            description = match.group("body").strip().lstrip("º°").strip()
            if not description:
                continue

            quantity = parse_decimal(match.group("qty")) or Decimal("1")
            value = parse_decimal(match.group("value")) or ZERO
            # A three-decimal quantity beside a €/unit price is the checkout
            # scale talking: 0,540 x 1,29 is 540 g of bananas, not 540 bananas.
            weighed = match.group("qty") is not None and len(match.group("qty").split(",")[-1]) == 3
            unit = "KG" if weighed and quantity != Decimal("1") else "UN"

            line_no += 1
            parsed.items.append(
                ParsedItem(
                    line_no=line_no,
                    merchant_section=section,
                    description_raw=description,
                    unit_price_pvp_eur=value,
                    quantity=quantity,
                    unit=unit_from_token(unit),
                    iva_class_raw=match.group("iva"),
                    weight_observed_kg=quantity if unit == "KG" else None,
                    is_bulk_weighed=unit == "KG",
                    product_flag=("DEPOSIT_RETURN" if "DEP" in description.upper()[:6] else None),
                    text_confidence=text_confidence,
                )
            )

    def _read_totals(self, parsed: ParsedReceipt, lines: list[str]) -> None:
        total: Decimal | None = None
        total_to_pay: Decimal | None = None
        for line in lines:
            upper = line.upper().strip()
            if upper.startswith("TOTAL A PAGAR"):
                total_to_pay = last_money(line)
            elif upper.startswith("TOTAL POUPAN"):
                continue  # already captured per item; adding it here double-counts
            elif upper.startswith("TOTAL PAGO"):
                continue
            elif upper.startswith("TOTAL"):
                total = total or last_money(line)
            elif re.match(r"^(Multibanco|Numerario|Dinheiro|Cart[ãa]o)\b", line, re.I):
                amount = last_money(line)
                if amount is not None:
                    parsed.payment_methods.append(
                        {"method": line.split()[0].title(), "amount_eur": str(amount)}
                    )

        # A one-article receipt prints only «TOTAL A PAGAR» and no gross TOTAL.
        parsed.total_eur = total_to_pay if total_to_pay is not None else total
        parsed.item_count = len(parsed.items)

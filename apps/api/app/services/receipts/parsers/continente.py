"""Continente — IVA token **first**, line values already **net** of POUPANCA.

    Mercearia Salgada:                  <- the merchant's own section heading
    (C) POLPA TOMATE GULOSO 500G  1,19  <- (class) description   value
        POUPANCA                 0,30   <- saving on the line above
    (C) BAT FR AZEITE CONTINENTE 150G
          2 X 1,45               2,90   <- quantity x unit price, wrapped

Verified against all four fixtures: ``Σ line values == SUBTOTAL`` and
``SUBTOTAL - Desconto Cartao Utilizado == TOTAL A PAGAR``. So the printed value
is **net of POUPANCA**, and the gross is ``value + POUPANCA``. Getting this
backwards silently overstates the household's spending (Decision #28).
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
    money_in,
    normalize_line,
    parse_pt_date,
    parse_time,
    slice_between,
)

# `(C) DESCRIPTION 1,19`, and the bare `NS VALOR DE DEPOSITO UN 0,10` used for taras.
_ITEM = re.compile(r"^\((?P<iva>[A-Z]{1,2})\)\s+(?P<rest>.+)$")
_BARE_ITEM = re.compile(r"^(?P<iva>NS)\s+(?P<rest>.+)$")
_QUANTITY_LINE = re.compile(r"^(?P<qty>\d+(?:,\d+)?)\s*[Xx]\s*(?P<unit_price>[\d.,]+)$")
_SECTION = re.compile(r"^(?P<name>[A-Za-zÀ-ÿ0-9&./ \-]+):$")
_CARD = re.compile(r"Cartao cliente n[ºo°]?\s*([X\d]+)", re.IGNORECASE)


class ContinenteParser:
    key = "continente_v1"
    display_name = "Continente PDF"

    def parse(self, extraction: Extraction, hints: dict) -> ParsedReceipt:
        lines = [normalize_line(line) for line in extraction.lines]
        text = "\n".join(lines)
        parsed = ParsedReceipt(merchant_name_hint="Continente")

        self._read_header(parsed, lines, text)
        start, end = slice_between(
            lines, r"IVA\s+DESCRICAO", (r"^SUBTOTAL\b", r"^TOTAL\s+A\s+PAGAR")
        )
        self._read_items(parsed, lines[start:end], extraction.text_confidence)
        self._read_totals(parsed, lines, text)
        return parsed

    # --- header ---------------------------------------------------------------
    def _read_header(self, parsed: ParsedReceipt, lines: list[str], text: str) -> None:
        for line in lines[:20]:
            if line.startswith("Nro:") or "Fatura Simplificada" in line:
                date = parse_pt_date(line)
                time = parse_time(line)
                if date:
                    parsed.purchase_date = date
                    parsed.purchased_at = dt.datetime.combine(date, time or dt.time(0, 0))
                    break
        match = _CARD.search(text)
        if match:
            parsed.loyalty_scheme = "Cartão Continente"
            parsed.loyalty_card_masked = match.group(1)

    # --- items ----------------------------------------------------------------
    def _read_items(
        self, parsed: ParsedReceipt, block: list[str], text_confidence: Decimal
    ) -> None:
        section: str | None = None
        line_no = 0

        for raw in block:
            line = raw.strip()
            if not line:
                continue

            if line.upper().startswith("POUPANCA"):
                self._apply_promo(parsed, line)
                continue
            # Loyalty *accrual*, not a discount: it credits the card, it does not
            # reduce what this receipt cost.
            if line.upper().startswith("ACUMULA EM CARTAO"):
                parsed.loyalty_accrued_eur += last_money(line) or ZERO
                continue
            if line.upper().startswith("IVA NAO SUJEITO"):
                continue

            section_match = _SECTION.match(line)
            if section_match and not money_in(line):
                section = section_match.group("name").strip()
                continue

            quantity_match = _QUANTITY_LINE.match(line)
            if quantity_match is None:
                # `2 X 1,45   2,90` — the wrapped continuation of the line above.
                wrapped = re.match(
                    r"^(?P<qty>\d+(?:,\d+)?)\s*[Xx]\s*(?P<unit_price>[\d.,]+)\s+(?P<value>[\d.,]+)$",
                    line,
                )
                if wrapped and parsed.items:
                    item = parsed.items[-1]
                    item.quantity = parse_decimal(wrapped.group("qty")) or Decimal("1")
                    item.unit_price_pvp_eur = parse_decimal(wrapped.group("value")) or ZERO
                    continue

            match = _ITEM.match(line) or _BARE_ITEM.match(line)
            if not match:
                continue

            rest = match.group("rest").strip()
            value = None
            tokens = rest.split()
            if (
                tokens
                and (candidate := parse_decimal(tokens[-1])) is not None
                and "," in tokens[-1]
            ):
                value = candidate
                description = " ".join(tokens[:-1]).strip()
            else:
                # A multi-buy prints its description alone and its value on the
                # wrapped line below; the value arrives on the next pass.
                description = rest

            if not description:
                continue
            line_no += 1
            parsed.items.append(
                ParsedItem(
                    line_no=line_no,
                    merchant_section=section,
                    description_raw=description,
                    unit_price_pvp_eur=value if value is not None else ZERO,
                    iva_class_raw=match.group("iva"),
                    product_flag=("DEPOSIT_RETURN" if "DEPOSITO" in description.upper() else None),
                    text_confidence=text_confidence,
                )
            )

    def _apply_promo(self, parsed: ParsedReceipt, line: str) -> None:
        if not parsed.items:
            return
        amount = last_money(line)
        if amount is None:
            return
        item = parsed.items[-1]
        item.promo_discount_eur += amount
        item.promo_type = "ABSOLUTE"
        # The printed value is net, so the gross is value + saving.
        item.unit_price_pvp_eur += amount

    # --- totals ---------------------------------------------------------------
    def _read_totals(self, parsed: ParsedReceipt, lines: list[str], text: str) -> None:
        for line in lines:
            upper = line.upper()
            if upper.startswith("TOTAL") and "A PAGAR" in upper:
                parsed.total_eur = last_money(line)
            elif upper.startswith("DESCONTO CARTAO"):
                parsed.total_discount_eur = last_money(line) or ZERO
            elif upper.startswith("UTILIZOU DO SEU CARTAO"):
                parsed.loyalty_discount_eur = last_money(line) or ZERO
            elif upper.startswith("ACUMULOU NO SEU CARTAO"):
                parsed.loyalty_accrued_eur = last_money(line) or parsed.loyalty_accrued_eur
            elif re.match(r"^(Cartao Credito|Multibanco|Numerario|Dinheiro)\b", line, re.I):
                amount = last_money(line)
                if amount is not None:
                    parsed.payment_methods.append(
                        {"method": line.split()[0].title(), "amount_eur": str(amount)}
                    )

        if parsed.total_eur is None:
            match = re.search(r"SUBTOTAL\s+([\d.,]+)", text)
            parsed.total_eur = parse_decimal(match.group(1)) if match else None
            parsed.warnings.append("Sem linha «TOTAL A PAGAR»; usado o SUBTOTAL.")
        parsed.item_count = len(parsed.items)

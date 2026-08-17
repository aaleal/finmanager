"""Piquete da Fruta — quantity **first**, IVA as a literal percentage, all by weight.

    QTD  UNI DESCRICAO           IVA    VALOR
    --FRUTAS--
    0,302 KG  NECTARINA MEDIA     6%     0,60
      Preco: 1,99/KG                            <- €/kg printed outright
    0,45  KIL BATATA OLHO DE      6%     0,67   <- "KIL" and "KG" on one receipt

This is the only **photograph** in the fixture set, so it is the fixture that
exercises OCR on a curved, skewed thermal slip. Its lines are expected to land in
review far more often than a digital PDF's — that is reported, not hidden.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from app.core.money import ZERO
from app.services.receipts.extraction import Extraction
from app.services.receipts.normalize import parse_decimal, strip_accents, unit_from_token
from app.services.receipts.parsers.base import (
    ParsedItem,
    ParsedReceipt,
    normalize_line,
    parse_pt_date,
    parse_time,
)

# OCR on a curved thermal slip reads `6%` as `6x` and `KIL` as `KlL`, so the IVA
# token is matched loosely and split off the description tail rather than being
# required in place. What it must never do is *repair* a misread price.
_ITEM = re.compile(
    r"^(?P<qty>\d+[,.]\d+|\d+)\s+(?P<unit>KGS?|K[I1L]L|KIt|GRS?|G|UN|LTS?|L)\s+"
    r"(?P<rest>.+?)\s+(?P<value>\d+[,.]\d{2})\s*$",
    re.IGNORECASE,
)
_IVA_TAIL = re.compile(r"^(?P<description>.+?)\s+(?P<iva>\d{1,2}\s*[%xX°]?|[A-Z]{1,2}\d?%?)$")
_PER_KG = re.compile(r"Preco\s*[:;]?\s*(?P<price>\d+[,.]\d+)\s*/\s*(?P<unit>KG|KIL)", re.IGNORECASE)
_SECTION = re.compile(r"^[-=]{2,}\s*(?P<name>[A-ZÀ-ÿ ]+?)\s*[-=]{2,}$")
_TOTAL = re.compile(r"TOTAL\s*[:;.]?\s*(?:Eur)?\s*(?P<value>\d+[,.]\d{2})", re.IGNORECASE)


class PiqueteParser:
    key = "piquete_v1"
    display_name = "Piquete da Fruta (fotografia)"

    def parse(self, extraction: Extraction, hints: dict) -> ParsedReceipt:
        lines = [normalize_line(line) for line in extraction.lines]
        parsed = ParsedReceipt(merchant_name_hint="Piquete da Fruta")

        for line in lines[:25]:
            date = parse_pt_date(line)
            if date:
                parsed.purchase_date = date
                parsed.purchased_at = dt.datetime.combine(date, parse_time(line) or dt.time(0, 0))
                break

        section: str | None = None
        line_no = 0
        for raw in lines:
            line = strip_accents(raw).strip()
            if not line:
                continue

            section_match = _SECTION.match(line)
            if section_match:
                section = section_match.group("name").strip().title()
                continue

            per_kg = _PER_KG.search(line)
            if per_kg and parsed.items:
                # The €/kg is printed, so it is captured — never derived from a
                # guessed weight (FR-1.12).
                parsed.items[-1].is_bulk_weighed = True
                continue

            match = _ITEM.match(line)
            if not match:
                total = _TOTAL.search(line)
                if total and "INCIDENCIA" not in line.upper():
                    parsed.total_eur = parse_decimal(total.group("value"))
                continue

            rest = match.group("rest").strip()
            iva_match = _IVA_TAIL.match(rest)
            description = (iva_match.group("description") if iva_match else rest).strip()
            iva = iva_match.group("iva").replace(" ", "")[:4] if iva_match else None
            if not description:
                continue

            quantity = parse_decimal(match.group("qty")) or Decimal("1")
            unit = unit_from_token(match.group("unit"))
            line_no += 1
            parsed.items.append(
                ParsedItem(
                    line_no=line_no,
                    merchant_section=section,
                    description_raw=description,
                    unit_price_pvp_eur=parse_decimal(match.group("value")) or ZERO,
                    quantity=quantity,
                    unit=unit,
                    iva_class_raw=iva,
                    weight_observed_kg=quantity if unit in {"KG", "G"} else None,
                    is_bulk_weighed=unit in {"KG", "G"},
                    text_confidence=extraction.text_confidence,
                )
            )

        if parsed.total_eur is None:
            parsed.warnings.append(
                "Total ilegível na fotografia: a fatura vai para revisão em vez de ser inventado."
            )
        parsed.item_count = len(parsed.items)
        return parsed

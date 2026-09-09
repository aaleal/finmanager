"""The Portuguese fiscal anchor: ATCUD, the AT QR code, and NIF disambiguation.

The QR defined by Portaria 195/2020 encodes *invoice-level* fields only — issuer
NIF, buyer NIF, document type and date, the unique document id, the ATCUD, the
VAT breakdown per rate and the gross total. It carries **no line items**. When it
is present and structurally valid it is the **highest-confidence anchor in the
module**: its NIF resolves the merchant exactly, its date sets ``purchase_date``,
and its total becomes the reference that item-level arithmetic reconciles against.

A missing or malformed QR lowers confidence and flags for review. It never blocks
ingestion — the ATCUD is also printed as plain text on every fixture we have, so
a QR that will not decode still yields the reference (Decision #24).
"""

from __future__ import annotations

import datetime as dt
import io
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.services.supermarket.normalize import parse_decimal, strip_accents

logger = logging.getLogger(__name__)

# `ATCUD:JFP767JJ-035904` — an AT-issued validation code, a dash, a sequence.
_ATCUD_IN_TEXT = re.compile(r"ATCUD\s*[:.]?\s*([A-Z0-9]{4,}\s*-\s*\d+)", re.IGNORECASE)
_ATCUD_SHAPE = re.compile(r"^[A-Z0-9]{8}-\d{1,20}$")
_NIF_IN_TEXT = re.compile(r"\b(?:PT)?\s?(\d{9})\b")

#: First digit decides: natural persons vs organisations (Decision #29).
_PERSON_PREFIXES = frozenset("123")
_ORGANISATION_PREFIXES = frozenset("5689")


def nif_checksum_valid(nif: str) -> bool:
    """Portuguese NIF checksum (modulo 11)."""
    if not nif.isdigit() or len(nif) != 9:
        return False
    total = sum(int(digit) * (9 - index) for index, digit in enumerate(nif[:8]))
    remainder = total % 11
    check = 0 if remainder < 2 else 11 - remainder
    return check == int(nif[8])


def is_organisation_nif(nif: str) -> bool:
    return bool(nif) and nif[0] in _ORGANISATION_PREFIXES


def is_person_nif(nif: str) -> bool:
    return bool(nif) and nif[0] in _PERSON_PREFIXES


def find_nifs(text: str) -> list[str]:
    """Every checksum-valid NIF in the document, in reading order."""
    seen: list[str] = []
    for match in _NIF_IN_TEXT.finditer(text or ""):
        nif = match.group(1)
        if nif_checksum_valid(nif) and nif not in seen:
            seen.append(nif)
    return seen


def merchant_nif(text: str) -> str | None:
    """Pick the *merchant's* NIF out of a receipt that may print two.

    Continente prints its own ``PT501591109`` and the household's
    ``PT209362367``; the leading ``5`` versus ``2`` separates them with no
    positional guessing. Header position is only the tie-break when both are
    organisational.
    """
    candidates = find_nifs(text)
    organisations = [n for n in candidates if is_organisation_nif(n)]
    if organisations:
        return organisations[0]
    return None


def buyer_nif(text: str) -> str | None:
    for nif in find_nifs(text):
        if is_person_nif(nif):
            return nif
    return None


@dataclass(slots=True)
class FiscalAnchor:
    atcud: str | None = None
    atcud_valid: bool | None = None
    atcud_reason: str | None = None
    issuer_nif: str | None = None
    buyer_nif: str | None = None
    document_type: str | None = None
    document_date: dt.date | None = None
    document_id: str | None = None
    gross_total_eur: Decimal | None = None
    total_vat_eur: Decimal | None = None
    source: str = "none"  # qr | text | none
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def has_qr(self) -> bool:
        return self.source == "qr"


def _validate_atcud(atcud: str) -> tuple[bool, str | None]:
    normalized = atcud.replace(" ", "").upper()
    if not _ATCUD_SHAPE.match(normalized):
        return False, "Formato ATCUD inesperado (esperado 8 caracteres, hífen, sequência)."
    return True, None


def atcud_from_text(text: str) -> tuple[str | None, bool | None, str | None]:
    match = _ATCUD_IN_TEXT.search(strip_accents(text or ""))
    if not match:
        return None, None, "Nenhum ATCUD legível no documento."
    raw = match.group(1).replace(" ", "").upper()
    valid, reason = _validate_atcud(raw)
    return raw, valid, reason


def parse_qr_payload(payload: str) -> dict[str, str]:
    """Split the ``A:…*B:…*C:…`` field string defined by Portaria 195/2020."""
    fields: dict[str, str] = {}
    for chunk in payload.split("*"):
        key, separator, value = chunk.partition(":")
        if separator:
            fields[key.strip().upper()] = value.strip()
    return fields


def anchor_from_qr(payload: str) -> FiscalAnchor | None:
    fields = parse_qr_payload(payload)
    if "A" not in fields or "H" not in fields:
        return None

    anchor = FiscalAnchor(source="qr", raw=fields)
    anchor.issuer_nif = fields.get("A") or None
    buyer = fields.get("B") or None
    anchor.buyer_nif = None if buyer in {"999999990", "", None} else buyer
    anchor.document_type = fields.get("D") or None
    anchor.document_id = fields.get("G") or None
    anchor.atcud = (fields.get("H") or "").upper() or None
    if anchor.atcud:
        anchor.atcud_valid, anchor.atcud_reason = _validate_atcud(anchor.atcud)

    raw_date = fields.get("F", "")
    if len(raw_date) == 8 and raw_date.isdigit():
        try:
            anchor.document_date = dt.date(
                int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8])
            )
        except ValueError:
            anchor.document_date = None

    anchor.gross_total_eur = parse_decimal(fields.get("O"))
    anchor.total_vat_eur = parse_decimal(fields.get("N"))
    return anchor


def decode_qr(data: bytes, mime_type: str) -> str | None:
    """Best-effort QR read. Every failure degrades to the printed ATCUD text."""
    try:
        from pyzbar.pyzbar import decode as zbar_decode
    except Exception:  # pragma: no cover - libzbar missing is a deployment concern
        logger.info("pyzbar unavailable; falling back to the printed ATCUD")
        return None

    try:
        from PIL import Image

        images: list[object] = []
        if mime_type == "application/pdf":
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages[:2]:
                    images.append(page.to_image(resolution=220).original)
        else:
            images.append(Image.open(io.BytesIO(data)))

        for image in images:
            for symbol in zbar_decode(image):  # type: ignore[arg-type]
                payload = symbol.data.decode("utf-8", errors="replace")
                if payload.startswith("A:"):
                    return payload
    except Exception as exc:  # pragma: no cover - a corrupt image must not stop ingestion
        logger.info("QR decoding failed (%s); falling back to the printed ATCUD", exc)
    return None


def read_anchor(data: bytes, mime_type: str, text: str) -> FiscalAnchor:
    """The QR when it decodes, the printed ATCUD otherwise, honest about which."""
    payload = decode_qr(data, mime_type)
    if payload:
        anchor = anchor_from_qr(payload)
        if anchor is not None:
            return anchor

    atcud, valid, reason = atcud_from_text(text)
    return FiscalAnchor(
        atcud=atcud,
        atcud_valid=valid,
        atcud_reason=reason,
        issuer_nif=merchant_nif(text),
        buyer_nif=buyer_nif(text),
        source="text" if atcud else "none",
    )

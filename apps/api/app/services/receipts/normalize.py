"""Text normalization — the only key a receipt line gives us.

Real *talões* print neither an EAN nor an article code (Decision #23), so a
truncated, accent-stripped, abbreviation-ridden description is the whole basis
for matching. ``description_norm`` produced here is a **matching key and is never
displayed**; ``description_raw`` stays verbatim as the audit trail against paper.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Pack-size tokens carry real information (Decision #25) so they are extracted
# before being stripped, never silently discarded.
_SIZE_TOKEN = re.compile(
    r"(?<![A-Z0-9])(\d+(?:[.,]\d+)?)\s?(KGS?|KILOS?|KIL|GRS?|GRAMAS?|GR|G|LTS?|LITROS?|L|MLS?|ML|CL|UN|UNI|UND)(?![A-Z])",
    re.IGNORECASE,
)
_MULTIPACK = re.compile(
    r"(?<![A-Z0-9])(\d+)\s?[X*]\s?(\d+(?:[.,]\d+)?)\s?(KG|G|GR|L|ML|CL)\b", re.IGNORECASE
)
_PUNCTUATION = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")

# Store-brand markers. Dropping them is what lets Continente's own-brand and Pingo
# Doce's own-brand of the same genus meet in one product, which is the whole point
# of a cross-merchant €/kg comparison. The brand itself lives on `MasterProduct`.
_NOISE_WORDS = frozenset({"CNT", "PD", "EQ", "SEL", "ORIG", "ORIGINAL"})

# Pingo Doce prefixes some lines with `º`. NFKD folds it into a bare `o`, so it has
# to go **before** accents are stripped or `ºSMOOTHIE` becomes `OSMOOTHIE`.
_ORDINAL_MARKERS = str.maketrans({"º": " ", "ª": " ", "°": " "})

_TO_KG: dict[str, Decimal] = {
    "KG": Decimal("1"),
    "KGS": Decimal("1"),
    "KILO": Decimal("1"),
    "KILOS": Decimal("1"),
    "KIL": Decimal("1"),
    "G": Decimal("0.001"),
    "GR": Decimal("0.001"),
    "GRS": Decimal("0.001"),
    "GRAMA": Decimal("0.001"),
    "GRAMAS": Decimal("0.001"),
    # Volume is priced per litre; treating 1 L as 1 kg is the household's own
    # convention for liquids and is what makes €/kg comparable across a shelf.
    "L": Decimal("1"),
    "LT": Decimal("1"),
    "LTS": Decimal("1"),
    "LITRO": Decimal("1"),
    "LITROS": Decimal("1"),
    "ML": Decimal("0.001"),
    "MLS": Decimal("0.001"),
    "CL": Decimal("0.01"),
}


def strip_accents(value: str) -> str:
    """Thermal printers corrupt ``ç``/``ã``/``€`` — matching never depends on them."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_description(raw: str) -> str:
    """Accent-, case- and punctuation-stripped matching key.

    Size tokens are kept: ``POLPA TOMATE GULOSO 500G`` and the 1 kg bag are the
    same product but *not* the same pack, and the token is what tells them apart.
    """
    text = strip_accents((raw or "").translate(_ORDINAL_MARKERS)).upper()
    text = _PUNCTUATION.sub(" ", text)
    tokens = [t for t in _SPACES.split(text) if t and t not in _NOISE_WORDS]
    return " ".join(tokens).strip()


def normalize_merchant_name(raw: str) -> str:
    """``Mercadona`` and ``mercadona`` are one shop; so are stray-whitespace twins."""
    return _SPACES.sub(" ", strip_accents(raw or "").upper()).strip()


def parse_decimal(raw: str | None) -> Decimal | None:
    """Read a Portuguese-formatted number (``1.234,56`` or ``0,590``)."""
    if raw is None:
        return None
    text = raw.strip().replace("\u00a0", "").replace(" ", "").replace("€", "")
    if not text:
        return None
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.strip("()").lstrip("+-")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def extract_pack_weight_kg(description: str) -> Decimal | None:
    """Recover the pack weight from the description, where the till puts it.

    ``3X250G`` is 0,750 kg, not 0,250 — a multipack's weight is the product of
    its factors, and getting that wrong silently halves or triples a €/kg trend.
    """
    text = strip_accents(description or "").upper()

    multipack = _MULTIPACK.search(text)
    if multipack:
        count = Decimal(multipack.group(1))
        size = parse_decimal(multipack.group(2))
        factor = _TO_KG.get(multipack.group(3).upper())
        if size is not None and factor is not None:
            return (count * size * factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    best: Decimal | None = None
    for match in _SIZE_TOKEN.finditer(text):
        size = parse_decimal(match.group(1))
        factor = _TO_KG.get(match.group(2).upper())
        if size is None or factor is None:
            continue
        candidate = (size * factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if candidate > 0 and (best is None or candidate > best):
            best = candidate
    return best


def unit_from_token(token: str | None) -> str:
    """Map a printed unit token onto the stored ``unit`` domain."""
    if not token:
        return "UN"
    key = strip_accents(token).upper().strip().rstrip(".")
    if key in {"KG", "KGS", "KIL", "KILO", "KILOS"}:
        return "KG"
    if key in {"G", "GR", "GRS", "GRAMA", "GRAMAS"}:
        return "G"
    if key in {"L", "LT", "LTS", "LITRO", "LITROS"}:
        return "L"
    if key in {"ML", "MLS", "CL"}:
        return "ML"
    if key in {"PACK", "EMB", "CX"}:
        return "PACK"
    return "UN"

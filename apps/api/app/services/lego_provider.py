"""LEGO metadata provider.

Brickset is the single configured provider (M9 FR-9.2). It is opt-in, off by
default, and contacted **only** on an explicit user action — never on a schedule,
never during a render. A failure is never a dead end: the caller falls back to
the identical manual form.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.schemas.lego import LookupResult
from app.services import settings_service

BRICKSET_BASE = "https://brickset.com/api/v3.asmx"
BRICKSET_ENDPOINT = f"{BRICKSET_BASE}/getSets"

#: Which manuals are worth keeping — see ADR-0040.
KEPT_LANGUAGE_PREFIXES = ("EN", "PT")

#: `10280_ENGB_Info_Booklet` → `ENGB`. A building instruction («BI 3106, 80+4,
#: 10280 V29») matches nothing, which is exactly what marks it as universal.
_LANGUAGE_TOKEN = re.compile(r"_([A-Z]{2,5})_")

DISABLED_MESSAGE = (
    "A consulta ao Brickset está desativada. Ative-a em Definições "
    "e indique a chave da API, ou preencha os dados manualmente."
)


@dataclass(frozen=True)
class RemoteImage:
    url: str


@dataclass(frozen=True)
class RemoteInstruction:
    url: str
    description: str
    language: str | None


class MetadataProvider(Protocol):
    name: str
    enabled: bool

    def lookup(self, set_number: str) -> LookupResult: ...

    def additional_images(self, set_number: str) -> list[RemoteImage]: ...

    def instructions(self, set_number: str) -> list[RemoteInstruction]: ...


def normalize_set_number(raw: str) -> str:
    """Brickset keys sets as ``10307-1``; users type ``10307``."""
    value = raw.strip().upper()
    return value if re.search(r"-\d+$", value) else f"{value}-1"


def _set_number_candidates(raw: str) -> list[str]:
    """A bare number (no explicit ``-N``) is ambiguous: most sets are ``-1``, but a
    closed collectible pack (e.g. the F1 car collectibles) is keyed ``-0`` — the
    box, not any one item inside. Try the pack first, then the ordinary set
    (ADR-0050). Once a pack is opened its contents get their own explicit ``-1``,
    ``-2``, ... numbers typed by hand, which never reach this fallback at all —
    the regex below only fires for a truly bare number."""
    value = raw.strip().upper()
    if re.search(r"-\d+$", value):
        return [value]
    return [f"{value}-0", f"{value}-1"]


def _decimal(value: Any, places: str = "0.01") -> Decimal | None:
    if value in (None, "", 0):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(places))
    except (InvalidOperation, TypeError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _brickset_date(raw: Any) -> dt.date | None:
    """Brickset dates are ISO timestamps; a bare year means the end of it."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    head = raw[:4]
    return dt.date(int(head), 12, 31) if head.isdigit() else None


def _january_first(year: Any) -> dt.date | None:
    """Fallback when a set has no ``launchDate``: anchor it to the 1st of January."""
    try:
        return dt.date(int(year), 1, 1)
    except (TypeError, ValueError):
        return None


def instruction_language(description: str) -> str | None:
    """The language a manual is written in, or ``None`` if it is picture-only."""
    match = _LANGUAGE_TOKEN.search(description or "")
    return match.group(1) if match else None


def is_kept_instruction(language: str | None) -> bool:
    """Universal manuals and the two languages this household reads (ADR-0040)."""
    return language is None or language.startswith(KEPT_LANGUAGE_PREFIXES)


def _retirement_date(data: dict[str, Any]) -> dt.date | None:
    """``exitDate`` is the set's own retirement (ADR-0039), not a shop's last day."""
    exit_date = _brickset_date(data.get("exitDate"))
    if exit_date is not None:
        return exit_date
    # No exitDate: the latest day any LEGO.com store still had it is the best
    # evidence there is that it is gone.
    dates = [
        value
        for value in (
            _brickset_date(region.get("dateLastAvailable"))
            for region in (data.get("LEGOCom") or {}).values()
            if isinstance(region, dict)
        )
        if value is not None
    ]
    return max(dates) if dates else None


def _result_of(data: dict[str, Any]) -> LookupResult:
    lego_com = data.get("LEGOCom") or {}
    # The German store quotes euros; many older/retired sets were never sold
    # there, so fall back to the US dollar price at 1:1 rather than leave the
    # RRP empty (ADR-0051) — still better than no figure at all.
    retail = lego_com.get("DE") or lego_com.get("US") or {}
    age_range = data.get("ageRange") or {}
    dimensions = data.get("dimensions") or {}

    return LookupResult(
        found=True,
        set_number=str(data.get("number") or "").strip() or None,
        name=data.get("name"),
        theme=data.get("theme"),
        subtheme=data.get("subtheme"),
        release_date=_brickset_date(data.get("launchDate")) or _january_first(data.get("year")),
        retirement_date=_retirement_date(data),
        piece_count=data.get("pieces"),
        minifig_count=data.get("minifigs"),
        age_min=_integer(age_range.get("min")),
        age_max=_integer(age_range.get("max")),
        box_height_cm=_decimal(dimensions.get("height"), "0.1"),
        box_width_cm=_decimal(dimensions.get("width"), "0.1"),
        box_depth_cm=_decimal(dimensions.get("depth"), "0.1"),
        box_weight_kg=_decimal(dimensions.get("weight"), "0.001"),
        rrp_eur=_decimal(retail.get("retailPrice")),
        image_url=(data.get("image") or {}).get("imageURL"),
        short_description=(data.get("extendedData") or {}).get("notes"),
        additional_image_count=_integer(data.get("additionalImageCount")) or 0,
        instruction_count=_integer(data.get("instructionsCount")) or 0,
    )


class BricksetProvider:
    name = "brickset"
    enabled = True

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _call(self, method: str, **params: str) -> dict[str, Any]:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{BRICKSET_BASE}/{method}", params={"apiKey": self.api_key, **params}
            )
            response.raise_for_status()
            payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _set_data(self, set_number: str) -> dict[str, Any] | None:
        """Tries each candidate variant in order (ADR-0050) and returns the first
        one Brickset actually has — the caller can tell which one matched from
        the returned ``number`` field."""
        for candidate in _set_number_candidates(set_number):
            payload = self._call(
                "getSets",
                userHash="",
                params=json.dumps({"setNumber": candidate}),
            )
            if payload.get("status") != "success" or not payload.get("sets"):
                continue
            first = payload["sets"][0]
            if isinstance(first, dict):
                return first
        return None

    def lookup(self, set_number: str) -> LookupResult:
        try:
            data = self._set_data(set_number)
        except (httpx.HTTPError, ValueError) as exc:
            return LookupResult(
                found=False,
                message=f"Brickset indisponível ({exc.__class__.__name__}). Preencha manualmente.",
            )

        if data is None:
            return LookupResult(
                found=False,
                message="Conjunto não encontrado no Brickset. Preencha manualmente.",
            )
        return _result_of(data)

    def additional_images(self, set_number: str) -> list[RemoteImage]:
        """``getAdditionalImages`` is keyed by the internal ``setID``, not the number."""
        set_id = _integer((self._set_data(set_number) or {}).get("setID"))
        if set_id is None:
            return []
        payload = self._call("getAdditionalImages", setID=str(set_id))
        if payload.get("status") != "success":
            return []
        return [
            RemoteImage(url=str(entry["imageURL"]))
            for entry in payload.get("additionalImages") or []
            if isinstance(entry, dict) and entry.get("imageURL")
        ]

    def instructions(self, set_number: str) -> list[RemoteInstruction]:
        """``getInstructions2`` takes the set number, so no ``setID`` lookup first."""
        payload = self._call("getInstructions2", setNumber=normalize_set_number(set_number))
        if payload.get("status") != "success":
            return []

        kept: list[RemoteInstruction] = []
        for entry in payload.get("instructions") or []:
            if not isinstance(entry, dict) or not entry.get("URL"):
                continue
            description = str(entry.get("description") or "").strip()[:250]
            language = instruction_language(description)
            if not is_kept_instruction(language):
                continue
            kept.append(
                RemoteInstruction(
                    url=str(entry["URL"]),
                    description=description or normalize_set_number(set_number),
                    language=language,
                )
            )
        return kept


class DisabledProvider:
    name = "brickset"
    enabled = False

    def lookup(self, set_number: str) -> LookupResult:
        return LookupResult(found=False, message=DISABLED_MESSAGE)

    def additional_images(self, set_number: str) -> list[RemoteImage]:
        return []

    def instructions(self, set_number: str) -> list[RemoteInstruction]:
        return []


def get_provider(db: DbSession) -> MetadataProvider:
    enabled = bool(settings_service.get(db, settings_service.BRICKSET_ENABLED, default=False))
    api_key = str(
        settings_service.get(db, settings_service.BRICKSET_API_KEY, default="")
        or settings.brickset_api_key
    )
    if not enabled or not api_key:
        return DisabledProvider()
    return BricksetProvider(api_key)

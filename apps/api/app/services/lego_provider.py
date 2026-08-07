"""LEGO metadata provider.

Brickset is the single configured provider (M9 FR-9.2). It is opt-in, off by
default, and contacted **only** on an explicit user action — never on a schedule,
never during a render. A failure is never a dead end: the caller falls back to
the identical manual form.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.schemas.lego import LookupResult
from app.services import settings_service

BRICKSET_ENDPOINT = "https://brickset.com/api/v3.asmx/getSets"


class MetadataProvider(Protocol):
    name: str

    def lookup(self, set_number: str) -> LookupResult: ...


def normalize_set_number(raw: str) -> str:
    """Brickset keys sets as ``10307-1``; users type ``10307``."""
    value = raw.strip().upper()
    return value if re.search(r"-\d+$", value) else f"{value}-1"


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", 0):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None


class BricksetProvider:
    name = "brickset"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def lookup(self, set_number: str) -> LookupResult:
        params = {
            "apiKey": self.api_key,
            "userHash": "",
            "params": json.dumps({"setNumber": normalize_set_number(set_number)}),
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(BRICKSET_ENDPOINT, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return LookupResult(
                found=False,
                message=f"Brickset indisponível ({exc.__class__.__name__}). Preencha manualmente.",
            )

        if payload.get("status") != "success" or not payload.get("sets"):
            return LookupResult(
                found=False,
                message="Conjunto não encontrado no Brickset. Preencha manualmente.",
            )

        data = payload["sets"][0]
        lego_com = data.get("LEGOCom") or {}
        retail = lego_com.get("DE") or lego_com.get("UK") or lego_com.get("US") or {}
        date_last_available = retail.get("dateLastAvailable") or ""
        retired_year = None
        if isinstance(date_last_available, str) and len(date_last_available) >= 4:
            with_year = date_last_available[:4]
            retired_year = int(with_year) if with_year.isdigit() else None

        return LookupResult(
            found=True,
            set_number=str(data.get("number") or "").strip() or None,
            name=data.get("name"),
            theme=data.get("theme"),
            subtheme=data.get("subtheme"),
            release_year=data.get("year"),
            retired_year=retired_year,
            piece_count=data.get("pieces"),
            minifig_count=data.get("minifigs"),
            rrp_eur=_decimal(retail.get("retailPrice")),
            image_url=(data.get("image") or {}).get("imageURL"),
            short_description=(data.get("extendedData") or {}).get("notes"),
        )


class DisabledProvider:
    name = "brickset"

    def lookup(self, set_number: str) -> LookupResult:
        return LookupResult(
            found=False,
            message=(
                "A consulta ao Brickset está desativada. Ative-a em Definições "
                "e indique a chave da API, ou preencha os dados manualmente."
            ),
        )


def get_provider(db: DbSession) -> MetadataProvider:
    enabled = bool(settings_service.get(db, settings_service.BRICKSET_ENABLED, default=False))
    api_key = str(
        settings_service.get(db, settings_service.BRICKSET_API_KEY, default="")
        or settings.brickset_api_key
    )
    if not enabled or not api_key:
        return DisabledProvider()
    return BricksetProvider(api_key)

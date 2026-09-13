"""The controlled vocabulary behind the product's descriptive attributes.

A dictionary, not a table: these values are read on every write and never joined
against, so a JSON file shipped with the release (ADR-0029) buys the same
normalisation a reference table would without the bootstrap, the migration and
the soft-delete edge cases a table drags along.

Only ``conservation`` is also guarded by a CHECK in the schema, because its set is
genuinely closed. ``presentation`` and ``dietary`` grow with the shopping, so they
are enforced *here* — adding «Espetada» is a one-line edit, not a migration.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError
from app.services.supermarket.normalize import normalize_description

VOCABULARY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / ("supermarket-product-attributes.pt-PT.json")
)


def _key(value: str) -> str:
    """The same accent-, case- and punctuation-blind funnel the catalogue matches
    through, so «Sem Glúten», «sem gluten» and «S/ GLUTEN» arrive as one key."""
    return normalize_description(value)


@lru_cache(maxsize=1)
def _vocabulary() -> dict[str, Any]:
    payload = json.loads(VOCABULARY_FILE.read_text(encoding="utf-8"))
    compiled: dict[str, Any] = {}
    for axis in ("conservation", "presentation", "dietary"):
        entries = payload.get(axis) or []
        # `code` is what the column stores for conservation (the CHECK's domain);
        # the other two store their own label, so a value reads as written.
        values = [entry.get("code") or entry["label"] for entry in entries]
        lookup: dict[str, str] = {}
        for entry, value in zip(entries, values, strict=True):
            for spelling in (value, entry["label"], *(entry.get("synonyms") or [])):
                key = _key(str(spelling))
                if key:
                    lookup[key] = value
        compiled[axis] = {
            "values": values,
            "labels": {(entry.get("code") or entry["label"]): entry["label"] for entry in entries},
            "lookup": lookup,
        }
    return compiled


def vocabulary() -> dict[str, list[dict[str, str]]]:
    """What the pickers offer: one ordered list of ``{value, label}`` per axis."""
    compiled = _vocabulary()
    return {
        axis: [
            {"value": value, "label": compiled[axis]["labels"][value]}
            for value in compiled[axis]["values"]
        ]
        for axis in ("conservation", "presentation", "dietary")
    }


def label_for(axis: str, value: str | None) -> str | None:
    """How a stored value reads. Only ``conservation`` stores a code that differs
    from its label, so any other axis — including ones with no vocabulary at all,
    like a brand — passes straight through."""
    if value is None:
        return None
    compiled = _vocabulary().get(axis)
    return compiled["labels"].get(value, value) if compiled else value


def _resolve(axis: str, raw: Any, *, noun: str) -> str:
    compiled = _vocabulary()[axis]
    key = _key(str(raw))
    resolved = compiled["lookup"].get(key)
    if resolved is None:
        known = ", ".join(compiled["labels"][value] for value in compiled["values"])
        raise ValidationError(f"{noun} desconhecido: «{raw}». Valores aceites: {known}.")
    return resolved


def sanitize_conservation(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    return _resolve("conservation", raw, noun="Estado de conservação")


def sanitize_presentation(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    return _resolve("presentation", raw, noun="Corte/apresentação")


def sanitize_dietary(raw: Any) -> list[str]:
    """Deduplicated and ordered as the dictionary orders it, so two products
    carrying the same tags compare equal and group together."""
    if raw in (None, ""):
        return []
    values = raw if isinstance(raw, list | tuple | set) else [raw]
    resolved = {_resolve("dietary", value, noun="Atributo dietético") for value in values if value}
    order = _vocabulary()["dietary"]["values"]
    return [value for value in order if value in resolved]


__all__ = [
    "label_for",
    "sanitize_conservation",
    "sanitize_dietary",
    "sanitize_presentation",
    "vocabulary",
]

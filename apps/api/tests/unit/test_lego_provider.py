"""Protects: ADR-0039 «the set's own fields, not a shop's» and ADR-0040's
language rule for manuals.

The bug this file exists for: `retirement_date` used to come from
`LEGOCom.DE.dateLastAvailable`, which is the day one national shop stopped
listing the set — days or weeks off the set's own `exitDate`, and absent
entirely for sets Germany never sold.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from typing import Any

from app.services import lego_provider

#: Trimmed from a real `getSets` answer for 10280-1.
FLOWER_BOUQUET: dict[str, Any] = {
    "setID": 31025,
    "number": "10280",
    "name": "Flower Bouquet",
    "year": 2021,
    "theme": "Icons",
    "launchDate": "2021-01-01T00:00:00Z",
    "exitDate": "2026-07-31T00:00:00Z",
    "pieces": 756,
    "minifigs": None,
    "ageRange": {"min": 18},
    "dimensions": {"height": 38.2, "width": 26.2, "depth": 7.1, "weight": 0.76},
    "LEGOCom": {
        "US": {"retailPrice": 59.99, "dateFirstAvailable": "2021-01-02T00:00:00Z"},
        "UK": {"retailPrice": 54.99, "dateLastAvailable": "2026-06-29T00:00:00Z"},
        "DE": {"retailPrice": 59.99, "dateLastAvailable": "2026-07-03T00:00:00Z"},
    },
    "image": {"imageURL": "https://images.brickset.com/sets/images/10280-1.jpg"},
    "additionalImageCount": 20,
    "instructionsCount": 13,
}


class _FakeBrickset(lego_provider.BricksetProvider):
    """The real provider with the network swapped for a dictionary."""

    def __init__(self, payloads: dict[str, Any]) -> None:
        super().__init__("test-key")
        self.payloads = payloads
        self.calls: list[str] = []

    def _call(self, method: str, **params: str) -> dict[str, Any]:
        self.calls.append(method)
        return self.payloads.get(method, {"status": "success"})


def _provider(set_data: dict[str, Any], **extra: Any) -> _FakeBrickset:
    return _FakeBrickset({"getSets": {"status": "success", "sets": [set_data]}, **extra})


def test_retirement_is_the_sets_exit_date_not_a_shops_last_day() -> None:
    result = _provider(FLOWER_BOUQUET).lookup("10280")

    assert result.found
    assert result.retirement_date == dt.date(2026, 7, 31)
    assert result.release_date == dt.date(2021, 1, 1)


def test_without_an_exit_date_the_latest_shop_still_selling_it_wins() -> None:
    data = {**FLOWER_BOUQUET}
    data.pop("exitDate")

    result = _provider(data).lookup("10280")

    # The German shop's 3 July, not the British 29 June it merely happens to
    # find first — and never `None` just because one region has no date.
    assert result.retirement_date == dt.date(2026, 7, 3)


def test_a_set_still_on_sale_has_no_retirement_date() -> None:
    data = {**FLOWER_BOUQUET, "exitDate": None, "LEGOCom": {"DE": {"retailPrice": 59.99}}}

    assert _provider(data).lookup("10280").retirement_date is None


def test_the_age_range_and_the_box_come_across() -> None:
    result = _provider(FLOWER_BOUQUET).lookup("10280")

    assert (result.age_min, result.age_max) == (18, None)
    assert result.box_width_cm == Decimal("26.2")
    assert result.box_depth_cm == Decimal("7.1")
    assert result.box_height_cm == Decimal("38.2")
    assert result.box_weight_kg == Decimal("0.760")
    assert (result.additional_image_count, result.instruction_count) == (20, 13)


def test_the_rrp_is_read_only_from_the_euro_store() -> None:
    data = {
        **FLOWER_BOUQUET,
        "LEGOCom": {"US": {"retailPrice": 59.99}, "UK": {"retailPrice": 54.99}},
    }

    # A dollar figure written into a EUR column would be worse than no figure.
    assert _provider(data).lookup("10280").rrp_eur is None
    assert _provider(FLOWER_BOUQUET).lookup("10280").rrp_eur == Decimal("59.99")


def test_only_portuguese_english_and_wordless_manuals_are_kept() -> None:
    provider = _provider(
        FLOWER_BOUQUET,
        getInstructions2={
            "status": "success",
            "instructions": [
                {"URL": "https://x/de.pdf", "description": "10280_DE_Info_Booklet"},
                {"URL": "https://x/en.pdf", "description": "10280_EN_Info_Booklet"},
                {"URL": "https://x/engb.pdf", "description": "10280_ENGB_Info_Booklet"},
                {"URL": "https://x/pt.pdf", "description": "10280_PT_Info_Booklet"},
                {"URL": "https://x/zh.pdf", "description": "10280_ZHSI_Info_Booklet"},
                {"URL": "https://x/bi.pdf", "description": "BI 3106, 80+4, 10280 V29"},
                {"URL": "", "description": "sem endereço"},
            ],
        },
    )

    manuals = provider.instructions("10280")

    assert [manual.language for manual in manuals] == ["EN", "ENGB", "PT", None]
    # The building instruction is pictures: it names no language because it needs
    # none, and dropping it would leave the shelf with nothing to build from.
    assert manuals[-1].url == "https://x/bi.pdf"


def test_additional_images_are_looked_up_by_the_internal_set_id() -> None:
    provider = _provider(
        FLOWER_BOUQUET,
        getAdditionalImages={
            "status": "success",
            "additionalImages": [
                {"imageURL": "https://x/alt1.jpg", "thumbnailURL": "https://x/tn1.jpg"},
                {"thumbnailURL": "https://x/tn2.jpg"},
            ],
        },
    )

    images = provider.additional_images("10280")

    assert provider.calls == ["getSets", "getAdditionalImages"]
    assert [image.url for image in images] == ["https://x/alt1.jpg"]


class _VariantAwareBrickset(lego_provider.BricksetProvider):
    """Unlike `_FakeBrickset`, actually inspects the requested `setNumber` — needed
    to tell the `-0`/`-1` fallback candidates apart (ADR-0050)."""

    def __init__(self, sets_by_number: dict[str, dict[str, Any]]) -> None:
        super().__init__("test-key")
        self.sets_by_number = sets_by_number
        self.queried_numbers: list[str] = []

    def _call(self, method: str, **params: str) -> dict[str, Any]:
        if method != "getSets":
            return {"status": "success"}
        number = json.loads(params["params"])["setNumber"]
        self.queried_numbers.append(number)
        data = self.sets_by_number.get(number)
        return {"status": "success", "sets": [data]} if data else {"status": "success", "sets": []}


def test_a_bare_number_tries_the_closed_pack_variant_before_the_ordinary_one() -> None:
    """The F1 car collectibles case: a closed pack is keyed `-0`, not `-1`."""
    provider = _VariantAwareBrickset({"71046-0": {**FLOWER_BOUQUET, "number": "71046-0"}})

    result = provider.lookup("71046")

    assert result.found
    assert result.set_number == "71046-0"
    assert provider.queried_numbers == ["71046-0"]


def test_a_bare_number_falls_back_to_the_ordinary_variant_when_no_pack_exists() -> None:
    provider = _VariantAwareBrickset({"10280-1": {**FLOWER_BOUQUET, "number": "10280-1"}})

    result = provider.lookup("10280")

    assert result.found
    assert result.set_number == "10280-1"
    assert provider.queried_numbers == ["10280-0", "10280-1"]


def test_an_explicit_variant_suffix_is_never_second_guessed() -> None:
    provider = _VariantAwareBrickset({"71046-2": {**FLOWER_BOUQUET, "number": "71046-2"}})

    result = provider.lookup("71046-2")

    assert result.found
    assert provider.queried_numbers == ["71046-2"]

"""Protects: M9 Definition of Done — «storage capacity math» and the rule that
``capacity_pct`` is *never* computed from the item count.

``stored_count`` and ``capacity_pct`` are deliberately independent: a box can hold
one enormous set and still be 100 % full.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.models.lego import StorageLocation
from app.services.lego_service import _storage_out


def _location(capacity: int | None, container: str | None = "Caixa TV") -> StorageLocation:
    return StorageLocation(
        id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        area="Garagem",
        container=container,
        capacity_pct=capacity,
    )


def test_remaining_capacity_is_the_complement() -> None:
    out = _storage_out(_location(75), stored_count=12, stored_value_eur=Decimal("100.00"))
    assert out.remaining_capacity_pct == 25
    assert out.is_full is False


def test_full_at_exactly_one_hundred() -> None:
    assert _storage_out(_location(100)).is_full is True
    assert _storage_out(_location(100)).remaining_capacity_pct == 0


def test_untracked_capacity_stays_null_and_is_never_full() -> None:
    out = _storage_out(_location(None), stored_count=40)
    assert out.capacity_pct is None
    assert out.remaining_capacity_pct is None
    assert out.is_full is False
    # 40 copies stored and still «not full» — capacity is a human estimate only.
    assert out.stored_count == 40


def test_empty_location_is_not_full() -> None:
    out = _storage_out(_location(0))
    assert out.remaining_capacity_pct == 100
    assert out.is_full is False


def test_label_uses_the_area_alone_when_there_is_no_container() -> None:
    assert _storage_out(_location(None, container=None)).label == "Garagem"
    assert _storage_out(_location(10)).label == "Garagem › Caixa TV"

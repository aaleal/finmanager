"""Protects: a fresh install with ``BRICKSET_API_KEY`` in the environment starts
with Brickset already switched on, with no visit to Definições required — and
that an owner's later choice in Definições is never overridden by ``.env`` on a
subsequent boot.
"""

from __future__ import annotations

import pytest
from app.core.config import settings as app_settings
from app.services import settings_service
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_a_key_in_the_environment_switches_brickset_on(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "brickset_api_key", "key-TEST-0000-0000")

    changed = settings_service.ensure_brickset_from_env(db)

    assert changed is True
    assert settings_service.get(db, settings_service.BRICKSET_API_KEY) == "key-TEST-0000-0000"
    assert settings_service.get(db, settings_service.BRICKSET_ENABLED) is True


def test_without_a_key_in_the_environment_nothing_changes(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "brickset_api_key", "")

    changed = settings_service.ensure_brickset_from_env(db)

    assert changed is False
    assert settings_service.get(db, settings_service.BRICKSET_API_KEY, default="") == ""


def test_an_owners_later_choice_is_never_overridden_on_a_later_boot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "brickset_api_key", "key-TEST-0000-0000")
    settings_service.ensure_brickset_from_env(db)

    # The owner disables it and clears the key by hand, from Definições.
    settings_service.set_value(db, settings_service.BRICKSET_ENABLED, False)
    settings_service.set_value(db, settings_service.BRICKSET_API_KEY, "")

    changed = settings_service.ensure_brickset_from_env(db)

    assert changed is False
    assert settings_service.get(db, settings_service.BRICKSET_ENABLED) is False
    assert settings_service.get(db, settings_service.BRICKSET_API_KEY) == ""

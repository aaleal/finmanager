"""Module 7 — Household, users, entities and sessions.

Five tables, three roles, no per-entity read isolation. Entity is an attribution
and filter dimension, never a permission boundary (FR-7.1 / FR-7.3).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk

Role = Literal["OWNER", "MEMBER", "VIEWER"]
ROLES: tuple[Role, ...] = ("OWNER", "MEMBER", "VIEWER")
ROLE_RANK = {"VIEWER": 0, "MEMBER": 1, "OWNER": 2}


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class User(Base, TimestampMixin, SoftDeleteMixin):
    """``is_dependent`` users have no password and never log in (FR-7.5)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('OWNER', 'MEMBER', 'VIEWER')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "NOT (is_dependent AND password_hash IS NOT NULL)",
            name="ck_users_dependent_has_no_password",
        ),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(String(16), nullable=False, default="MEMBER")
    is_dependent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="pt-PT")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Lisbon")


class HouseholdMember(Base):
    """``role`` here is the single source of truth for RBAC."""

    __tablename__ = "household_members"
    __table_args__ = (
        CheckConstraint("role IN ('OWNER', 'MEMBER', 'VIEWER')", name="ck_household_members_role"),
        UniqueConstraint("household_id", "user_id", name="uq_household_members_household_user"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("households.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[Role] = mapped_column(String(16), nullable=False, default="MEMBER")
    joined_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    left_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(User, lazy="joined")


class Entity(Base, SoftDeleteMixin):
    """A named owner made up of one or more members. No ``type`` enum, by decision."""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("household_id", "name", name="uq_entities_household_id_name"),
        Index("ix_entities_household_id", "household_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("households.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    member_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), nullable=False, default=list
    )
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_readonly: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class Session(Base):
    """Server-side session. The row is authoritative; Redis is the fast path."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "ROLES",
    "ROLE_RANK",
    "Entity",
    "Household",
    "HouseholdMember",
    "Role",
    "Session",
    "User",
]

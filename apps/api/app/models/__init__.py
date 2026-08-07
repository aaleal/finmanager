"""Every model imported here so Alembic autogenerate sees the full metadata."""

from __future__ import annotations

from app.models.base import Base
from app.models.core import (
    AuditLog,
    Category,
    Document,
    ImportBatch,
    Link,
    Merchant,
    ProcessingJob,
    ReviewTask,
    Setting,
    Tag,
)
from app.models.household import (
    ROLE_RANK,
    ROLES,
    Entity,
    Household,
    HouseholdMember,
    Session,
    User,
)
from app.models.lego import LegoSetInstance, LegoSetModel, StorageLocation

__all__ = [
    "ROLES",
    "ROLE_RANK",
    "AuditLog",
    "Base",
    "Category",
    "Document",
    "Entity",
    "Household",
    "HouseholdMember",
    "ImportBatch",
    "LegoSetInstance",
    "LegoSetModel",
    "Link",
    "Merchant",
    "ProcessingJob",
    "ReviewTask",
    "Session",
    "Setting",
    "StorageLocation",
    "Tag",
    "User",
]

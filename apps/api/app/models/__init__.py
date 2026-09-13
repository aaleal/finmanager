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
from app.models.lego import LegoSetImage, LegoSetInstance, LegoSetModel, StorageLocation
from app.models.prices import ProductPriceHistory
from app.models.products import MasterProduct, ProductAlias, ProductMergeDismissal
from app.models.supermarket import MerchantParserProfile, SupermarketReceipt, SupermarketReceiptItem

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
    "LegoSetImage",
    "LegoSetInstance",
    "LegoSetModel",
    "Link",
    "MasterProduct",
    "Merchant",
    "MerchantParserProfile",
    "ProcessingJob",
    "ProductAlias",
    "ProductMergeDismissal",
    "ProductPriceHistory",
    "ReviewTask",
    "Session",
    "Setting",
    "StorageLocation",
    "SupermarketReceipt",
    "SupermarketReceiptItem",
    "Tag",
    "User",
]

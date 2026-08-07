from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.household import Role
from app.schemas.common import ApiModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(ApiModel):
    id: uuid.UUID
    email: str | None
    display_name: str
    role: Role
    is_dependent: bool
    must_change_password: bool
    locale: str
    timezone: str
    is_deleted: bool


class MemberOut(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    joined_at: dt.datetime
    left_at: dt.datetime | None
    display_name: str
    email: str | None
    is_dependent: bool
    is_active: bool


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    role: Role = "MEMBER"
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)
    is_dependent: bool = False

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ("OWNER", "MEMBER", "VIEWER"):
            raise ValueError("role deve ser OWNER, MEMBER ou VIEWER")
        return v


class MemberUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    role: Role | None = None
    is_dependent: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("OWNER", "MEMBER", "VIEWER"):
            raise ValueError("role deve ser OWNER, MEMBER ou VIEWER")
        return v


class EntityOut(ApiModel):
    id: uuid.UUID
    name: str
    member_ids: list[uuid.UUID]
    color: str | None
    is_readonly: bool
    created_at: dt.datetime


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[uuid.UUID] = Field(min_length=1)
    color: str | None = None


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    member_ids: list[uuid.UUID] | None = None
    color: str | None = None


class SessionOut(BaseModel):
    user: UserOut
    household_id: uuid.UUID
    household_name: str
    role: Role
    active_entity_id: uuid.UUID | None
    csrf_token: str
    expires_at: dt.datetime


class EntitySwitch(BaseModel):
    entity_id: uuid.UUID | None = None


class EntitySwitchResult(BaseModel):
    active_entity_id: uuid.UUID | None
    csrf_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: str | None = None
    timezone: str | None = None

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


class SetupStatus(BaseModel):
    """Public probe: is this installation still waiting to be configured?"""

    needs_setup: bool


class SetupRequest(BaseModel):
    household_name: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # Longer than the 8 required elsewhere: this account can never be reset from
    # inside the application, so it is the one password that must be strong.
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def _not_trivial(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("a palavra-passe não pode começar nem terminar com espaços")
        if v.lower() in {"palavrapasse", "passwordpassword", "finmanager123"}:
            raise ValueError("escolha uma palavra-passe menos previsível")
        return v

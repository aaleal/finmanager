"""Application error types mapped to clean, pt-PT-friendly API responses."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    code = "app_error"

    def __init__(self, detail: str, *, status_code: int = 400, **extra: Any) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.extra = extra


class NotFound(AppError):
    code = "not_found"

    def __init__(self, detail: str = "Registo não encontrado.") -> None:
        super().__init__(detail, status_code=status.HTTP_404_NOT_FOUND)


class Conflict(AppError):
    code = "conflict"

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail, status_code=status.HTTP_409_CONFLICT, **extra)


class Forbidden(AppError):
    code = "forbidden"

    def __init__(self, detail: str = "Não tem permissões para esta operação.") -> None:
        super().__init__(detail, status_code=status.HTTP_403_FORBIDDEN)


class Unauthorized(AppError):
    code = "unauthorized"

    def __init__(self, detail: str = "Sessão inválida ou expirada.") -> None:
        super().__init__(detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ValidationError(AppError):
    code = "validation_error"

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, **extra)

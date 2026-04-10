"""
Repository facade module.

This file intentionally stays thin and composes stable responsibilities
from `app.core.repository_parts.*` mixins.
"""

from __future__ import annotations

from typing import Generic

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository_parts import (
    ModelType,
    RepositoryCrudMixin,
    RepositoryFilteringMixin,
    RepositoryQueryMixin,
    RepositoryRecycleBinMixin,
    RepositorySortingMixin,
    TenantScopeMixin,
)


class BaseRepository(
    RepositoryCrudMixin[ModelType],
    RepositoryQueryMixin[ModelType],
    RepositorySortingMixin[ModelType],
    RepositoryRecycleBinMixin[ModelType],
    RepositoryFilteringMixin[ModelType],
    Generic[ModelType],
):
    """
    Base repository facade.

    Public API remains compatible while internal responsibilities are
    implemented by dedicated mixins.
    """

    model: type[ModelType]
    _scope_fields: dict[str, set[str]] = {}

    def __init__(self, db: AsyncSession):
        self.db = db


class TenantRepository(TenantScopeMixin[ModelType], BaseRepository[ModelType]):
    """
    Tenant-scoped repository facade.

    Keeps compatibility with existing callers while delegating behavior
    to `TenantScopeMixin`.
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db)
        self.tenant_id = tenant_id


__all__ = ["ModelType", "BaseRepository", "TenantRepository"]

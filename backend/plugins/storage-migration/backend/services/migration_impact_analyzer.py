"""Impact analysis for storage migration plans."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.models.tenant.attachment import Attachment
from app.storage.base import StorageVisibility
from app.storage.manager import storage_manager

try:
    from .migration_helpers import normalize_scope
except ImportError:
    _services_dir = Path(__file__).resolve().parent
    _helpers_spec = importlib.util.spec_from_file_location(
        "storage_migration_runtime_helpers_for_analyzer",
        _services_dir / "migration_helpers.py",
    )
    if _helpers_spec is None or _helpers_spec.loader is None:
        raise ImportError("Unable to load migration_helpers.py")
    _helpers_module = importlib.util.module_from_spec(_helpers_spec)
    _helpers_spec.loader.exec_module(_helpers_module)
    normalize_scope = _helpers_module.normalize_scope


class MigrationImpactAnalyzer:
    """Analyze impact before switching storage driver."""

    def __init__(self, db):
        self._db = db

    async def analyze(
        self,
        source_driver: str,
        target_driver: str,
        scope: str = "all",
    ) -> dict[str, Any]:
        if source_driver == target_driver:
            raise ValueError("Source and target drivers must be different")

        scope = normalize_scope(scope)
        conditions = [
            Attachment.driver == source_driver,
            Attachment.is_deleted.is_(False),
        ]

        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":", 1)[1])
            conditions.append(Attachment.tenant_id == tenant_id)

        total_q = select(
            func.count(Attachment.id).label("total_files"),
            func.coalesce(func.sum(Attachment.size), 0).label("total_size_bytes"),
        ).where(*conditions)
        total_result = await self._db.execute(total_q)
        total_row = total_result.one()

        visibility_q = (
            select(
                Attachment.visibility,
                func.count(Attachment.id).label("count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size_bytes"),
            )
            .where(*conditions)
            .group_by(Attachment.visibility)
        )
        visibility_result = await self._db.execute(visibility_q)

        private_files = 0
        private_size = 0
        public_files = 0
        public_size = 0
        for row in visibility_result.all():
            if row.visibility == StorageVisibility.PRIVATE:
                private_files = row.count
                private_size = row.size_bytes
            elif row.visibility == StorageVisibility.PUBLIC:
                public_files = row.count
                public_size = row.size_bytes

        tenant_breakdown: list[dict[str, Any]] = []
        if scope == "all":
            tenant_q = (
                select(
                    Attachment.tenant_id,
                    func.count(Attachment.id).label("count"),
                    func.coalesce(func.sum(Attachment.size), 0).label("size_bytes"),
                )
                .where(*conditions)
                .group_by(Attachment.tenant_id)
                .order_by(func.count(Attachment.id).desc())
                .limit(20)
            )
            tenant_result = await self._db.execute(tenant_q)
            tenant_breakdown = [
                {
                    "tenant_id": row.tenant_id,
                    "file_count": row.count,
                    "size_bytes": int(row.size_bytes),
                }
                for row in tenant_result.all()
            ]

        return {
            "source_driver": source_driver,
            "target_driver": target_driver,
            "source_available": storage_manager.has_driver(source_driver),
            "target_available": storage_manager.has_driver(target_driver),
            "total_files": total_row.total_files,
            "total_size_bytes": int(total_row.total_size_bytes),
            "private_files": private_files,
            "private_size_bytes": int(private_size),
            "public_files": public_files,
            "public_size_bytes": int(public_size),
            "tenant_breakdown": tenant_breakdown,
            "scope": scope,
        }


__all__ = ["MigrationImpactAnalyzer"]

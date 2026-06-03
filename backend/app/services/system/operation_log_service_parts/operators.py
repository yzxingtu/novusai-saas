"""Operator query helpers for operation logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system.operation_log import OperationLog

from .identity import _OperationLogIdentityFacade


class _OperationLogOperatorFacade:
    """Operator query surface for admin/tenant operation log dropdowns."""

    def __init__(self, db: AsyncSession, identity: _OperationLogIdentityFacade):
        self.db = db
        self.identity = identity

    async def get_admin_operators(self) -> list[dict[str, Any]]:
        distinct_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id.is_(None),
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )
        result = await self.db.execute(distinct_q)
        rows = result.all()
        if not rows:
            return []

        identity_meta_map = await self._load_identity_meta_map(rows)
        return [
            self.identity.serialize_operator_row(
                row,
                identity_meta_map.get(
                    self.identity.identity_ref(row.user_type, row.user_id),
                    {},
                ),
            )
            for row in rows
        ]

    async def get_admin_operators_select(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        from sqlalchemy import or_

        base_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id.is_(None),
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )

        if search:
            base_q = base_q.having(
                or_(
                    func.max(OperationLog.username).ilike(f"%{search}%"),
                    func.max(OperationLog.nickname).ilike(f"%{search}%"),
                )
            )

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (
            await self.db.execute(
                base_q.offset((page - 1) * page_size).limit(page_size)
            )
        ).all()

        identity_meta_map = await self._load_identity_meta_map(rows)
        items = []
        for row in rows:
            operator = self.identity.serialize_operator_row(
                row,
                identity_meta_map.get(
                    self.identity.identity_ref(row.user_type, row.user_id),
                    {},
                ),
            )
            display_name = operator["display_name"] or operator["username"] or ""
            items.append(
                {
                    "label": display_name,
                    "value": operator["username"] or "",
                    "extra": {
                        "user_id": operator["user_id"],
                        "display_name": operator["display_name"],
                        "username": operator["username"],
                        "nickname": operator["nickname"],
                        "avatar": operator["avatar"],
                        "org_node_id": operator["org_node_id"],
                        "org_node_name": operator["org_node_name"],
                        "role_name": operator["role_name"],
                        "user_type": operator["user_type"],
                        "is_active": operator["is_active"],
                        "is_leader": operator["is_leader"],
                        "is_owner": operator["is_owner"],
                    },
                    "disabled": operator["is_active"] is False,
                }
            )

        return items, total

    async def get_tenant_operators(self, tenant_id: int) -> list[dict[str, Any]]:
        distinct_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id == tenant_id,
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )
        result = await self.db.execute(distinct_q)
        rows = result.all()
        if not rows:
            return []

        identity_meta_map = await self._load_identity_meta_map(rows)
        return [
            self.identity.serialize_operator_row(
                row,
                identity_meta_map.get(
                    self.identity.identity_ref(row.user_type, row.user_id),
                    {},
                ),
            )
            for row in rows
        ]

    async def get_tenant_operators_select(
        self,
        tenant_id: int,
        search: str | None = None,
        user_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        from sqlalchemy import or_

        from app.core.i18n import _

        base_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id == tenant_id,
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )
        if user_type:
            base_q = base_q.where(OperationLog.user_type == user_type)
        if search:
            base_q = base_q.having(
                or_(
                    func.max(OperationLog.username).ilike(f"%{search}%"),
                    func.max(OperationLog.nickname).ilike(f"%{search}%"),
                )
            )

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (
            await self.db.execute(
                base_q.offset((page - 1) * page_size).limit(page_size)
            )
        ).all()

        identity_meta_map = await self._load_identity_meta_map(rows)
        items = []
        for row in rows:
            operator = self.identity.serialize_operator_row(
                row,
                identity_meta_map.get(
                    self.identity.identity_ref(row.user_type, row.user_id),
                    {},
                ),
            )
            display_name = operator["display_name"] or ""
            username = operator["username"] or ""
            label = _("enum.user_type." + row.user_type) if row.user_type else ""
            items.append(
                {
                    "label": f"{display_name} ({label})" if label else display_name,
                    "value": username,
                    "extra": {
                        "user_id": operator["user_id"],
                        "display_name": operator["display_name"],
                        "username": operator["username"],
                        "nickname": operator["nickname"],
                        "avatar": operator["avatar"],
                        "org_node_id": operator["org_node_id"],
                        "org_node_name": operator["org_node_name"],
                        "role_name": operator["role_name"],
                        "user_type": operator["user_type"],
                        "is_active": operator["is_active"],
                        "is_leader": operator["is_leader"],
                        "is_owner": operator["is_owner"],
                    },
                    "disabled": operator["is_active"] is False,
                }
            )
        return items, total

    async def _load_identity_meta_map(
        self, rows: list[Any]
    ) -> dict[tuple[str, int], dict[str, Any]]:
        return await self.identity.load_identity_meta_map(
            {
                ref
                for row in rows
                if (ref := self.identity.identity_ref(row.user_type, row.user_id))
                is not None
            }
        )


__all__ = ["_OperationLogOperatorFacade"]

"""
Call log read-side helpers.
"""

from __future__ import annotations


class CallLogReadServiceMixin:
    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
        group_by: str = "daily",
    ):
        return await self.repo.get_statistics(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

    async def get_overall_summary(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
    ):
        return await self.repo.get_overall_summary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date=None,
        limit: int = 100,
    ):
        return await self.repo.get_failed_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            limit=limit,
        )

    async def query_list_with_names(
        self,
        spec,
        *,
        include_caller_names: bool = False,
    ):
        return await self.repo.query_list_with_names(
            spec,
            include_caller_names=include_caller_names,
        )


__all__ = ["CallLogReadServiceMixin"]

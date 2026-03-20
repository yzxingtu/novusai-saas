"""
AI 调用日志 Repository / AI Call Log Repository

提供调用日志查询、统计和分析功能 / Provides AI call log query, statistics and analysis functions
"""

from datetime import date, datetime, timezone as dt_timezone

from sqlalchemy import case, func, select

from app.core.base_repository import BaseRepository
from app.core.logging import LogManager
from app.schemas.common.query import FilterRule
from app.enums.ai import CallStatusEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai import AICallLog
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser

logger = LogManager.get_logger("ai.call_log")


def _display_name(nickname: str | None, username: str | None, fallback: str) -> str:
    if nickname and str(nickname).strip():
        return str(nickname).strip()
    if username and str(username).strip():
        return str(username).strip()
    return fallback


def _datetime_to_iso_utc_str(value: object) -> object:
    """
    与 BaseSchema 一致：DB naive UTC → 带时区 ISO，避免 JSON 输出无后缀时被浏览器当作本地时间解析。
    Align with BaseSchema: naive UTC → timezone-aware ISO for correct browser local display.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc).isoformat()
        return value.isoformat()
    return value


def _normalize_call_log_dict_datetimes(d: dict) -> None:
    """就地规范化 API 中的时间字段 / Normalize datetime fields in-place for JSON API."""
    for key in ("created_at", "updated_at", "deleted_at"):
        if key in d:
            d[key] = _datetime_to_iso_utc_str(d[key])


class AICallLogRepository(BaseRepository[AICallLog]):
    """
    AI 调用日志 Repository / AI call log repository.
    """
    model = AICallLog

    async def enrich_logs_to_dicts(
        self,
        items: list[AICallLog],
        *,
        include_tenant_names: bool = True,
        include_caller_names: bool = False,
        include_payload: bool = False,
    ) -> list[dict]:
        """
        将 ORM 列表转为 dict，并批量填充 model/provider/tenant/caller 展示字段。
        """
        if not items:
            return []

        model_ids = {
            model_id
            for item in items
            for model_id in (item.model_id, item.routed_model_id)
            if model_id
        }
        provider_ids = {i.provider_id for i in items if i.provider_id}
        tenant_ids = {i.tenant_id for i in items if i.tenant_id is not None}

        model_map: dict[int, str] = {}
        if model_ids:
            rows = (await self.db.execute(
                select(AIModel.id, AIModel.name).where(AIModel.id.in_(model_ids))
            )).all()
            model_map = {r.id: r.name for r in rows}

        provider_map: dict[int, str] = {}
        provider_icon_map: dict[int, str | None] = {}
        if provider_ids:
            rows = (await self.db.execute(
                select(AIProvider.id, AIProvider.name, AIProvider.icon).where(
                    AIProvider.id.in_(provider_ids)
                )
            )).all()
            provider_map = {r.id: r.name for r in rows}
            provider_icon_map = {r.id: r.icon for r in rows}

        tenant_map: dict[int, str] = {}
        if include_tenant_names and tenant_ids:
            rows = (await self.db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
            )).all()
            tenant_map = {r.id: r.name for r in rows}

        tenant_admin_ids: set[int] = set()
        tenant_user_ids: set[int] = set()
        platform_admin_ids: set[int] = set()
        if include_caller_names:
            for i in items:
                if not i.user_id:
                    continue
                ut = i.user_type
                if ut == LogUserTypeEnum.TENANT_ADMIN.value:
                    tenant_admin_ids.add(i.user_id)
                elif ut == LogUserTypeEnum.TENANT_USER.value:
                    tenant_user_ids.add(i.user_id)
                elif ut == LogUserTypeEnum.ADMIN.value:
                    platform_admin_ids.add(i.user_id)

        tenant_admin_display: dict[int, str] = {}
        if tenant_admin_ids:
            rows = (await self.db.execute(
                select(TenantAdmin.id, TenantAdmin.username, TenantAdmin.nickname).where(
                    TenantAdmin.id.in_(tenant_admin_ids)
                )
            )).all()
            for r in rows:
                tenant_admin_display[r.id] = _display_name(
                    r.nickname, r.username, f"#{r.id}",
                )

        tenant_user_display: dict[int, str] = {}
        if tenant_user_ids:
            rows = (await self.db.execute(
                select(TenantUser.id, TenantUser.username, TenantUser.nickname, TenantUser.email).where(
                    TenantUser.id.in_(tenant_user_ids)
                )
            )).all()
            for r in rows:
                tenant_user_display[r.id] = _display_name(
                    r.nickname,
                    r.username,
                    (r.email or f"#{r.id}"),
                )

        platform_admin_display: dict[int, str] = {}
        if platform_admin_ids:
            rows = (await self.db.execute(
                select(Admin.id, Admin.username, Admin.nickname).where(
                    Admin.id.in_(platform_admin_ids)
                )
            )).all()
            for r in rows:
                platform_admin_display[r.id] = _display_name(
                    r.nickname, r.username, f"#{r.id}",
                )

        result: list[dict] = []
        for item in items:
            d = item.to_dict() if hasattr(item, "to_dict") else {
                "id": item.id,
                "tenant_id": item.tenant_id,
                "model_id": item.model_id,
                "provider_id": item.provider_id,
                "request_type": item.request_type,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "cost": float(item.cost or 0),
                "latency_ms": item.latency_ms,
                "status": item.status,
                "error_message": item.error_message,
                "user_id": item.user_id,
                "user_type": item.user_type,
                "created_at": item.created_at,
            }
            d["model_name"] = model_map.get(item.model_id, "-")
            d["provider_name"] = provider_map.get(item.provider_id, "-")
            d["provider_icon"] = provider_icon_map.get(item.provider_id)
            d["routed_model_name"] = model_map.get(item.routed_model_id, "-")
            if include_tenant_names:
                d["tenant_name"] = tenant_map.get(item.tenant_id, "-")

            caller = "-"
            if include_caller_names and item.user_id:
                ut = item.user_type
                uid = item.user_id
                if ut == LogUserTypeEnum.TENANT_ADMIN.value:
                    caller = tenant_admin_display.get(uid, f"ID:{uid}")
                elif ut == LogUserTypeEnum.TENANT_USER.value:
                    caller = tenant_user_display.get(uid, f"ID:{uid}")
                elif ut == LogUserTypeEnum.ADMIN.value:
                    caller = platform_admin_display.get(uid, f"ID:{uid}")
                else:
                    caller = f"ID:{uid}"
            d["caller_name"] = caller

            metadata = (
                item.request_metadata
                if isinstance(item.request_metadata, dict)
                else {}
            )
            d.pop("request_metadata", None)
            if not d.get("routed_model_id"):
                d["routed_model_id"] = metadata.get("routed_model_id")
            if not d.get("route_reason"):
                d["route_reason"] = metadata.get("route_reason")
            if include_payload:
                d["request_data"] = metadata.get("request")
                d["response_data"] = metadata.get("response")

            _normalize_call_log_dict_datetimes(d)

            result.append(d)

        return result

    async def query_list_with_names(
        self,
        spec,
        *,
        forced_filters: list[FilterRule] | None = None,
        include_tenant_names: bool = True,
        include_caller_names: bool = False,
    ) -> tuple[list[dict], int]:
        """
        查询调用日志列表，附带 model_name / provider_name / tenant_name / Query call log list with names.

        通过批量查 ID→Name 映射，避免逐行 JOIN 性能问题
        """
        items, total = await self.query_list(spec, forced_filters=forced_filters)
        if not items:
            return [], total

        result = await self.enrich_logs_to_dicts(
            items,
            include_tenant_names=include_tenant_names,
            include_caller_names=include_caller_names,
            include_payload=False,
        )
        return result, total

    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        group_by: str | None = None
    ) -> list[dict]:
        """
        获取统计信息 / Get call statistics.

        Args:
            tenant_id: 企业 ID (可选)
            start_date: 开始日期
            end_date: 结束日期
            group_by: 分组维度 (daily/model/user)

        Returns:
            统计数据列表
        """
        # 聚合列（所有分组模式共用）
        agg_columns = [
            func.count(AICallLog.id).label("call_count"),
            func.sum(AICallLog.total_tokens).label("total_tokens"),
            func.sum(AICallLog.input_tokens).label("input_tokens"),
            func.sum(AICallLog.output_tokens).label("output_tokens"),
            func.sum(AICallLog.cost).label("total_cost"),
            func.avg(AICallLog.latency_ms).label("avg_latency"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_count"),
        ]

        # 根据分组维度确定 SELECT 和 GROUP BY 列
        if group_by == "model":
            group_columns = [AICallLog.model_id]
            select_columns = [AICallLog.model_id] + agg_columns
        elif group_by == "user":
            group_columns = [AICallLog.user_id]
            select_columns = [AICallLog.user_id] + agg_columns
        else:
            # daily（默认）
            group_columns = [func.date(AICallLog.created_at), AICallLog.model_id]
            select_columns = [
                func.date(AICallLog.created_at).label("date"),
                AICallLog.model_id,
            ] + agg_columns

        stmt = select(*select_columns)

        # 企业筛选
        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        # 日期筛选
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AICallLog.created_at <= end_date)

        # 分组
        stmt = stmt.group_by(*group_columns)

        # 排序
        if group_by == "model":
            stmt = stmt.order_by(AICallLog.model_id)
        elif group_by == "user":
            stmt = stmt.order_by(AICallLog.user_id)
        else:
            stmt = stmt.order_by(func.date(AICallLog.created_at).desc(), AICallLog.model_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "date": str(row.date) if hasattr(row, 'date') else None,
                "model_id": getattr(row, 'model_id', None),
                "user_id": getattr(row, 'user_id', None),
                "call_count": row.call_count or 0,
                "total_tokens": row.total_tokens or 0,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "total_cost": float(row.total_cost or 0),
                "avg_latency": float(row.avg_latency) if row.avg_latency else 0,
                "success_count": row.success_count or 0,
                "failed_count": row.failed_count or 0,
            }
            for row in rows
        ]

    async def get_by_request_hash(
        self,
        request_hash: str,
        tenant_id: int | None = None
    ) -> AICallLog | None:
        """
        根据请求哈希查询日志（用于缓存命中检测）/ Get log by request hash (for cache hit detection).

        Args:
            request_hash: 请求哈希
            tenant_id: 企业 ID (可选)

        Returns:
            AICallLog 实例或 None
        """
        stmt = select(AICallLog).where(
            AICallLog.request_hash == request_hash,
            AICallLog.status == CallStatusEnum.SUCCESS.value,
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        # 按创建时间倒序,获取最新的匹配记录
        stmt = stmt.order_by(AICallLog.created_at.desc())

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_logs(
        self,
        tenant_id: int | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AICallLog]:
        """
        获取最近的调用日志 / Get recent call logs.

        Args:
            tenant_id: 企业 ID (可选)
            limit: 返回数量
            offset: 偏移量

        Returns:
            AICallLog 列表
        """
        stmt = select(AICallLog)

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.order_by(AICallLog.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        limit: int = 100
    ) -> list[AICallLog]:
        """
        获取失败的调用日志 / Get failed call logs.

        Args:
            tenant_id: 企业 ID (可选)
            start_date: 开始日期
            limit: 返回数量

        Returns:
            AICallLog 列表
        """
        stmt = select(AICallLog).where(
            AICallLog.status == CallStatusEnum.FAILED.value
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)

        stmt = stmt.order_by(AICallLog.created_at.desc())
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def get_overall_summary(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        获取总体统计汇总（单个 dict，非分组列表）/ Get overall call summary (single dict, not grouped).
        """
        stmt = select(
            func.count(AICallLog.id).label("total_calls"),
            func.sum(AICallLog.total_tokens).label("total_tokens"),
            func.sum(AICallLog.input_tokens).label("input_tokens"),
            func.sum(AICallLog.output_tokens).label("output_tokens"),
            func.sum(AICallLog.cost).label("total_cost"),
            func.avg(AICallLog.latency_ms).label("avg_latency"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_calls"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_calls"),
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AICallLog.created_at <= end_date)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total_calls": row.total_calls or 0,
            "total_tokens": row.total_tokens or 0,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "avg_latency": float(row.avg_latency) if row.avg_latency else 0,
            "success_calls": row.success_calls or 0,
            "failed_calls": row.failed_calls or 0,
        }


__all__ = ["AICallLogRepository"]

"""
AI 调用日志 Repository / AI Call Log Repository

提供调用日志查询、监控统计和基于账单事实的使用量聚合。
Provides call log queries, monitoring statistics, and billing-fact usage aggregations.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from sqlalchemy import Date, case, cast, func, select

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_repository import BaseRepository
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, UserTypeEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai import AICallLog
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.schemas.common.query import FilterRule, QuerySpec

logger = LogManager.get_logger("ai.call_log")


def _normalize_actor_type(
    actor_user_type: str | None,
    legacy_user_type: str | None,
) -> str | None:
    if actor_user_type and str(actor_user_type).strip():
        return str(actor_user_type).strip()
    if legacy_user_type == LogUserTypeEnum.ADMIN.value:
        return "platform_admin"
    if legacy_user_type == LogUserTypeEnum.TENANT_ADMIN.value:
        return "tenant_admin"
    if legacy_user_type == LogUserTypeEnum.TENANT_USER.value:
        return "tenant_user"
    return legacy_user_type


def _actor_type_fallback_name(actor_type: str | None) -> str:
    return {
        "platform_admin": "平台管理员",
        "tenant_admin": "企业管理员",
        "tenant_user": "企业用户",
        LogUserTypeEnum.ADMIN.value: "平台管理员",
        LogUserTypeEnum.TENANT_ADMIN.value: "企业管理员",
        LogUserTypeEnum.TENANT_USER.value: "企业用户",
    }.get(actor_type or "", "-")


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
    PLATFORM_USAGE_TENANT_NAME = "平台管理端"

    @classmethod
    def _platform_usage_tenant_expr(cls):
        """
        Platform internal calls are stored with tenant_id=0 and billing_tenant_id=NULL.
        平台内部调用以 tenant_id=0、billing_tenant_id=NULL 落账。
        """
        return case(
            (
                AICallLog.tenant_id == PLATFORM_TENANT_ID,
                PLATFORM_TENANT_ID,
            ),
            else_=None,
        )

    @classmethod
    def _effective_usage_tenant_expr(cls):
        """
        Billing tenant wins; otherwise treat platform tenant_id=0 as a first-class usage bucket.
        优先计费企业；若为空，则将平台 tenant_id=0 视为有效统计归属。
        """
        return func.coalesce(
            AICallLog.billing_tenant_id,
            cls._platform_usage_tenant_expr(),
        )

    @classmethod
    def _effective_usage_tenant_name_expr(cls):
        """Stable tenant display name for usage aggregates, including platform internal usage."""
        return func.coalesce(
            AICallLog.billing_tenant_name_snapshot,
            Tenant.name,
            case(
                (
                    cls._effective_usage_tenant_expr() == PLATFORM_TENANT_ID,
                    cls.PLATFORM_USAGE_TENANT_NAME,
                ),
                else_=None,
            ),
        )

    @staticmethod
    def _date_filters(
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        filters = [AICallLog.is_deleted.is_(False)]
        if start_date:
            filters.append(AICallLog.created_at >= start_date)
        if end_date:
            filters.append(AICallLog.created_at < end_date + timedelta(days=1))
        return filters

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
        tenant_ids = set()
        for item in items:
            effective_tenant_id = item.billing_tenant_id
            if effective_tenant_id is None and item.tenant_id is not None:
                effective_tenant_id = item.tenant_id
            if effective_tenant_id is not None:
                tenant_ids.add(effective_tenant_id)

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
                actor_id = i.actor_user_id or i.user_id
                actor_type = _normalize_actor_type(i.actor_user_type, i.user_type)
                if not actor_id or not actor_type:
                    continue
                if actor_type == "tenant_admin":
                    tenant_admin_ids.add(actor_id)
                elif actor_type == "tenant_user":
                    tenant_user_ids.add(actor_id)
                elif actor_type == "platform_admin":
                    platform_admin_ids.add(actor_id)

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
            snap_model = getattr(item, "model_name_snapshot", None)
            snap_provider = getattr(item, "provider_name_snapshot", None)
            snap_agent = getattr(item, "agent_name_snapshot", None)
            d["model_name"] = snap_model or model_map.get(item.model_id, "-")
            d["provider_name"] = snap_provider or provider_map.get(item.provider_id, "-")
            d["provider_icon"] = provider_icon_map.get(item.provider_id)
            d["routed_model_name"] = model_map.get(item.routed_model_id, "-")
            d["agent_name"] = snap_agent or "-"
            d["agent_id_snapshot"] = getattr(item, "agent_id_snapshot", None)
            d["billing_tenant_name_snapshot"] = getattr(
                item, "billing_tenant_name_snapshot", None,
            )
            if include_tenant_names:
                effective_tenant_id = item.billing_tenant_id
                if effective_tenant_id is None and item.tenant_id is not None:
                    effective_tenant_id = item.tenant_id
                if getattr(item, "billing_tenant_name_snapshot", None):
                    d["tenant_name"] = item.billing_tenant_name_snapshot
                elif effective_tenant_id == PLATFORM_TENANT_ID:
                    d["tenant_name"] = self.PLATFORM_USAGE_TENANT_NAME
                else:
                    d["tenant_name"] = tenant_map.get(effective_tenant_id, "-")

            caller = "-"
            if include_caller_names:
                actor_id = item.actor_user_id or item.user_id
                actor_type = _normalize_actor_type(item.actor_user_type, item.user_type)
                if actor_id and actor_type == "tenant_admin":
                    caller = tenant_admin_display.get(actor_id, f"ID:{actor_id}")
                elif actor_id and actor_type == "tenant_user":
                    caller = tenant_user_display.get(actor_id, f"ID:{actor_id}")
                elif actor_id and actor_type == "platform_admin":
                    caller = platform_admin_display.get(actor_id, f"ID:{actor_id}")
                elif actor_type:
                    caller = _actor_type_fallback_name(actor_type)
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

    async def query_usage_stats(
        self,
        spec: QuerySpec,
    ) -> tuple[list[dict], int]:
        """
        Query billing usage statistics grouped by day + tenant + model + request_type.
        查询按日期 + 计费企业 + 模型 + 请求类型聚合的计费用量统计。
        """
        stat_date_col = cast(AICallLog.created_at, Date)
        # 优先账本快照，避免企业/模型改名后聚合展示漂移 / Prefer billing snapshots for stable aggregates
        model_name_expr = func.coalesce(
            AICallLog.model_name_snapshot,
            AIModel.name,
        )

        usage_base = (
            select(
                stat_date_col.label("stat_date"),
                self._effective_usage_tenant_expr().label("tenant_id"),
                self._effective_usage_tenant_name_expr().label("tenant_name"),
                AICallLog.model_id.label("model_id"),
                model_name_expr.label("model_name"),
                AICallLog.request_type.label("request_type"),
                AICallLog.input_tokens.label("input_tokens"),
                AICallLog.output_tokens.label("output_tokens"),
                AICallLog.total_tokens.label("total_tokens"),
                AICallLog.cost.label("cost"),
                AICallLog.latency_ms.label("latency_ms"),
                AICallLog.status.label("status"),
            )
            .select_from(AICallLog)
            .join(AIModel, AIModel.id == AICallLog.model_id, isouter=True)
            .join(Tenant, Tenant.id == AICallLog.billing_tenant_id, isouter=True)
            .where(
                AICallLog.is_deleted.is_(False),
                self._effective_usage_tenant_expr().is_not(None),
            )
        ).subquery("usage_base")

        input_tokens_expr = func.coalesce(func.sum(usage_base.c.input_tokens), 0)
        output_tokens_expr = func.coalesce(func.sum(usage_base.c.output_tokens), 0)
        total_tokens_expr = func.coalesce(func.sum(usage_base.c.total_tokens), 0)
        call_count_expr = func.count()
        success_count_expr = func.sum(
            case((usage_base.c.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        )
        failed_count_expr = func.sum(
            case((usage_base.c.status == CallStatusEnum.FAILED.value, 1), else_=0)
        )
        total_cost_expr = func.coalesce(func.sum(usage_base.c.cost), 0)
        avg_latency_expr = func.avg(usage_base.c.latency_ms)
        max_latency_expr = func.max(usage_base.c.latency_ms)

        query = select(
            usage_base.c.stat_date.label("stat_date"),
            usage_base.c.tenant_id.label("tenant_id"),
            usage_base.c.tenant_name.label("tenant_name"),
            usage_base.c.model_id.label("model_id"),
            usage_base.c.model_name.label("model_name"),
            usage_base.c.request_type.label("request_type"),
            input_tokens_expr.label("input_tokens"),
            output_tokens_expr.label("output_tokens"),
            total_tokens_expr.label("total_tokens"),
            call_count_expr.label("call_count"),
            success_count_expr.label("success_count"),
            failed_count_expr.label("failed_count"),
            total_cost_expr.label("total_cost"),
            avg_latency_expr.label("avg_latency_ms"),
            max_latency_expr.label("max_latency_ms"),
        )

        allowed_filters = {
            "tenant_id": usage_base.c.tenant_id,
            "tenant_name": usage_base.c.tenant_name,
            "model_id": usage_base.c.model_id,
            "model_name": usage_base.c.model_name,
            "request_type": usage_base.c.request_type,
            "stat_date": usage_base.c.stat_date,
        }
        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_filters)

        query = query.group_by(
            usage_base.c.stat_date,
            usage_base.c.tenant_id,
            usage_base.c.tenant_name,
            usage_base.c.model_id,
            usage_base.c.model_name,
            usage_base.c.request_type,
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        sortable_fields = {
            "stat_date": usage_base.c.stat_date,
            "tenant_id": usage_base.c.tenant_id,
            "tenant_name": usage_base.c.tenant_name,
            "model_id": usage_base.c.model_id,
            "model_name": usage_base.c.model_name,
            "request_type": usage_base.c.request_type,
            "input_tokens": input_tokens_expr,
            "output_tokens": output_tokens_expr,
            "total_tokens": total_tokens_expr,
            "call_count": call_count_expr,
            "success_count": success_count_expr,
            "failed_count": failed_count_expr,
            "total_cost": total_cost_expr,
            "avg_latency_ms": avg_latency_expr,
            "max_latency_ms": max_latency_expr,
        }
        if spec.sort:
            query = self._apply_sort(query, spec.sort, sortable_fields)
        else:
            query = query.order_by(stat_date_col.desc(), total_tokens_expr.desc())

        query = query.offset(spec.offset).limit(spec.limit)
        rows = (await self.db.execute(query)).mappings().all()

        items = []
        for row in rows:
            items.append({
                "tenant_id": row["tenant_id"],
                "tenant_name": row["tenant_name"] or "-",
                "model_id": row["model_id"],
                "model_name": row["model_name"] or "-",
                "request_type": row["request_type"],
                "stat_date": str(row["stat_date"]),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "total_tokens": int(row["total_tokens"] or 0),
                "call_count": int(row["call_count"] or 0),
                "success_count": int(row["success_count"] or 0),
                "failed_count": int(row["failed_count"] or 0),
                "total_cost": float(row["total_cost"] or 0),
                "avg_latency_ms": (
                    float(row["avg_latency_ms"])
                    if row["avg_latency_ms"] is not None
                    else None
                ),
                "max_latency_ms": row["max_latency_ms"],
            })

        return items, total

    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        group_by: str | None = None,
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

        if group_by == "model":
            group_columns = [AICallLog.model_id]
            select_columns = [AICallLog.model_id] + agg_columns
        elif group_by == "user":
            group_columns = [AICallLog.user_id]
            select_columns = [AICallLog.user_id] + agg_columns
        else:
            group_columns = [func.date(AICallLog.created_at), AICallLog.model_id]
            select_columns = [
                func.date(AICallLog.created_at).label("date"),
                AICallLog.model_id,
            ] + agg_columns

        stmt = select(*select_columns).where(AICallLog.is_deleted.is_(False))

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AICallLog.created_at < end_date + timedelta(days=1))

        stmt = stmt.group_by(*group_columns)

        if group_by == "model":
            stmt = stmt.order_by(AICallLog.model_id)
        elif group_by == "user":
            stmt = stmt.order_by(AICallLog.user_id)
        else:
            stmt = stmt.order_by(func.date(AICallLog.created_at).desc(), AICallLog.model_id)

        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "date": str(row.date) if hasattr(row, "date") else None,
                "model_id": getattr(row, "model_id", None),
                "user_id": getattr(row, "user_id", None),
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
        tenant_id: int | None = None,
    ) -> AICallLog | None:
        """
        根据请求哈希查询日志（用于缓存命中检测）/ Get log by request hash (for cache hit detection).
        """
        stmt = select(AICallLog).where(
            AICallLog.request_hash == request_hash,
            AICallLog.status == CallStatusEnum.SUCCESS.value,
            AICallLog.is_deleted.is_(False),
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.order_by(AICallLog.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_logs(
        self,
        tenant_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AICallLog]:
        """
        获取最近的调用日志 / Get recent call logs.
        """
        stmt = select(AICallLog).where(AICallLog.is_deleted.is_(False))

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        limit: int = 100,
    ) -> list[AICallLog]:
        """
        获取失败的调用日志 / Get failed call logs.
        """
        stmt = select(AICallLog).where(
            AICallLog.status == CallStatusEnum.FAILED.value,
            AICallLog.is_deleted.is_(False),
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)

        stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit)
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
        ).where(AICallLog.is_deleted.is_(False))

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AICallLog.created_at < end_date + timedelta(days=1))

        row = (await self.db.execute(stmt)).one()

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

    async def get_billing_tenant_usage_summary(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get tenant usage summary from billing facts.
        从计费事实获取企业用量汇总。
        """
        filters = self._date_filters(start_date, end_date)
        filters.append(self._effective_usage_tenant_expr() == tenant_id)

        stmt = select(
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.count(AICallLog.id).label("call_count"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_count"),
        ).where(*filters)

        row = (await self.db.execute(stmt)).one()

        summary = {
            "total_tokens": int(row.total_tokens or 0),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "total_calls": int(row.call_count or 0),
            "total_cost": float(row.total_cost or 0),
            "success_calls": int(row.success_count or 0),
            "failed_calls": int(row.failed_count or 0),
        }

        ch_stmt = select(
            AICallLog.access_channel,
            func.count(AICallLog.id).label("ch_calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("ch_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("ch_cost"),
        ).where(*filters).group_by(AICallLog.access_channel)
        ch_rows = (await self.db.execute(ch_stmt)).all()
        summary["access_channel_stats"] = [
            {
                "access_channel": r.access_channel,
                "call_count": int(r.ch_calls or 0),
                "total_tokens": int(r.ch_tokens or 0),
                "total_cost": float(r.ch_cost or 0),
            }
            for r in ch_rows
        ]

        summary["daily_stats"] = await self.get_billing_daily_stats(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        summary["model_stats"] = await self.get_billing_model_stats(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        return summary

    async def get_billing_user_usage_summary(
        self,
        tenant_id: int,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get tenant-user usage summary from billing facts.
        从计费事实获取企业用户用量汇总。
        """
        filters = self._date_filters(start_date, end_date)
        filters.extend([
            self._effective_usage_tenant_expr() == tenant_id,
            AICallLog.actor_user_id == user_id,
            AICallLog.actor_user_type == UserTypeEnum.TENANT_USER.value,
        ])

        stmt = select(
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.count(AICallLog.id).label("call_count"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_count"),
        ).where(*filters)

        row = (await self.db.execute(stmt)).one()
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "total_tokens": int(row.total_tokens or 0),
            "total_calls": int(row.call_count or 0),
            "total_cost": float(row.total_cost or 0),
            "success_calls": int(row.success_count or 0),
            "failed_calls": int(row.failed_count or 0),
        }

    async def get_billing_model_usage_summary(
        self,
        model_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get model usage summary from billing facts.
        从计费事实获取模型用量汇总。
        """
        filters = self._date_filters(start_date, end_date)
        filters.extend([
            AICallLog.model_id == model_id,
            self._effective_usage_tenant_expr().is_not(None),
        ])

        stmt = select(
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.count(AICallLog.id).label("call_count"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.count(func.distinct(self._effective_usage_tenant_expr())).label("tenant_count"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_count"),
        ).where(*filters)

        row = (await self.db.execute(stmt)).one()
        model_name = None
        model = await self.db.get(AIModel, model_id)
        if model:
            model_name = model.name

        return {
            "model_id": model_id,
            "model_name": model_name,
            "total_tokens": int(row.total_tokens or 0),
            "call_count": int(row.call_count or 0),
            "total_cost": float(row.total_cost or 0),
            "tenant_count": int(row.tenant_count or 0),
            "success_calls": int(row.success_count or 0),
            "failed_calls": int(row.failed_count or 0),
        }

    async def get_billing_daily_stats(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get tenant daily usage stats from billing facts / 从计费事实获取企业每日用量统计。"""
        stat_date_col = cast(AICallLog.created_at, Date)
        filters = self._date_filters(start_date, end_date)
        filters.append(self._effective_usage_tenant_expr() == tenant_id)

        stmt = select(
            stat_date_col.label("stat_date"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
            func.count(AICallLog.id).label("calls"),
        ).where(*filters).group_by(stat_date_col).order_by(stat_date_col)

        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "date": str(row.stat_date),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "cost": float(row.cost or 0),
                "calls": int(row.calls or 0),
            }
            for row in rows
        ]

    async def get_billing_model_stats(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get tenant usage stats by model from billing facts / 从计费事实获取企业按模型用量统计。"""
        filters = self._date_filters(start_date, end_date)
        filters.append(self._effective_usage_tenant_expr() == tenant_id)

        stmt = select(
            AICallLog.model_id,
            AIModel.name.label("model_name"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
            func.count(AICallLog.id).label("calls"),
        ).join(
            AIModel,
            AIModel.id == AICallLog.model_id,
            isouter=True,
        ).where(
            *filters
        ).group_by(
            AICallLog.model_id,
            AIModel.name,
        ).order_by(
            func.coalesce(func.sum(AICallLog.total_tokens), 0).desc(),
        )

        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "model_id": row.model_id,
                "model_name": row.model_name or "Unknown",
                "total_tokens": int(row.total_tokens or 0),
                "cost": float(row.cost or 0),
                "calls": int(row.calls or 0),
            }
            for row in rows
        ]


__all__ = ["AICallLogRepository"]

"""
Internal usage/query helpers for AI call log repository.
AI 调用日志 Repository 内部用量查询辅助函数。
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Date, case, cast, func, select

from app.configs.service import PLATFORM_TENANT_ID
from app.enums.ai import CallStatusEnum, UserTypeEnum
from app.models.ai import AICallLog
from app.models.ai.model import AIModel
from app.models.tenant.tenant import Tenant


def platform_usage_tenant_expr():
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


def effective_usage_tenant_expr():
    """
    Billing tenant wins; otherwise treat platform tenant_id=0 as a first-class usage bucket.
    优先计费企业；若为空，则将平台 tenant_id=0 视为有效统计归属。
    """
    return func.coalesce(
        AICallLog.billing_tenant_id,
        platform_usage_tenant_expr(),
    )


def effective_usage_tenant_name_expr(platform_usage_tenant_name: str):
    """Stable tenant display name for usage aggregates, including platform internal usage."""
    return func.coalesce(
        AICallLog.billing_tenant_name_snapshot,
        Tenant.name,
        case(
            (
                effective_usage_tenant_expr() == PLATFORM_TENANT_ID,
                platform_usage_tenant_name,
            ),
            else_=None,
        ),
    )


def date_filters(
    start_date: date | None = None,
    end_date: date | None = None,
) -> list:
    filters = [AICallLog.is_deleted.is_(False)]
    if start_date:
        filters.append(AICallLog.created_at >= start_date)
    if end_date:
        filters.append(AICallLog.created_at < end_date + timedelta(days=1))
    return filters


async def query_usage_stats(repo, spec) -> tuple[list[dict], int]:
    """
    Query billing usage statistics grouped by day + tenant + model + request_type.
    查询按日期 + 计费企业 + 模型 + 请求类型聚合的计费用量统计。
    """
    stat_date_col = cast(AICallLog.created_at, Date)
    model_name_expr = func.coalesce(AIModel.name, AIModel.code)

    usage_base = (
        select(
            stat_date_col.label("stat_date"),
            repo._effective_usage_tenant_expr().label("tenant_id"),
            repo._effective_usage_tenant_name_expr().label("tenant_name"),
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
            repo._effective_usage_tenant_expr().is_not(None),
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
        query = repo._apply_filters(query, spec.filters, allowed_filters)

    query = query.group_by(
        usage_base.c.stat_date,
        usage_base.c.tenant_id,
        usage_base.c.tenant_name,
        usage_base.c.model_id,
        usage_base.c.model_name,
        usage_base.c.request_type,
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await repo.db.execute(count_query)).scalar() or 0

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
        query = repo._apply_sort(query, spec.sort, sortable_fields)
    else:
        query = query.order_by(stat_date_col.desc(), total_tokens_expr.desc())

    query = query.offset(spec.offset).limit(spec.limit)
    rows = (await repo.db.execute(query)).mappings().all()

    items = []
    for row in rows:
        items.append(
            {
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
            }
        )

    return items, total


async def get_statistics(
    db,
    *,
    tenant_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    group_by: str | None = None,
) -> list[dict]:
    agg_columns = [
        func.count(AICallLog.id).label("call_count"),
        func.sum(AICallLog.total_tokens).label("total_tokens"),
        func.sum(AICallLog.input_tokens).label("input_tokens"),
        func.sum(AICallLog.output_tokens).label("output_tokens"),
        func.sum(AICallLog.cost).label("total_cost"),
        func.avg(AICallLog.latency_ms).label("avg_latency"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
        ).label("failed_count"),
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

    rows = (await db.execute(stmt)).all()
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


async def get_overall_summary(
    db,
    *,
    tenant_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    stmt = select(
        func.count(AICallLog.id).label("total_calls"),
        func.sum(AICallLog.total_tokens).label("total_tokens"),
        func.sum(AICallLog.input_tokens).label("input_tokens"),
        func.sum(AICallLog.output_tokens).label("output_tokens"),
        func.sum(AICallLog.cost).label("total_cost"),
        func.avg(AICallLog.latency_ms).label("avg_latency"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        ).label("success_calls"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
        ).label("failed_calls"),
    ).where(AICallLog.is_deleted.is_(False))

    if tenant_id is not None:
        stmt = stmt.where(AICallLog.tenant_id == tenant_id)
    if start_date:
        stmt = stmt.where(AICallLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AICallLog.created_at < end_date + timedelta(days=1))

    row = (await db.execute(stmt)).one()
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
    repo,
    *,
    tenant_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    filters = repo._date_filters(start_date, end_date)
    filters.append(repo._effective_usage_tenant_expr() == tenant_id)

    stmt = select(
        func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
        func.count(AICallLog.id).label("call_count"),
        func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
        ).label("failed_count"),
    ).where(*filters)

    row = (await repo.db.execute(stmt)).one()
    summary = {
        "total_tokens": int(row.total_tokens or 0),
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "total_calls": int(row.call_count or 0),
        "total_cost": float(row.total_cost or 0),
        "success_calls": int(row.success_count or 0),
        "failed_calls": int(row.failed_count or 0),
    }

    ch_stmt = (
        select(
            AICallLog.access_channel,
            func.count(AICallLog.id).label("ch_calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("ch_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("ch_cost"),
        )
        .where(*filters)
        .group_by(AICallLog.access_channel)
    )
    ch_rows = (await repo.db.execute(ch_stmt)).all()
    summary["access_channel_stats"] = [
        {
            "access_channel": row.access_channel,
            "call_count": int(row.ch_calls or 0),
            "total_tokens": int(row.ch_tokens or 0),
            "total_cost": float(row.ch_cost or 0),
        }
        for row in ch_rows
    ]

    summary["daily_stats"] = await get_billing_daily_stats(
        repo,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    summary["model_stats"] = await get_billing_model_stats(
        repo,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return summary


async def get_billing_user_usage_summary(
    repo,
    *,
    tenant_id: int,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    filters = repo._date_filters(start_date, end_date)
    filters.extend(
        [
            repo._effective_usage_tenant_expr() == tenant_id,
            AICallLog.actor_user_id == user_id,
            AICallLog.actor_user_type == UserTypeEnum.TENANT_USER.value,
        ]
    )

    stmt = select(
        func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
        func.count(AICallLog.id).label("call_count"),
        func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
        ).label("failed_count"),
    ).where(*filters)

    row = (await repo.db.execute(stmt)).one()
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
    repo,
    *,
    model_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    filters = repo._date_filters(start_date, end_date)
    filters.extend(
        [
            AICallLog.model_id == model_id,
            repo._effective_usage_tenant_expr().is_not(None),
        ]
    )

    stmt = select(
        func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
        func.count(AICallLog.id).label("call_count"),
        func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
        func.count(func.distinct(repo._effective_usage_tenant_expr())).label(
            "tenant_count"
        ),
        func.sum(
            case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
        ).label("failed_count"),
    ).where(*filters)

    row = (await repo.db.execute(stmt)).one()
    model_name = None
    model = await repo.db.get(AIModel, model_id)
    if model:
        model_name = model.name or model.code

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
    repo,
    *,
    tenant_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    stat_date_col = cast(AICallLog.created_at, Date)
    filters = repo._date_filters(start_date, end_date)
    filters.append(repo._effective_usage_tenant_expr() == tenant_id)

    stmt = (
        select(
            stat_date_col.label("stat_date"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
            func.count(AICallLog.id).label("calls"),
        )
        .where(*filters)
        .group_by(stat_date_col)
        .order_by(stat_date_col)
    )

    rows = (await repo.db.execute(stmt)).all()
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
    repo,
    *,
    tenant_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    filters = repo._date_filters(start_date, end_date)
    filters.append(repo._effective_usage_tenant_expr() == tenant_id)

    stmt = (
        select(
            AICallLog.model_id,
            func.coalesce(AIModel.name, AIModel.code).label("model_name"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
            func.count(AICallLog.id).label("calls"),
        )
        .join(
            AIModel,
            AIModel.id == AICallLog.model_id,
            isouter=True,
        )
        .where(*filters)
        .group_by(
            AICallLog.model_id,
            AIModel.name,
            AIModel.code,
        )
        .order_by(
            func.coalesce(func.sum(AICallLog.total_tokens), 0).desc(),
        )
    )

    rows = (await repo.db.execute(stmt)).all()
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


__all__ = [
    "date_filters",
    "effective_usage_tenant_expr",
    "effective_usage_tenant_name_expr",
    "get_billing_daily_stats",
    "get_billing_model_stats",
    "get_billing_model_usage_summary",
    "get_billing_tenant_usage_summary",
    "get_billing_user_usage_summary",
    "get_overall_summary",
    "get_statistics",
    "platform_usage_tenant_expr",
    "query_usage_stats",
]

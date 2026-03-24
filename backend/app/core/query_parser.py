"""
JSON:API 查询参数解析器 / JSON:API Query Parameter Parser

解析 JSON:API 风格的查询参数，转换为 QuerySpec 对象
Parses JSON:API style query parameters and converts them to QuerySpec objects.

支持的参数格式 / Supported parameter formats:
- filter[field]=value          等值过滤 / Equality filter
- filter[field][op]=value      带操作符过滤 / Operator filter
- sort=-created_at,name        排序（前缀 - 表示降序） / Sort (prefix - for descending)
- page[number]=1               页码 / Page number
- page[size]=20                每页数量 / Page size
"""

import re
from typing import Annotated

from fastapi import Depends, Request

from app.schemas.common.query import FilterOp, FilterRule, QuerySpec

# 正则表达式匹配 filter[field] 或 filter[field][op]
FILTER_PATTERN = re.compile(r"^filter\[([^\]]+)\](?:\[([^\]]+)\])?$")
PAGE_NUMBER_KEY = "page[number]"
PAGE_SIZE_KEY = "page[size]"


def parse_query_spec(request: Request) -> QuerySpec:
    """
    从请求中解析 JSON:API 风格的查询参数。
    Parse JSON:API-style query parameters from the request.

    Args:
        request: FastAPI 请求对象 / FastAPI request object.

    Returns:
        QuerySpec 对象 / QuerySpec instance.

    示例 / Example:
        GET /users?filter[status]=active&filter[created_at][gte]=2025-01-01&sort=-created_at&page[number]=1&page[size]=20

        解析结果 / Parsed result:
        QuerySpec(
            filters=[
                FilterRule(field="status", op="eq", value="active"),
                FilterRule(field="created_at", op="gte", value="2025-01-01"),
            ],
            sort=["-created_at"],
            page=1,
            size=20
        )
    """
    params = dict(request.query_params)
    filters: list[FilterRule] = []
    sort: list[str] = []
    page = 1
    size = 20

    for key, value in params.items():
        # 跳过空值 / Skip empty values
        if not value:
            continue

        # 解析 filter 参数 / Parse filter parameter
        match = FILTER_PATTERN.match(key)
        if match:
            field = match.group(1)
            op_str = match.group(2)

            # 确定操作符 / Determine operator
            if op_str:
                try:
                    op = FilterOp(op_str)
                except ValueError:
                    # 未知操作符，跳过 / Unknown operator, skip
                    continue
            else:
                op = FilterOp.eq

            # 处理 between 操作符的第二个值
            value2 = None
            if op == FilterOp.between and "," in value:
                # between 值格式: "start,end"
                parts = value.split(",", 1)
                value = parts[0].strip()
                value2 = parts[1].strip() if len(parts) > 1 else None

            filters.append(FilterRule(
                field=field,
                op=op,
                value=value,
                value2=value2,
            ))
            continue

        # 解析 sort 参数
        if key == "sort":
            sort = [s.strip() for s in value.split(",") if s.strip()]
            continue

        # 解析分页参数 / Parse JSON:API page[number] / page[size]
        if key == PAGE_NUMBER_KEY:
            try:
                page = max(1, int(value))
            except ValueError:
                page = 1
            continue

        if key == PAGE_SIZE_KEY:
            try:
                size = max(1, min(100, int(value)))
            except ValueError:
                size = 20
            continue

    return QuerySpec(
        filters=filters,
        sort=sort,
        page=page,
        size=size,
    )


async def get_query_spec(request: Request) -> QuerySpec:
    """
    FastAPI 依赖注入函数 / FastAPI dependency injection function.

    用于在路由中注入 QuerySpec 对象

    使用示例:
        @router.get("/users")
        async def list_users(
            spec: QuerySpec = Depends(get_query_spec),
        ):
            items, total = await repo.query_list(spec)
            return {"items": items, "total": total}
    """
    return parse_query_spec(request)


QueryParams = Annotated[QuerySpec, Depends(get_query_spec)]


__all__ = [
    "parse_query_spec",
    "get_query_spec",
    "QueryParams",
]

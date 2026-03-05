"""
通用查询 Schema

定义列表筛选、排序、分页的数据结构，支持 JSON:API 风格查询参数
"""

from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from app.core.base_schema import BaseSchema


class FilterOp(str, Enum):
    """
    筛选操作符枚举

    支持的操作符:
    - eq: 等于（默认）
    - ne: 不等于
    - lt: 小于
    - lte: 小于等于
    - gt: 大于
    - gte: 大于等于
    - like: 模糊匹配（区分大小写）
    - ilike: 模糊匹配（不区分大小写）
    - in_: 在列表中
    - between: 区间
    - isnull: 为空
    - notnull: 不为空
    """

    eq = "eq"
    ne = "ne"
    lt = "lt"
    lte = "lte"
    gt = "gt"
    gte = "gte"
    like = "like"
    ilike = "ilike"
    in_ = "in"
    between = "between"
    isnull = "isnull"
    notnull = "notnull"


class FilterRule(BaseSchema):
    """
    筛选规则

    定义单个筛选条件的结构

    示例:
    - 等值: {"field": "status", "op": "eq", "value": "active"}
    - 区间: {"field": "created_at", "op": "between", "value": "2025-01-01", "value2": "2025-12-31"}
    - 列表: {"field": "id", "op": "in", "value": "1,2,3"}
    """

    field: str = Field(..., description="字段名")
    op: FilterOp = Field(default=FilterOp.eq, description="操作符")
    value: Any = Field(default=None, description="筛选值")
    value2: Any = Field(default=None, description="第二个值（用于 between 操作符）")


class QuerySpec(BaseSchema):
    """
    查询规格

    定义列表查询的完整参数，包括筛选、排序、分页

    JSON:API 风格参数示例:
    - filter[status]=active
    - filter[created_at][gte]=2025-01-01
    - sort=-created_at,name
    - page[number]=1
    - page[size]=20
    """

    filters: list[FilterRule] = Field(default_factory=list, description="筛选条件列表")
    sort: list[str] = Field(default_factory=list, description="排序字段列表，前缀 - 表示降序")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        """验证页码"""
        if v < 1:
            raise ValueError("errors.pagination.invalid_page")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        """验证每页数量"""
        if v < 1:
            raise ValueError("errors.pagination.invalid_size")
        if v > 100:
            raise ValueError("errors.pagination.size_exceeded")
        return v

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: list[FilterRule]) -> list[FilterRule]:
        """验证筛选条件数量"""
        if len(v) > 20:
            raise ValueError("errors.filters.too_many")
        return v

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.size


__all__ = [
    "FilterOp",
    "FilterRule",
    "QuerySpec",
]

"""
通用排序 Schema

提供批量重排序相关的请求/响应模型
"""

from pydantic import BaseModel, Field


class ReorderRequest(BaseModel):
    """
    批量重排序请求

    前端拖拽排序完成后，发送完整的有序 ID 列表
    后端会按顺序分配排序值（step*1, step*2, ...）

    Example:
        {
            "ids": [3, 1, 5, 2, 4],
            "parent_id": 1  // 可选，限定同级范围
        }
    """

    ids: list[int] = Field(
        ...,
        min_length=1,
        description="有序的 ID 列表，按此顺序重新分配排序值",
    )

    # 可选的作用域参数
    parent_id: int | None = Field(
        None,
        description="父节点 ID（用于树形结构的同级排序）",
    )

    tenant_id: int | None = Field(
        None,
        description="租户 ID（用于租户内排序，通常由系统自动注入）",
    )


class ReorderResponse(BaseModel):
    """
    批量重排序响应
    """

    updated_count: int = Field(
        ...,
        description="更新的记录数",
    )


__all__ = ["ReorderRequest", "ReorderResponse"]

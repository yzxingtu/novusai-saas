"""
通用下拉选项 Schema / Common Select Option Schema

提供前端远程下拉组件的统一响应格式，支持列表和树型两种结构
Provides unified response format for frontend remote select components, supports list and tree structures.

使用示例:
    # 列表模式（默认） / List mode (default)
    GET /api/roles/select
    -> {"items": [{"label": "角色1", "value": 1}, ...]}

    # 树型模式 / Tree mode
    GET /api/roles/select?tree=true
    -> {"items": [{"label": "研发部", "value": 1, "children": [...]}]}

    # 懒加载模式（获取指定父节点的子节点） / Lazy load (children of parent)
    GET /api/roles/select?tree=true&parent_id=1
    -> {"items": [{"label": "前端组", "value": 2, "is_leaf": true}, ...]}
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SelectOption(BaseModel):
    """
    下拉选项（支持树型结构） / Select option (supports tree).

    统一的下拉选项数据结构，同时支持列表和树型两种模式。List mode: label, value, extra, disabled. Tree mode: includes children.
    """

    label: str
    """显示文本 / Display label"""

    value: int | str
    """选中值 / Selected value"""

    extra: dict[str, Any] | None = None
    """额外数据（如 code、icon、type 等）/ Extra data (e.g. code, icon, type)"""

    disabled: bool = False
    """是否禁用 / Whether disabled"""

    # ========== 树型扩展字段 ========== / Tree extra fields
    children: list[SelectOption] | None = Field(default=None)
    """子节点列表（仅 tree=true 时返回）/ Children (when tree=true)"""

    is_leaf: bool | None = Field(default=None)
    """是否叶子节点（仅 tree=true 时返回，用于懒加载场景）/ Is leaf node (for lazy load)"""


class SelectResponse(BaseModel):
    """
    下拉选项列表响应（支持分页） / Select list response (supports pagination).
    分页模式: page>=1 返回分页信息；非分页: page=0 返回全部（受 limit 限制）。
    """

    items: list[SelectOption]
    """选项列表（列表模式或树型模式）/ Option list (list or tree mode)"""

    # ========== 分页字段（仅分页模式返回） ========== / Pagination fields
    total: int | None = None
    """总记录数（仅分页模式返回）/ Total count (when paginated)"""

    page: int | None = None
    """当前页码（仅分页模式返回）/ Current page (when paginated)"""

    page_size: int | None = None
    """每页数量（仅分页模式返回）/ Page size (when paginated)"""

    has_more: bool | None = None
    """是否有更多数据（仅分页模式返回）/ Whether more data (when paginated)"""


__all__ = ["SelectOption", "SelectResponse"]

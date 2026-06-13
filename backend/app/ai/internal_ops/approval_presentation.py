"""
Tool Approval Presentation Builder / 工具操作确认展示数据构建器

Generates a user-readable ``ToolApprovalPresentation`` structure for
``invoke_internal_operation`` write confirmations, so the frontend can
render a meaningful approval card instead of raw JSON.

基于 RBAC 权限树为内部操作写确认生成用户可读展示数据，
供前端确认卡片渲染，不额外调用 LLM。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.auth.permission import Permission
from app.rbac.services.permission_domains.presentation import (
    PermissionPresentationDomain,
)

logger = LogManager.get_logger("ai.internal_ops.approval_presentation")

# ── Sensitive field filtering / 敏感字段过滤 ──────────────────────────────

_SENSITIVE_KEYWORDS: frozenset[str] = frozenset({
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "headers",
    "access_token",
    "refresh_token",
    "secret_key",
    "private_key",
    "credential",
})

_SENSITIVE_RE = re.compile(
    "|".join(
        re.escape(kw.replace("_", "").replace("-", ""))
        for kw in _SENSITIVE_KEYWORDS
    ),
    re.IGNORECASE,
)

# ── Action label mapping / 操作标签映射 ───────────────────────────────────

_ACTION_LABELS: dict[str, str] = {
    "create": "创建",
    "update": "更新",
    "delete": "删除",
    "read": "查看",
    "list": "查询列表",
    "export": "导出",
    "import": "导入",
    "enable": "启用",
    "disable": "禁用",
    "reset": "重置",
    "assign": "分配",
    "revoke": "撤销",
}

# ── Risk level heuristics / 风险等级启发式 ─────────────────────────────────

_HIGH_RISK_METHODS = frozenset({"DELETE"})
_HIGH_RISK_ACTIONS = frozenset({"delete", "disable", "revoke", "reset"})


# ── Data structures / 数据结构 ─────────────────────────────────────────────


@dataclass
class ApprovalTarget:
    """Target entity of the operation / 操作目标实体"""

    type: str | None = None
    name: str | None = None


@dataclass
class ApprovalDetail:
    """A single safe business detail / 单条安全业务详情"""

    label: str
    value: str
    sensitive: bool = False


@dataclass
class ToolApprovalPresentation:
    """User-readable confirmation card payload / 用户可读确认卡片数据"""

    title: str
    summary: str | None = None
    risk_level: str | None = None  # low | medium | high
    operation_type: str | None = None
    permission_code: str | None = None
    menu_label: str | None = None
    action_label: str | None = None
    target: ApprovalTarget | None = None
    details: list[ApprovalDetail] = field(default_factory=list)
    technical: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict / 序列化为 JSON 安全字典"""
        data = asdict(self)
        # Remove None top-level fields for cleaner JSON / 移除空字段
        return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}


# ── Internal helpers / 内部辅助 ────────────────────────────────────────────


def _is_sensitive_key(key: str) -> bool:
    """Whether a field name is sensitive / 字段名是否敏感"""
    normalized = key.replace("-", "").replace("_", "").lower()
    return bool(_SENSITIVE_RE.search(normalized))


def _infer_risk_level(method: str, action: str) -> str:
    """Heuristic risk level from HTTP method + RBAC action / 从方法和操作推断风险等级"""
    if method in _HIGH_RISK_METHODS or action in _HIGH_RISK_ACTIONS:
        return "high"
    if method in ("POST", "PATCH", "PUT"):
        return "medium"
    return "low"


def _resolve_action_label(action: str) -> str:
    """Translate an RBAC action to a display label / 将 RBAC 操作标识转为显示标签"""
    if action in _ACTION_LABELS:
        return _ACTION_LABELS[action]
    return PermissionPresentationDomain.translate_name(action)


def _extract_safe_details(
    *,
    body: dict[str, Any] | None,
    path_params: dict[str, Any],
    query_params: dict[str, Any],
    max_fields: int = 10,
) -> list[ApprovalDetail]:
    """
    Extract non-sensitive key-value pairs from request params /
    从请求参数中提取非敏感键值对。

    Sensitive keys are excluded entirely (not even shown with mask).
    敏感字段完全排除（不展示，不传给 LLM）。
    """
    details: list[ApprovalDetail] = []

    # Body fields (most relevant for write ops) / 请求体字段
    if body and isinstance(body, dict):
        for key, value in body.items():
            if _is_sensitive_key(key):
                continue
            if value is None:
                continue
            display_value = _format_detail_value(value)
            if display_value:
                details.append(ApprovalDetail(label=key, value=display_value))
                if len(details) >= max_fields:
                    return details

    # Path params (entity identifiers) / 路径参数
    for key, value in path_params.items():
        if _is_sensitive_key(key):
            continue
        display_value = _format_detail_value(value)
        if display_value:
            details.append(ApprovalDetail(label=key, value=display_value))
            if len(details) >= max_fields:
                return details

    # Query params (supplementary) / 查询参数
    for key, value in query_params.items():
        if _is_sensitive_key(key):
            continue
        display_value = _format_detail_value(value)
        if display_value:
            details.append(ApprovalDetail(label=key, value=display_value))
            if len(details) >= max_fields:
                return details

    return details


def _format_detail_value(value: Any) -> str:
    """Format a value for display, skipping complex nested objects / 格式化展示值"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        # Skip overly long strings (likely blobs/JSON) / 跳过过长字符串
        if len(text) > 200:
            return ""
        return text
    # Skip dicts / lists (too complex for a summary card) / 跳过复杂结构
    return ""


def _build_title(
    *,
    action_label: str,
    menu_label: str | None,
    permission: Permission | None,
    operation_summary: str,
    method: str,
    path: str,
    permission_code: str,
) -> str:
    """
    Build a human-readable title with stable fallback chain /
    构建可读标题，带稳定兜底链。

    Priority:
    1. action_label + menu_label (e.g. "创建 套餐管理")
    2. translated permission name
    3. operation summary
    4. method + path + permission_code
    """
    if permission is not None:
        translated = PermissionPresentationDomain.translate_name(permission.name)
        if translated and translated != permission.name:
            if action_label and menu_label:
                return f"{action_label} {menu_label}"
            return translated

    if action_label and menu_label:
        return f"{action_label} {menu_label}"

    if operation_summary:
        return operation_summary

    return f"{method} {path} ({permission_code})"


# ── DB lookup / 数据库查询 ─────────────────────────────────────────────────


async def _find_permission_by_code(
    db: AsyncSession,
    permission_code: str,
) -> Permission | None:
    """Look up a Permission record by code / 按权限码查找 Permission 记录"""
    result = await db.execute(
        select(Permission).where(Permission.code == permission_code).limit(1)
    )
    return result.scalar_one_or_none()


async def _find_parent_menu(
    db: AsyncSession,
    permission: Permission,
) -> Permission | None:
    """
    Walk up the parent chain to find the nearest menu-type ancestor /
    沿父级链向上查找最近的菜单类型祖先。
    """
    current = permission
    guard = 0
    while current.parent_id is not None and guard < 10:
        guard += 1
        result = await db.execute(
            select(Permission).where(Permission.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent is None:
            break
        if parent.type == "menu":
            return parent
        current = parent
    return None


# ── Public API / 公开接口 ──────────────────────────────────────────────────


async def build_approval_presentation(
    *,
    db: AsyncSession | None,
    operation_id: str,
    method: str,
    path: str,
    permission_code: str,
    summary: str = "",
    action: str = "",
    body: dict[str, Any] | None = None,
    path_params: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
) -> ToolApprovalPresentation:
    """
    Build a ``ToolApprovalPresentation`` for a write operation confirmation /
    为写操作确认构建展示数据。

    This function is **pure lookup** — no LLM calls, no token consumption.
    本函数纯查询，不调用 LLM，不消耗 token。
    """
    path_params = dict(path_params or {})
    query_params = dict(query_params or {})

    permission: Permission | None = None
    menu_label: str | None = None

    # DB-backed lookup (permission + parent menu) / 数据库查询权限与父菜单
    if db is not None:
        try:
            permission = await _find_permission_by_code(db, permission_code)
            if permission is not None:
                parent_menu = await _find_parent_menu(db, permission)
                if parent_menu is not None:
                    menu_label = PermissionPresentationDomain.translate_name(
                        parent_menu.name
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Approval presentation DB lookup failed for {}: {}",
                permission_code,
                exc,
            )

    action_label = _resolve_action_label(action) if action else None
    risk_level = _infer_risk_level(method, action)

    title = _build_title(
        action_label=action_label or method,
        menu_label=menu_label,
        permission=permission,
        operation_summary=summary,
        method=method,
        path=path,
        permission_code=permission_code,
    )

    details = _extract_safe_details(
        body=body,
        path_params=path_params,
        query_params=query_params,
    )

    # Infer target entity from path_params / 从路径参数推断目标实体
    target: ApprovalTarget | None = None
    if path_params:
        first_key = next(iter(path_params))
        target = ApprovalTarget(
            type=first_key.replace("_id", "").replace("_", " "),
            name=str(path_params[first_key]),
        )

    technical = {
        "operation_id": operation_id,
        "method": method,
        "path": path,
        "permission_code": permission_code,
        "action": action,
    }

    return ToolApprovalPresentation(
        title=title,
        summary=summary or None,
        risk_level=risk_level,
        operation_type=method,
        permission_code=permission_code,
        menu_label=menu_label,
        action_label=action_label,
        target=target,
        details=details,
        technical=technical,
    )


__all__ = [
    "ApprovalDetail",
    "ApprovalTarget",
    "ToolApprovalPresentation",
    "build_approval_presentation",
]

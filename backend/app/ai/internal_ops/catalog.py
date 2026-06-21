"""
Internal Operation Catalog / 内部操作目录

Scans the FastAPI route table at runtime and extracts every endpoint that
carries RBAC permission decorators (_permission_resource + _permission_action)
into a machine-readable operation catalog. The catalog requires zero manual
maintenance: any new admin/tenant endpoint shows up automatically.
运行时扫描 FastAPI 路由表，将携带 RBAC 权限装饰器的端点提取为机器可读的
操作目录。目录零手工维护：新增后台端点会自动进入目录。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import LogManager
from app.enums.common import UserRoleEnum

logger = LogManager.get_logger("ai.internal_ops.catalog")

# Scope prefixes by API surface / 各端 API 前缀
SCOPE_PREFIXES: dict[str, str] = {
    "admin": "/admin",
    "tenant": "/tenant",
    "user": "/api/user",
}

# Map conversation user_role to catalog scope / 对话用户角色到目录作用域的映射
USER_ROLE_TO_SCOPE: dict[str, str] = {
    UserRoleEnum.PLATFORM_ADMIN.value: "admin",
    UserRoleEnum.TENANT_ADMIN.value: "tenant",
    UserRoleEnum.TENANT_USER.value: "user",
}

# Path snippets excluded from the catalog / 排除出目录的路径片段
# - plugin dynamic routes use their own auth wrapper / 插件动态路由有独立鉴权包装
# - agent-chat endpoints would let the copilot recurse into itself / 避免对话端点自递归
# - SSE/websocket endpoints are not suitable for tool invocation / 流式端点不适合工具调用
_EXCLUDED_PATH_SNIPPETS = (
    "/plugins/",
    "/agent-chat",
    "/ws",
)
_EXCLUDED_PATH_SUFFIXES = ("/stream",)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass
class InternalOperation:
    """A single internal API operation / 单个内部 API 操作"""

    operation_id: str
    method: str
    path: str
    scope: str  # admin | tenant | user
    module: str  # RBAC resource, e.g. "tenant" / RBAC 资源标识
    action: str  # RBAC action, e.g. "create" / RBAC 操作标识
    permission_code: str  # e.g. "tenant:create"
    summary: str = ""
    path_params: list[dict[str, Any]] = field(default_factory=list)
    query_params: list[dict[str, Any]] = field(default_factory=list)
    body_schema: dict[str, Any] | None = None

    @property
    def is_write(self) -> bool:
        """Whether this operation mutates state / 是否为写操作"""
        return self.method in _WRITE_METHODS

    def to_brief(self) -> dict[str, Any]:
        """Compact form for list results / 列表结果的紧凑形式"""
        return {
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "module": self.module,
            "summary": self.summary,
            "permission": self.permission_code,
            "is_write": self.is_write,
        }

    def to_detail(self) -> dict[str, Any]:
        """Full form for describe results / 详情结果的完整形式"""
        detail = self.to_brief()
        detail["path_params"] = self.path_params
        detail["query_params"] = self.query_params
        detail["body_schema"] = self.body_schema
        if self.is_write:
            detail["note"] = (
                "Write operation: invocation requires user confirmation "
                "before it is executed."
            )
        elif self.method == "GET" and not self.query_params:
            # List endpoints parse the query string dynamically (QuerySpec)
            # 列表端点动态解析查询串（QuerySpec 约定）
            detail["note"] = (
                "List endpoints accept the standard query convention: "
                "filter[field]=value, filter[field][op]=value (op: gte/lte/"
                "like/in...), sort=-created_at, page[number]=1, page[size]=20."
            )
        return detail


_catalog_lock = threading.Lock()
_catalog_cache: list[InternalOperation] | None = None


def _resolve_scope(path: str) -> str | None:
    """Resolve catalog scope from route path / 从路由路径解析目录作用域"""
    for scope, prefix in SCOPE_PREFIXES.items():
        if path == prefix or path.startswith(prefix + "/"):
            return scope
    return None


def _is_excluded_path(path: str) -> bool:
    if any(snippet in path for snippet in _EXCLUDED_PATH_SNIPPETS):
        return True
    return any(path.endswith(suffix) for suffix in _EXCLUDED_PATH_SUFFIXES)


def _join_paths(prefix: str, path: str) -> str:
    """Join route path fragments without losing the leading slash."""
    prefix = str(prefix or "").strip()
    path = str(path or "").strip()
    if not prefix and not path:
        return ""
    if not prefix:
        joined = path
    elif not path:
        joined = prefix
    else:
        joined = f"{prefix.rstrip('/')}/{path.lstrip('/')}"
    if not joined.startswith("/"):
        joined = f"/{joined}"
    return joined


def _iter_routes(routes: Any, prefix: str = ""):
    """
    Recursively yield concrete routes with their effective path.

    FastAPI/Starlette may keep included routers as nested routing nodes in some
    runtime versions, so catalog building must not rely on a flat app.routes.
    """
    for route in routes or []:
        route_path = str(getattr(route, "path", "") or "")
        route_prefix = str(getattr(route, "prefix", "") or "")
        nested_routes = getattr(route, "routes", None)

        if nested_routes:
            nested_prefix = _join_paths(prefix, route_path or route_prefix)
            yield from _iter_routes(nested_routes, nested_prefix)
            continue

        if route_path:
            yield route, _join_paths(prefix, route_path)


def _annotation_name(annotation: Any) -> str:
    """Best-effort readable type name / 尽力而为的可读类型名"""
    if annotation is None:
        return "string"
    name = getattr(annotation, "__name__", None)
    if name:
        return str(name)
    return str(annotation).replace("typing.", "")


def _collect_dependant_fields(dependant: Any, attr: str) -> list[Any]:
    """
    Recursively collect path/query param fields, including sub-dependencies
    (e.g. QuerySpec-style dependency injectors).
    递归收集路径/查询参数字段，包含子依赖（如 QuerySpec 风格的依赖注入器）。
    """
    if dependant is None:
        return []
    collected: list[Any] = []
    seen_names: set[str] = set()
    stack = [dependant]
    guard = 0
    while stack and guard < 200:
        guard += 1
        current = stack.pop()
        for f in getattr(current, attr, None) or []:
            name = str(getattr(f, "alias", None) or getattr(f, "name", ""))
            if name and name not in seen_names:
                seen_names.add(name)
                collected.append(f)
        stack.extend(getattr(current, "dependencies", None) or [])
    return collected


def _extract_param_fields(fields: Any) -> list[dict[str, Any]]:
    """
    Extract name/type/required from FastAPI dependant ModelFields.
    从 FastAPI dependant 的 ModelField 中提取参数名/类型/必填信息。
    """
    params: list[dict[str, Any]] = []
    for f in fields or []:
        try:
            field_info = getattr(f, "field_info", None)
            annotation = getattr(field_info, "annotation", None) if field_info else None
            description = (
                str(getattr(field_info, "description", "") or "") if field_info else ""
            )
            default = getattr(field_info, "default", None) if field_info else None
            entry: dict[str, Any] = {
                "name": str(getattr(f, "alias", None) or getattr(f, "name", "")),
                "type": _annotation_name(annotation),
                "required": bool(getattr(f, "required", False)),
            }
            if description:
                entry["description"] = description
            if not entry["required"] and default is not None:
                default_repr = repr(default)
                # PydanticUndefined and similar sentinels are noise / 过滤未定义哨兵值
                if "Undefined" not in default_repr and "Ellipsis" not in default_repr:
                    entry["default"] = default_repr
            params.append(entry)
        except Exception:  # noqa: BLE001
            # A single odd parameter must not break the whole catalog
            # 单个异常参数不应破坏整个目录
            continue
    return params


def _extract_body_schema(route: Any) -> dict[str, Any] | None:
    """Extract request body JSON Schema if present / 提取请求体 JSON Schema"""
    body_field = getattr(route, "body_field", None)
    if body_field is None:
        return None
    try:
        model = getattr(body_field, "type_", None)
        if model is not None and hasattr(model, "model_json_schema"):
            return model.model_json_schema()
        field_info = getattr(body_field, "field_info", None)
        annotation = getattr(field_info, "annotation", None) if field_info else None
        if annotation is not None and hasattr(annotation, "model_json_schema"):
            return annotation.model_json_schema()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Body schema extraction failed for {}: {}", route, exc)
    return None


def _extract_summary(route: Any) -> str:
    summary = str(getattr(route, "summary", "") or "").strip()
    if summary:
        return summary
    endpoint = getattr(route, "endpoint", None)
    doc = str(getattr(endpoint, "__doc__", "") or "").strip()
    if doc:
        return doc.splitlines()[0].strip()
    return str(getattr(route, "name", "") or "")


def _build_catalog_from_app(app: Any) -> list[InternalOperation]:
    """Build catalog from a FastAPI app instance / 从 FastAPI 应用实例构建目录"""
    operations: list[InternalOperation] = []
    seen_ids: set[str] = set()

    for route, path in _iter_routes(getattr(app, "routes", [])):
        methods = getattr(route, "methods", None)
        endpoint = getattr(route, "endpoint", None)
        if not path or not methods or endpoint is None:
            continue

        scope = _resolve_scope(path)
        if scope is None or _is_excluded_path(path):
            continue

        resource = getattr(endpoint, "_permission_resource", None)
        action_info = getattr(endpoint, "_permission_action", None)
        if not resource or not isinstance(action_info, dict):
            # public / auth-only endpoints stay out of the catalog
            # 公开或仅认证端点不进入目录
            continue
        action = str(action_info.get("action") or "").strip()
        if not action:
            continue

        dependant = getattr(route, "dependant", None)
        path_params = _extract_param_fields(_collect_dependant_fields(dependant, "path_params"))
        query_params = _extract_param_fields(_collect_dependant_fields(dependant, "query_params"))
        body_schema = _extract_body_schema(route)
        summary = _extract_summary(route)

        for method in sorted(methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            operation_id = f"{method}:{path}"
            if operation_id in seen_ids:
                continue
            seen_ids.add(operation_id)
            operations.append(
                InternalOperation(
                    operation_id=operation_id,
                    method=method,
                    path=path,
                    scope=scope,
                    module=str(resource),
                    action=action,
                    permission_code=f"{resource}:{action}",
                    summary=summary,
                    path_params=path_params,
                    query_params=query_params,
                    body_schema=body_schema,
                )
            )

    operations.sort(key=lambda op: (op.scope, op.module, op.path, op.method))
    return operations


def _get_fastapi_app() -> Any:
    """
    Lazily fetch the running FastAPI app.
    懒加载获取正在运行的 FastAPI 应用实例。

    The executor only runs inside the API process where app.main is already
    imported, so this never triggers a fresh circular import at startup.
    执行器只在 API 进程内运行，app.main 已加载，不会触发启动期循环导入。
    """
    from app.main import app

    # app.main.app is a socketio ASGIApp wrapping the FastAPI instance
    # app.main.app 是包装了 FastAPI 实例的 socketio ASGIApp
    if hasattr(app, "routes"):
        return app
    inner = getattr(app, "other_asgi_app", None)
    if inner is not None and hasattr(inner, "routes"):
        return inner
    raise RuntimeError("FastAPI app instance not found on app.main.app")


def get_operation_catalog(refresh: bool = False) -> list[InternalOperation]:
    """Get (and lazily build) the operation catalog / 获取（懒构建）操作目录"""
    global _catalog_cache
    if _catalog_cache is not None and not refresh:
        return _catalog_cache
    with _catalog_lock:
        if _catalog_cache is not None and not refresh:
            return _catalog_cache
        try:
            app = _get_fastapi_app()
        except Exception as exc:  # noqa: BLE001
            logger.error("Internal ops catalog: app not available: {}", exc)
            return []
        catalog = _build_catalog_from_app(app)
        _catalog_cache = catalog
        logger.info("Internal ops catalog built: {} operations", len(catalog))
        return catalog


def get_operation(operation_id: str) -> InternalOperation | None:
    """Find one operation by id / 按 ID 查找操作"""
    normalized = str(operation_id or "").strip()
    if not normalized:
        return None
    for op in get_operation_catalog():
        if op.operation_id == normalized:
            return op
    return None


def has_permission(user_permissions: set[str], permission_code: str) -> bool:
    """
    Wildcard-aware permission check, mirroring RBAC decorator semantics.
    支持通配符的权限检查，与 RBAC 装饰器语义保持一致。
    """
    if "*" in user_permissions:
        return True
    if permission_code in user_permissions:
        return True
    if ":" in permission_code:
        resource = permission_code.split(":")[0]
        if f"{resource}:*" in user_permissions:
            return True
    return False


def search_operations(
    *,
    scope: str,
    user_permissions: set[str],
    keyword: str = "",
    module: str = "",
    method: str = "",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[InternalOperation], int]:
    """
    Search operations visible to the caller / 搜索调用者可见的操作

    Filters by scope (API surface), the caller's RBAC permission set,
    then by optional keyword/module/method.
    先按端作用域与调用者 RBAC 权限过滤，再按关键词/模块/方法筛选。

    Returns:
        (page, total) tuple / （分页结果，总数）元组
    """
    keyword_terms = [t for t in str(keyword or "").lower().split() if t]
    module_filter = str(module or "").strip().lower()
    method_filter = str(method or "").strip().upper()

    # OR matching with hit-count scoring: LLMs often pass several loosely
    # related keywords, so requiring all terms is too strict.
    # 按命中数评分的 OR 匹配：LLM 常传入多个弱相关关键词，全量 AND 匹配过于严格。
    scored: list[tuple[int, InternalOperation]] = []
    for op in get_operation_catalog():
        if op.scope != scope:
            continue
        if not has_permission(user_permissions, op.permission_code):
            continue
        if module_filter and op.module.lower() != module_filter:
            continue
        if method_filter and op.method != method_filter:
            continue
        score = 0
        if keyword_terms:
            haystack = " ".join(
                (
                    op.operation_id,
                    op.path,
                    op.module,
                    op.action,
                    op.permission_code,
                    op.summary,
                )
            ).lower()
            score = sum(1 for term in keyword_terms if term in haystack)
            if score == 0:
                continue
        scored.append((score, op))

    scored.sort(
        key=lambda item: (-item[0], item[1].module, item[1].path, item[1].method)
    )
    matched = [op for _score, op in scored]

    total = len(matched)
    safe_offset = max(int(offset or 0), 0)
    safe_limit = min(max(int(limit or 20), 1), 50)
    return matched[safe_offset : safe_offset + safe_limit], total


__all__ = [
    "InternalOperation",
    "USER_ROLE_TO_SCOPE",
    "get_operation",
    "get_operation_catalog",
    "has_permission",
    "search_operations",
]

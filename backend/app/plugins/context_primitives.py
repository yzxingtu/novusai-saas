"""
Plugin context primitives / 插件上下文基础原语

Keeps shared request, DB, and storage proxy primitives out of the main
PluginContext facade so the public import path can stay stable.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.plugins.exceptions import PluginSecurityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Precompiled: match SQL keywords followed by table names (including \t \n whitespace separators)
# / 预编译：匹配 SQL 关键字后跟表名（含 \t \n 等空白分隔符）
_TABLE_KEYWORD_RE = _re.compile(
    r'\b(?:from|join|into|update|table)\s+["\']?([a-z0-9_][a-z0-9_.]*)',
    _re.IGNORECASE,
)


@dataclass(frozen=True)
class RequestContext:
    """
    Request context — identity info extracted from HTTP request / WebSocket connection.
    / 请求上下文 — 从 HTTP 请求 / WebSocket 连接中提取的身份信息。

    Created in API dispatcher layer, injected into PluginContext.
    Lifecycle hook scenarios (on_enable/on_disable, etc.) have no request context,
    in which case it is None and PluginContext methods return safe defaults.
    / 在 API dispatcher 层创建，注入到 PluginContext。
    lifecycle hook 场景（on_enable/on_disable 等）无请求上下文，
    此时为 None，PluginContext 方法返回安全默认值。
    """

    tenant_id: int | None = None
    user_id: int | None = None
    user_role: str = ""  # "admin" / "tenant_admin" / "tenant_user" / 用户角色取值示例
    permissions: list[str] = field(default_factory=list)
    request_id: str = ""


class PluginDbProxy:
    """
    Database proxy — restricts plugins to only operate on px_{name}_* tables
    / 数据库代理 — 限制插件只能操作 px_{name}_* 表

    Wraps AsyncSession, intercepts execute() to check table name prefixes.
    / 包装 AsyncSession，拦截 execute() 检查表名前缀。
    """

    def __init__(
        self,
        db: AsyncSession,
        plugin_name: str,
        allowed_table_prefixes: list[str] | None = None,
    ) -> None:
        self._db = db
        own_prefix = f"px_{plugin_name.replace('-', '_')}_"
        prefixes = allowed_table_prefixes or [own_prefix]
        if own_prefix not in prefixes:
            prefixes = [own_prefix, *prefixes]
        self._allowed_prefixes = tuple(dict.fromkeys(prefixes))

    @property
    def session(self) -> AsyncSession:
        """Forbidden: do not expose raw session to avoid bypassing sandbox checks. / 禁止暴露原始 session，避免绕过沙箱检查。"""
        raise PluginSecurityError(
            message=_("plugin.error.raw_session_forbidden"),
        )

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute SQL with table name prefix check / 执行 SQL，检查表名前缀"""
        sql_text = str(statement)
        self._check_table_access(sql_text)
        return await self._db.execute(statement, *args, **kwargs)

    async def flush(self) -> None:
        await self._db.flush()

    async def commit(self) -> None:
        """
        Flush plugin data within the current transaction (does not commit outer transaction).
        / 在当前事务内 flush 插件数据（不提交外层事务）。

        Note: To protect lifecycle transaction atomicity, this method is equivalent to flush().
        For cross-session visibility, use flush() in the plugin's final response path;
        the lifecycle framework will commit uniformly at request end.
        / 注意：为保护生命周期事务原子性，此方法等同于 flush()。
        若需要确保跨会话可见性，请在插件代码的最终响应路径使用 flush()；
        生命周期框架会在请求结束时统一 commit。
        """
        await self._db.flush()

    async def rollback(self) -> None:
        """
        Plugins cannot rollback the entire database session.
        / 禁止插件回滚整个数据库会话。

        Calling rollback() would undo all lifecycle changes (e.g. plugin.status=ENABLED),
        causing the system to enter an inconsistent state. To undo plugin's own writes,
        avoid writing to DB in on_enable hooks or use business logic checks.
        / 调用 rollback() 会撤销所有生命周期变更（如 plugin.status=ENABLED），
        导致系统进入不一致状态。如需撤销插件自身写入，
        请避免在 on_enable 等 Hook 中写入 DB 或使用业务逻辑判断。
        """
        raise PluginSecurityError(
            message=_("plugin.error.rollback_forbidden"),
        )

    def add(self, instance: Any) -> None:
        self._check_instance_access(instance)
        self._db.add(instance)

    def add_all(self, instances: list[Any]) -> None:
        for instance in instances:
            self._check_instance_access(instance)
        self._db.add_all(instances)

    async def delete(self, instance: Any) -> None:
        self._check_instance_access(instance)
        await self._db.delete(instance)

    async def refresh(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self._check_instance_access(instance)
        await self._db.refresh(instance, *args, **kwargs)

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        table_name = getattr(entity, "__tablename__", "")
        if table_name and not self._is_allowed_table(table_name):
            raise PluginSecurityError(
                message=_("plugin.error.table_prefix_violation").format(
                    prefixes=", ".join(self._allowed_prefixes),
                    table=table_name,
                ),
            )
        return await self._db.get(entity, ident, **kwargs)

    @staticmethod
    def text(sql: str) -> Any:
        from sqlalchemy import text

        return text(sql)

    def _check_instance_access(self, instance: Any) -> None:
        table_name = getattr(instance.__class__, "__tablename__", "")
        if table_name and not self._is_allowed_table(table_name):
            raise PluginSecurityError(
                message=_("plugin.error.table_prefix_violation").format(
                    prefixes=", ".join(self._allowed_prefixes),
                    table=table_name,
                ),
            )

    def _is_allowed_table(self, table_name: str) -> bool:
        return any(table_name.startswith(prefix) for prefix in self._allowed_prefixes)

    def _check_table_access(self, sql_text: str) -> None:
        """Check if SQL only involves plugin-owned tables (basic check + CTE detection)
        / 检查 SQL 是否只涉及插件自有表（基础检查 + CTE 检测）

        Known limitations (defense-in-depth, not a perfect sandbox) / 已知限制：
        - String constants with "FROM xxx" may trigger false checks / 字符串常量中的 "FROM xxx" 可能误触发检查
        - Does not check function calls in raw SQL (e.g. pg_catalog.*) / 不检查 raw SQL 中的函数调用
        - SQLAlchemy ORM queries have extra _check_instance_access protection via add/execute
          / SQLAlchemy ORM 查询经过 add/execute 时有额外 _check_instance_access 保护
        - CTE inner table names detected via FROM|JOIN|INTO|UPDATE|TABLE keywords (M52-T6)
          / CTE 内部的表名已通过关键字检测
        - Strongly recommend PostgreSQL RLS as the final defense in production
          / 生产环境强烈建议通过 PostgreSQL RLS 做最终防线

        Note: real_table in WITH cte AS (SELECT ... FROM real_table ...) is captured
        by the internal FROM keyword scan, so CTE itself needs no extra handling.
        / 注意：CTE 中的 real_table 会被内部 FROM 关键字扫描捕获，故不需额外处理。
        """
        sql_lower = sql_text.lower()
        if not sql_lower.strip():
            return

        _ALLOW_LIST = {"alembic_version", "information_schema", "pg_catalog", "dual"}

        for match in _TABLE_KEYWORD_RE.finditer(sql_lower):
            table_name = match.group(1).strip("\"'")
            if (
                table_name
                and not self._is_allowed_table(table_name)
                and table_name not in _ALLOW_LIST
            ):
                raise PluginSecurityError(
                    message=_("plugin.error.table_access_forbidden").format(
                        prefixes=", ".join(self._allowed_prefixes),
                        table=table_name,
                    ),
                )


class _NamespacedStorageProxy:
    """Storage proxy — restricts plugins to only access files under plugins/{name}/ path
    / 存储代理 — 限制插件只能访问 plugins/{name}/ 路径下的文件

    Method signatures align with StorageDriver base class, but paths are auto-prefixed with plugins/{name}/.
    / 方法签名与 StorageDriver 基类对齐，但路径自动加 plugins/{name}/ 前缀。
    """

    def __init__(self, driver: Any, namespace: str) -> None:
        self._driver = driver
        self._namespace = namespace

    def _ns_path(self, path: str) -> str:
        """Normalize path and ensure it doesn't escape namespace (prevent ../ path traversal) / 规范化路径并确保不逃逸命名空间（防止 ../ 路径遍历）"""
        import posixpath

        stripped = path.lstrip("/")
        if not stripped:
            return self._namespace
        normalized = posixpath.normpath(stripped)
        if normalized.startswith("..") or normalized == ".":
            raise PluginSecurityError(
                message=_("plugin.error.path_traversal_detected").format(path=path),
            )
        return f"{self._namespace}/{normalized}"

    async def put(
        self,
        path: str,
        content: Any,
        mime_type: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._driver.put(
            self._ns_path(path), content, mime_type=mime_type, **kwargs
        )

    async def get(self, path: str) -> Any:
        return await self._driver.get(self._ns_path(path))

    async def delete(self, path: str) -> bool:
        return await self._driver.delete(self._ns_path(path))

    async def exists(self, path: str) -> bool:
        return await self._driver.exists(self._ns_path(path))

    async def get_url(self, path: str, expires: int = 3600, **kwargs: Any) -> str:
        return await self._driver.get_url(
            self._ns_path(path), expires=expires, **kwargs
        )

    async def get_info(self, path: str) -> Any:
        return await self._driver.get_info(self._ns_path(path))


__all__ = [
    "PluginDbProxy",
    "RequestContext",
    "_NamespacedStorageProxy",
]

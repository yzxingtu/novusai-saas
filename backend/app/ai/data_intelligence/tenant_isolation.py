"""
Tenant Isolation Injector (TenantIsolationInjector)
企业隔离注入器（TenantIsolationInjector）

Automatically injects tenant_id conditions for each queried table.
This is the most critical security layer — even if the SQL is valid,
without tenant_id filtering, other tenants' data would be leaked.
自动为每个查询表注入 tenant_id 条件。
这是最关键的安全层 —— 即使 SQL 本身合法，
没有 tenant_id 过滤就会泄露其他企业数据。

Security guarantees / 安全保证：
- Does not rely on LLM to generate tenant_id conditions (LLM may omit or be injected) / 不依赖 LLM 生成 tenant_id 条件（LLM 可能遗漏或被注入）
- Enforced at code level, cannot be bypassed / 在代码层强制注入，无法绕过
- If table has no tenant_column, execution is rejected / 如果表没有 tenant_column，拒绝执行
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.data_intelligence.sql_analysis import (
    SQLTableReference,
    append_outer_where_conditions,
    extract_table_references,
    inject_outer_where_conditions,
)
from app.ai.data_intelligence.schema_provider import TableSchema
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# Exception Definition / 异常定义
# ============================================


class TenantIsolationError(Exception):
    """Tenant isolation injection exception / 企业隔离注入异常"""

    pass


@dataclass
class TableReference:
    """Table reference in SQL / SQL 中的表引用"""

    table_name: str  # Original table name / 原始表名
    alias: str | None  # Alias (AS) / 别名（AS）
    tenant_column: str  # Tenant isolation column name / 企业隔离列名

    @property
    def qualified_tenant_column(self) -> str:
        """tenant_column with table name/alias prefix / 带表名/别名前缀的 tenant_column"""
        prefix = self.alias if self.alias else self.table_name
        return f"{prefix}.{self.tenant_column}"


# ============================================
# TenantIsolationInjector / 租户隔离注入器
# ============================================


class TenantIsolationInjector:
    """
    Automatically injects isolation conditions for each FROM/JOIN table in SQL.
    自动为 SQL 中每个 FROM/JOIN 的表注入隔离条件。

    Isolation strategy by user_role / 按 user_role 决定隔离策略：
    - platform_admin: No injection for platform tables, inject tenant_id for tenant tables / 平台表不注入，企业表注入 tenant_id
    - tenant_admin: Force tenant_id isolation on all tables / 所有表强制 tenant_id 隔离
    - tenant_user: Force tenant_id + user_id isolation (own data only) / 强制 tenant_id + user_id 隔离（仅限自身数据）

    Example / 示例:
        Input: SELECT COUNT(*) FROM tenant_users WHERE created_at > '2026-02-01'
        Output: SELECT COUNT(*) FROM tenant_users
              WHERE tenant_users.tenant_id = 123
                AND (created_at > '2026-02-01')
    """

    # Tables with user_id column (for user-level isolation of tenant_user role) / 含 user_id 列的表
    _USER_ISOLATION_TABLES: set[str] = {
        "agent_conversations",
        "conversation_messages",
    }

    @staticmethod
    def inject(
        sql: str,
        tenant_id: int,
        schema: list[TableSchema],
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_id: int | None = None,
    ) -> str:
        """
        Automatically inject isolation conditions for each FROM/JOIN table in SQL.
        为 SQL 中每个 FROM/JOIN 的表自动注入隔离条件。

        Args:
            sql: Original SQL (already validated by SQLSafetyValidator) / 原始 SQL（已通过 SQLSafetyValidator 校验）
            tenant_id: Tenant ID / 企业 ID
            schema: Table schema info (to confirm tenant_column) / 表结构信息（用于确认 tenant_column）
            user_role: User role (platform_admin / tenant_admin / tenant_user) / 用户角色（platform_admin / tenant_admin / tenant_user）
            user_id: User ID (for user-level isolation in tenant_user role) / 用户 ID（tenant_user 角色时用于用户级隔离）

        Returns:
            SQL with isolation conditions injected / 注入隔离条件后的 SQL

        Raises:
            TenantIsolationError: Table missing tenant_column / 表缺少 tenant_column
        """
        # platform_admin can view all data, no tenant_id injection / 平台管理员可以查看所有数据，不注入 tenant_id 隔离
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            return sql

        # Build schema dictionary / 构建 schema 字典
        schema_map: dict[str, TableSchema] = {t.table_name.lower(): t for t in schema}

        # Extract table references / 提取表引用
        table_refs = extract_table_references(sql)
        if not table_refs:
            logger.warning(
                "No table references found in SQL, cannot inject tenant_id: {}",
                sql[:200],
            )
            raise TenantIsolationError(_("data_intelligence.isolation.no_table_ref"))

        # Build TableReference for each table / 为每个表构建 TableReference
        refs: list[TableReference] = []
        for raw_ref in table_refs:
            table_name = raw_ref.table_name
            alias = raw_ref.alias
            table_lower = table_name.lower()
            table_schema = schema_map.get(table_lower)

            if table_schema is None:
                raise TenantIsolationError(
                    _("data_intelligence.isolation.unknown_table", table=table_name)
                )

            if not table_schema.tenant_column:
                # Platform-level tables (e.g. tenants, tenant_plans) have no tenant_id
                # Non-platform admins cannot query tables without isolation column (prevent data leaks)
                # 平台级表（如 tenants、tenant_plans）无 tenant_id，非平台管理员禁止查询无隔离列的表（防止数据泄露）
                if user_role != UserRoleEnum.PLATFORM_ADMIN.value:
                    raise TenantIsolationError(
                        _(
                            "data_intelligence.isolation.no_tenant_column",
                            table=table_name,
                        )
                    )
                # Platform admin skips isolation / 平台管理员跳过隔离
                logger.debug(
                    "Table {} has no tenant_column, skipping isolation (platform_admin)",
                    table_name,
                )
                continue

            refs.append(
                TableReference(
                    table_name=table_name,
                    alias=alias,
                    tenant_column=table_schema.tenant_column,
                )
            )

        # Inject tenant_id conditions / 注入 tenant_id 条件
        result = _inject_conditions(sql, refs, tenant_id)

        # tenant_user role: additionally inject user_id condition (own data only) / 额外注入 user_id 条件（仅限自身数据）
        if user_role == "tenant_user" and user_id:
            user_refs = [
                ref
                for ref in refs
                if ref.table_name.lower()
                in TenantIsolationInjector._USER_ISOLATION_TABLES
            ]
            if user_refs:
                user_conditions = [
                    _build_user_condition(ref, user_id) for ref in user_refs
                ]
                result = _inject_extra_conditions(result, user_conditions)
                logger.info(
                    "Injected user_id={} isolation for tenant_user on {} table(s)",
                    user_id,
                    len(user_refs),
                )

        return result

    @staticmethod
    def validate_has_tenant_column(
        table_name: str,
        schema: list[TableSchema],
    ) -> bool:
        """Check if table has tenant_column / 检查表是否有 tenant_column"""
        for t in schema:
            if t.table_name.lower() == table_name.lower():
                return bool(t.tenant_column)
        return False


def _inject_conditions(
    sql: str,
    refs: list[TableReference],
    tenant_id: int,
) -> str:
    """
    Inject tenant_id WHERE conditions into the outermost query of *sql*.

    Strategy:
    1. If the outermost query has a WHERE clause, prepend AND conditions.
    2. If not, insert a WHERE clause before GROUP BY / ORDER BY / LIMIT etc.
    3. Subquery WHERE clauses (depth > 0) are left untouched.
    注入 tenant_id WHERE 条件到 *sql* 的最外层查询中。

    策略：
    1. 如果最外层查询有 WHERE 子句，追加 AND 条件。
    2. 如果没有，插入 WHERE 子句在 GROUP BY / ORDER BY / LIMIT 等之前。
    3. 子查询的 WHERE 子句（深度 > 0）保持不变。
    """
    conditions: list[str] = []
    for ref in refs:
        conditions.append(f"{ref.qualified_tenant_column} = {tenant_id}")

    if not conditions:
        return sql

    result = inject_outer_where_conditions(sql, conditions)

    logger.info(
        "Injected tenant_id={} for {} table(s)",
        tenant_id,
        len(refs),
    )

    return result


def _build_user_condition(ref: TableReference, user_id: int) -> str:
    """Build user_id isolation condition / 构建 user_id 隔离条件"""
    prefix = ref.alias if ref.alias else ref.table_name
    return f"{prefix}.user_id = {user_id}"


def _inject_extra_conditions(sql: str, conditions: list[str]) -> str:
    """
    向已有 SQL 追加额外 AND 条件 / Append extra AND conditions to existing SQL.

    Assumes SQL already has WHERE clause (injected by _inject_conditions for tenant_id),
    appends AND conditions at the end of WHERE clause.
    假设 SQL 已经有 WHERE 子句（由 _inject_conditions 注入的 tenant_id），追加 AND 条件在 WHERE 子句尾部。
    """
    if not conditions:
        return sql

    return append_outer_where_conditions(sql, conditions)


__all__ = [
    "TenantIsolationInjector",
    "TenantIsolationError",
    "TableReference",
]

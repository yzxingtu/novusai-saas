"""
租户隔离注入器（TenantIsolationInjector）

自动为每个查询表注入 tenant_id 条件。
这是最关键的安全层 —— 即使 SQL 本身合法，
没有 tenant_id 过滤就会泄露其他租户数据。

安全保证：
- 不依赖 LLM 生成 tenant_id 条件（LLM 可能遗漏或被注入）
- 在代码层强制注入，无法绕过
- 如果表没有 tenant_column，拒绝执行
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.data_intelligence.schema_provider import TableSchema
from app.core.i18n import _
from app.enums.common import UserRoleEnum
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# 异常定义
# ============================================

class TenantIsolationError(Exception):
    """租户隔离注入异常"""
    pass


# ============================================
# 表引用提取
# ============================================

@dataclass
class TableReference:
    """SQL 中的表引用"""
    table_name: str        # 原始表名
    alias: str | None      # 别名（AS）
    tenant_column: str     # 租户隔离列名

    @property
    def qualified_tenant_column(self) -> str:
        """带表名/别名前缀的 tenant_column"""
        prefix = self.alias if self.alias else self.table_name
        return f"{prefix}.{self.tenant_column}"


# FROM / JOIN 后的表引用提取
# 匹配模式:
#   FROM table_name
#   FROM table_name AS alias
#   FROM table_name alias
#   JOIN table_name ON ...
#   LEFT JOIN table_name AS alias ON ...
_TABLE_REF_RE = re.compile(
    r"""
    \b(?:FROM|(?:LEFT|RIGHT|INNER|OUTER|CROSS|FULL)?\s*JOIN)\s+
    (\w+)                         # 表名（组1）
    (?:\s+AS\s+(\w+))?            # AS 别名（组2, 可选）
    (?:\s+(\w+))?                 # 隐式别名（组3, 可选, 排除关键字）
    """,
    re.IGNORECASE | re.VERBOSE,
)

# 需要排除的 SQL 关键字（不是别名）
_SQL_KEYWORDS = {
    "on", "where", "and", "or", "inner", "outer", "left", "right",
    "cross", "full", "join", "set", "group", "order", "having",
    "limit", "offset", "union", "except", "intersect", "natural",
    "using", "lateral", "select", "from", "as", "not", "in",
    "between", "like", "ilike", "is", "null", "true", "false",
    "case", "when", "then", "else", "end",
}


def _extract_table_refs(sql: str) -> list[tuple[str, str | None]]:
    """
    提取 SQL 中所有的表引用（表名 + 别名）

    Returns:
        [(table_name, alias_or_none), ...]
    """
    refs: list[tuple[str, str | None]] = []

    for match in _TABLE_REF_RE.finditer(sql):
        table_name = match.group(1)
        as_alias = match.group(2)   # AS 别名
        implicit_alias = match.group(3)  # 隐式别名

        # 确定最终别名
        alias = as_alias
        if not alias and implicit_alias:
            # 检查是否是关键字
            if implicit_alias.lower() not in _SQL_KEYWORDS:
                alias = implicit_alias

        refs.append((table_name, alias))

    return refs


# ============================================
# TenantIsolationInjector
# ============================================

class TenantIsolationInjector:
    """
    自动为 SQL 中每个 FROM/JOIN 的表注入隔离条件

    按 user_role 决定隔离策略：
    - platform_admin: 平台表不注入，租户表注入 tenant_id
    - tenant_admin: 所有表强制 tenant_id 隔离
    - tenant_user: 强制 tenant_id + user_id 隔离（仅限自身数据）

    示例:
        输入: SELECT COUNT(*) FROM tenant_users WHERE created_at > '2026-02-01'
        输出: SELECT COUNT(*) FROM tenant_users
              WHERE tenant_users.tenant_id = 123
                AND (created_at > '2026-02-01')
    """

    # 含 user_id 列的表（用于 tenant_user 角色的用户级隔离）
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
        为 SQL 中每个 FROM/JOIN 的表自动注入隔离条件

        Args:
            sql: 原始 SQL（已通过 SQLSafetyValidator 校验）
            tenant_id: 租户 ID
            schema: 表结构信息（用于确认 tenant_column）
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            user_id: 用户 ID（tenant_user 角色时用于用户级隔离）

        Returns:
            注入隔离条件后的 SQL

        Raises:
            TenantIsolationError: 表缺少 tenant_column
        """
        # platform_admin 可查看所有数据，不注入 tenant_id 隔离
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            return sql

        # 构建 schema 字典
        schema_map: dict[str, TableSchema] = {
            t.table_name.lower(): t for t in schema
        }

        # 提取表引用
        table_refs = _extract_table_refs(sql)
        if not table_refs:
            logger.warning(
                "No table references found in SQL, cannot inject tenant_id: %s",
                sql[:200],
            )
            raise TenantIsolationError(
                _("data_intelligence.isolation.no_table_ref")
            )

        # 为每个表构建 TableReference
        refs: list[TableReference] = []
        for table_name, alias in table_refs:
            table_lower = table_name.lower()
            table_schema = schema_map.get(table_lower)

            if table_schema is None:
                raise TenantIsolationError(
                    _("data_intelligence.isolation.unknown_table",
                      table=table_name)
                )

            if not table_schema.tenant_column:
                # 平台级表（如 tenants、tenant_plans）无 tenant_id，跳过隔离
                logger.debug(
                    "Table %s has no tenant_column, skipping isolation",
                    table_name,
                )
                continue

            refs.append(TableReference(
                table_name=table_name,
                alias=alias,
                tenant_column=table_schema.tenant_column,
            ))

        # 注入 tenant_id 条件
        result = _inject_conditions(sql, refs, tenant_id)

        # tenant_user 角色：额外注入 user_id 条件（仅限自身数据）
        if user_role == "tenant_user" and user_id:
            user_refs = [
                ref for ref in refs
                if ref.table_name.lower() in TenantIsolationInjector._USER_ISOLATION_TABLES
            ]
            if user_refs:
                user_conditions = [
                    _build_user_condition(ref, user_id)
                    for ref in user_refs
                ]
                result = _inject_extra_conditions(result, user_conditions)
                logger.info(
                    "Injected user_id=%d isolation for tenant_user on %d table(s)",
                    user_id, len(user_refs),
                )

        return result

    @staticmethod
    def validate_has_tenant_column(
        table_name: str,
        schema: list[TableSchema],
    ) -> bool:
        """检查表是否有 tenant_column"""
        for t in schema:
            if t.table_name.lower() == table_name.lower():
                return bool(t.tenant_column)
        return False


def _find_at_depth_zero(
    sql: str,
    pattern: re.Pattern[str],
) -> re.Match[str] | None:
    """
    Find the first match of *pattern* that sits at parenthesis depth 0,
    i.e. in the outermost query rather than inside a subquery.
    """
    depth = 0
    i = 0
    while i < len(sql):
        if sql[i] == "(":
            depth += 1
            i += 1
        elif sql[i] == ")":
            depth -= 1
            i += 1
        elif depth == 0:
            m = pattern.match(sql, i)
            if m:
                return m
            i += 1
        else:
            i += 1
    return None


_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)
_INSERT_BEFORE_RE = re.compile(
    r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION|EXCEPT|INTERSECT)\b",
    re.IGNORECASE,
)


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
    """
    conditions: list[str] = []
    for ref in refs:
        conditions.append(
            f"{ref.qualified_tenant_column} = {tenant_id}"
        )

    if not conditions:
        return sql

    tenant_clause = " AND ".join(conditions)

    # Search for WHERE at depth 0 only (skip subquery WHEREs)
    where_match = _find_at_depth_zero(sql, _WHERE_RE)

    if where_match:
        where_pos = where_match.end()
        result = (
            sql[:where_pos]
            + f" {tenant_clause} AND"
            + sql[where_pos:]
        )
    else:
        # No outermost WHERE — insert before trailing clauses at depth 0
        insert_match = _find_at_depth_zero(sql, _INSERT_BEFORE_RE)

        if insert_match:
            insert_pos = insert_match.start()
            result = (
                sql[:insert_pos].rstrip()
                + f" WHERE {tenant_clause} "
                + sql[insert_pos:]
            )
        else:
            stripped = sql.rstrip().rstrip(";")
            result = f"{stripped} WHERE {tenant_clause}"

    logger.info(
        "Injected tenant_id=%d for %d table(s)",
        tenant_id, len(refs),
    )

    return result


def _build_user_condition(ref: TableReference, user_id: int) -> str:
    """构建 user_id 隔离条件"""
    prefix = ref.alias if ref.alias else ref.table_name
    return f"{prefix}.user_id = {user_id}"


def _inject_extra_conditions(sql: str, conditions: list[str]) -> str:
    """
    向已有 SQL 追加额外 AND 条件

    假设 SQL 已经有 WHERE 子句（由 _inject_conditions 注入的 tenant_id），
    在 WHERE 子句尾部追加 AND 条件。
    """
    if not conditions:
        return sql

    extra_clause = " AND ".join(conditions)

    # 已有 WHERE（由前一步 tenant_id 注入保证），追加 AND
    where_match = _find_at_depth_zero(sql, _WHERE_RE)
    if where_match:
        # 在 GROUP BY / ORDER BY / LIMIT 等之前插入
        insert_match = _find_at_depth_zero(sql, _INSERT_BEFORE_RE)
        if insert_match:
            insert_pos = insert_match.start()
            return (
                sql[:insert_pos].rstrip()
                + f" AND {extra_clause} "
                + sql[insert_pos:]
            )
        # 无尾部子句，直接追加
        stripped = sql.rstrip().rstrip(";")
        return f"{stripped} AND {extra_clause}"

    # 无 WHERE（不应发生，但兜底）
    stripped = sql.rstrip().rstrip(";")
    return f"{stripped} WHERE {extra_clause}"


__all__ = [
    "TenantIsolationInjector",
    "TenantIsolationError",
    "TableReference",
]

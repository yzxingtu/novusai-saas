"""
Data Dictionary Service (SchemaProvider)
数据字典服务（SchemaProvider）

Provides database schema awareness for AI Text-to-SQL.
为 AI Text-to-SQL 提供数据库 schema 感知能力。

Security strategy / 安全策略：
- Dynamic table/column visibility via ai_table_policies table / 基于 ai_table_policies 表动态控制
- Column masking: blocked_columns not exposed to AI / 列脱敏
- Tenant filtering: permission_code implements RBAC / 按企业过滤
- Redis cache: reduces DB reflection calls / Redis 缓存
- Tenant overrides: ai_table_policy_overrides can tighten policies / 企业覆盖
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import SCHEMA_CACHE_TTL, schema_cache_key
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum
from app.models.ai.table_policy import AITablePolicy, AITablePolicyOverride

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# Data Structure Definitions / 数据结构定义
# ============================================

@dataclass
class ColumnSchema:
    """Column schema description / 列结构描述"""

    name: str
    type: str              # Simplified type: int/str/float/bool/datetime/json / 简化类型
    description: str       # Column description (from Model.comment) / 列描述
    nullable: bool = True
    is_primary: bool = False
    is_foreign_key: bool = False
    fk_table: str | None = None  # Foreign key target table / 外键目标表

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "nullable": self.nullable,
        }
        if self.is_primary:
            result["is_primary"] = True
        if self.is_foreign_key and self.fk_table:
            result["fk_table"] = self.fk_table
        return result


@dataclass
class TableSchema:
    """Table schema description / 表结构描述"""

    table_name: str
    description: str           # Table description / 表描述
    columns: list[ColumnSchema] = field(default_factory=list)
    tenant_column: str = "tenant_id"  # Tenant isolation column / 企业隔离列名
    row_count_approx: int = 0  # Approx row count (from pg_stat, no COUNT) / 近似行数
    max_rows: int = 200        # Max rows per query / 单次查询最大行数
    allow_read: bool = True
    allow_create: bool = False
    allow_update: bool = False
    allow_delete: bool = False
    permission_code: str = "*"   # RBAC permission code / RBAC 权限码

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "description": self.description,
            "columns": [c.to_dict() for c in self.columns],
            "tenant_column": self.tenant_column,
            "row_count_approx": self.row_count_approx,
            "max_rows": self.max_rows,
            "allow_read": self.allow_read,
            "allow_create": self.allow_create,
            "allow_update": self.allow_update,
            "allow_delete": self.allow_delete,
            "permission_code": self.permission_code,
        }

    def to_ddl(self) -> str:
        """Convert to compact DDL string (for LLM use) / 转换为精简 DDL 字符串"""
        cols = []
        for c in self.columns:
            parts = [f"  {c.name} {c.type}"]
            if c.description:
                parts.append(f"-- {c.description}")
            if c.is_primary:
                parts.append("PK")
            if c.is_foreign_key and c.fk_table:
                parts.append(f"FK\u2192{c.fk_table}")
            cols.append(" ".join(parts))
        header = f"-- {self.description} (\u2248{self.row_count_approx} rows, limit {self.max_rows})"
        return f"{header}\n{self.table_name} (\n" + ",\n".join(cols) + "\n)"


# ============================================
# Type Mapping / 类型映射
# ============================================

_PG_TYPE_MAP: dict[str, str] = {
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "serial": "int",
    "bigserial": "int",
    "real": "float",
    "double precision": "float",
    "numeric": "float",
    "decimal": "float",
    "character varying": "str",
    "varchar": "str",
    "character": "str",
    "char": "str",
    "text": "str",
    "boolean": "bool",
    "timestamp without time zone": "datetime",
    "timestamp with time zone": "datetime",
    "date": "datetime",
    "time without time zone": "str",
    "time with time zone": "str",
    "json": "json",
    "jsonb": "json",
    "uuid": "str",
    "inet": "str",
    "bytea": "bytes",
}


def _simplify_type(pg_type: str) -> str:
    """Map PostgreSQL type to simplified type / 将 PostgreSQL 类型映射为简化类型"""
    lower = pg_type.lower()
    for prefix, simple in _PG_TYPE_MAP.items():
        if lower.startswith(prefix):
            return simple
    return "str"


# ============================================
# SchemaProvider
# ============================================

class SchemaProvider:
    """
    Provides database schema awareness for AI.
    为 AI 提供数据库 schema 感知能力。

    Security strategy / 安全策略：
    - Dynamically loads available tables from ai_table_policies / 动态加载可用表
    - blocked_columns not exposed to AI / 列不暴露给 AI
    - permission_code implements RBAC / RBAC 权限控制
    - Tenant overrides can tighten but not loosen global policies / 企业覆盖可收紧不能放开
    """

    # ===== Global sensitive column names (fallback, not exposed even if policy misconfigured) / 全局敏感列名（兜底，即使策略配置错误也不暴露） =====
    _GLOBAL_BLOCKED_COLUMNS: set[str] = {
        "password", "password_hash", "hashed_password",
        "secret", "secret_key", "api_key", "access_token",
        "refresh_token", "encrypted_key", "salt",
    }

    async def get_schema(
        self,
        db: AsyncSession,
        tenant_id: int,
        question: str | None = None,
        permissions: set[str] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
    ) -> list[TableSchema]:
        """
        Get table schemas queryable by tenant.
        获取企业可查询的表结构。

        Args:
            db: Database session / 数据库会话
            tenant_id: Tenant ID / 企业 ID
            question: User question (optional, for smart filtering) / 用户问题
            permissions: User RBAC permission code set (for table-level filtering) / RBAC 权限码集合
            user_role: User role (platform_admin / tenant_admin / tenant_user) / 用户角色

        Returns:
            List of TableSchema (only tables user has permission to access) / 可访问的表列表
        """
        # Try to get from Redis cache / 尝试从 Redis 缓存获取
        cached = await self._get_cached_schema(tenant_id)
        if cached is not None:
            tables = cached
        else:
            # Load policies from DB and reflect schema / 从 DB 加载策略并反射 schema
            policies = await self._load_active_policies(db, tenant_id)
            tables = await self._load_schema_from_policies(db, policies)
            await self._cache_schema(tenant_id, tables)

        # Filter accessible tables by RBAC permissions / 按 RBAC 权限过滤
        tables = self._filter_by_permissions(tables, permissions, user_role)

        # Filter relevant tables by question keywords / 按问题关键词过滤
        if question:
            tables = self._filter_by_question(tables, question)

        return tables

    async def get_allowed_table_names(
        self,
        db: AsyncSession,
        permissions: set[str] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        tenant_id: int = 0,
    ) -> set[str]:
        """Get set of table names allowed for current user (after RBAC filtering) / 获取当前用户允许查询的表名集合"""
        policies = await self._load_active_policies(db, tenant_id)
        return self._filter_policy_names_by_permissions(
            policies, permissions, user_role
        )

    # ============================================
    # Policy Loading / 策略加载
    # ============================================

    @staticmethod
    async def _load_active_policies(
        db: AsyncSession,
        tenant_id: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Load active policy list (merge global + tenant overrides).
        加载有效策略列表（合并全局 + 企业覆盖）。

        Returns:
            Policy dict list, each containing table name, CRUD switches, blocked_columns, etc.
            策略字典列表，每项包含表名、CRUD 开关、blocked_columns 等。
        """
        # Load global policies / 加载全局策略
        stmt = select(AITablePolicy).where(
            AITablePolicy.is_active == True,  # noqa: E712
            AITablePolicy.is_deleted == False,  # noqa: E712
        ).order_by(AITablePolicy.sort_order, AITablePolicy.table_name)
        result = await db.execute(stmt)
        global_policies = result.scalars().all()

        # Load tenant overrides (when tenant_id > 0) / 加载企业覆盖
        overrides_map: dict[int, AITablePolicyOverride] = {}
        if tenant_id and tenant_id > 0:
            override_stmt = select(AITablePolicyOverride).where(
                AITablePolicyOverride.tenant_id == tenant_id,
                AITablePolicyOverride.is_deleted == False,  # noqa: E712
            )
            override_result = await db.execute(override_stmt)
            for ov in override_result.scalars().all():
                overrides_map[ov.policy_id] = ov

        policies: list[dict[str, Any]] = []
        for gp in global_policies:
            ov = overrides_map.get(gp.id)
            policy = _merge_policy_with_override(gp, ov)
            # Skip if disabled after merge / 合并后如果被禁用则跳过
            if not policy["is_active"]:
                continue
            policies.append(policy)

        return policies

    async def _load_schema_from_policies(
        self,
        db: AsyncSession,
        policies: list[dict[str, Any]],
    ) -> list[TableSchema]:
        """Load schema from DB reflection based on policy list / 根据策略列表从数据库反射加载 schema"""
        tables: list[TableSchema] = []

        for policy in policies:
            if not policy.get("allow_read"):
                continue
            try:
                table_schema = await self._load_table_schema(db, policy)
                if table_schema is not None:
                    tables.append(table_schema)
            except Exception as exc:
                logger.warning(
                    "Failed to load schema for table %s: %s",
                    policy["table_name"], str(exc),
                )

        return tables

    async def _load_table_schema(
        self,
        db: AsyncSession,
        policy: dict[str, Any],
    ) -> TableSchema | None:
        """Load schema for a single table (based on policy config) / 加载单个表的 schema"""
        table_name = policy["table_name"]
        blocked_cols = set(policy.get("blocked_columns") or [])
        blocked_cols |= self._GLOBAL_BLOCKED_COLUMNS
        col_descriptions: dict[str, str] = policy.get("column_descriptions") or {}

        # Query column information / 查询列信息
        col_query = text("""
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                pgd.description AS column_comment,
                tc.constraint_type,
                ccu.table_name AS fk_table
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st
                ON st.schemaname = c.table_schema AND st.relname = c.table_name
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
            LEFT JOIN information_schema.key_column_usage kcu
                ON kcu.table_name = c.table_name
                AND kcu.column_name = c.column_name
                AND kcu.table_schema = c.table_schema
            LEFT JOIN information_schema.table_constraints tc
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND tc.constraint_type = 'FOREIGN KEY'
            WHERE c.table_schema = 'public'
                AND c.table_name = :table_name
            ORDER BY c.ordinal_position
        """)
        result = await db.execute(col_query, {"table_name": table_name})
        rows = result.fetchall()

        if not rows:
            return None

        columns: list[ColumnSchema] = []
        has_tenant_column = False

        for row in rows:
            col_name = row[0]
            data_type = row[1]
            is_nullable = row[2] == "YES"
            column_comment = row[4] or ""
            constraint_type = row[5]
            fk_table = row[6]

            # Skip blocked columns / 跳过被屏蔽的列
            if col_name in blocked_cols:
                continue

            if col_name == "tenant_id":
                has_tenant_column = True

            is_pk = constraint_type == "PRIMARY KEY"
            is_fk = constraint_type == "FOREIGN KEY"

            # Prefer policy column description, fallback to DB comment / 优先使用策略中的列描述
            desc = col_descriptions.get(col_name, column_comment)

            columns.append(ColumnSchema(
                name=col_name,
                type=_simplify_type(data_type),
                description=desc,
                nullable=is_nullable,
                is_primary=is_pk,
                is_foreign_key=is_fk,
                fk_table=fk_table if is_fk else None,
            ))

        # Get approximate row count / 获取近似行数
        row_count = await self._get_approx_row_count(db, table_name)

        return TableSchema(
            table_name=table_name,
            description=policy.get("description") or policy.get("label", ""),
            columns=columns,
            tenant_column="tenant_id" if has_tenant_column else "",
            row_count_approx=row_count,
            max_rows=policy.get("max_rows", 200),
            allow_read=policy.get("allow_read", True),
            allow_create=policy.get("allow_create", False),
            allow_update=policy.get("allow_update", False),
            allow_delete=policy.get("allow_delete", False),
            permission_code=policy.get("permission_code", "*"),
        )

    @staticmethod
    async def _get_approx_row_count(db: AsyncSession, table_name: str) -> int:
        """Get approx row count from pg_stat (no COUNT executed) / 从 pg_stat 获取近似行数"""
        query = text("""
            SELECT COALESCE(n_live_tup, 0)::int
            FROM pg_stat_user_tables
            WHERE relname = :table_name
        """)
        result = await db.execute(query, {"table_name": table_name})
        row = result.scalar()
        return int(row) if row else 0

    # ============================================
    # RBAC Filtering / RBAC 过滤
    # ============================================

    @staticmethod
    def _filter_policy_names_by_permissions(
        policies: list[dict[str, Any]],
        permissions: set[str] | None,
        user_role: str,
    ) -> set[str]:
        """Filter policies by RBAC permissions, return allowed table name set / 根据 RBAC 权限过滤策略"""
        is_platform = user_role == UserRoleEnum.PLATFORM_ADMIN.value

        # Platform admin can access all active tables (CRUD switches checked upstream) / 平台管理员可访问所有活跃表
        if is_platform:
            return {p["table_name"] for p in policies}

        allowed: set[str] = set()
        for policy in policies:
            table_name = policy["table_name"]
            perm_code = policy.get("permission_code", "*")

            if perm_code == "platform_only":
                continue

            if perm_code == "*" or permissions and perm_code in permissions:
                allowed.add(table_name)

        return allowed

    @staticmethod
    def _filter_by_permissions(
        tables: list[TableSchema],
        permissions: set[str] | None,
        user_role: str,
    ) -> list[TableSchema]:
        """Filter tables by RBAC permissions (prevent unauthorized queries at source).
        按 RBAC 权限过滤表（从源头杜绝越权查询）。

        Rules (all users subject to table-policies) / 规则：
        - platform_admin: Can access all tables / 可访问所有表
        - tenant_admin / tenant_user: Only permission-matched tables with tenant_column / 仅匹配且有 tenant_column
        - permission_code='*': Any logged-in user can access / 任何登录用户可访问
        - permission_code='platform_only': Platform admins only / 仅平台管理员
        - Tables without tenant_column (platform-level) invisible to non-platform users / 平台级表不可见
        """
        is_platform = user_role == UserRoleEnum.PLATFORM_ADMIN.value

        # Platform admin can access all active tables (allow_read checked in _load_schema_from_policies) / 平台管理员可访问所有表
        if is_platform:
            return tables

        filtered: list[TableSchema] = []
        for t in tables:
            perm_code = t.permission_code

            # platform_only: Non-platform admins cannot access / 非平台管理员不可访问
            if perm_code == "platform_only":
                continue

            # Platform-level tables without tenant_column: non-platform users cannot access (prevent data leak) / 无 tenant_column 的平台级表不可访问
            if not t.tenant_column:
                continue

            # '*' permission code: any logged-in user can access / '*' 权限码可访问
            if perm_code == "*":
                filtered.append(t)
                continue

            # Check if user has corresponding read permission / 检查用户是否有读权限
            if permissions and perm_code in permissions:
                filtered.append(t)

        return filtered

    @staticmethod
    def _filter_by_question(
        tables: list[TableSchema],
        question: str,
    ) -> list[TableSchema]:
        """Filter tables by question keywords to return relevant ones (reduce LLM token consumption).
        按问题关键词过滤返回相关表（减少 LLM token 消耗）。

        For small table sets (≤30), returns all tables for LLM to judge.
        Only performs keyword filtering when table count is large to save tokens.
        对于小型表集合直接返回全部表，仅在表数量较大时进行关键词过滤。
        """
        # Skip filtering for small table sets (LLM context can handle) / 表数量较少时跳过过滤
        if len(tables) <= 30:
            return tables

        question_lower = question.lower()
        relevant_tables: set[str] = set()

        for t in tables:
            # Table name match (English table name appears in question) / 表名匹配
            if t.table_name in question_lower:
                relevant_tables.add(t.table_name)
                continue

            # Table name fragment match ("tenants" matches "tenant") / 表名片段匹配
            name_parts = t.table_name.replace("_", " ").split()
            if any(part in question_lower for part in name_parts if len(part) >= 3):
                relevant_tables.add(t.table_name)
                continue

            # Description match (supports Chinese: space tokenization + sliding window 2-4 char match) / 描述匹配
            if t.description:
                desc = t.description.lower()
                # Space tokenization match / 空格分词匹配
                for word in desc.split():
                    if len(word) >= 2 and word in question_lower:
                        relevant_tables.add(t.table_name)
                        break
                else:
                    # Chinese sliding window: extract 2~4 char segments to match question / 中文滑动窗口
                    for win in range(2, 5):
                        for i in range(len(desc) - win + 1):
                            seg = desc[i:i + win]
                            if seg.isascii():
                                continue
                            if seg in question_lower:
                                relevant_tables.add(t.table_name)
                                break
                        if t.table_name in relevant_tables:
                            break

            # Label match (Chinese label) / label 匹配
            label = getattr(t, "label", None) or ""
            if label and label in question_lower:
                relevant_tables.add(t.table_name)

        # If no keyword matches, return all tables (let LLM judge) / 无匹配时返回全部表
        if not relevant_tables:
            return tables

        return [t for t in tables if t.table_name in relevant_tables]

    # ============================================
    # Redis Cache / Redis 缓存
    # ============================================

    @staticmethod
    async def _get_cached_schema(tenant_id: int) -> list[TableSchema] | None:
        """Get cached schema from Redis / 从 Redis 获取缓存的 schema"""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            key = schema_cache_key(tenant_id)
            data = await redis.get(key)
            if data is None:
                return None
            tables_data = json.loads(data)
            return [_dict_to_table_schema(t) for t in tables_data]
        except Exception as exc:
            logger.warning("Failed to get cached schema: %s", str(exc))
            return None

    @staticmethod
    async def _cache_schema(tenant_id: int, tables: list[TableSchema]) -> None:
        """Cache schema to Redis / 将 schema 缓存到 Redis"""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            key = schema_cache_key(tenant_id)
            data = json.dumps([t.to_dict() for t in tables], ensure_ascii=False)
            await redis.set(key, data, ex=SCHEMA_CACHE_TTL)
        except Exception as exc:
            logger.warning("Failed to cache schema: %s", str(exc))

    @staticmethod
    async def invalidate_cache(tenant_id: int) -> None:
        """Clear tenant schema cache / 清除企业 schema 缓存"""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            key = schema_cache_key(tenant_id)
            await redis.delete(key)
        except Exception as exc:
            logger.warning("Failed to invalidate schema cache: %s", str(exc))

    @staticmethod
    async def get_table_descriptions(
        db: AsyncSession,
        table_policy_ids: list[int] | None = None,
    ) -> list[tuple[str, str]]:
        """Get (table_name, label) list for enabled tables, for tool description registration.
        获取启用表的 (table_name, label) 列表，用于工具描述注册。

        Args:
            db: Database session / 数据库会话
            table_policy_ids: Restricted table policy ID list (from Skill.config).
                              When None, loads all active policies (backward compatible).
                              限定的表策略 ID 列表，为 None 时加载所有 active 策略。
        """
        stmt = select(
            AITablePolicy.table_name,
            AITablePolicy.label,
        ).where(
            AITablePolicy.is_active == True,  # noqa: E712
            AITablePolicy.is_deleted == False,  # noqa: E712
            AITablePolicy.allow_read == True,  # noqa: E712
        )
        if table_policy_ids is not None:
            stmt = stmt.where(AITablePolicy.id.in_(table_policy_ids))
        stmt = stmt.order_by(AITablePolicy.sort_order, AITablePolicy.table_name)
        result = await db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    @staticmethod
    async def get_crud_allowed_tables(
        db: AsyncSession,
        table_policy_ids: list[int] | None = None,
    ) -> dict[str, list[tuple[str, str]]]:
        """Get tables allowed for each CRUD operation.
        获取各 CRUD 操作允许的表列表。

        Args:
            db: Database session / 数据库会话
            table_policy_ids: Restricted table policy ID list (from Skill.config).
                              When None, loads all active policies (backward compatible).
                              限定的表策略 ID 列表，为 None 时加载所有 active 策略。

        Returns:
            {"create": [(name, label), ...], "update": [...], "delete": [...]}
        """
        stmt = select(
            AITablePolicy.table_name,
            AITablePolicy.label,
            AITablePolicy.allow_create,
            AITablePolicy.allow_update,
            AITablePolicy.allow_delete,
        ).where(
            AITablePolicy.is_active == True,  # noqa: E712
            AITablePolicy.is_deleted == False,  # noqa: E712
        )
        if table_policy_ids is not None:
            stmt = stmt.where(AITablePolicy.id.in_(table_policy_ids))
        stmt = stmt.order_by(AITablePolicy.sort_order, AITablePolicy.table_name)
        result = await db.execute(stmt)

        crud_tables: dict[str, list[tuple[str, str]]] = {
            "create": [], "update": [], "delete": [],
        }
        for row in result.all():
            tname, label = row[0], row[1]
            if row[2]:  # allow_create
                crud_tables["create"].append((tname, label))
            if row[3]:  # allow_update
                crud_tables["update"].append((tname, label))
            if row[4]:  # allow_delete
                crud_tables["delete"].append((tname, label))
        return crud_tables


# ============================================
# Policy Merge Helper / 策略合并辅助函数
# ============================================

def _merge_policy_with_override(
    gp: AITablePolicy,
    ov: AITablePolicyOverride | None,
) -> dict[str, Any]:
    """Merge global policy with tenant override. Override can only tighten, not loosen. / 合并全局策略与企业覆盖"""
    policy: dict[str, Any] = {
        "table_name": gp.table_name,
        "label": gp.label,
        "description": gp.description or "",
        "keywords": gp.keywords or [],
        "column_descriptions": gp.column_descriptions or {},
        "allow_read": gp.allow_read,
        "allow_create": gp.allow_create,
        "allow_update": gp.allow_update,
        "allow_delete": gp.allow_delete,
        "max_rows": gp.max_rows,
        "blocked_columns": list(gp.blocked_columns or []),
        "permission_code": gp.permission_code,
        "is_active": gp.is_active,
    }

    if ov is None:
        return policy

    # Override can only tighten: True → False OK, False → True NOT OK / 覆盖只能收紧
    if ov.allow_read is not None and not ov.allow_read:
        policy["allow_read"] = False
    if ov.allow_create is not None and not ov.allow_create:
        policy["allow_create"] = False
    if ov.allow_update is not None and not ov.allow_update:
        policy["allow_update"] = False
    if ov.allow_delete is not None and not ov.allow_delete:
        policy["allow_delete"] = False
    if ov.is_active is not None and not ov.is_active:
        policy["is_active"] = False

    # max_rows can only be smaller / max_rows 只能更小
    if ov.max_rows is not None and ov.max_rows < policy["max_rows"]:
        policy["max_rows"] = ov.max_rows

    # blocked_columns can only be appended / blocked_columns 只能追加
    if ov.blocked_columns:
        existing = set(policy["blocked_columns"])
        existing.update(ov.blocked_columns)
        policy["blocked_columns"] = list(existing)

    return policy


# ============================================
# Helper Functions / 辅助函数
# ============================================

def _dict_to_table_schema(data: dict[str, Any]) -> TableSchema:
    """Restore TableSchema from dict / 从字典恢复 TableSchema"""
    columns = [
        ColumnSchema(
            name=c["name"],
            type=c["type"],
            description=c.get("description", ""),
            nullable=c.get("nullable", True),
            is_primary=c.get("is_primary", False),
            is_foreign_key=bool(c.get("fk_table")),
            fk_table=c.get("fk_table"),
        )
        for c in data.get("columns", [])
    ]
    return TableSchema(
        table_name=data["table_name"],
        description=data.get("description", ""),
        columns=columns,
        tenant_column=data.get("tenant_column", "tenant_id"),
        row_count_approx=data.get("row_count_approx", 0),
        max_rows=data.get("max_rows", 200),
        allow_read=data.get("allow_read", True),
        allow_create=data.get("allow_create", False),
        allow_update=data.get("allow_update", False),
        allow_delete=data.get("allow_delete", False),
    )


__all__ = [
    "ColumnSchema",
    "TableSchema",
    "SchemaProvider",
]

"""
AI 表策略自动发现与同步服务 / AI Table Policy Auto-Discovery & Sync Service

负责扫描 SQLAlchemy 模型元数据，自动创建 ai_table_policies 默认记录。
Scans SQLAlchemy model metadata to auto-create ai_table_policies default records.
支持启动时自动同步和管理员手动触发同步。
Supports auto-sync at startup and manual trigger by admins.
"""

from enum import Enum
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper

from app.core.base_model import Base, BaseModel, utc_now
from app.core.logging import get_logger
from app.models.ai.table_policy import AITablePolicy

logger = get_logger(__name__)

# ===== 安全敏感表：默认禁用 =====
_BLOCKED_TABLES: set[str] = {
    "admins",
    "admin_roles",
    "permissions",
    "tenant_admin_roles",
    "ai_api_keys",
    "system_configs",
    "system_config_groups",
    "system_config_values",
    "alembic_version",
    "admin_role_permissions",
    "tenant_admin_role_permissions",
}

# ===== 全局敏感列名模式 =====
_SENSITIVE_COLUMN_PATTERNS: set[str] = {
    "password",
    "password_hash",
    "hashed_password",
    "secret",
    "secret_key",
    "api_key",
    "access_token",
    "refresh_token",
    "encrypted_key",
    "salt",
}

# ===== 只读系统列 =====
_READONLY_COLUMNS: list[str] = [
    "id",
    "created_at",
    "updated_at",
    "is_deleted",
    "tenant_id",
]

# ===== 表名 → 中文关键词映射（常用表手动维护） =====
_TABLE_KEYWORDS: dict[str, list[str]] = {
    "tenants": ["企业", "tenant", "组织", "商户", "客户"],
    "tenant_plans": ["套餐", "plan", "计划", "订阅"],
    "tenant_users": ["用户", "user", "终端用户"],
    "tenant_admins": ["管理员", "admin", "企业管理员"],
    "tenant_domains": ["域名", "domain"],
    "agents": ["智能体", "agent", "机器人", "bot", "助手"],
    "agent_conversations": ["对话", "conversation", "chat", "聊天"],
    "conversation_messages": ["消息", "message", "对话消息"],
    "knowledge_bases": ["知识库", "knowledge", "知识"],
    "knowledge_documents": ["文档", "document", "知识文档"],
    "document_chunks": ["分块", "chunk", "文档块"],
    "ai_providers": ["供应商", "provider", "AI供应商"],
    "ai_models": ["模型", "model", "AI模型"],
    "ai_call_logs": ["调用日志", "call_log", "AI调用"],
    "ai_query_logs": ["查询日志", "query_log", "审计"],
    "ai_action_logs": ["操作日志", "action_log"],
    "ai_usage_stats": ["用量", "usage", "统计"],
    "operation_logs": ["操作日志", "operation", "日志"],
    "attachments": ["附件", "attachment", "文件"],
    "batch_runs": ["批处理", "batch", "批量运行"],
    "agent_versions": ["版本", "version", "智能体版本"],
    "agent_access": ["访问权限", "access", "智能体权限"],
    "tenant_quotas": ["配额", "quota", "企业配额"],
    "tenant_model_rate_limits": ["限流", "rate_limit", "速率限制"],
    "periodic_tasks": ["定时任务", "periodic", "计划任务"],
    "task_logs": ["任务日志", "task_log"],
}


def _humanize_table_name(table_name: str) -> str:
    """将 snake_case 表名转为可读标签 / Convert snake_case table name to readable label."""
    return table_name.replace("_", " ").title()


def _derive_permission_code(table_name: str, has_tenant: bool) -> str:
    """从表名推导权限码 / Derive permission code from table name."""
    if not has_tenant:
        return "platform_only"
    # 去除复数 s，转为资源名
    resource = table_name.rstrip("s")
    # 特殊处理一些表名
    resource_map = {
        "tenant_user": "tenant_user",
        "tenant_admin": "tenant_admin",
        "tenant_domain": "tenant_domain",
        "tenant_plan": "tenant_plan",
        "tool_definition": "tool_definition",
        "knowledge_base": "knowledge_base",
        "knowledge_document": "knowledge_base",
        "document_chunk": "knowledge_base",
        "agent_conversation": "agent_conversation",
        "conversation_message": "agent_conversation",
        "operation_log": "operation_log",
        "ai_call_log": "ai_call_log",
        "ai_query_log": "ai_query_log",
        "ai_action_log": "ai_action_log",
        "ai_usage_stat": "ai_usage_stat",
        "agent_version": "agent",
        "agent_acces": "agent",
        "batch_run": "batch_run",
        "attachment": "attachment",
    }
    resource = resource_map.get(resource, resource)
    return f"{resource}:read"


def _is_log_table(table_name: str) -> bool:
    """判断是否为日志/审计/统计表 / Whether table is log/audit/stats."""
    return any(
        pattern in table_name
        for pattern in ("_log", "_stat", "operation_log", "task_log")
    )


def _get_model_class_for_table(table_name: str) -> type[BaseModel] | None:
    """根据表名查找对应的 Model 类 / Find Model class by table name."""
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, "__tablename__") and cls.__tablename__ == table_name:
            return cls
    return None


def _extract_column_descriptions(model_cls: type[BaseModel]) -> dict[str, str]:
    """从 Model 的 column comment 提取列描述 / Extract column descriptions from Model comments."""
    descriptions: dict[str, str] = {}
    mapper: Mapper = sa_inspect(model_cls)

    for attr in mapper.column_attrs:
        col = attr.columns[0]
        col_name = col.name
        comment = col.comment

        # 跳过敏感列
        if col_name in _SENSITIVE_COLUMN_PATTERNS:
            continue

        desc_parts: list[str] = []

        # 1. 列 comment
        if comment:
            desc_parts.append(str(comment))

        # 2. 枚举值自动提取
        col_type = col.type
        if hasattr(col_type, "enum_class") and col_type.enum_class is not None:
            enum_cls = col_type.enum_class
            if issubclass(enum_cls, Enum):
                values = [f"{m.value}" for m in enum_cls]
                desc_parts.append(f"values: {', '.join(values)}")
        else:
            # 检查 Model 类上是否有同名的 default 引用枚举
            default = col.default
            if default is not None and hasattr(default, "arg"):
                arg = default.arg
                if isinstance(arg, str):
                    # 尝试查找 import 的枚举类
                    _try_extract_enum_from_default(
                        model_cls, col_name, arg, desc_parts
                    )

        if desc_parts:
            descriptions[col_name] = "; ".join(desc_parts)

    return descriptions


def _try_extract_enum_from_default(
    model_cls: type[BaseModel],
    col_name: str,
    default_value: str,
    desc_parts: list[str],
) -> None:
    """尝试从列默认值反查枚举类并提取合法值 / Try to infer enum from column default."""
    import sys

    module = sys.modules.get(model_cls.__module__)
    if not module:
        return

    # 扫描模块级别的枚举导入
    for _name, obj in vars(module).items():
        if not isinstance(obj, type) or not issubclass(obj, Enum):
            continue
        # 检查默认值是否属于该枚举
        try:
            if any(m.value == default_value for m in obj):
                labels = []
                for m in obj:
                    if hasattr(m, "label_key") and m.label_key:
                        labels.append(f"{m.value}({m.name.lower()})")
                    else:
                        labels.append(m.value)
                desc_parts.append(f"values: {', '.join(labels)}")
                return
        except Exception:
            continue


def _detect_blocked_columns(table) -> list[str]:
    """检测表中的敏感列 / Detect sensitive columns in table."""
    blocked = []
    for col in table.columns:
        if col.name in _SENSITIVE_COLUMN_PATTERNS:
            blocked.append(col.name)
    return blocked


def _detect_readonly_columns(table) -> list[str]:
    """检测表中的只读列 / Detect readonly columns in table."""
    readonly = []
    for col in table.columns:
        if col.name in _READONLY_COLUMNS:
            readonly.append(col.name)
    return readonly


def _has_tenant_id(table) -> bool:
    """判断表是否有 tenant_id 列 / Whether table has tenant_id column."""
    return "tenant_id" in {c.name for c in table.columns}


def _build_default_policy(table_name: str, table) -> dict[str, Any]:
    """为一张表构建默认策略数据 / Build default policy for a table."""
    model_cls = _get_model_class_for_table(table_name)
    has_tenant = _has_tenant_id(table)
    is_blocked = table_name in _BLOCKED_TABLES
    is_log = _is_log_table(table_name)

    # 权限码
    permission_code = _derive_permission_code(table_name, has_tenant)

    # CRUD 权限
    if is_blocked:
        allow_read = False
        allow_create = False
        allow_update = False
        allow_delete = False
        is_active = False
    elif is_log:
        allow_read = True
        allow_create = False
        allow_update = False
        allow_delete = False
        is_active = True
    else:
        allow_read = True
        allow_create = False
        allow_update = False
        allow_delete = False
        is_active = True

    # 标签
    label = _humanize_table_name(table_name)
    if model_cls and model_cls.__doc__:
        # 取 docstring 第一行作为 label
        first_line = model_cls.__doc__.strip().split("\n")[0].strip()
        if first_line:
            label = first_line

    # 描述
    description = ""
    if model_cls and model_cls.__doc__:
        description = model_cls.__doc__.strip()

    # 关键词
    keywords = _TABLE_KEYWORDS.get(table_name, [table_name])

    # 列描述
    column_descriptions: dict[str, str] = {}
    if model_cls:
        column_descriptions = _extract_column_descriptions(model_cls)

    # 敏感列
    blocked_columns = _detect_blocked_columns(table)
    readonly_columns = _detect_readonly_columns(table)

    now = utc_now()

    return {
        "table_name": table_name,
        "label": label,
        "description": description,
        "keywords": keywords,
        "column_descriptions": column_descriptions,
        "allow_read": allow_read,
        "allow_create": allow_create,
        "allow_update": allow_update,
        "allow_delete": allow_delete,
        "max_rows": 200,
        "blocked_columns": blocked_columns,
        "readonly_columns": readonly_columns,
        "permission_code": permission_code,
        "sort_order": 0,
        "is_active": is_active,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }


async def sync_table_policies(db: AsyncSession) -> dict[str, int]:
    """
    同步表策略：扫描所有 SQLAlchemy 模型，为新表创建默认策略 / Sync table policies: scan models, create default for new tables.

    已存在的策略不会被覆盖。

    Returns:
        {"new": N, "existing": M, "blocked": B}
    """
    # 获取所有已注册的表
    all_tables = Base.metadata.tables

    # 查询已有策略的表名
    result = await db.execute(
        select(AITablePolicy.table_name)
    )
    existing_names: set[str] = {row[0] for row in result.all()}

    new_count = 0
    existing_count = 0
    blocked_count = 0

    for table_name, table in all_tables.items():
        if table_name in existing_names:
            existing_count += 1
            continue

        # 跳过 alembic 内部表
        if table_name == "alembic_version":
            blocked_count += 1
            continue

        # 跳过关联表（无主键或纯中间表）
        if not table.primary_key:
            blocked_count += 1
            continue

        policy_data = _build_default_policy(table_name, table)

        if not policy_data["is_active"]:
            blocked_count += 1

        policy = AITablePolicy(**policy_data)
        db.add(policy)
        new_count += 1

    if new_count > 0:
        await db.commit()

    logger.info(
        "Table policy sync: new={}, existing={}, blocked={}",
        new_count, existing_count, blocked_count,
    )

    return {
        "new": new_count,
        "existing": existing_count,
        "blocked": blocked_count,
    }


__all__ = ["sync_table_policies"]

# -*- coding: utf-8 -*-
"""
Alembic Migration Environment
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入配置和模型
from app.core.config import settings
from app.core.base_model import Base

# 导入所有模型以确保它们被注册到 Base.metadata
from app.models import (
    # 平台级模型
    Admin,
    SystemConfigGroup,
    SystemConfig,
    SystemConfigValue,
    OperationLog,
    TaskLog,
    PeriodicTask,
    SystemAgentAssignment,
    # 企业级模型
    Tenant,
    TenantAdmin,
    TenantUser,
    TenantDomain,
    TenantPlan,
    tenant_plan_permissions,
    Attachment,
    # RBAC
    Permission,
    AdminRole,
    admin_role_permissions,
    TenantAdminRole,
    tenant_admin_role_permissions,
    TenantUserRole,
    tenant_user_role_permissions,
    # 通知
    NotificationTemplate,
    Notification,
    NotificationPreference,
    # AI 网关
    AIProvider,
    AIModel,
    ProviderApiKey,
    AICallLog,
    UsageStat,
    TenantModelRateLimit,
    TenantQuota,
    # 智能体
    Agent,
    AgentConversation,
    ConversationMessage,
    BatchRun,
    AgentVersion,
    AgentAccess,
    AIActionLog,
    AITablePolicy,
    AITablePolicyOverride,
    # 技能包 & 技能
    SkillPackage,
    Skill,
    AgentSkillBinding,
    # 域名 SSL
    DomainSslCertificate,
    # 插件
    Plugin,
    PluginVersion,
    PluginLicense,
    ResourceTenantAssignment,
)
# AI 子模块中有但未在 models/__init__.py 再导出的模型
from app.models.ai.query_log import AIQueryLog
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_base_tenant_access import KnowledgeBaseTenantAccess
from app.models.ai.knowledge_document import KnowledgeDocument
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.skill_call_log import SkillCallLog
from app.models.system.email_log import EmailLog
from app.models.common.user_preference import UserPreference

# Dynamic plugin model discovery (Alembic autogenerate needs models registered on Base.metadata)
# Scans plugins/*/backend/models/__init__.py — no hardcoded plugin names
import importlib
_plugins_base = Path(__file__).parent.parent / "plugins"
if _plugins_base.exists():
    for _pd in sorted(_plugins_base.iterdir()):
        _models_init = _pd / "backend" / "models" / "__init__.py"
        if _models_init.is_file():
            _mod_name = f"plugins.{_pd.name}.backend.models"
            try:
                importlib.import_module(_mod_name)
            except Exception:
                pass  # plugin not installed or import error — skip

# Alembic 配置对象
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# 迁移文件目录
_migrations_dir = Path(__file__).parent / "versions"
_version_paths = [str(_migrations_dir)]

# 只扫描已安装插件的迁移目录（防止未安装插件的迁移被意外执行）
_plugins_dir = Path(__file__).parent.parent / "plugins"
if _plugins_dir.exists():
    _installed_plugin_names: set[str] = set()
    try:
        import psycopg2
        _conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
        _cur = _conn.cursor()
        _cur.execute("SELECT name FROM plugins WHERE is_deleted = false")
        _installed_plugin_names = {row[0] for row in _cur.fetchall()}
        _cur.close()
        _conn.close()
    except Exception:
        pass  # DB not ready or table missing — skip plugin migrations

    for _plugin_dir in _plugins_dir.iterdir():
        if not _plugin_dir.is_dir():
            continue
        if _plugin_dir.name not in _installed_plugin_names:
            continue
        _plugin_migrations = _plugin_dir / "backend" / "migrations" / "versions"
        if _plugin_migrations.is_dir():
            _version_paths.append(str(_plugin_migrations))

config.set_main_option(
    "version_locations",
    " ".join(_version_paths),
)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 元数据对象（用于自动生成迁移）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式运行迁移
    
    仅生成 SQL 脚本，不实际连接数据库
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移
    
    连接数据库并执行迁移
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# 根据模式运行迁移
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

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
    Admin,
    Tenant,
    TenantAdmin,
    TenantUser,
    Permission,
    AdminRole,
    admin_role_permissions,
    TenantAdminRole,
    tenant_admin_role_permissions,
    # AI 网关模型
    AIProvider,
    AIModel,
    ProviderApiKey,
    AICallLog,
    UsageStat,
    TenantModelRateLimit,
    TenantQuota,
    # 智能体模型
    Agent,
    AgentConversation,
    ConversationMessage,
    # 批量运行
    BatchRun,
    # 智能体版本
    AgentVersion,
    # 智能体访问权限
    AgentAccess,
    # AI 操作审计日志
    AIActionLog,
    # AI 表策略
    AITablePolicy,
    AITablePolicyOverride,
    # 技能包 & 技能
    SkillPackage,
    Skill,
    AgentSkillBinding,
    # 域名 SSL 证书
    DomainSslCertificate,
    # 通知
    NotificationTemplate,
    Notification,
    NotificationPreference,
    # 插件
    Plugin,
    PluginVersion,
    PluginTenantAssignment,
    PluginLicense,
)

# Alembic 配置对象
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# 确保 version_locations 包含 CRUD 子目录
_migrations_dir = Path(__file__).parent / "versions"
_crud_dir = _migrations_dir / "crud"
_crud_dir.mkdir(exist_ok=True)
# 动态扫描已安装插件的迁移目录
_version_paths = [str(_migrations_dir), str(_crud_dir)]
_plugins_dir = Path(__file__).parent.parent / "plugins"
if _plugins_dir.exists():
    for _plugin_dir in _plugins_dir.iterdir():
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

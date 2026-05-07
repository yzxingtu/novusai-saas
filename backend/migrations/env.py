"""
Alembic Migration Environment
"""

import importlib
import sys
import warnings
from logging.config import fileConfig
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from alembic.autogenerate import rewriter
from alembic.operations import ops as alembic_ops
from sqlalchemy import engine_from_config, pool

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入配置和模型
# Dynamic plugin model discovery (Alembic autogenerate needs models registered on Base.metadata)
# Only DB-registered plugins participate by default, so optional repo plugins do not
# leak into host autogenerate or revision graph resolution.
# / 默认只让数据库已注册插件参与，避免仓库里未安装插件污染宿主迁移与 autogenerate。

from app import models as registered_models
from app.core.base_model import Base
from app.core.config import settings
from app.plugins.migration_paths import (
    build_migration_version_locations,
    get_migration_plugin_names,
)

# 中文: 导入 app.models 包即可触发所有导出模型注册到 Base.metadata。
# EN: Importing app.models triggers registration of every exported model on Base.metadata.
_registered_model_exports = registered_models.__all__

_plugins_base = Path(__file__).parent.parent / "plugins"
for _plugin_name in get_migration_plugin_names(
    backend_dir=Path(__file__).parent.parent,
    db_url=settings.DATABASE_URL_SYNC,
):
    _models_init = _plugins_base / _plugin_name / "backend" / "models" / "__init__.py"
    if _models_init.is_file():
        _mod_name = f"plugins.{_plugin_name}.backend.models"
        try:
            importlib.import_module(_mod_name)
        except Exception as exc:
            # 中文: 插件模型注册是可选扩展；失败时给出可见诊断，但不阻断宿主迁移。
            # EN: Plugin model registration is optional; warn on failures without blocking host migrations.
            warnings.warn(
                f"Skip optional Alembic plugin model import {_mod_name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )

# Alembic 配置对象
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# 迁移文件目录
_migrations_dir = Path(__file__).parent / "versions"
_version_paths = build_migration_version_locations(
    backend_dir=Path(__file__).parent.parent,
    db_url=settings.DATABASE_URL_SYNC,
)

config.set_main_option(
    "version_locations",
    "\n".join(_version_paths),
)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 元数据对象（用于自动生成迁移）
target_metadata = Base.metadata

_known_model_tables = set(target_metadata.tables.keys())

_autogen_rewriter = rewriter.Rewriter()
_LIFECYCLE_DATETIME_COLUMNS = {
    "created_at",
    "updated_at",
    "deleted_at",
    "promoted_to_global_at",
}


@_autogen_rewriter.rewrites(alembic_ops.AlterColumnOp)
def _drop_comment_only_alter_ops(context, revision, op):
    """Strip pure comment diffs so autogenerate focuses on structural changes."""
    if op.modify_comment is False:
        return op

    op.modify_comment = False
    if not op.has_changes():
        return []
    return op


@_autogen_rewriter.rewrites(alembic_ops.CreateIndexOp)
def _drop_redundant_single_id_indexes(context, revision, op):
    """Ignore autogen requests for explicit single-column PK id indexes."""
    column_names = tuple(
        column if isinstance(column, str) else getattr(column, "name", None)
        for column in op.columns
    )
    if not op.unique and column_names == ("id",):
        return []
    return op


def _compare_type(
    context, inspected_column, metadata_column, inspected_type, metadata_type
):
    """Ignore timezone-only churn on shared lifecycle datetime columns."""
    column_name = getattr(metadata_column, "name", None) or getattr(
        inspected_column, "name", None
    )
    if (
        column_name in _LIFECYCLE_DATETIME_COLUMNS
        and isinstance(inspected_type, sa.DateTime)
        and isinstance(metadata_type, sa.DateTime)
    ):
        return False
    return None


def _include_object(obj, name, type_, reflected, compare_to):
    """Only emit autogenerate diffs for tables registered in our models."""
    return not (type_ == "table" and reflected and name not in _known_model_tables)


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
        compare_type=_compare_type,
        compare_server_default=False,
        include_object=_include_object,
        process_revision_directives=_autogen_rewriter,
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
            compare_type=_compare_type,
            compare_server_default=False,
            include_object=_include_object,
            process_revision_directives=_autogen_rewriter,
        )

        with context.begin_transaction():
            context.run_migrations()


# 根据模式运行迁移
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

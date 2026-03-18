"""
迁移文件元数据注入 / Migration Helper

为生成的迁移文件注入 codegen 元数据变量
Injects codegen metadata variables into generated migration files.

Web/CLI 回滚时执行 alembic downgrade、删除迁移文件、并自动 DROP 数据表
Run alembic downgrade, delete migration file, and auto DROP table on web/CLI rollback.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def _get_table_name(resource: str) -> str:
    """从 resource 推断表名，与 model 模板一致。Infer table name from resource."""
    from app.codegen.config_parser import _infer_plural
    return _infer_plural(resource.replace("-", "_")) if resource else ""


def _drop_table_if_exists(resource: str) -> bool:
    """
    回滚时强制删除数据表。无论 downgrade 是否成功，均执行 DROP TABLE。
    Force drop table on rollback. Runs DROP TABLE regardless of downgrade result.
    """
    table = _get_table_name(resource)
    if not table:
        return False
    try:
        from sqlalchemy import text
        from app.core.database import sync_session_factory
        with sync_session_factory() as session:
            session.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            session.commit()
        return True
    except Exception:
        return False


def run_rollback_migration_cleanup(
    resource: str,
    migration_file: str | None,
    project_root: Path,
    backend_dir: Path | None = None,
) -> bool:
    """
    回滚后清理迁移：purge 孤立 stamp、downgrade、删除迁移文件。
    After rollback: purge orphaned stamps, downgrade, delete migration file.

    Returns:
        True 若成功执行 downgrade 并删除迁移文件
    """
    _backend = backend_dir or (project_root / "backend")
    _backend = Path(_backend)
    if not _backend.exists():
        return False

    _mp = None
    if migration_file:
        _mp = Path(migration_file)
        if not _mp.is_absolute():
            _mp = _backend / migration_file.replace("backend/", "").replace("backend\\", "")
        if not _mp.exists():
            _mp = _backend / "migrations" / "versions" / Path(migration_file).name
    if not _mp or not _mp.exists():
        _table = _get_table_name(resource)
        if _table:
            _vers = _backend / "migrations" / "versions"
            if _vers.exists():
                for _f in _vers.glob("*.py"):
                    if _f.name.startswith(".") or _f.name == "__init__.py":
                        continue
                    try:
                        _t = _f.read_text(encoding="utf-8", errors="replace")
                        if f"'{_table}'" in _t or f'"{_table}"' in _t:
                            _mp = _f
                            break
                    except Exception:
                        pass

    from app.core.database import purge_orphaned_alembic_stamps

    purge_orphaned_alembic_stamps(_backend)

    _down_rev = None
    if _mp and _mp.exists():
        _txt = _mp.read_text(encoding="utf-8", errors="replace")
        _m = re.search(r"down_revision[^=]*=\s*['\"]([^'\"]+)['\"]", _txt)
        if _m:
            _down_rev = _m.group(1).strip()

    _proc = None
    if _down_rev:
        _proc = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", _down_rev],
            cwd=str(_backend), capture_output=True, text=True,
        )
    elif _mp and _mp.exists():
        _proc = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            cwd=str(_backend), capture_output=True, text=True,
        )

    migration_cleaned = False
    if _proc is not None and _proc.returncode == 0:
        if _mp and _mp.exists():
            _mp.unlink()
            migration_cleaned = True

    # 无论 downgrade 是否成功，均执行 DROP TABLE 确保数据表被删除
    # Always run DROP TABLE to ensure table is removed, regardless of downgrade result
    table_dropped = _drop_table_if_exists(resource) if resource else False

    return migration_cleaned or table_dropped


def inject_migration_metadata(
    content: str,
    resource: str,
    source: str = "codegen",
    version: str = "1",
) -> str:
    """
    为迁移文件内容注入元数据变量 / Inject metadata variables into migration content.

    Args:
        content: 迁移文件原始内容
        resource: 资源名
        source: 来源标识，默认 codegen
        version: 版本号

    Returns:
        注入元数据后的内容
    """
    meta = f"""
# Codegen metadata / 代码生成器元数据
codegen_source = {repr(source)}
codegen_resource = {repr(resource)}
codegen_version = {repr(version)}
"""
    # 在 revision 变量之后插入
    if "revision" in content and "codegen_source" not in content:
        lines = content.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("revision") and "=" in line:
                insert_at = i + 1
                break
        lines.insert(insert_at, meta)
        return "\n".join(lines)
    return content


__all__ = ["inject_migration_metadata", "run_rollback_migration_cleanup"]

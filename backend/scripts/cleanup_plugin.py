"""
插件完整清理脚本：DB 记录 + Alembic downgrade + 文件系统产物

覆盖所有插件安装/启用阶段产生的 DB 副作用：
  install 阶段:
    - plugins             （插件主记录）
    - plugin_versions     （版本快照）
    - system_agent_assignments  （ai_requirements 声明的 feature）
    - skill_packages / skills   （on_install 钩子创建的 toolkit）
    - 插件迁移创建的表      （alembic downgrade）
  enable 阶段:
    - permissions         （菜单权限）
    - resource_tenant_assignments
    - periodic_tasks      （插件定时任务）
    - notification_templates

用法:
  # 通过 CLI（推荐）
  novusai plugin cleanup --plugin <plugin-name> [--revision ncc_001,ncc_002]

  # 或直接运行脚本
  python scripts/cleanup_plugin.py --plugin <plugin-name> [--revision ncc_001]

示例: novusai plugin cleanup -p novus-crud-code -r ncc_001
"""

import argparse
import subprocess
import sys

# 不用 pathlib——与插件安全扫描保持一致
_this_file: str = __file__
_base_dir = _this_file.replace("\\", "/").rsplit("/", 1)[0]  # scripts/
PROJECT_ROOT_STR = _base_dir.rsplit("/", 1)[0]  # backend/


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="完整清理指定插件的 DB 记录与迁移")
    parser.add_argument(
        "--plugin",
        required=True,
        metavar="NAME",
        help="插件名（如 novus-crud-code）",
    )
    parser.add_argument(
        "--revision",
        metavar="REV",
        help="可选：alembic_version 中需清理的 revision（如 ncc_001），逗号分隔多个",
    )
    return parser.parse_args()


def get_db_url() -> str:
    sys.path.insert(0, PROJECT_ROOT_STR)
    from app.core.config import settings

    return settings.DATABASE_URL_SYNC


def run_alembic_downgrade(plugin_name: str, plugin_safe: str) -> None:
    """降级插件分支，删除插件迁移创建的表。"""
    migrations_path = (
        PROJECT_ROOT_STR + "/plugins/" + plugin_name + "/backend/migrations/versions"
    )
    branch_label = f"plugin_{plugin_safe}"
    script = (
        "from alembic.config import Config; from alembic import command; "
        "cfg = Config('alembic.ini'); "
        "vl = cfg.get_main_option('version_locations') or 'migrations/versions'; "
        f"pm = '{migrations_path}'; "
        "cfg.set_main_option('version_locations', vl + ' ' + pm); "
        f"command.downgrade(cfg, '{branch_label}@base')"
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        print(f"  [OK] Alembic downgrade OK -> plugin_{plugin_safe} tables removed")
    else:
        stderr = r.stderr.strip()[-600:]
        if "already at base" in stderr or "No such revision" in stderr:
            print("  [INFO] Alembic already at base")
        else:
            print(f"  [WARN] Alembic downgrade warning:\n{stderr}")


def connect():
    """返回 psycopg2 同步连接（避免使用 asyncpg）"""
    import psycopg2

    url = get_db_url()  # postgresql://user:pass@host:port/dbname
    url = url.replace("postgresql://", "")
    user_pass, rest = url.split("@", 1)
    host_port, dbname = rest.split("/", 1)
    user, password = user_pass.split(":", 1)
    host, port = (host_port.split(":", 1) + ["5432"])[:2]
    return psycopg2.connect(
        host=host,
        port=int(port),
        dbname=dbname,
        user=user,
        password=password,
    )


def execute_step(cur, conn, sql: str, label: str) -> None:
    try:
        cur.execute(sql)
        count = cur.rowcount
        conn.commit()
        print(f"  [OK]  {label}: {count} row(s) deleted")
    except Exception as exc:
        conn.rollback()
        # 表不存在时静默跳过（插件从未安装时正常）
        if "does not exist" in str(exc) or "relation" in str(exc).lower():
            print(f"  [INFO]  {label}: table/relation not found (skipped)")
        else:
            print(f"  [WARN]  {label}: {exc}")


def clean_db(
    plugin_name: str, plugin_safe: str, revision_ids: list[str] | None
) -> None:
    conn = connect()
    cur = conn.cursor()

    # ── 按依赖顺序清理 ──────────────────────────────────────────────

    execute_step(
        cur,
        conn,
        f"DELETE FROM periodic_tasks WHERE name LIKE 'plugin.{plugin_name}.%'",
        "periodic_tasks",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM notification_templates WHERE code LIKE 'plugin.{plugin_name}.%'",
        "notification_templates",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM system_agent_assignments "
        f"WHERE feature_code LIKE 'plugin.{plugin_name}.%'",
        "system_agent_assignments",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM skills WHERE package_id IN ("
        f"  SELECT id FROM skill_packages WHERE source_plugin = '{plugin_name}'"
        f")",
        "skills",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM skill_packages WHERE source_plugin = '{plugin_name}'",
        "skill_packages",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM permissions "
        f"WHERE code LIKE 'menu:%.plugin_{plugin_safe}_%' "
        f"   OR code LIKE 'plugin.{plugin_name}.%' "
        f"   OR code LIKE '%{plugin_name}%'",
        "permissions",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM resource_tenant_assignments "
        f"WHERE resource_type = 'plugin' AND resource_id IN ("
        f"  SELECT id FROM plugins WHERE name = '{plugin_name}'"
        f")",
        "resource_tenant_assignments",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM plugin_versions WHERE plugin_id IN ("
        f"  SELECT id FROM plugins WHERE name = '{plugin_name}'"
        f")",
        "plugin_versions",
    )

    execute_step(
        cur,
        conn,
        f"DELETE FROM plugins WHERE name = '{plugin_name}'",
        "plugins",
    )

    if revision_ids:
        for rev in revision_ids:
            execute_step(
                cur,
                conn,
                f"DELETE FROM alembic_version WHERE version_num = '{rev.strip()}'",
                f"alembic_version ({rev})",
            )

    cur.close()
    conn.close()


def build_manual_sql(
    plugin_name: str, plugin_safe: str, revision_ids: list[str]
) -> str:
    rev_sql = ""
    if revision_ids:
        for r in revision_ids:
            rev_sql += f"DELETE FROM alembic_version WHERE version_num = '{r}';\n"
    return f"""
-- 手动执行（psycopg2 不可用时）:
DELETE FROM periodic_tasks WHERE name LIKE 'plugin.{plugin_name}.%';
DELETE FROM notification_templates WHERE code LIKE 'plugin.{plugin_name}.%';
DELETE FROM system_agent_assignments WHERE feature_code LIKE 'plugin.{plugin_name}.%';
DELETE FROM skills WHERE package_id IN (SELECT id FROM skill_packages WHERE source_plugin = '{plugin_name}');
DELETE FROM skill_packages WHERE source_plugin = '{plugin_name}';
DELETE FROM permissions WHERE code LIKE 'menu:%.plugin_{plugin_safe}_%' OR code LIKE 'plugin.{plugin_name}.%';
DELETE FROM resource_tenant_assignments WHERE resource_type = 'plugin' AND resource_id IN (SELECT id FROM plugins WHERE name = '{plugin_name}');
DELETE FROM plugin_versions WHERE plugin_id IN (SELECT id FROM plugins WHERE name = '{plugin_name}');
DELETE FROM plugins WHERE name = '{plugin_name}';
{rev_sql}
"""


def clean_filesystem(plugin_name: str) -> None:
    """清理插件目录中的生成产物和缓存文件（不删除源码）。"""
    import os
    import shutil

    plugin_root = PROJECT_ROOT_STR + "/plugins/" + plugin_name
    frontend_dir = plugin_root + "/frontend"

    targets = [
        (frontend_dir + "/node_modules", "frontend/node_modules"),
        (frontend_dir + "/dist", "frontend/dist"),
        (frontend_dir + "/package-lock.json", "frontend/package-lock.json"),
    ]

    if os.path.isdir(plugin_root):
        for dirpath, dirnames, _ in os.walk(plugin_root):
            for d in dirnames:
                if d == "__pycache__":
                    targets.append(
                        (
                            dirpath.replace("\\", "/") + "/" + d,
                            ".../__pycache__",
                        )
                    )
            dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git")]

    for path, label in targets:
        path_native = path.replace("/", "\\") if "\\" in PROJECT_ROOT_STR else path
        if os.path.isdir(path_native):
            shutil.rmtree(path_native, ignore_errors=True)
            print(f"  [DEL] Removed dir:  {label}")
        elif os.path.isfile(path_native):
            os.remove(path_native)
            print(f"  [DEL] Removed file: {label}")
        else:
            print(f"  [INFO] Not found:    {label}")


if __name__ == "__main__":
    args = parse_args()
    plugin_name = args.plugin
    plugin_safe = plugin_name.replace("-", "_")
    revision_ids = (
        [r.strip() for r in args.revision.split(",")] if args.revision else []
    )

    print(f"\n{'=' * 50}")
    print(f"  {plugin_name} 插件完整清理")
    print(f"{'=' * 50}\n")

    print("步骤 1 — Alembic downgrade...")
    run_alembic_downgrade(plugin_name, plugin_safe)

    print("\n步骤 2 — 清理数据库记录...")
    try:
        clean_db(plugin_name, plugin_safe, revision_ids)
    except ImportError:
        print("  [WARN] psycopg2 not installed, run the SQL below manually:")
        print(build_manual_sql(plugin_name, plugin_safe, revision_ids))
    except Exception as exc:
        print(f"  [ERROR] DB cleanup error: {exc}")
        import traceback

        traceback.print_exc()

    print("\n步骤 3 — 清理文件系统产物 (node_modules / dist / __pycache__)...")
    try:
        clean_filesystem(plugin_name)
    except Exception as exc:
        print(f"  [WARN] Filesystem cleanup warning: {exc}")

    print(f"\n{'=' * 50}")
    print("  Cleanup completed")
    print("  You can now reinstall or retest the plugin if needed")
    print(f"{'=' * 50}\n")

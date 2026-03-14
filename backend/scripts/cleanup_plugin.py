"""
完整清理脚本：novus-crud-code 插件所有 DB 记录 + Alembic downgrade

覆盖所有插件安装/启用阶段产生的 DB 副作用：
  install 阶段:
    - plugins             （插件主记录）
    - plugin_versions     （版本快照）
    - system_agent_assignments  （ai_requirements 声明的3个 feature）
    - skill_packages / skills   （on_install 钩子创建的 toolkit）
    - ncc_* tables        （alembic migration）
  enable 阶段:
    - permissions         （菜单权限，代码 menu:admin.plugin_novus_crud_code_*）
    - resource_tenant_assignments
    - periodic_tasks      （插件定时任务，当前插件无，预防性清理）
    - notification_templates   （同上）
  startup discover 阶段:
    - 同 install，已被以上步骤覆盖

用法: python scripts/cleanup_plugin.py
"""
import subprocess
import sys

# 不用 pathlib——与插件安全扫描保持一致
_this_file: str = __file__
_base_dir = _this_file.replace("\\", "/").rsplit("/", 1)[0]  # scripts/
PROJECT_ROOT_STR = _base_dir.rsplit("/", 1)[0]              # backend/

PLUGIN_NAME = "novus-crud-code"
PLUGIN_SAFE = PLUGIN_NAME.replace("-", "_")   # novus_crud_code
PLUGIN_MIGRATIONS = (
    PROJECT_ROOT_STR + "/plugins/" + PLUGIN_NAME + "/backend/migrations/versions"
)


def get_db_url() -> str:
    sys.path.insert(0, PROJECT_ROOT_STR)
    from app.core.config import settings
    return settings.DATABASE_URL_SYNC


def run_alembic_downgrade() -> None:
    """降级 plugin_novus_crud_code 分支，删除 ncc_* 4张表。"""
    branch_label = f"plugin_{PLUGIN_SAFE}"
    script = (
        "from alembic.config import Config; from alembic import command; "
        "cfg = Config('alembic.ini'); "
        "vl = cfg.get_main_option('version_locations') or 'migrations/versions'; "
        f"pm = '{PLUGIN_MIGRATIONS}'; "
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
        print("  ✅ Alembic downgrade OK  →  ncc_* 表已删除")
    else:
        stderr = r.stderr.strip()[-600:]
        if "already at base" in stderr or "No such revision" in stderr:
            print("  ℹ️  Alembic: 已在 base（ncc_* 表本来就不存在）")
        else:
            print(f"  ⚠️  Alembic downgrade warning:\n{stderr}")


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
        host=host, port=int(port), dbname=dbname, user=user, password=password,
    )


def execute_step(cur, conn, sql: str, label: str) -> None:
    try:
        cur.execute(sql)
        count = cur.rowcount
        conn.commit()
        print(f"  ✅  {label}: {count} row(s) deleted")
    except Exception as exc:
        conn.rollback()
        # 表不存在时静默跳过（插件从未安装时正常）
        if "does not exist" in str(exc) or "relation" in str(exc).lower():
            print(f"  ℹ️  {label}: table/relation not found (skipped)")
        else:
            print(f"  ⚠️  {label}: {exc}")


def clean_db() -> None:
    conn = connect()
    cur = conn.cursor()

    # ── 按依赖顺序清理 ──────────────────────────────────────────────

    # 1. 定时任务（若 plugin.yaml 有 tasks）
    execute_step(cur, conn,
        f"DELETE FROM periodic_tasks WHERE name LIKE 'plugin.{PLUGIN_NAME}.%'",
        "periodic_tasks",
    )

    # 2. 通知模板（若 plugin.yaml 有 notifications）
    execute_step(cur, conn,
        f"DELETE FROM notification_templates WHERE code LIKE 'plugin.{PLUGIN_NAME}.%'",
        "notification_templates",
    )

    # 3. AI feature 绑定记录
    execute_step(cur, conn,
        f"DELETE FROM system_agent_assignments "
        f"WHERE feature_code LIKE 'plugin.{PLUGIN_NAME}.%'",
        "system_agent_assignments",
    )

    # 4. Skills（级联删除 skill_packages）
    execute_step(cur, conn,
        f"DELETE FROM skills WHERE package_id IN ("
        f"  SELECT id FROM skill_packages WHERE source_plugin = '{PLUGIN_NAME}'"
        f")",
        "skills",
    )

    # 5. SkillPackage（on_install 钩子创建 + 框架 extensions.skills 创建）
    execute_step(cur, conn,
        f"DELETE FROM skill_packages WHERE source_plugin = '{PLUGIN_NAME}'",
        "skill_packages",
    )

    # 6. 菜单权限 DB 记录
    #    代码格式: menu:admin.plugin_novus_crud_code_<menu_name>
    execute_step(cur, conn,
        f"DELETE FROM permissions "
        f"WHERE code LIKE 'menu:%.plugin_{PLUGIN_SAFE}_%' "
        f"   OR code LIKE 'plugin.{PLUGIN_NAME}.%' "
        f"   OR code LIKE '%{PLUGIN_NAME}%'",
        "permissions",
    )

    # 7. 企业资源分配（插件菜单/配置分配）
    execute_step(cur, conn,
        f"DELETE FROM resource_tenant_assignments "
        f"WHERE resource_type = 'plugin' AND resource_id IN ("
        f"  SELECT id FROM plugins WHERE name = '{PLUGIN_NAME}'"
        f")",
        "resource_tenant_assignments",
    )

    # 8. 版本快照
    execute_step(cur, conn,
        f"DELETE FROM plugin_versions WHERE plugin_id IN ("
        f"  SELECT id FROM plugins WHERE name = '{PLUGIN_NAME}'"
        f")",
        "plugin_versions",
    )

    # 9. 插件主记录（最后删除）
    execute_step(cur, conn,
        f"DELETE FROM plugins WHERE name = '{PLUGIN_NAME}'",
        "plugins",
    )

    # 10. alembic_version 残留（downgrade 应自动清理，这里二次保险）
    execute_step(cur, conn,
        "DELETE FROM alembic_version "
        "WHERE version_num = 'ncc_001'",
        "alembic_version (ncc_001)",
    )

    cur.close()
    conn.close()


MANUAL_SQL = f"""
-- 手动执行（psycopg2 不可用时）:
DELETE FROM periodic_tasks WHERE name LIKE 'plugin.{PLUGIN_NAME}.%';
DELETE FROM notification_templates WHERE code LIKE 'plugin.{PLUGIN_NAME}.%';
DELETE FROM system_agent_assignments WHERE feature_code LIKE 'plugin.{PLUGIN_NAME}.%';
DELETE FROM skills WHERE package_id IN (SELECT id FROM skill_packages WHERE source_plugin = '{PLUGIN_NAME}');
DELETE FROM skill_packages WHERE source_plugin = '{PLUGIN_NAME}';
DELETE FROM permissions WHERE code LIKE 'menu:%.plugin_{PLUGIN_SAFE}_%' OR code LIKE 'plugin.{PLUGIN_NAME}.%';
DELETE FROM resource_tenant_assignments WHERE resource_type = 'plugin' AND resource_id IN (SELECT id FROM plugins WHERE name = '{PLUGIN_NAME}');
DELETE FROM plugin_versions WHERE plugin_id IN (SELECT id FROM plugins WHERE name = '{PLUGIN_NAME}');
DELETE FROM plugins WHERE name = '{PLUGIN_NAME}';
DELETE FROM alembic_version WHERE version_num = 'ncc_001';
"""

def clean_filesystem() -> None:
    """清理插件目录中的生成产物和缓存文件（不删除源码）。"""
    import shutil

    plugin_root = PROJECT_ROOT_STR + "/plugins/" + PLUGIN_NAME
    frontend_dir = plugin_root + "/frontend"

    targets = [
        (frontend_dir + "/node_modules",    "frontend/node_modules"),
        (frontend_dir + "/dist",            "frontend/dist"),
        (frontend_dir + "/package-lock.json", "frontend/package-lock.json"),
    ]

    # 递归找 __pycache__
    import os
    for dirpath, dirnames, _ in os.walk(plugin_root):
        for d in dirnames:
            if d == "__pycache__":
                targets.append((
                    dirpath.replace("\\", "/") + "/" + d,
                    ".../__pycache__",
                ))
        # 跳过 node_modules（已在上面处理）
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git")]

    for path, label in targets:
        path_native = path.replace("/", "\\") if "\\" in PROJECT_ROOT_STR else path
        if os.path.isdir(path_native):
            shutil.rmtree(path_native, ignore_errors=True)
            print(f"  🗑️  Removed dir:  {label}")
        elif os.path.isfile(path_native):
            os.remove(path_native)
            print(f"  🗑️  Removed file: {label}")
        else:
            print(f"  ℹ️  Not found:    {label}")


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("  novus-crud-code 插件完整清理")
    print(f"{'=' * 50}\n")

    print("步骤 1 — Alembic downgrade (ncc_* 4张表)...")
    run_alembic_downgrade()

    print("\n步骤 2 — 清理数据库记录...")
    try:
        clean_db()
    except ImportError:
        print("  ⚠️  psycopg2 未安装，请手动执行以下 SQL：")
        print(MANUAL_SQL)
    except Exception as exc:
        print(f"  ❌ DB cleanup error: {exc}")
        import traceback
        traceback.print_exc()

    print("\n步骤 3 — 清理文件系统产物 (node_modules / dist / __pycache__)...")
    try:
        clean_filesystem()
    except Exception as exc:
        print(f"  ⚠️  Filesystem cleanup warning: {exc}")

    print(f"\n{'=' * 50}")
    print("  清理完成 — 现在可以重新安装/测试插件了")
    print("  重新安装: 在管理端插件页面执行「安装」")
    print("  重建前端: cd frontend && npm install && npx vite build")
    print(f"{'=' * 50}\n")

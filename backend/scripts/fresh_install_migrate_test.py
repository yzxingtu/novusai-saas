#!/usr/bin/env python3
"""
空库 / 指定库迁移验证：对 PostgreSQL 执行 `alembic upgrade heads`（与项目 Docker 默认一致）。

与 docker-compose.dev.yml 对齐的默认连接：
  host=localhost, port=5432, user=postgres, password=postgres

用法:
  cd backend
  python scripts/fresh_install_migrate_test.py --database test

环境变量（可选，覆盖默认值）:
  DATABASE_HOST, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD

迁移完成后可选做 schema 抽样断言（统一作用域相关）。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _build_sync_url(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> str:
    from urllib.parse import quote_plus

    user_enc = quote_plus(user)
    pwd_enc = quote_plus(password)
    return f"postgresql://{user_enc}:{pwd_enc}@{host}:{port}/{database}"


def _run_alembic_heads(env: dict[str, str]) -> None:
    cmd = [sys.executable, "-m", "alembic", "upgrade", "heads"]
    print("[migrate] cwd=", _BACKEND_DIR)
    print("[migrate] DATABASE_NAME=", env.get("DATABASE_NAME"))
    print("[migrate] command:", " ".join(cmd))
    r = subprocess.run(
        cmd,
        cwd=str(_BACKEND_DIR),
        env=env,
        check=False,
    )
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def _verify_schema(url: str) -> list[str]:
    """返回问题列表；空表示通过。"""
    from sqlalchemy import create_engine, text

    issues: list[str] = []
    eng = create_engine(url, echo=False)
    with eng.connect() as conn:

        def has_table(name: str) -> bool:
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :t"
                ),
                {"t": name},
            )
            return r.fetchone() is not None

        def has_column(table: str, col: str) -> bool:
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": col},
            )
            return r.fetchone() is not None

        retired_tables = (
            "periodic_tasks",
            "task_logs",
            "tenant_plugins",
            "plugin_migrations",
            "plugin_tenant_assignments",
            "tool_definitions",
            "agent_skill_bindings",
            "skill_scripts",
            "knowledge_base_tenant_access",
            "ephemeral_documents",
            "ai_usage_stats",
            "ai_table_policies",
            "ai_table_policy_overrides",
        )
        for table in retired_tables:
            if has_table(table):
                issues.append(f"旧表 {table} 仍存在（fresh schema 不应创建）")

        retired_columns = {
            "agents": (
                "tenant_id",
                "owner_type",
                "distribution_mode",
                "tool_bindings",
                "knowledge_base_ids",
                "target_audience",
            ),
            "agent_versions": ("tool_bindings", "knowledge_base_ids"),
            "knowledge_bases": ("tenant_id", "visibility"),
            "ai_api_keys": ("tenant_id",),
            "ai_call_logs": ("agent_distribution_mode",),
            "skills": ("script_content", "script_language"),
            "skill_packages": ("bind_mode", "target_audience"),
            "plugins": (
                "plugin_type",
                "entry_point",
                "is_system",
                "required_permissions",
                "dependencies",
                "conflicts",
                "platform_version",
                "default_config",
                "version_history",
                "readme",
            ),
        }
        for table, columns in retired_columns.items():
            if not has_table(table):
                continue
            for column in columns:
                if has_column(table, column):
                    issues.append(
                        f"旧列 {table}.{column} 仍存在（fresh schema 不应创建）"
                    )

        if has_table("agents") and not has_column("agents", "owner_tenant_id"):
            issues.append("agents 缺少 owner_tenant_id")

        if has_table("knowledge_bases") and not has_column(
            "knowledge_bases",
            "owner_tenant_id",
        ):
            issues.append("knowledge_bases 缺少 owner_tenant_id")

        if has_table("ai_api_keys") and not has_column(
            "ai_api_keys",
            "owner_tenant_id",
        ):
            issues.append("ai_api_keys 缺少 owner_tenant_id")

        if has_table("skills"):
            n = conn.execute(
                text("SELECT COUNT(*) FROM skills WHERE type = 'data_intelligence'")
            ).scalar_one()
            if int(n or 0) > 0:
                issues.append(
                    "旧 data_intelligence 技能仍存在（fresh schema 不应创建）"
                )

        if has_table("skill_packages"):
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM skill_packages "
                    "WHERE name IN ('系统数据智能技能包', '平台数据管理')"
                )
            ).scalar_one()
            if int(n or 0) > 0:
                issues.append("旧数据智能技能包仍存在（fresh schema 不应创建）")

        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        if not rows:
            issues.append("alembic_version 为空（迁移可能未写入版本）")
        else:
            print(f"[verify] alembic_version rows: {len(rows)} (multi-head OK)")

    eng.dispose()
    return issues


def main() -> None:
    p = argparse.ArgumentParser(
        description="Fresh DB alembic upgrade heads + optional verify"
    )
    p.add_argument(
        "--database", default=os.environ.get("DATABASE_NAME", "test"), help="目标库名"
    )
    p.add_argument("--host", default=os.environ.get("DATABASE_HOST", "localhost"))
    p.add_argument(
        "--port", type=int, default=int(os.environ.get("DATABASE_PORT", "5432"))
    )
    p.add_argument("--user", default=os.environ.get("DATABASE_USER", "postgres"))
    p.add_argument(
        "--password", default=os.environ.get("DATABASE_PASSWORD", "postgres")
    )
    p.add_argument(
        "--no-verify", action="store_true", help="跳过迁移后 schema 抽样检查"
    )
    p.add_argument(
        "--yes-i-know",
        action="store_true",
        help="若目标库已有 alembic 版本记录仍强制执行（默认会拒绝以免误伤）",
    )
    args = p.parse_args()

    url = _build_sync_url(
        args.host,
        args.port,
        args.user,
        args.password,
        args.database,
    )

    if not args.yes_i_know:
        from sqlalchemy import create_engine, text

        try:
            eng = create_engine(url, echo=False)
            with eng.connect() as conn:
                if conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name='alembic_version'"
                    )
                ).fetchone():
                    n = conn.execute(
                        text("SELECT COUNT(*) FROM alembic_version")
                    ).scalar_one()
                    if int(n or 0) > 0:
                        print(
                            "[abort] 目标库已有 alembic_version 记录；"
                            "若确认要在此库上继续升级，请加 --yes-i-know",
                        )
                        raise SystemExit(2)
            eng.dispose()
        except Exception as e:
            print(f"[warn] 预检连接/alembic_version 时: {e}")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["DATABASE_HOST"] = args.host
    env["DATABASE_PORT"] = str(args.port)
    env["DATABASE_USER"] = args.user
    env["DATABASE_PASSWORD"] = args.password
    env["DATABASE_NAME"] = args.database

    _run_alembic_heads(env)
    print("[migrate] OK: alembic upgrade heads completed")

    if args.no_verify:
        return

    issues = _verify_schema(url)
    if issues:
        print("[verify] FAILED:")
        for i in issues:
            print("  -", i)
        raise SystemExit(1)
    print("[verify] OK: 抽样检查通过")


if __name__ == "__main__":
    main()

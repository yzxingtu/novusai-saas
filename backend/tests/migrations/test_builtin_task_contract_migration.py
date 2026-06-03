"""Test type: structural
Scope: built-in periodic task contract canonicalization migration.
Mock strategy: no mocks; static inspection, pure helpers, and in-memory table updates.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260508_0034_task_contract.py"
)
FOLLOWUP_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260508_0036_task_contract.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_builtin_task_contract_migration_module",
        MIGRATION,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_followup_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_builtin_task_contract_followup_migration_module",
        FOLLOWUP_MIGRATION,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_contract_tables(conn):
    metadata = sa.MetaData()
    task_definitions = sa.Table(
        "task_definitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(255), nullable=False),
        sa.Column("handler_path", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("default_kwargs", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    task_bindings = sa.Table(
        "tenant_task_bindings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_definition_id", sa.Integer, nullable=False),
        sa.Column("kwargs_override", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    metadata.create_all(conn)
    return task_definitions, task_bindings


def test_task_contract_migration_targets_retired_task_log_handler() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260508_0034_task_contract"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260508_0033_retire_search"'
        in source
    )
    assert "app.tasks.scheduled.clean_expired_task_logs" in source
    assert "app.tasks.scheduled.clean_expired_task_runs" in source
    assert "task.clean_expired_task_logs.81d841c7" in source
    assert "task.clean_expired_task_runs.81d841c7" in source


def test_task_contract_migration_canonicalizes_recycle_kwargs() -> None:
    module = _load_migration_module()

    assert module._canonical_recycle_kwargs({"retention_days": 15}) == {
        "module_retention_days": 15,
        "global_retention_days": 15,
    }
    assert module._canonical_recycle_kwargs(
        {"module_retention_days": 20, "global_retention_days": 40}
    ) == {
        "module_retention_days": 20,
        "global_retention_days": 40,
    }
    assert module._canonical_recycle_kwargs(None) == {
        "module_retention_days": 30,
        "global_retention_days": 30,
    }


def test_task_contract_migration_canonicalizes_notification_cleanup_kwargs() -> None:
    module = _load_migration_module()

    assert module._canonical_notification_cleanup_kwargs({"retention_days": 90}) == {}
    assert module.NOTIFICATION_CLEANUP_HANDLER == (
        "app.tasks.notification_cleanup.cleanup_expired_notifications"
    )


def test_task_contract_migration_updates_existing_rows_to_canonical_kwargs() -> None:
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        task_definitions, task_bindings = _create_contract_tables(conn)
        conn.execute(
            task_definitions.insert(),
            [
                {
                    "id": 1,
                    "code": module.OLD_TASK_RUNS_CODE,
                    "handler_path": module.OLD_TASK_RUNS_HANDLER,
                    "name": "old",
                    "description": "old",
                    "default_kwargs": {"retention_days": 30},
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 2,
                    "code": module.RECYCLE_BIN_CODE,
                    "handler_path": module.RECYCLE_BIN_HANDLER,
                    "name": "recycle",
                    "description": "recycle",
                    "default_kwargs": {"retention_days": 15},
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 3,
                    "code": module.NOTIFICATION_CLEANUP_CODE,
                    "handler_path": module.NOTIFICATION_CLEANUP_HANDLER,
                    "name": "notification",
                    "description": "notification",
                    "default_kwargs": {"retention_days": 90},
                    "is_enabled": True,
                    "is_deleted": False,
                },
            ],
        )
        conn.execute(
            task_bindings.insert(),
            [
                {
                    "id": 10,
                    "task_definition_id": 2,
                    "kwargs_override": {"retention_days": 7},
                },
                {
                    "id": 11,
                    "task_definition_id": 3,
                    "kwargs_override": {"retention_days": 90},
                },
            ],
        )

        module._canonicalize_task_run_cleanup_definition(conn)
        module._canonicalize_recycle_bin_kwargs(conn)
        module._canonicalize_notification_cleanup_kwargs(conn)

        definitions = {
            row["id"]: row
            for row in conn.execute(sa.select(task_definitions)).mappings().all()
        }
        bindings = {
            row["id"]: row
            for row in conn.execute(sa.select(task_bindings)).mappings().all()
        }

    assert definitions[1]["code"] == module.TASK_RUNS_CODE
    assert definitions[1]["handler_path"] == module.TASK_RUNS_HANDLER
    assert definitions[1]["default_kwargs"] == {}
    assert definitions[2]["default_kwargs"] == {
        "module_retention_days": 15,
        "global_retention_days": 15,
    }
    assert bindings[10]["kwargs_override"] == {
        "module_retention_days": 7,
        "global_retention_days": 7,
    }
    assert definitions[3]["default_kwargs"] == {}
    assert bindings[11]["kwargs_override"] == {}


def test_task_contract_migration_retires_old_task_log_rows_when_canonical_exists() -> (
    None
):
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        task_definitions, _task_bindings = _create_contract_tables(conn)
        conn.execute(
            task_definitions.insert(),
            [
                {
                    "id": 1,
                    "code": module.TASK_RUNS_CODE,
                    "handler_path": module.TASK_RUNS_HANDLER,
                    "default_kwargs": {},
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 2,
                    "code": module.OLD_TASK_RUNS_CODE,
                    "handler_path": module.OLD_TASK_RUNS_HANDLER,
                    "default_kwargs": {"retention_days": 30},
                    "is_enabled": True,
                    "is_deleted": False,
                },
            ],
        )

        module._canonicalize_task_run_cleanup_definition(conn)

        definitions = {
            row["id"]: row
            for row in conn.execute(sa.select(task_definitions)).mappings().all()
        }

    assert definitions[1]["code"] == module.TASK_RUNS_CODE
    assert definitions[1]["handler_path"] == module.TASK_RUNS_HANDLER
    assert definitions[1]["is_enabled"] is True
    assert definitions[1]["is_deleted"] is False
    assert definitions[2]["is_enabled"] is False
    assert definitions[2]["is_deleted"] is True


def test_task_contract_followup_migration_updates_already_stamped_databases() -> None:
    module = _load_followup_migration_module()
    source = FOLLOWUP_MIGRATION.read_text(encoding="utf-8")
    engine = sa.create_engine("sqlite:///:memory:")

    assert 'revision: str = "20260508_0036_task_contract"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260508_0035_ai_proto_cfg"'
        in source
    )

    with engine.begin() as conn:
        task_definitions, task_bindings = _create_contract_tables(conn)
        conn.execute(
            task_definitions.insert(),
            [
                {
                    "id": 1,
                    "code": module.RECYCLE_BIN_CODE,
                    "handler_path": module.RECYCLE_BIN_HANDLER,
                    "default_kwargs": {"retention_days": 21},
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 2,
                    "code": module.NOTIFICATION_CLEANUP_CODE,
                    "handler_path": module.NOTIFICATION_CLEANUP_HANDLER,
                    "default_kwargs": {"retention_days": 90},
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 3,
                    "code": module.OLD_TASK_RUNS_CODE,
                    "handler_path": module.OLD_TASK_RUNS_HANDLER,
                    "default_kwargs": {"retention_days": 30},
                    "is_enabled": True,
                    "is_deleted": False,
                },
            ],
        )
        conn.execute(
            task_bindings.insert(),
            [
                {
                    "id": 10,
                    "task_definition_id": 1,
                    "kwargs_override": {"retention_days": 9},
                },
                {
                    "id": 11,
                    "task_definition_id": 2,
                    "kwargs_override": {"retention_days": 90},
                },
            ],
        )

        module._canonicalize_task_run_cleanup_definition(conn)
        module._canonicalize_recycle_bin_kwargs(conn)
        module._canonicalize_notification_cleanup_kwargs(conn)

        definitions = {
            row["id"]: row
            for row in conn.execute(sa.select(task_definitions)).mappings().all()
        }
        bindings = {
            row["id"]: row
            for row in conn.execute(sa.select(task_bindings)).mappings().all()
        }

    assert definitions[1]["default_kwargs"] == {
        "module_retention_days": 21,
        "global_retention_days": 21,
    }
    assert definitions[2]["default_kwargs"] == {}
    assert definitions[3]["code"] == module.TASK_RUNS_CODE
    assert definitions[3]["handler_path"] == module.TASK_RUNS_HANDLER
    assert definitions[3]["default_kwargs"] == {}
    assert bindings[10]["kwargs_override"] == {
        "module_retention_days": 9,
        "global_retention_days": 9,
    }
    assert bindings[11]["kwargs_override"] == {}

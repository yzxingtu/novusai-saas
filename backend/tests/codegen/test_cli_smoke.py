"""
CLI 冒烟测试 / CLI smoke tests.

验证 novusai CLI 可导入、codegen 子命令可用
"""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from app.exceptions import ConflictException, NotFoundException


def _raise_system_exit_not_found(coro) -> None:
    coro.close()
    raise SystemExit("Config not found")


def _return_value(value):
    def _inner(coro):
        coro.close()
        return value

    return _inner


def _raise_exception(exc):
    def _inner(coro):
        coro.close()
        raise exc

    return _inner


def _return_none(coro):
    import logging
    import sys

    coro.close()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
    logging.getLogger("cli-smoke").info("cli-json-noise")
    return None


def _fake_generate_output() -> SimpleNamespace:
    return SimpleNamespace(
        result=SimpleNamespace(
            success=True,
            files_created=["backend/app/models/system/demo.py"],
            files_modified=[
                "frontend/apps/web-antd/src/views/admin/system/demo/index.vue"
            ],
            errors=[],
        ),
        config_id=None,
        resource="demo",
    )


def _return_fake_generate_output(coro):
    import logging
    import sys

    coro.close()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
    logging.getLogger("cli-smoke").info("cli-generate-noise")
    return _fake_generate_output()


def _parse_output_json(result) -> dict:
    return json.loads(result.output)


def test_codegen_delete_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen delete 缺失配置时返回 JSON 错误而不是 traceback."""
    from app.cli import cli

    runner = CliRunner()

    def _raise_not_found(coro):
        coro.close()
        raise NotFoundException(message="Config not found")

    monkeypatch.setattr("app.cli._run_async", _raise_not_found)

    result = runner.invoke(
        cli, ["codegen", "delete", "--id", "999999", "--yes", "--json"]
    )

    assert result.exit_code == 1
    assert '"success": false' in result.output.lower()
    assert "Config not found" in result.output
    assert "Traceback" not in result.output
    assert "cli-json-noise" not in result.output


def test_codegen_duplicate_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen duplicate 缺失配置时返回 JSON 错误而不是 traceback."""
    from app.cli import cli

    runner = CliRunner()

    def _raise_not_found(coro):
        coro.close()
        raise NotFoundException(message="Config not found")

    monkeypatch.setattr("app.cli._run_async", _raise_not_found)

    result = runner.invoke(cli, ["codegen", "duplicate", "--id", "999999", "--json"])

    assert result.exit_code == 1
    assert '"success": false' in result.output.lower()
    assert "Config not found" in result.output
    assert "Traceback" not in result.output


def test_codegen_show_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen show 缺失配置时返回 JSON 错误而不是纯文本."""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr("app.cli._run_async", _return_none)

    result = runner.invoke(cli, ["codegen", "show", "--id", "999999", "--json"])

    assert result.exit_code == 1
    assert '"success": false' in result.output.lower()
    assert "Config not found" in result.output
    assert "Traceback" not in result.output


def test_codegen_preview_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen preview 缺失配置时返回 JSON 错误而不是 traceback."""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr("app.cli._run_async", _raise_system_exit_not_found)

    result = runner.invoke(cli, ["codegen", "preview", "--id", "999999", "--json"])

    assert result.exit_code == 1
    assert '"success": false' in result.output.lower()
    assert "Config not found" in result.output
    assert "Traceback" not in result.output


def test_codegen_generate_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen generate 缺失配置时返回 JSON 错误而不是 traceback."""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr("app.cli._run_async", _raise_system_exit_not_found)

    result = runner.invoke(cli, ["codegen", "generate", "--id", "999999", "--json"])

    assert result.exit_code == 1
    assert '"success": false' in result.output.lower()
    assert "Config not found" in result.output
    assert "Traceback" not in result.output


def test_codegen_generate_success_with_auto_migrate_returns_single_json(
    monkeypatch,
) -> None:
    """codegen generate --json 成功且 auto-migrate 成功时只输出单个 JSON 对象."""
    from app.cli import cli

    runner = CliRunner()

    def _run_auto_migrate(*_args, **_kwargs):
        import logging
        import sys

        logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
        logging.getLogger("cli-smoke").info("cli-auto-migrate-noise")
        return {
            "success": True,
            "message": "Migration generated and applied for demo",
            "migration_path": None,
        }

    monkeypatch.setattr("app.cli._load_config_stdin", lambda: {"resource": "demo"})
    monkeypatch.setattr("app.cli._run_async", _return_fake_generate_output)
    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService.run_auto_migrate",
        staticmethod(_run_auto_migrate),
    )

    result = runner.invoke(cli, ["codegen", "generate", "--stdin", "--json"])

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["auto_migrate"]["success"] is True
    assert payload["data"]["resource"] == "demo"
    assert "cli-generate-noise" not in result.output
    assert "cli-auto-migrate-noise" not in result.output
    assert "[auto-migrate]" not in result.output


def test_codegen_generate_auto_migrate_failure_returns_single_json(
    monkeypatch,
) -> None:
    """codegen generate --json 在 auto-migrate 失败时只输出 JSON 错误对象."""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr("app.cli._load_config_stdin", lambda: {"resource": "demo"})
    monkeypatch.setattr("app.cli._run_async", _return_fake_generate_output)
    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService.run_auto_migrate",
        staticmethod(
            lambda *_args, **_kwargs: {
                "success": False,
                "phase": "post_upgrade",
                "error": "migration failed",
            }
        ),
    )

    result = runner.invoke(cli, ["codegen", "generate", "--stdin", "--json"])

    assert result.exit_code == 1
    payload = _parse_output_json(result)
    assert payload["success"] is False
    assert payload["data"]["auto_migrate"]["phase"] == "post_upgrade"
    assert "migration failed" in payload["error"]["message"]
    assert "[auto-migrate]" not in result.output


def test_codegen_validate_draft_returns_enveloped_json(monkeypatch) -> None:
    """codegen validate --mode draft 返回统一 envelope，且 mode 透传到 service。"""
    from app.cli import cli

    runner = CliRunner()

    class _FakeService:
        def validate(self, config_json, *, mode):
            assert config_json == {"resource": "demo"}
            assert mode == "draft"
            return {"valid": True, "errors": [], "warnings": [], "mode": mode}

    monkeypatch.setattr("app.cli._load_config_stdin", lambda: {"resource": "demo"})
    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService.create_standalone",
        staticmethod(lambda: _FakeService()),
    )

    result = runner.invoke(
        cli, ["codegen", "validate", "--stdin", "--mode", "draft", "--json"]
    )

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload == {
        "success": True,
        "data": {"valid": True, "errors": [], "warnings": [], "mode": "draft"},
        "error": None,
    }


def test_codegen_preview_stdin_returns_enveloped_json(monkeypatch) -> None:
    """codegen preview --stdin 使用统一 envelope 返回数据。"""
    from app.cli import cli

    runner = CliRunner()

    class _FakeService:
        def preview(self, config_json, *, step=None, project_root=None):
            assert config_json == {"resource": "demo"}
            assert step is None
            assert project_root is not None
            return {
                "success": True,
                "files": [
                    {
                        "path": "backend/app/models/system/demo.py",
                        "type": "create",
                        "line_count": 12,
                    }
                ],
                "summary": {
                    "create_count": 1,
                    "modify_count": 0,
                    "backend_files": 1,
                    "frontend_files": 0,
                    "total_lines": 12,
                },
                "warnings": [],
                "conflicts": [],
                "error": None,
            }

    monkeypatch.setattr("app.cli._load_config_stdin", lambda: {"resource": "demo"})
    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService.create_standalone",
        staticmethod(lambda: _FakeService()),
    )

    result = runner.invoke(cli, ["codegen", "preview", "--stdin", "--json"])

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["summary"]["create_count"] == 1
    assert payload["data"]["files"][0]["path"] == "backend/app/models/system/demo.py"


def test_codegen_show_by_resource_returns_enveloped_json(monkeypatch) -> None:
    """codegen show --resource 使用统一 envelope 返回配置详情。"""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(
            {
                "id": 8,
                "name": "Demo",
                "resource": "demo",
                "module": "system",
                "status": "draft",
                "config_json": {"resource": "demo"},
            }
        ),
    )

    result = runner.invoke(cli, ["codegen", "show", "--resource", "demo", "--json"])

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["resource"] == "demo"
    assert payload["data"]["id"] == 8


def test_codegen_delete_blocked_returns_reason_code_and_clean_json(monkeypatch) -> None:
    """codegen delete 被 delete guard 阻断时返回结构化 JSON。"""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr(
        "app.cli._run_async",
        _raise_exception(
            ConflictException(
                message="Manifest entry still exists",
                data={"reason_code": "manifest_present"},
            )
        ),
    )

    result = runner.invoke(cli, ["codegen", "delete", "--id", "9", "--yes", "--json"])

    assert result.exit_code == 1
    payload = _parse_output_json(result)
    assert payload["success"] is False
    assert payload["error"]["code"] == "delete_blocked"
    assert payload["data"]["reason_code"] == "manifest_present"
    assert "Traceback" not in result.output


def test_codegen_presets_list_returns_enveloped_json(monkeypatch) -> None:
    """codegen presets list --json 返回结构化预设列表。"""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr(
        "app.codegen.preset_loader.list_presets",
        lambda: [
            {
                "name": "simple",
                "label_zh": "基础 CRUD",
                "label_en": "Basic CRUD",
                "category": "crud",
                "tags": ["basic"],
            }
        ],
    )

    result = runner.invoke(cli, ["codegen", "presets", "list", "--json"])

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["items"][0]["name"] == "simple"


def test_codegen_presets_show_returns_enveloped_json(monkeypatch) -> None:
    """codegen presets show --json 返回结构化预设详情。"""
    from app.cli import cli

    runner = CliRunner()

    monkeypatch.setattr(
        "app.codegen.preset_loader.get_preset",
        lambda name: {
            "name": name,
            "label_zh": "基础 CRUD",
            "label_en": "Basic CRUD",
            "content": "resource: demo\n",
            "parsed": {"resource": "demo"},
        },
    )

    result = runner.invoke(
        cli, ["codegen", "presets", "show", "--name", "simple", "--json"]
    )

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["parsed"]["resource"] == "demo"


def test_codegen_db_tables_json_uses_envelope(monkeypatch) -> None:
    """codegen db tables --json 使用统一 envelope。"""
    from app.cli import cli

    runner = CliRunner()

    class _FakeService:
        def introspect_tables(self):
            return [{"name": "demo", "has_model": True}]

    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService.create_standalone",
        staticmethod(lambda: _FakeService()),
    )

    result = runner.invoke(cli, ["codegen", "db", "tables", "--json"])

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert payload["data"]["items"][0]["name"] == "demo"


def test_codegen_rollback_no_auto_migrate_returns_partial_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """rollback --no-auto-migrate 不应误报成功，manifest 也必须保留."""
    from app.cli import cli

    runner = CliRunner()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "codegen_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "resource": "demo",
                        "module": "system",
                        "generated_at": "2026-03-23T00:00:00Z",
                        "config_id": 8,
                        "config_hash": "abc",
                        "files": [],
                    }
                ],
                "version": 1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.cli._BACKEND_DIR", backend_dir)
    monkeypatch.setattr("app.cli._CODEGEN_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        "app.codegen.rollback.CodegenRollback.rollback",
        lambda self, **kwargs: SimpleNamespace(
            success=True,
            files_deleted=["backend/app/models/system/demo.py"],
            files_modified=[],
            files_skipped=[],
            manual_steps=[],
            errors=[],
        ),
    )
    monkeypatch.setattr("app.cli._run_async", lambda coro: coro.close())

    result = runner.invoke(
        cli,
        [
            "codegen",
            "rollback",
            "--resource",
            "demo",
            "--no-auto-migrate",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _parse_output_json(result)
    assert payload["success"] is False
    assert payload["migration_cleaned"] is False
    assert payload["pending_migration_cleanup"] is True
    assert payload["files_deleted"] == ["backend/app/models/system/demo.py"]
    assert any(
        "cleanup" in error.lower() or "清理" in error for error in payload["errors"]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["entries"][0]["resource"] == "demo"


def test_codegen_download_by_id_uses_service_download(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """codegen download --id 应下载 manifest 对应快照，而不是走 preview_zip."""
    from app.cli import cli

    runner = CliRunner()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "demo.zip"
    calls: dict[str, object] = {}

    class _DummyDbContext:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeService:
        def __init__(self, db):
            self.db = db

        async def get_by_id(self, config_id: int):
            return SimpleNamespace(
                id=config_id, resource="demo", config_json={"resource": "demo"}
            )

        async def get_by_resource(self, resource: str):
            return SimpleNamespace(
                id=8, resource=resource, config_json={"resource": resource}
            )

        async def download(self, config_id: int, project_root: Path | None = None):
            calls["config_id"] = config_id
            calls["project_root"] = project_root
            return b"zip-bytes"

        @staticmethod
        def create_standalone():
            raise AssertionError(
                "create_standalone should not be used for --id download"
            )

    monkeypatch.setattr("app.cli._BACKEND_DIR", backend_dir)
    monkeypatch.setattr("app.cli._CODEGEN_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.core.database.get_db_context", lambda: _DummyDbContext())
    monkeypatch.setattr(
        "app.services.system.codegen_service.CodegenService", _FakeService
    )

    result = runner.invoke(
        cli,
        ["codegen", "download", "--id", "8", "--output", str(output_path), "--json"],
    )

    assert result.exit_code == 0
    payload = _parse_output_json(result)
    assert payload["success"] is True
    assert output_path.read_bytes() == b"zip-bytes"
    assert calls == {"config_id": 8, "project_root": tmp_path}


def test_cli_imports() -> None:
    """CLI 模块可导入."""
    from app.cli import cli

    assert cli is not None


def test_codegen_help() -> None:
    """novusai codegen --help 可执行."""
    backend = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "codegen", "--help"],
        cwd=str(backend),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "generate" in result.stdout
    assert "rollback" in result.stdout
    assert "preview" in result.stdout


def test_codegen_generate_help() -> None:
    """novusai codegen generate --help 显示 --auto-migrate 等."""
    backend = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "codegen", "generate", "--help"],
        cwd=str(backend),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "auto-migrate" in result.stdout or "auto_migrate" in result.stdout.lower()
    assert "config" in result.stdout or "--config" in result.stdout


def test_db_merge_help() -> None:
    """novusai db merge --help 显示 revisions 选项."""
    backend = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "db", "merge", "--help"],
        cwd=str(backend),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "revisions" in result.stdout or "heads" in result.stdout.lower()

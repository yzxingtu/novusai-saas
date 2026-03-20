"""
CLI 冒烟测试 / CLI smoke tests.

验证 novusai CLI 可导入、codegen 子命令可用
"""

import subprocess
import sys
import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from app.exceptions import NotFoundException


def _raise_system_exit_not_found(coro) -> None:
    coro.close()
    raise SystemExit("Config not found")


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
            files_modified=["frontend/apps/web-antd/src/views/admin/system/demo/index.vue"],
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


def test_codegen_delete_not_found_returns_clean_json(monkeypatch) -> None:
    """codegen delete 缺失配置时返回 JSON 错误而不是 traceback."""
    from app.cli import cli

    runner = CliRunner()

    def _raise_not_found(coro):
        coro.close()
        raise NotFoundException(message="Config not found")

    monkeypatch.setattr("app.cli._run_async", _raise_not_found)

    result = runner.invoke(cli, ["codegen", "delete", "--id", "999999", "--yes", "--json"])

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
    payload = json.loads(result.output)
    assert payload["success"] is True
    assert payload["auto_migrate"]["success"] is True
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
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["auto_migrate"]["phase"] == "post_upgrade"
    assert "migration failed" in payload["error"]
    assert "[auto-migrate]" not in result.output


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

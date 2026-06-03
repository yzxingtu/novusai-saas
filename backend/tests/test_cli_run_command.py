"""中文: novusai run 命令契约测试。

EN: Contract tests for the novusai run command.

Test type: structural
"""

from __future__ import annotations

import subprocess

from click.testing import CliRunner


def _patch_uvicorn_run(monkeypatch, returncode: int) -> list[tuple[list[str], bool]]:
    from app.cli_commands import core_commands

    calls: list[tuple[list[str], bool]] = []

    def _fake_run(cmd: list[str], check: bool = False):
        calls.append((cmd, check))
        return subprocess.CompletedProcess(cmd, returncode)

    monkeypatch.setattr(core_commands.os, "chdir", lambda _path: None)
    monkeypatch.setattr(core_commands, "_get_venv_python", lambda: "python")
    monkeypatch.setattr(core_commands.subprocess, "run", _fake_run)
    return calls


def test_run_treats_windows_reloader_termination_as_clean(monkeypatch) -> None:
    """中文: Windows reload 子进程被外部停止时，CLI 不应打印 Python traceback。

    EN: When the Windows reload subprocess is stopped externally, the CLI should
    not print a Python traceback.
    """
    from app.cli import cli

    calls = _patch_uvicorn_run(monkeypatch, 0xFFFFFFFF)

    result = CliRunner().invoke(cli, ["run", "--no-reload"])

    assert result.exit_code == 0
    assert "Traceback" not in result.output
    assert calls
    assert calls[0][1] is False
    assert calls[0][0][:3] == ["python", "-m", "uvicorn"]


def test_run_reports_uvicorn_startup_failure_without_traceback(monkeypatch) -> None:
    """中文: 真实启动失败保留失败退出，但提示应是运维可读的一行错误。

    EN: Real startup failures keep a failed exit while reporting an
    operator-readable one-line error.
    """
    from app.cli import cli

    _patch_uvicorn_run(monkeypatch, 1)

    result = CliRunner().invoke(cli, ["run", "--no-reload"])

    assert result.exit_code == 1
    assert "Uvicorn exited with status 1" in result.output
    assert "Traceback" not in result.output

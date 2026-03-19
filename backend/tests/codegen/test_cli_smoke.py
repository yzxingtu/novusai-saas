"""
CLI 冒烟测试 / CLI smoke tests.

验证 novusai CLI 可导入、codegen 子命令可用
"""

import subprocess
import sys
from pathlib import Path


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

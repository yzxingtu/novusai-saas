"""中文: CLI 运行时路径解析契约测试。

EN: Contract tests for CLI runtime path resolution.

Test type: structural
"""

from __future__ import annotations

from pathlib import Path

from app.cli_commands import state


def _make_backend_root(path: Path) -> Path:
    (path / "app").mkdir(parents=True)
    (path / "migrations").mkdir()
    (path / "alembic.ini").write_text(
        "[alembic]\nscript_location = migrations\n",
        encoding="utf-8",
    )
    return path


def test_resolve_backend_dir_prefers_runtime_cwd_for_installed_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """中文: 容器内 console script 位于 site-packages，但工作目录才是迁移根。

    EN: In containers the console script lives in site-packages while cwd is the
    migration root.
    """
    monkeypatch.delenv("NOVUSAI_BACKEND_DIR", raising=False)
    runtime_root = _make_backend_root(tmp_path / "app-runtime")
    package_root = tmp_path / "site-packages"
    package_root.mkdir()

    assert (
        state._resolve_backend_dir(
            package_backend_dir=package_root,
            cwd=runtime_root,
        )
        == runtime_root
    )


def test_resolve_backend_dir_allows_explicit_env_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """中文: 运维可显式覆盖后端根目录，避免入口点位置影响迁移配置。

    EN: Operators can explicitly override the backend root so entrypoint
    location does not affect migration configuration.
    """
    runtime_root = _make_backend_root(tmp_path / "configured-runtime")
    package_root = tmp_path / "site-packages"
    package_root.mkdir()
    monkeypatch.setenv("NOVUSAI_BACKEND_DIR", str(runtime_root))

    assert (
        state._resolve_backend_dir(
            package_backend_dir=package_root,
            cwd=tmp_path / "not-a-backend",
        )
        == runtime_root
    )

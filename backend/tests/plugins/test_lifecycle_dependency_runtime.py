"""中文: 插件依赖运行时契约测试。

EN: Plugin dependency runtime contract tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import app.plugins.lifecycle_dependency_runtime as dependency_runtime
from app.plugins.lifecycle_dependency_runtime import LifecycleDependencyRuntimeMixin


class _FakeDistribution:
    version = "1.0"

    def read_text(self, filename: str) -> str:
        if filename == "METADATA":
            return "Metadata-Version: 2.1\nName: foo-bar\n"
        if filename == "top_level.txt":
            return ""
        return ""


class _DependencyHarness(LifecycleDependencyRuntimeMixin):
    def __init__(self) -> None:
        self._db = AsyncMock()

    def _load_project_pyproject_requirements(self) -> list[str]:
        return []

    async def _load_other_plugin_python_requirements(
        self,
        *,
        exclude_plugin_name: str | None = None,
    ) -> dict[str, list[str]]:
        _ = exclude_plugin_name
        return {}

    def _resolve_pip_python_executable(self) -> str:
        return "python"

    def _build_python_install_env(self, plugin_name: str) -> dict[str, str]:
        _ = plugin_name
        return {}


@pytest.mark.asyncio
async def test_install_python_deps_does_not_guess_import_name_from_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: Test type: behavioral. 无 wheel 元数据时不得把 foo-bar 猜成 foo_bar 后强制重装。

    EN: Test type: behavioral. Without wheel metadata, foo-bar must not be guessed as
    foo_bar and forced into reinstall.
    """
    pip_calls: list[tuple[object, ...]] = []

    async def _fake_subprocess(*args, **_kwargs):
        pip_calls.append(args)
        raise AssertionError("pip install should not run for a satisfied package")

    monkeypatch.setattr(
        "importlib.metadata.distribution", lambda _name: _FakeDistribution()
    )
    monkeypatch.setattr(dependency_runtime, "run_subprocess_async", _fake_subprocess)

    installed = await _DependencyHarness()._install_python_deps(
        "demo-plugin",
        ["foo-bar==1.0"],
    )

    assert installed == []
    assert pip_calls == []

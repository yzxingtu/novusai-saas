"""Plugin dependency runtime model regression tests. / 插件依赖运行时模型回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.i18n import get_locale, set_locale
from app.plugins.dependencies import (
    PluginDependencyRequirement,
    build_plugin_dependency_states,
    plugin_dependency_is_version_satisfied,
)
from app.plugins.exceptions import PluginDependencyError
from app.plugins.lifecycle import PluginLifecycle
from app.services.system.plugin_service import PluginService


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def test_plugin_dependency_is_version_satisfied_handles_happy_path() -> None:
    assert plugin_dependency_is_version_satisfied("*", "1.0.0") is True
    assert plugin_dependency_is_version_satisfied(">=1.0.0", "1.5.0") is True
    assert plugin_dependency_is_version_satisfied(">=1.0.0,<2.0.0", "2.1.0") is False


def test_build_plugin_dependency_states_reports_ready_when_satisfied() -> None:
    original_locale = get_locale()
    set_locale("zh_CN")
    try:
        states = build_plugin_dependency_states(
            [
                PluginDependencyRequirement(
                    plugin="base-plugin",
                    version=">=1.0.0",
                )
            ],
            {
                "base-plugin": {
                    "name": "base-plugin",
                    "version": "1.5.0",
                    "status": "enabled",
                }
            },
            require_enabled=True,
        )
    finally:
        set_locale(original_locale)

    assert len(states) == 1
    assert states[0].state == "ready"
    assert states[0].message == "插件依赖 base-plugin 当前版本 1.5.0 满足 >=1.0.0"


@pytest.mark.asyncio
async def test_collect_plugin_dependency_states_reports_disabled_and_version_mismatch() -> (
    None
):
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_RowsResult(
            [
                ("base-plugin", "1.5.0", "disabled"),
            ]
        )
    )

    lifecycle = PluginLifecycle(db)
    manifest = {
        "dependencies": {
            "plugins": [
                {"plugin": "base-plugin", "version": ">=2.0.0"},
            ]
        }
    }

    states = await lifecycle._collect_plugin_dependency_states(
        manifest,
        require_enabled=True,
    )

    assert len(states) == 1
    assert states[0]["plugin"] == "base-plugin"
    assert states[0]["state"] == "disabled"
    assert states[0]["installed_version"] == "1.5.0"


@pytest.mark.asyncio
async def test_get_dependents_uses_versioned_plugin_dependencies_for_uninstall() -> (
    None
):
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_RowsResult(
            [
                (
                    2,
                    "child-plugin",
                    "1.1.0",
                    "disabled",
                    {
                        "dependencies": {
                            "plugins": [
                                {
                                    "plugin": "base-plugin",
                                    "version": ">=1.0.0,<2.0.0",
                                }
                            ]
                        }
                    },
                ),
            ]
        )
    )

    lifecycle = PluginLifecycle(db)
    dependents = await lifecycle._get_dependents("base-plugin")

    assert dependents == [
        {
            "plugin_id": 2,
            "plugin": "child-plugin",
            "version": "1.1.0",
            "status": "disabled",
            "required_version": ">=1.0.0,<2.0.0",
            "source": "dependencies.plugins",
        }
    ]


@pytest.mark.asyncio
async def test_python_dependency_preflight_rejects_shared_env_exact_pin_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = PluginLifecycle(AsyncMock())

    monkeypatch.setattr(
        lifecycle,
        "_load_project_pyproject_requirements",
        lambda: ["shared-lib==1.0.0"],
    )
    monkeypatch.setattr(
        lifecycle,
        "_load_other_plugin_python_requirements",
        AsyncMock(
            return_value={"existing-plugin": ["shared-lib==1.0.0"]},
        ),
    )
    monkeypatch.setattr(
        "app.plugins.lifecycle.get_installed_distribution_version",
        lambda _package: "1.0.0",
    )

    with pytest.raises(PluginDependencyError, match="shared-lib"):
        await lifecycle._ensure_python_dependency_preflight(
            "new-plugin",
            ["shared-lib==2.0.0"],
        )


@pytest.mark.asyncio
async def test_dependency_status_returns_real_python_and_plugin_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = SimpleNamespace(
        manifest={
            "dependencies": {
                "python": ["missing-lib>=1.0.0"],
                "plugins": [
                    {"plugin": "base-plugin", "version": ">=2.0.0"},
                ],
            }
        }
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_RowsResult(
            [
                ("base-plugin", "1.5.0", "disabled"),
            ]
        )
    )

    service = PluginService(db)
    monkeypatch.setattr(
        "app.plugins.dependencies.get_installed_distribution_version",
        lambda _package: None,
    )

    status = await service.get_dependency_status(plugin)

    assert status["overall"] == "missing"
    assert "npm" not in status
    assert status["python"]["state"] == "missing"
    assert status["plugins"]["state"] == "missing"
    assert status["plugins"]["details"][0]["state"] == "disabled"

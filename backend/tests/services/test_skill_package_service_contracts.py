"""Test type: behavioral
Scope: skill package service catalog preview and owner-contract updates.
Real dependencies: service methods and resolved-tools payload shaping.
Mocked dependencies: repository and SkillResolver at service boundary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.skills.resolver import SkillResolveIssue, SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.services.ai.skill_package_service import (
    AdminSkillPackageService,
    _build_resolved_tools_payload,
)


@pytest.mark.asyncio
async def test_resolved_tools_payload_marks_catalog_resolution_unavailable(
    monkeypatch,
) -> None:
    issue = SkillResolveIssue(
        code="plugin_resolver_missing",
        message="Plugin resolver missing",
        skill_id=51,
        skill_name="实时天气查询",
        source_plugin="weather-widget",
    )

    class _Resolver:
        def __init__(self, db) -> None:
            self.db = db

        async def resolve(self, _skills) -> SkillResolveResult:
            return SkillResolveResult(
                tools=[],
                warnings=["Plugin resolver missing"],
                resolution_issues=[issue],
            )

    monkeypatch.setattr("app.ai.skills.resolver.SkillResolver", _Resolver)
    pkg = SimpleNamespace(id=103, name="Weather Widget", source_plugin="weather-widget")

    payload = await _build_resolved_tools_payload(db=object(), pkg=pkg, skills=[])

    assert payload["preview_mode"] == "catalog_resolution"
    assert payload["runtime_truth"] is False
    assert payload["resolution_status"] == "unavailable"
    assert payload["resolution_issue_count"] == 1
    assert payload["resolution_issues"][0]["code"] == "plugin_resolver_missing"
    assert payload["tool_count"] == 0
    assert payload["tools"] == []


@pytest.mark.asyncio
async def test_resolved_tools_payload_marks_catalog_resolution_degraded(
    monkeypatch,
) -> None:
    issue = SkillResolveIssue(
        code="plugin_resolver_returned_no_tools",
        message="One plugin skill returned no tools",
        skill_id=52,
        skill_name="Broken Skill",
        source_plugin="mixed-plugin",
    )

    class _Resolver:
        def __init__(self, db) -> None:
            self.db = db

        async def resolve(self, _skills) -> SkillResolveResult:
            return SkillResolveResult(
                tools=[
                    ToolDefinition(
                        name="usable_tool",
                        description="Usable tool",
                        source_skill_id=53,
                        source_skill_name="Usable Skill",
                        source_plugin="mixed-plugin",
                    )
                ],
                resolution_issues=[issue],
            )

    monkeypatch.setattr("app.ai.skills.resolver.SkillResolver", _Resolver)
    pkg = SimpleNamespace(id=104, name="Mixed Plugin", source_plugin="mixed-plugin")

    payload = await _build_resolved_tools_payload(db=object(), pkg=pkg, skills=[])

    assert payload["resolution_status"] == "degraded"
    assert payload["resolution_issue_count"] == 1
    assert payload["tool_count"] == 1
    assert payload["tools"][0]["name"] == "usable_tool"
    assert payload["tools"][0]["source_plugin"] == "mixed-plugin"


@pytest.mark.asyncio
async def test_resolved_tools_payload_reports_plugin_issue_when_package_relation_unloaded(
    monkeypatch,
) -> None:
    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    class _Rows:
        def __iter__(self):
            return iter([SimpleNamespace(id=103, source_plugin="weather-widget")])

    class _Db:
        async def execute(self, _stmt):
            return _Rows()

    pkg = SimpleNamespace(id=103, name="Weather Widget", source_plugin="weather-widget")
    skill = SimpleNamespace(
        id=51,
        name="实时天气查询",
        type="toolkit",
        package_id=103,
        key="weather-widget:weather-realtime",
        source_ref="weather-widget:weather-realtime",
        config={},
        toolkit_content=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    payload = await _build_resolved_tools_payload(db=_Db(), pkg=pkg, skills=[skill])

    assert payload["resolution_status"] == "unavailable"
    assert payload["resolution_issue_count"] == 1
    assert payload["resolution_issues"][0]["code"] == "plugin_resolver_missing"
    assert payload["resolution_issues"][0]["source_plugin"] == "weather-widget"
    assert payload["tool_count"] == 0


@pytest.mark.asyncio
async def test_admin_package_update_cascades_skill_tenant_to_platform() -> None:
    service = AdminSkillPackageService.__new__(AdminSkillPackageService)
    service.repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(id=7, tenant_id=42, is_system=False)
        ),
        cascade_update_skill_tenant_id=AsyncMock(),
    )

    await AdminSkillPackageService._before_update(service, 7, {"tenant_id": None})

    service.repo.cascade_update_skill_tenant_id.assert_awaited_once_with(7, None)


@pytest.mark.asyncio
async def test_admin_service_lists_recommended_packages_through_repository() -> None:
    service = AdminSkillPackageService.__new__(AdminSkillPackageService)
    packages = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    service.repo = SimpleNamespace(
        list_recommended_packages=AsyncMock(return_value=packages)
    )

    result = await service.list_recommended_packages()

    assert result == packages
    service.repo.list_recommended_packages.assert_awaited_once_with()

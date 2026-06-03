"""Test type: structural
Scope: skill-package export/import field governance for AI runtime skill contracts.
Real dependencies: shared skill-package IO helpers and ORM model constructors.
Mocked dependencies: repository lookup seams and async DB flush/add boundary.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.admin import _skill_io as skill_io
from app.api.shared import _skill_package_export as package_io
from app.exceptions import BusinessException
from app.services.ai.retired_skill_guard import (
    ensure_not_retired_online_search_plugin_skill,
)


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1
        if self.added and getattr(self.added[0], "id", None) is None:
            self.added[0].id = 9001


_RICH_TEXT_SKILL_CONFIG = {
    "internal": True,
    "catalog_only": True,
    "runtime_feature_code": "system.ai_writing",
}


@pytest.mark.asyncio
async def test_export_skill_package_preserves_stable_skill_contract_fields(
    monkeypatch,
) -> None:
    skill = SimpleNamespace(
        name="Rich Text AI Actions",
        key="novusdoc.rich_text_ai.actions",
        description="Catalog-only rich text actions",
        avatar=None,
        type="builtin",
        source_type="platform_builtin",
        source_ref="novusdoc.rich_text_ai.actions",
        skill_md="---\nname: rich_text_ai\ndescription: Rich text AI\n---\nBody",
        version="1.2.3",
        status="disabled",
        is_readonly=True,
        config=dict(_RICH_TEXT_SKILL_CONFIG),
        toolkit_content=None,
        toolkit_meta={"contract": "rich_text"},
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        is_system=True,
        is_active=False,
        sort_order=10,
        timeout=30,
    )
    package = SimpleNamespace(
        id=77,
        name="NovusDoc Rich Text AI",
        description="Default rich text package",
        avatar=None,
        is_recommended=False,
        is_system=True,
        is_active=False,
        sort_order=20,
        source_plugin="novusdoc",
        valves_schema={"type": "object"},
        valves_config={
            "internal": True,
            "catalog_visible": False,
            "runtime_feature_code": "system.ai_writing",
        },
    )

    class _Repo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_package_id(self, package_id: int):
            assert package_id == 77
            return [skill]

    monkeypatch.setattr(package_io, "AdminSkillRepository", _Repo)

    exported = await package_io.export_skill_package(_FakeDb(), package)

    assert exported["package_info"]["is_recommended"] is False
    assert exported["package_info"]["is_active"] is False
    assert exported["package_info"]["valves_config"] == {
        "internal": True,
        "catalog_visible": False,
        "runtime_feature_code": "system.ai_writing",
    }
    exported_skill = exported["skills"][0]
    assert exported_skill["key"] == "novusdoc.rich_text_ai.actions"
    assert exported_skill["source_type"] == "platform_builtin"
    assert exported_skill["source_ref"] == "novusdoc.rich_text_ai.actions"
    assert exported_skill["skill_md"].startswith("---")
    assert exported_skill["version"] == "1.2.3"
    assert exported_skill["status"] == "disabled"
    assert exported_skill["is_active"] is False
    assert exported_skill["is_readonly"] is True
    assert exported_skill["config"] == _RICH_TEXT_SKILL_CONFIG
    assert "legacy_runtime_feature_code" not in exported_skill["config"]
    assert "fallback_policy" not in exported_skill["config"]


@pytest.mark.asyncio
async def test_import_platform_rich_text_package_is_rejected(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, _name: str):
            pytest.fail("platform built-in package imports must fail before lookup")
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await package_io.import_skill_package(
            db,
            {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {
                    "name": "NovusDoc Rich Text AI",
                    "description": "Default rich text package",
                    "source_plugin": "novusdoc",
                    "is_recommended": True,
                    "is_active": True,
                },
                "skills": [
                    {
                        "name": "Rich Text AI Actions",
                        "key": "novusdoc.rich_text_ai.actions",
                        "type": "builtin",
                        "source_type": "platform_builtin",
                        "source_ref": "novusdoc.rich_text_ai.actions",
                        "skill_md": "---\nname: rich_text_ai\ndescription: Rich text AI\n---\nBody",
                        "version": "1.2.3",
                        "status": "active",
                        "is_readonly": True,
                        "config": dict(_RICH_TEXT_SKILL_CONFIG),
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    }
                ],
                "valves_schema": {"type": "object"},
            },
        )

    assert db.added == []


@pytest.mark.asyncio
async def test_import_retired_online_search_package_is_rejected() -> None:
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await package_io.import_skill_package(
            db,
            {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {
                    "name": "联网搜索技能包",
                    "source_plugin": "web-search",
                },
                "skills": [],
            },
        )


@pytest.mark.asyncio
async def test_import_skills_rejects_retired_online_search_toolkit_method() -> None:
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await skill_io.import_skills(
            db,
            [
                {
                    "name": "Current Events Toolkit",
                    "type": "toolkit",
                    "toolkit_content": (
                        "class Tools:\n"
                        "    def web_search(self, query: str) -> str:\n"
                        "        return query\n"
                    ),
                }
            ],
            tenant_id=None,
            package_id=7,
        )

    assert db.added == []


@pytest.mark.asyncio
async def test_import_retired_online_search_skill_is_rejected(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, _name: str):
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await package_io.import_skill_package(
            db,
            {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {"name": "Custom Skill Package"},
                "skills": [
                    {
                        "name": "联网搜索",
                        "key": "web_search",
                        "source_ref": "web_search",
                    }
                ],
            },
        )


@pytest.mark.asyncio
async def test_import_retired_online_search_config_tool_is_rejected(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, _name: str):
            pytest.fail("retired tool imports must fail before package lookup")
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await package_io.import_skill_package(
            db,
            {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {"name": "Current Events Toolkit"},
                "skills": [
                    {
                        "name": "Current Events",
                        "key": "current_events",
                        "type": "builtin",
                        "config": {
                            "tools": [
                                {
                                    "name": "web_search",
                                    "description": "Retired search tool",
                                }
                            ]
                        },
                    }
                ],
            },
        )

    assert db.added == []


@pytest.mark.asyncio
async def test_import_retired_online_search_toolkit_method_is_rejected(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, _name: str):
            pytest.fail("retired toolkit imports must fail before package lookup")
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    with pytest.raises(BusinessException):
        await package_io.import_skill_package(
            db,
            {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {"name": "Current Events Toolkit"},
                "skills": [
                    {
                        "name": "Current Events",
                        "key": "current_events.toolkit",
                        "type": "toolkit",
                        "toolkit_content": (
                            "class Tools:\n"
                            "    def web_search(self, query: str) -> str:\n"
                            "        return query\n"
                        ),
                    }
                ],
            },
        )

    assert db.added == []


def test_plugin_lifecycle_guard_rejects_retired_search_preview_tool() -> None:
    skill_ext = SimpleNamespace(
        name="current-events",
        display_name={"en": "Current Events"},
        description={"en": "General current events helper"},
        entry_point="skills.current_events",
        executor_entry_point="executors.current_events.Executor",
        config_schema=None,
        preview_tool_names=["web_search"],
        preview_semantic_families=[],
    )

    with pytest.raises(BusinessException):
        ensure_not_retired_online_search_plugin_skill(
            plugin_name="current-events-helper",
            skill_extension=skill_ext,
            skill_display_name="Current Events",
            skill_key="current-events-helper:current-events",
            source_ref="current-events-helper:current-events",
        )


def test_plugin_lifecycle_guard_allows_plugin_owned_weather_tools() -> None:
    skill_ext = SimpleNamespace(
        name="weather-realtime",
        display_name={"zh-CN": "实时天气查询", "en": "Real-time Weather Query"},
        description={
            "zh-CN": "调用免 Key 的天气服务查询真实天气数据（当前天气 + 多日预报）",
            "en": "Query real weather data via no-key weather services",
        },
        entry_point="skills.weather_resolver",
        executor_entry_point="executors.weather_widget_executor.WeatherWidgetExecutor",
        config_schema=None,
        preview_tool_names=["get_current_weather", "get_weather_forecast"],
        preview_semantic_families=["weather"],
    )

    ensure_not_retired_online_search_plugin_skill(
        plugin_name="weather-widget",
        skill_extension=skill_ext,
        skill_display_name="Real-time Weather Query",
        skill_key="weather-widget:weather-realtime",
        source_ref="weather-widget:weather-realtime",
    )


@pytest.mark.asyncio
async def test_import_renamed_package_clears_skill_key_to_avoid_unique_conflict(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, name: str):
            return SimpleNamespace(id=41, name=name)

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    result = await package_io.import_skill_package(
        db,
        {
            "conflict_mode": "rename",
            "export_data": {
                "export_version": package_io.EXPORT_VERSION,
                "package_info": {"name": "Custom Skill Package"},
                "skills": [
                    {
                        "name": "Custom Actions",
                        "key": "custom.actions",
                        "type": "builtin",
                    }
                ],
            },
        },
    )

    assert result["status"] == "created"
    assert result["package_name"].startswith("Custom Skill Package_")
    imported_skill = db.added[1]
    assert imported_skill.key is None


@pytest.mark.asyncio
async def test_import_skill_status_drives_is_active_flag(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, name: str):
            assert name == "Custom Skill Package"
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    result = await package_io.import_skill_package(
        db,
        {
            "export_version": package_io.EXPORT_VERSION,
            "package_info": {"name": "Custom Skill Package"},
            "skills": [
                {
                    "name": "Dormant Skill",
                    "key": "custom.dormant",
                    "type": "builtin",
                    "status": "disabled",
                    "is_active": True,
                }
            ],
        },
    )

    assert result["skills_created"] == 1
    imported_skill = db.added[1]
    assert imported_skill.status == "disabled"
    assert imported_skill.is_active is False

"""Test type: structural
Scope: skill-package export/import field compatibility for AI runtime skill contracts.
Real dependencies: shared skill-package IO helpers and ORM model constructors.
Mocked dependencies: repository lookup seams and async DB flush/add boundary.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.shared import _skill_package_export as package_io


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
async def test_import_skill_package_restores_stable_skill_contract_fields(
    monkeypatch,
) -> None:
    class _PackageRepo:
        def __init__(self, db) -> None:
            self.db = db

        async def get_by_name_global(self, name: str):
            assert name == "NovusDoc Rich Text AI"
            return None

    monkeypatch.setattr(package_io, "AdminSkillPackageRepository", _PackageRepo)
    db = _FakeDb()

    result = await package_io.import_skill_package(
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

    assert result["status"] == "created"
    assert result["skills_created"] == 1
    imported_package = db.added[0]
    assert imported_package.is_recommended is False
    assert imported_package.is_active is False
    assert imported_package.valves_config == {
        "internal": True,
        "catalog_visible": False,
        "runtime_feature_code": "system.ai_writing",
    }
    imported_skill = db.added[1]
    assert imported_skill.key == "novusdoc.rich_text_ai.actions"
    assert imported_skill.source_type == "platform_builtin"
    assert imported_skill.source_ref == "novusdoc.rich_text_ai.actions"
    assert imported_skill.skill_md.startswith("---")
    assert imported_skill.version == "1.2.3"
    assert imported_skill.status == "disabled"
    assert imported_skill.is_active is False
    assert imported_skill.is_readonly is True
    assert imported_skill.config == _RICH_TEXT_SKILL_CONFIG
    assert "legacy_runtime_feature_code" not in imported_skill.config
    assert "fallback_policy" not in imported_skill.config


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
                "package_info": {"name": "NovusDoc Rich Text AI"},
                "skills": [
                    {
                        "name": "Rich Text AI Actions",
                        "key": "novusdoc.rich_text_ai.actions",
                        "type": "builtin",
                    }
                ],
            },
        },
    )

    assert result["status"] == "created"
    assert result["package_name"].startswith("NovusDoc Rich Text AI_")
    imported_skill = db.added[1]
    assert imported_skill.key is None

"""Test type: behavioral
中文: 覆盖技能注册表读模型、安装/升级流程以及退役能力 installed map 过滤。
EN: Covers skill registry read models, install/upgrade flows, and retired
installed-map filtering.

Real dependencies: service read-model helpers and query composition.
Mocked dependencies: HTTP fetches and install/upgrade seams only.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ai.skill_registry_service import SkillRegistryService


class _EmptyAllResult:
    def all(self) -> list[object]:
        return []


class _CaptureDb:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _EmptyAllResult()


@pytest.mark.asyncio
async def test_skill_registry_list_packages_marks_installed_state(mock_db) -> None:
    service = SkillRegistryService(mock_db)
    service.fetch_registry = AsyncMock(
        return_value=[
            {
                "slug": "mail-tools",
                "display_name": "Mail Tools",
                "downloads": 32,
                "rating": 4.9,
                "tags": ["email"],
                "version": "1.2.0",
            },
            {
                "slug": "workflow-tools",
                "display_name": "Workflow Tools",
                "downloads": 10,
                "rating": 4.2,
                "tags": ["workflow"],
                "version": "0.3.0",
            },
        ]
    )
    service._build_installed_map = AsyncMock(
        return_value={
            "mail-tools": {
                "source_locked": True,
                "version": "1.2.0",
            }
        }
    )

    result = await service.list_packages(search="mail")

    assert result["total"] == 1
    assert result["items"] == [
        {
            "slug": "mail-tools",
            "display_name": "Mail Tools",
            "downloads": 32,
            "rating": 4.9,
            "tags": ["email"],
            "version": "1.2.0",
            "is_installed": True,
            "installed_version": "1.2.0",
            "latest_version": "1.2.0",
            "can_upgrade": False,
            "source_locked": True,
        }
    ]


@pytest.mark.asyncio
async def test_skill_registry_fetch_registry_falls_back_to_local_registry(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service._get_cached = AsyncMock(return_value=None)
    service._set_cached = AsyncMock()
    service._select_source = AsyncMock(return_value="https://registry.example")
    service._get_local_registry = MagicMock(
        return_value=[{"slug": "local-only", "display_name": "Local Only"}]
    )

    async def _boom(*args, **kwargs):
        raise httpx.HTTPError("network down")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(httpx.AsyncClient, "get", _boom)
        result = await service.fetch_registry()

    assert result == [{"slug": "local-only", "display_name": "Local Only"}]
    service._set_cached.assert_awaited_once_with(
        "registry",
        [{"slug": "local-only", "display_name": "Local Only"}],
    )


@pytest.mark.asyncio
async def test_skill_registry_install_preview_includes_installed_version(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "workflow-tools",
            "display_name": "Workflow Tools",
            "version": "2.0.0",
        }
    )
    service._build_installed_map = AsyncMock(
        return_value={
            "workflow-tools": {
                "source_locked": True,
                "source_url": "https://locked.example/skills",
                "version": "1.9.1",
            }
        }
    )

    preview = await service.install_preview("workflow-tools")

    assert preview["slug"] == "workflow-tools"
    assert preview["is_installed"] is True
    assert preview["installed_version"] == "1.9.1"
    assert preview["latest_version"] == "2.0.0"
    assert preview["can_upgrade"] is True
    assert preview["source_locked"] is True
    assert preview["source_url"] == "https://locked.example/skills"


@pytest.mark.asyncio
async def test_skill_registry_install_package_rejects_non_github_download_url(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "workflow-tools",
            "version": "1.0.0",
            "download_url": "https://evil.example/workflow-tools-1.0.0.zip",
        }
    )
    service._build_installed_map = AsyncMock(return_value={})

    with pytest.raises(Exception, match="hosted on GitHub"):
        await service.install_package("workflow-tools")


@pytest.mark.asyncio
async def test_skill_registry_list_installed_updates_uses_locked_source(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service._build_installed_map = AsyncMock(
        return_value={
            "mail-tools": {
                "package_id": 11,
                "skill_id": 12,
                "source_locked": True,
                "source_url": "https://locked.example/skills",
                "version": "1.0.0",
            }
        }
    )
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "mail-tools",
            "display_name": "Mail Tools",
            "version": "1.2.0",
        }
    )

    updates = await service.list_installed_updates()

    service.fetch_package_detail.assert_awaited_once_with(
        "mail-tools",
        source_url="https://locked.example/skills",
    )
    assert updates == [
        {
            "slug": "mail-tools",
            "display_name": "Mail Tools",
            "package_id": 11,
            "skill_id": 12,
            "installed_version": "1.0.0",
            "latest_version": "1.2.0",
            "source_locked": True,
            "source_url": "https://locked.example/skills",
        }
    ]


@pytest.mark.asyncio
async def test_skill_registry_upgrade_package_respects_source_lock(mock_db) -> None:
    service = SkillRegistryService(mock_db)
    service._build_installed_map = AsyncMock(
        return_value={
            "workflow-tools": {
                "package_id": 21,
                "skill_id": 22,
                "source_locked": True,
                "source_url": "https://locked.example/skills",
                "version": "1.0.0",
            }
        }
    )
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "workflow-tools",
            "version": "1.2.0",
            "download_url": "https://github.com/novusai/workflow-tools/releases/download/v1.2.0/workflow-tools-1.2.0.zip",
        }
    )
    service._download_archive = AsyncMock(return_value=None)
    service._load_archive_payload = AsyncMock(
        return_value={
            "extract_dir": "E:/tmp/extracted",
            "skill_name": "Workflow Tools",
            "skill_desc": "desc",
            "skill_icon": "lucide:workflow",
            "env_requires": ["API_KEY"],
            "valves_schema": {"type": "object"},
            "toolkit_content": "class Tools: pass",
        }
    )

    existing_package = MagicMock()
    existing_package.id = 21
    existing_skill = MagicMock()
    existing_skill.id = 22
    existing_skill.version = "1.0.0"
    existing_skill.config = {"registry_source_locked": True}

    package_service = MagicMock()
    package_service.get_by_id = AsyncMock(return_value=existing_package)
    package_service.update = AsyncMock(return_value=existing_package)
    skill_service = MagicMock()
    skill_service.get_by_id = AsyncMock(return_value=existing_skill)
    skill_service.update = AsyncMock(return_value=existing_skill)

    with (
        patch(
            "app.services.ai.skill_package_service.AdminSkillPackageService",
            return_value=package_service,
        ),
        patch(
            "app.services.ai.skill_service.AdminSkillService",
            return_value=skill_service,
        ),
        patch("app.services.ai.skill_registry_service.shutil.copytree"),
        patch("app.services.ai.skill_registry_service.shutil.rmtree"),
    ):
        result = await service.upgrade_package("workflow-tools")

    service.fetch_package_detail.assert_awaited_once_with(
        "workflow-tools",
        source_url="https://locked.example/skills",
    )
    assert result["status"] == "upgraded"
    assert result["previous_version"] == "1.0.0"
    assert result["latest_version"] == "1.2.0"


@pytest.mark.asyncio
async def test_skill_registry_upgrade_preview_uses_locked_source(mock_db) -> None:
    service = SkillRegistryService(mock_db)
    service._build_installed_map = AsyncMock(
        return_value={
            "workflow-tools": {
                "source_locked": True,
                "source_url": "https://locked.example/skills",
                "version": "1.0.0",
            }
        }
    )
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "workflow-tools",
            "display_name": "Workflow Tools",
            "version": "1.2.0",
            "changelog": "## 1.2.0\n- Improved prompts",
        }
    )

    preview = await service.upgrade_preview("workflow-tools")

    service.fetch_package_detail.assert_awaited_once_with(
        "workflow-tools",
        source_url="https://locked.example/skills",
    )
    assert preview["can_upgrade"] is True
    assert preview["installed_version"] == "1.0.0"
    assert preview["latest_version"] == "1.2.0"
    assert preview["source_locked"] is True


@pytest.mark.asyncio
async def test_skill_registry_upgrade_package_rejects_non_github_download_url(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service._build_installed_map = AsyncMock(
        return_value={
            "workflow-tools": {
                "package_id": 21,
                "skill_id": 22,
                "source_locked": True,
                "source_url": "https://locked.example/skills",
                "version": "1.0.0",
            }
        }
    )
    service.fetch_package_detail = AsyncMock(
        return_value={
            "slug": "workflow-tools",
            "version": "1.2.0",
            "download_url": "https://evil.example/workflow-tools-1.2.0.zip",
        }
    )

    with pytest.raises(Exception, match="hosted on GitHub"):
        await service.upgrade_package("workflow-tools")


@pytest.mark.asyncio
async def test_skill_registry_batch_upgrade_aggregates_success_and_failures(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service.list_installed_updates = AsyncMock(
        return_value=[
            {"slug": "workflow-tools"},
            {"slug": "mail-tools"},
        ]
    )

    async def _upgrade(slug: str):
        if slug == "mail-tools":
            raise RuntimeError("boom")
        return {"registry_slug": slug, "status": "upgraded"}

    service.upgrade_package = AsyncMock(side_effect=_upgrade)

    result = await service.batch_upgrade()

    assert result["requested"] == 2
    assert result["upgraded"] == [
        {"registry_slug": "workflow-tools", "status": "upgraded"}
    ]
    assert result["failed"] == [{"slug": "mail-tools", "error": "boom"}]


@pytest.mark.asyncio
async def test_skill_registry_list_official_starter_packs_marks_package_state(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service.fetch_registry = AsyncMock(
        return_value=[
            {"slug": "novusai-doctor", "display_name": "Doctor", "version": "1.1.0"},
            {
                "slug": "novusai-root-cause",
                "display_name": "Root Cause",
                "version": "1.0.0",
            },
            {"slug": "novusai-smoke", "display_name": "Smoke", "version": "1.0.0"},
        ]
    )
    service._build_installed_map = AsyncMock(
        return_value={
            "novusai-doctor": {
                "version": "1.0.0",
                "source_locked": True,
                "source_url": "https://registry.example",
            }
        }
    )

    result = await service.list_official_starter_packs()

    assert result["automatic_agent_grant"] is False
    runtime_pack = next(
        item for item in result["packs"] if item["key"] == "novusai-runtime-ops"
    )
    assert runtime_pack["summary"]["total"] == 4
    assert runtime_pack["summary"]["installed"] == 1
    assert runtime_pack["summary"]["upgradable"] == 1
    assert runtime_pack["summary"]["missing_in_catalog"] == 1
    doctor_entry = next(
        item for item in runtime_pack["packages"] if item["slug"] == "novusai-doctor"
    )
    assert doctor_entry["is_installed"] is True
    assert doctor_entry["can_upgrade"] is True
    missing_entry = next(
        item
        for item in runtime_pack["packages"]
        if item["slug"] == "novusai-plugin-audit"
    )
    assert missing_entry["available_in_catalog"] is False


@pytest.mark.asyncio
async def test_skill_registry_sync_official_starter_packs_installs_and_upgrades(
    mock_db,
) -> None:
    service = SkillRegistryService(mock_db)
    service.list_official_starter_packs = AsyncMock(
        return_value={
            "packs": [
                {
                    "key": "novusai-runtime-ops",
                    "packages": [
                        {
                            "slug": "novusai-doctor",
                            "available_in_catalog": True,
                            "is_installed": False,
                            "can_upgrade": False,
                        },
                        {
                            "slug": "novusai-root-cause",
                            "available_in_catalog": True,
                            "is_installed": True,
                            "can_upgrade": True,
                        },
                        {
                            "slug": "novusai-plugin-audit",
                            "available_in_catalog": False,
                            "is_installed": False,
                            "can_upgrade": False,
                        },
                    ],
                }
            ]
        }
    )
    service.install_package = AsyncMock(
        return_value={"registry_slug": "novusai-doctor", "status": "installed"}
    )
    service.upgrade_package = AsyncMock(
        return_value={"registry_slug": "novusai-root-cause", "status": "upgraded"}
    )

    result = await service.sync_official_starter_packs(
        pack_keys=["novusai-runtime-ops"],
        install_missing=True,
        upgrade_existing=True,
    )

    service.install_package.assert_awaited_once_with("novusai-doctor")
    service.upgrade_package.assert_awaited_once_with("novusai-root-cause")
    assert result["automatic_agent_grant"] is False
    assert result["missing_pack_keys"] == []
    assert result["installed"] == [
        {"registry_slug": "novusai-doctor", "status": "installed"}
    ]
    assert result["upgraded"] == [
        {"registry_slug": "novusai-root-cause", "status": "upgraded"}
    ]
    assert {
        "pack_key": "novusai-runtime-ops",
        "reason": "missing_in_catalog",
        "slug": "novusai-plugin-audit",
    } in result["skipped"]


@pytest.mark.asyncio
async def test_skill_registry_build_installed_map_filters_retired_search_entries() -> (
    None
):
    from app.services.ai.skill_registry_support import SkillRegistrySupport

    db = _CaptureDb()
    support = SkillRegistrySupport(db)

    await support.build_installed_map()

    assert len(db.statements) == 1
    compiled = db.statements[0].compile(compile_kwargs={"render_postcompile": True})
    sql = str(compiled).lower()
    assert "join skill_packages" in sql
    assert "skills.is_deleted is false" in sql
    assert "skill_packages.is_deleted is false" in sql
    params = " ".join(str(value).lower() for value in compiled.params.values())
    assert "web_search" in params

"""SkillPackageService + SkillService 单元测试 / Test.

Test type: behavioral.
Scope: skill package CRUD, binding/select contracts, version/status guards,
and retired online-search write-time rejection.
Mock strategy: service/repository seams are mocked; no LLM/tool executor mocks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _make_package(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "name": "Test Package",
        "description": "A test skill package",
        "is_system": False,
        "is_active": True,
        "source_plugin": None,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


def _make_skill(**overrides):
    defaults = {
        "id": 1,
        "package_id": 1,
        "name": "test_skill",
        "type": "builtin",
        "description": "A test skill",
        "is_active": True,
        "status": "active",
        "config_schema": None,
        "valves_schema": None,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestSkillPackageCreate:
    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.skill_package_service import SkillPackageService

        existing = _make_package(id=99, name="Duplicate")
        service = SkillPackageService.__new__(SkillPackageService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.find_by_name = AsyncMock(return_value=existing)

        with pytest.raises(BusinessException):
            await service._before_create({"name": "Duplicate"})


class TestSkillPackageDelete:
    @pytest.mark.asyncio
    async def test_system_package_cannot_delete(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.skill_package_service import SkillPackageService

        pkg = _make_package(is_system=True)
        service = SkillPackageService.__new__(SkillPackageService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=pkg)

        with pytest.raises(BusinessException):
            await service._before_delete(1)


class TestSkillPackageUpdate:
    @pytest.mark.asyncio
    async def test_system_package_limited_update(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.skill_package_service import SkillPackageService

        pkg = _make_package(is_system=True)
        service = SkillPackageService.__new__(SkillPackageService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=pkg)

        with pytest.raises(BusinessException):
            await service._before_update(1, {"name": "New Name"})


class TestSkillCreate:
    @pytest.mark.asyncio
    async def test_skill_create_validates_type(self, mock_db):
        from app.services.ai.skill_service import SkillService

        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        skill = _make_skill(type="builtin")
        service.repo.get_by_id = AsyncMock(return_value=skill)

        assert skill.type == "builtin"

    @pytest.mark.asyncio
    async def test_skill_create_status_disabled_syncs_is_active(self, mock_db):
        from app.services.ai.skill_service import SkillService

        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_name = AsyncMock(return_value=None)
        service._get_toolkit_security_level = AsyncMock(return_value=None)

        data = {"name": "Disabled Skill", "type": "builtin", "status": "disabled"}

        await service._before_create(data)

        assert data["status"] == "disabled"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_skill_create_inactive_flag_syncs_status_disabled(self, mock_db):
        from app.services.ai.skill_service import SkillService

        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_name = AsyncMock(return_value=None)
        service._get_toolkit_security_level = AsyncMock(return_value=None)

        data = {"name": "Inactive Skill", "type": "builtin", "is_active": False}

        await service._before_create(data)

        assert data["status"] == "disabled"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_skill_create_rejects_retired_search_config_tool(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.skill_service import SkillService

        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.tenant_id = 1
        service.repo.get_by_name = AsyncMock(return_value=None)
        service._get_toolkit_security_level = AsyncMock(return_value=None)

        data = {
            "name": "Current Events Helper",
            "type": "builtin",
            "config": {"tools": [{"name": "web_search"}]},
        }

        with pytest.raises(BusinessException):
            await service._before_create(data)

    @pytest.mark.asyncio
    async def test_skill_create_rejects_hook_injected_retired_search_tool(
        self,
        mock_db,
        monkeypatch,
    ):
        from app.exceptions import BusinessException
        from app.services.ai.skill_service import SkillService

        class _HookRegistry:
            def has_hooks(self, _hook_point):
                return True

            async def trigger(self, *_args, **_kwargs):
                return {
                    "skill_data": {
                        "name": "Hooked Helper",
                        "type": "builtin",
                        "config": {"tools": [{"name": "web_search"}]},
                    }
                }

        monkeypatch.setattr(
            "app.ai.events.hooks.get_hook_registry",
            lambda: _HookRegistry(),
        )

        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.tenant_id = 1
        service.repo.get_by_name = AsyncMock(return_value=None)
        service._get_toolkit_security_level = AsyncMock(return_value=None)

        data = {"name": "Hooked Helper", "type": "builtin"}

        with pytest.raises(BusinessException):
            await service._before_create(data)


class TestSkillQuery:
    @pytest.mark.asyncio
    async def test_get_active_skills(self, mock_db):
        from app.services.ai.skill_service import SkillService

        skills = [_make_skill(id=i, is_active=True) for i in range(3)]
        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_active_skills = AsyncMock(return_value=skills)

        result = await service.get_active_skills()
        assert len(result) == 3


class TestSkillQueryByPackage:
    @pytest.mark.asyncio
    async def test_query_by_package(self, mock_db):
        from app.services.ai.skill_service import SkillService

        skills = [_make_skill(id=i) for i in range(3)]
        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_package_id = AsyncMock(return_value=skills)

        result = await service.repo.get_by_package_id(1)
        assert len(result) == 3


class TestAdminSkillStatus:
    @pytest.mark.asyncio
    async def test_admin_skill_create_rejects_retired_search_toolkit_method(
        self,
        mock_db,
    ):
        from app.exceptions import BusinessException
        from app.services.ai.skill_service import AdminSkillService

        service = AdminSkillService.__new__(AdminSkillService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._get_toolkit_security_level = AsyncMock(return_value=None)

        data = {
            "name": "Current Events Toolkit",
            "type": "toolkit",
            "toolkit_content": (
                "class Tools:\n"
                "    def web_search(self, query: str) -> str:\n"
                "        return query\n"
            ),
        }

        with pytest.raises(BusinessException):
            await service._before_create(data)

    @pytest.mark.asyncio
    async def test_update_status_syncs_status_field(self, mock_db):
        from app.services.ai.skill_service import AdminSkillService

        service = AdminSkillService.__new__(AdminSkillService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_skill(is_system=False))
        service.repo.update = AsyncMock(return_value=_make_skill(is_active=False))

        await service.update_status(1, False)

        service.repo.update.assert_awaited_once_with(
            1,
            {"is_active": False, "status": "disabled"},
        )


class TestSkillValvesConfig:
    @pytest.mark.asyncio
    async def test_update_valves_config(self, mock_db):
        from app.services.ai.skill_service import SkillService

        skill = _make_skill(valves_config={"key": "old_value"})
        service = SkillService.__new__(SkillService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=skill)

        new_config = {"key": "new_value"}
        skill.valves_config = new_config

        assert skill.valves_config["key"] == "new_value"


class TestAdminSkillPackageResolvedTools:
    @pytest.mark.asyncio
    async def test_missing_package_raises_not_found(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.skill_package_service import AdminSkillPackageService

        service = AdminSkillPackageService.__new__(AdminSkillPackageService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.get_resolved_tools(7)

    @pytest.mark.asyncio
    async def test_maps_resolved_tool_payload(self, mock_db):
        from app.ai.skills.resolver import SkillResolveResult
        from app.ai.tools.types import ToolDefinition, ToolParameter
        from app.services.ai.skill_package_service import AdminSkillPackageService

        package = _make_package(
            id=7, name="Toolkit Package", source_plugin="weather-widget"
        )
        skills = [
            _make_skill(id=11, package_id=7, name="weather_tools", type="toolkit")
        ]

        service = AdminSkillPackageService.__new__(AdminSkillPackageService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=package)

        resolve_result = SkillResolveResult(
            tools=[
                ToolDefinition(
                    name="get_weather",
                    description="Fetch weather by city",
                    tool_type="http",
                    parameters=[
                        ToolParameter(
                            name="city",
                            type="string",
                            description="City name",
                            required=True,
                        )
                    ],
                    source_skill_id=11,
                    source_skill_name="weather_tools",
                )
            ]
        )

        skill_service_stub = AsyncMock()
        skill_service_stub.get_by_package_id = AsyncMock(return_value=skills)
        resolver_stub = AsyncMock()
        resolver_stub.resolve = AsyncMock(return_value=resolve_result)

        with (
            patch(
                "app.services.ai.skill_service.AdminSkillService",
                return_value=skill_service_stub,
            ),
            patch("app.ai.skills.resolver.SkillResolver", return_value=resolver_stub),
        ):
            result = await service.get_resolved_tools(7)

        skill_service_stub.get_by_package_id.assert_awaited_once_with(7)
        resolver_stub.resolve.assert_awaited_once_with(skills)
        assert result["package_id"] == 7
        assert result["package_name"] == "Toolkit Package"
        assert result["source_plugin"] == "weather-widget"
        assert result["tool_count"] == 1
        assert result["tools"][0] == {
            "name": "get_weather",
            "description": "Fetch weather by city",
            "tool_type": "http",
            "parameters": [
                {
                    "name": "city",
                    "type": "string",
                    "description": "City name",
                    "required": True,
                }
            ],
            "source_skill_id": 11,
            "source_skill_name": "weather_tools",
            "source_plugin": "weather-widget",
        }

    @pytest.mark.asyncio
    async def test_empty_resolve_result_returns_empty_tools(self, mock_db):
        from app.ai.skills.resolver import SkillResolveResult
        from app.services.ai.skill_package_service import AdminSkillPackageService

        package = _make_package(id=8, name="Empty Package", source_plugin=None)

        service = AdminSkillPackageService.__new__(AdminSkillPackageService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=package)

        skill_service_stub = AsyncMock()
        skill_service_stub.get_by_package_id = AsyncMock(return_value=[])
        resolver_stub = AsyncMock()
        resolver_stub.resolve = AsyncMock(return_value=SkillResolveResult())

        with (
            patch(
                "app.services.ai.skill_service.AdminSkillService",
                return_value=skill_service_stub,
            ),
            patch("app.ai.skills.resolver.SkillResolver", return_value=resolver_stub),
        ):
            result = await service.get_resolved_tools(8)

        assert result["tool_count"] == 0
        assert result["tools"] == []


class TestAdminSkillBindingSelect:
    @pytest.mark.asyncio
    async def test_binding_select_uses_tenant_visible_repo_for_tenant_agent(
        self, mock_db
    ):
        from app.services.ai.skill_service import AdminSkillService

        service = AdminSkillService.__new__(AdminSkillService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_admin_binding_select = AsyncMock()

        agent = make_mock_model(id=59, owner_tenant_id=7)
        skill = _make_skill(id=38, tenant_id=None, name="Cross Tenant Safe Skill")
        package = _make_package(id=5, tenant_id=None, name="Shared Package")

        agent_repo = AsyncMock()
        agent_repo.get_by_id = AsyncMock(return_value=agent)
        tenant_repo = AsyncMock()
        tenant_repo.query_binding_select = AsyncMock(
            return_value=([(skill, package)], 1)
        )

        with (
            patch(
                "app.services.ai.skill_service.AdminAgentRepository",
                return_value=agent_repo,
            ),
            patch(
                "app.services.ai.skill_service.SkillRepository",
                return_value=tenant_repo,
            ),
        ):
            result = await service.get_binding_select_options(
                agent_id=59,
                search="skill",
                package_id=5,
                page=2,
                page_size=10,
                include_system=True,
            )

        agent_repo.get_by_id.assert_awaited_once_with(59)
        tenant_repo.query_binding_select.assert_awaited_once_with(
            search="skill",
            package_id=5,
            page=2,
            page_size=10,
            include_system=True,
            only_active=True,
        )
        service.repo.query_admin_binding_select.assert_not_awaited()
        assert result.total == 1
        assert result.items[0].value == 38
        assert result.items[0].extra["package_name"] == "Shared Package"

    @pytest.mark.asyncio
    async def test_binding_select_keeps_admin_repo_for_platform_agent(self, mock_db):
        from app.services.ai.skill_service import AdminSkillService

        service = AdminSkillService.__new__(AdminSkillService)
        service.db = mock_db
        service.repo = AsyncMock()

        skill = _make_skill(id=51, name="Platform Skill")
        package = _make_package(id=8, tenant_id=None, name="Platform Package")
        service.repo.query_admin_binding_select = AsyncMock(
            return_value=([(skill, package)], 1)
        )

        agent_repo = AsyncMock()
        agent_repo.get_by_id = AsyncMock(
            return_value=make_mock_model(id=77, owner_tenant_id=None)
        )

        with patch(
            "app.services.ai.skill_service.AdminAgentRepository",
            return_value=agent_repo,
        ):
            result = await service.get_binding_select_options(
                agent_id=77,
                search="platform",
                package_id=None,
                page=1,
                page_size=20,
                include_system=True,
            )

        service.repo.query_admin_binding_select.assert_awaited_once_with(
            search="platform",
            package_id=None,
            page=1,
            page_size=20,
            include_system=True,
            only_active=True,
        )
        assert result.total == 1
        assert result.items[0].value == 51

    @pytest.mark.asyncio
    async def test_binding_select_always_uses_active_candidates(self, mock_db):
        from app.services.ai.skill_service import AdminSkillService

        service = AdminSkillService.__new__(AdminSkillService)
        service.db = mock_db
        service.repo = AsyncMock()

        skill = _make_skill(id=88, name="Always Active Candidate")
        package = _make_package(id=18, tenant_id=None, name="Platform Package")
        service.repo.query_admin_binding_select = AsyncMock(
            return_value=([(skill, package)], 1)
        )

        result = await service.get_binding_select_options(
            agent_id=None,
            search="active",
            package_id=None,
            page=1,
            page_size=20,
            include_system=True,
        )

        service.repo.query_admin_binding_select.assert_awaited_once_with(
            search="active",
            package_id=None,
            page=1,
            page_size=20,
            include_system=True,
            only_active=True,
        )
        assert result.total == 1
        assert result.items[0].value == 88

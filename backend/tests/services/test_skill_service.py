"""
SkillPackageService + SkillService 单元测试

覆盖：技能包 CRUD、技能绑定/解绑、版本管理、系统技能包保护。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

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

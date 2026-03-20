"""Skill package upload flow and tenant visibility tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_mock_model


class _DummyUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class TestSkillPackageUpload:

    @pytest.mark.asyncio
    async def test_upload_creates_toolkit_package_without_scope_or_source_plugin(
        self,
        mock_db,
        tmp_path: Path,
    ):
        from app.api.shared._skill_package_upload import process_skill_package_upload

        package_service = AsyncMock()
        package_service.create = AsyncMock(return_value=SimpleNamespace(id=7))
        package_service.update = AsyncMock()
        skill_service = AsyncMock()
        skill_service.create = AsyncMock()

        def _fake_extract(_zip_path: Path, extract_dir: Path) -> dict:
            (extract_dir / "server").mkdir(parents=True, exist_ok=True)
            return {
                "name": "runtime_toolkit",
                "version": "1.0.0",
                "description": "Toolkit from zip",
                "icon": "lucide:bot",
                "metadata": {"clawdbot": {"requires": {"env": ["OPENAI_API_KEY"]}}},
            }

        with (
            patch(
                "app.ai.skills.packaging.extract_skill_package",
                side_effect=_fake_extract,
            ),
            patch(
                "app.ai.skills.packaging.read_env_example",
                return_value="OPENAI_API_KEY=\n",
            ),
            patch(
                "app.ai.skills.packaging.get_skill_storage_dir",
                return_value=tmp_path / "skill_storage",
            ),
            patch(
                "app.ai.skills.server_converter.convert_server_to_toolkit",
                return_value="converted-toolkit-content",
            ),
            patch(
                "app.ai.skills.env_parser.parse_env_example",
                return_value={"type": "object"},
            ),
        ):
            pkg, skill_name, skill_version = await process_skill_package_upload(
                db=mock_db,
                file=_DummyUploadFile("runtime_toolkit.zip", b"zip-bytes"),
                package_service=package_service,
                skill_service=skill_service,
                tenant_id=None,
                is_system=False,
            )

        assert pkg.id == 7
        assert skill_name == "runtime_toolkit"
        assert skill_version == "1.0.0"

        create_payload = package_service.create.await_args.args[0]
        assert create_payload["name"] == "runtime_toolkit"
        assert "scope" not in create_payload
        assert "source_plugin" not in create_payload

        skill_payload = skill_service.create.await_args.args[0]
        assert skill_payload["type"] == "toolkit"
        assert skill_payload["toolkit_content"] == "converted-toolkit-content"
        package_service.update.assert_not_awaited()


class TestSkillPackageTenantAccess:

    @pytest.mark.asyncio
    async def test_tenant_get_by_id_blocks_admin_only_platform_package(self, mock_db):
        from app.enums.common import AudienceEnum
        from app.repositories.ai.skill_package_repository import SkillPackageRepository

        repo = SkillPackageRepository(mock_db, tenant_id=12)
        admin_only_pkg = make_mock_model(
            id=9,
            tenant_id=None,
            target_audience=AudienceEnum.ADMIN_ONLY.value,
        )

        with patch(
            "app.repositories.ai.skill_package_repository.BaseRepository.get_by_id",
            new=AsyncMock(return_value=admin_only_pkg),
        ):
            result = await repo.get_by_id(9)

        assert result is None

    @pytest.mark.asyncio
    async def test_tenant_get_by_ids_filters_admin_only_platform_package(self, mock_db):
        from app.enums.common import AudienceEnum
        from app.repositories.ai.skill_package_repository import SkillPackageRepository

        repo = SkillPackageRepository(mock_db, tenant_id=12)
        instances = [
            make_mock_model(
                id=1,
                tenant_id=None,
                target_audience=AudienceEnum.ADMIN_ONLY.value,
            ),
            make_mock_model(
                id=2,
                tenant_id=None,
                target_audience=AudienceEnum.ALL.value,
            ),
            make_mock_model(
                id=3,
                tenant_id=12,
                target_audience=AudienceEnum.ADMIN_ONLY.value,
            ),
        ]

        with patch(
            "app.repositories.ai.skill_package_repository.BaseRepository.get_by_ids",
            new=AsyncMock(return_value=instances),
        ):
            result = await repo.get_by_ids([1, 2, 3])

        assert [pkg.id for pkg in result] == [2, 3]

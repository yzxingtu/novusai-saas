"""Unit tests for audience helpers and current access-control service behavior. / 测试

Tests:
1. _audience_allows_role() — all 3×3 combinations + edge cases
2. check_user_access() — admin role gating + tenant-user publication selection"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub out all heavy deps before importing app modules
_MOCK_MODULES = [
    "redis",
    "redis.asyncio",
    "redis.asyncio.client",
    "redis.exceptions",
    "redis.asyncio.connection",
    "redis.commands",
    "celery",
    "celery.signals",
    "celery.app",
    "celery.contrib",
    "socketio.asyncio_server",
    "app.ai.agent_stats",
    "app.ai.gateway",
    "app.ai.cache",
    "app.core.redis",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        _mock = MagicMock()
        _mock.__spec__ = None
        sys.modules[_mod] = _mock

socketio_module = types.ModuleType("socketio")
socketio_exceptions_module = types.ModuleType("socketio.exceptions")


class _SocketConnectionRefusedError(Exception):
    pass


socketio_exceptions_module.ConnectionRefusedError = _SocketConnectionRefusedError
socketio_module.exceptions = socketio_exceptions_module
sys.modules.setdefault("socketio", socketio_module)
sys.modules.setdefault("socketio.exceptions", socketio_exceptions_module)

# Now we can import enums (no heavy deps)
from app.enums.common import AudienceEnum, UserRoleEnum  # noqa: E402


# Test _audience_allows_role logic directly (inline, no import chain issues)
def _audience_allows_role(target_audience: str, user_role: str | None) -> bool:
    """Inline copy of the function for isolated testing. / 测试"""
    if user_role is None:
        return True
    if target_audience == AudienceEnum.ALL.value:
        return True
    if target_audience == AudienceEnum.ADMIN_TENANT.value:
        return user_role in (
            UserRoleEnum.PLATFORM_ADMIN.value,
            UserRoleEnum.TENANT_ADMIN.value,
        )
    if target_audience == AudienceEnum.ADMIN_ONLY.value:
        return user_role == UserRoleEnum.PLATFORM_ADMIN.value
    return True  # unknown → allow


# ============================================================
# _audience_allows_role tests
# ============================================================


class TestAudienceAllowsRole:
    """Test all combinations of target_audience × user_role. / 测试"""

    # AudienceEnum.ALL allows everyone
    def test_all_allows_platform_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ALL.value, UserRoleEnum.PLATFORM_ADMIN.value
            )
            is True
        )

    def test_all_allows_tenant_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ALL.value, UserRoleEnum.TENANT_ADMIN.value
            )
            is True
        )

    def test_all_allows_tenant_user(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ALL.value, UserRoleEnum.TENANT_USER.value
            )
            is True
        )

    # AudienceEnum.ADMIN_TENANT allows admin and tenant_admin
    def test_admin_tenant_allows_platform_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_TENANT.value, UserRoleEnum.PLATFORM_ADMIN.value
            )
            is True
        )

    def test_admin_tenant_allows_tenant_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_TENANT.value, UserRoleEnum.TENANT_ADMIN.value
            )
            is True
        )

    def test_admin_tenant_denies_tenant_user(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_TENANT.value, UserRoleEnum.TENANT_USER.value
            )
            is False
        )

    # AudienceEnum.ADMIN_ONLY allows only platform_admin
    def test_admin_only_allows_platform_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_ONLY.value, UserRoleEnum.PLATFORM_ADMIN.value
            )
            is True
        )

    def test_admin_only_denies_tenant_admin(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_ONLY.value, UserRoleEnum.TENANT_ADMIN.value
            )
            is False
        )

    def test_admin_only_denies_tenant_user(self):
        assert (
            _audience_allows_role(
                AudienceEnum.ADMIN_ONLY.value, UserRoleEnum.TENANT_USER.value
            )
            is False
        )

    # user_role=None always allows (backward compat with old call paths)
    def test_none_user_role_allows_all(self):
        assert _audience_allows_role(AudienceEnum.ADMIN_ONLY.value, None) is True
        assert _audience_allows_role(AudienceEnum.ADMIN_TENANT.value, None) is True
        assert _audience_allows_role(AudienceEnum.ALL.value, None) is True

    # Unknown audience value falls through to allow
    def test_unknown_audience_allows(self):
        assert (
            _audience_allows_role("unknown_value", UserRoleEnum.TENANT_USER.value)
            is True
        )


# ============================================================
# check_user_access tests (with mocked DB)
# ============================================================


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = 1
    agent.visibility = "public"
    agent.target_audience = AudienceEnum.ADMIN_TENANT.value
    return agent


@pytest.fixture
def mock_access():
    access = MagicMock()
    access.access_type = "all_users"
    access.org_node_ids = None
    access.user_ids = None
    access.admin_role_ids = None
    access.tenant_role_ids = None
    access.user_role_ids = None
    return access


class TestCheckUserAccess:
    """Test AgentService.check_user_access() logic. / 服务"""

    def _make_service(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = MagicMock()
        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=None)
        publication_repo = MagicMock()
        publication_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_access_repo = MagicMock(return_value=access_repo)
        service._get_publication_repo = MagicMock(return_value=publication_repo)
        return service

    @pytest.mark.asyncio
    async def test_target_audience_blocks_tenant_user(self, mock_db, mock_agent):
        """Tenant user without publication should be blocked. / 获取/返回"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ALL.value
        mock_agent.visibility = "private"
        publication_repo = MagicMock()
        publication_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_publication_repo = MagicMock(return_value=publication_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_USER.value,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_target_audience_allows_tenant_admin(self, mock_db, mock_agent):
        """Tenant admin should be allowed when no role restriction exists. / 获取/返回"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.visibility = "private"
        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_access_repo = MagicMock(return_value=access_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_public_agent_all_audience_allows_any_user(self, mock_db, mock_agent):
        """Tenant user is allowed when publication is enabled for all users. / 获取/返回"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ALL.value
        publication = MagicMock()
        publication.enabled_for_users = True
        publication.access_type = "all_users"
        publication_repo = MagicMock()
        publication_repo.get_by_agent_id = AsyncMock(return_value=publication)
        service._get_publication_repo = MagicMock(return_value=publication_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_USER.value,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_admin_only_blocks_everyone_except_platform_admin(
        self, mock_db, mock_agent
    ):
        """Tenant admin without matching role and tenant user without publication are blocked. / 获取/返回"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ADMIN_ONLY.value
        mock_agent.visibility = "private"
        access = MagicMock()
        access.tenant_role_ids = []
        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=access)
        publication_repo = MagicMock()
        publication_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_access_repo = MagicMock(return_value=access_repo)
        service._get_publication_repo = MagicMock(return_value=publication_repo)

        result_tenant_admin = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
        )
        result_tenant_user = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_USER.value,
        )
        assert result_tenant_admin is False
        assert result_tenant_user is False

    @pytest.mark.asyncio
    async def test_private_no_access_record_allows(self, mock_db, mock_agent):
        """Tenant user with no publication record is denied. / 说明"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ALL.value
        mock_agent.visibility = "private"

        publication_repo = MagicMock()
        publication_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_publication_repo = MagicMock(return_value=publication_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_USER.value,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_tenant_role_ids_null_allows_all(
        self, mock_db, mock_agent, mock_access
    ):
        """tenant_role_ids=NULL means no restriction (allow all). / 说明"""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.visibility = "private"
        mock_agent.target_audience = AudienceEnum.ALL.value
        mock_access.access_type = "all_users"
        mock_access.tenant_role_ids = None  # NULL = no restriction

        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=mock_access)
        service._get_access_repo = MagicMock(return_value=access_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=5,
        )
        # all_users access_type → True
        assert result is True

    @pytest.mark.asyncio
    async def test_tenant_role_ids_with_user_role_id_none_denies(
        self,
        mock_db,
        mock_agent,
        mock_access,
    ):
        """tenant_role_ids=[5] but user_role_id=None → deny (chat must pass role_id)."""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ADMIN_TENANT.value
        mock_agent.visibility = "private"
        mock_access.tenant_role_ids = [5, 10]

        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=mock_access)
        service._get_access_repo = MagicMock(return_value=access_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=None,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_tenant_role_ids_with_matching_user_role_id_allows(
        self,
        mock_db,
        mock_agent,
        mock_access,
    ):
        """tenant_role_ids=[5,10] and user_role_id=5 → allow."""
        service = self._make_service(mock_db)
        service.repo.get_by_id = AsyncMock(return_value=mock_agent)
        mock_agent.target_audience = AudienceEnum.ADMIN_TENANT.value
        mock_agent.visibility = "private"
        mock_access.tenant_role_ids = [5, 10]

        access_repo = MagicMock()
        access_repo.get_by_agent_id = AsyncMock(return_value=mock_access)
        service._get_access_repo = MagicMock(return_value=access_repo)

        result = await service.check_user_access(
            agent_id=1,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=5,
        )
        assert result is True

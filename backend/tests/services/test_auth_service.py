"""AuthService 单元测试 / Test.

覆盖：管理员登录、企业管理员登录、Token 刷新、密码修改、密码策略、账户锁定。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_mock_model, make_scalar_result

# ── Helpers ──

def _make_admin(**overrides):
    defaults = {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "password_hash": "hashed_password",
        "is_active": True,
        "is_super": True,
        "login_fail_count": 0,
        "last_fail_at": None,
        "locked_until": None,
        "last_login_at": None,
        "last_login_ip": None,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


def _make_tenant_admin(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "username": "tenant_admin",
        "email": "admin@tenant.com",
        "password_hash": "hashed_password",
        "is_active": True,
        "login_fail_count": 0,
        "last_fail_at": None,
        "locked_until": None,
        "last_login_at": None,
        "last_login_ip": None,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


def _make_tenant(**overrides):
    defaults = {"id": 1, "is_active": True}
    defaults.update(overrides)
    return make_mock_model(**defaults)


# ── Tests ──

class TestPasswordPolicy:
    """密码策略验证测试 / Test."""

    @pytest.mark.asyncio
    async def test_password_too_short(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        with patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock) as mock_cfg:
            mock_cfg.side_effect = lambda key, default=None: {
                "password_min_length": 8,
                "password_complexity": "low",
            }.get(key, default)

            with pytest.raises(BusinessException):
                await service._validate_password_policy("short")

    @pytest.mark.asyncio
    async def test_password_medium_complexity_no_digit(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        with patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock) as mock_cfg:
            mock_cfg.side_effect = lambda key, default=None: {
                "password_min_length": 6,
                "password_complexity": "medium",
            }.get(key, default)

            with pytest.raises(BusinessException):
                await service._validate_password_policy("abcdefgh")

    @pytest.mark.asyncio
    async def test_password_medium_complexity_valid(self, mock_db):
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        with patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock) as mock_cfg:
            mock_cfg.side_effect = lambda key, default=None: {
                "password_min_length": 6,
                "password_complexity": "medium",
            }.get(key, default)

            await service._validate_password_policy("abc123def")

    @pytest.mark.asyncio
    async def test_password_high_complexity_no_special(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        with patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock) as mock_cfg:
            mock_cfg.side_effect = lambda key, default=None: {
                "password_min_length": 6,
                "password_complexity": "high",
            }.get(key, default)

            with pytest.raises(BusinessException):
                await service._validate_password_policy("abc123def")

    @pytest.mark.asyncio
    async def test_password_high_complexity_valid(self, mock_db):
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        with patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock) as mock_cfg:
            mock_cfg.side_effect = lambda key, default=None: {
                "password_min_length": 6,
                "password_complexity": "high",
            }.get(key, default)

            await service._validate_password_policy("abc123!@#")


class TestAdminLogin:
    """管理员登录测试 / Test."""

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        mock_db.execute.return_value = make_scalar_result(None)
        service = AuthService(mock_db)

        with (
            patch.object(service, "_record_admin_login_failure", new_callable=AsyncMock),
            patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock, return_value=True),
            pytest.raises(AuthenticationException),
        ):
            await service.authenticate_admin("nonexistent", "password")

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        mock_db.execute.return_value = make_scalar_result(admin)
        service = AuthService(mock_db)

        with (
            patch.object(service, "_is_account_locked", new_callable=AsyncMock, return_value=False),
            patch.object(service, "_record_admin_login_failure", new_callable=AsyncMock),
            patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock, return_value=False),
            patch("app.services.common.auth_service.verify_password", return_value=False),
            pytest.raises(AuthenticationException),
        ):
            await service.authenticate_admin("admin", "wrong_password")

    @pytest.mark.asyncio
    async def test_login_account_locked(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        mock_db.execute.return_value = make_scalar_result(admin)
        service = AuthService(mock_db)

        with (
            patch.object(service, "_is_account_locked", new_callable=AsyncMock, return_value=True),
            pytest.raises(AuthenticationException),
        ):
            await service.authenticate_admin("admin", "password")

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        admin = _make_admin(is_active=False)
        mock_db.execute.return_value = make_scalar_result(admin)
        service = AuthService(mock_db)

        with (
            patch.object(service, "_is_account_locked", new_callable=AsyncMock, return_value=False),
            pytest.raises(AuthenticationException),
        ):
            await service.authenticate_admin("admin", "password")

    @pytest.mark.asyncio
    async def test_login_success(self, mock_db):
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        mock_db.execute.return_value = make_scalar_result(admin)
        service = AuthService(mock_db)

        with (
            patch.object(service, "_is_account_locked", new_callable=AsyncMock, return_value=False),
            patch.object(service, "_reset_admin_login_failures", new_callable=AsyncMock),
            patch.object(service._config_service, "get_platform_config", new_callable=AsyncMock, return_value=False),
            patch("app.services.common.auth_service.verify_password", return_value=True),
            patch("app.services.common.auth_service.create_access_token", return_value="access_tok"),
            patch("app.services.common.auth_service.create_refresh_token", return_value="refresh_tok"),
        ):
            result = await service.authenticate_admin("admin", "correct_password")

        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"
        assert result["token_type"] == "bearer"


class TestChangePassword:
    """密码修改测试 / Test."""

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        service = AuthService(mock_db)

        with (
            patch("app.services.common.auth_service.verify_password", return_value=False),
            pytest.raises(BusinessException),
        ):
            await service.change_admin_password(admin, "wrong_old", "new_pass123!")

    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_db):
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        service = AuthService(mock_db)

        with (
            patch("app.services.common.auth_service.verify_password", return_value=True),
            patch("app.services.common.auth_service.get_password_hash", return_value="new_hash"),
            patch.object(service, "_validate_password_policy", new_callable=AsyncMock),
        ):
            await service.change_admin_password(admin, "old_pass", "new_pass123!")

        assert admin.password_hash == "new_hash"


# ── 真实密码 Hash 测试（无 Mock，测试 security 模块）──

class TestRealPasswordHash:
    """使用真实 hash/verify 函数，不 mock"""

    def test_hash_and_verify_correct(self):
        from app.core.security import get_password_hash, verify_password

        raw = "MyP@ssw0rd!2026"
        hashed = get_password_hash(raw)

        assert hashed != raw
        assert hashed.startswith("$2b$")  # bcrypt format
        assert verify_password(raw, hashed) is True

    def test_verify_wrong_password(self):
        from app.core.security import get_password_hash, verify_password

        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        from app.core.security import get_password_hash

        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2  # bcrypt uses random salt


class TestRealTokenGeneration:
    """使用真实 Token 生成函数，验证 JWT 格式 / Token ， JWT"""

    def test_access_token_is_jwt(self):
        from app.core.security import TOKEN_SCOPE_ADMIN, create_access_token

        token = create_access_token(subject=1, scope=TOKEN_SCOPE_ADMIN)
        parts = token.split(".")
        assert len(parts) == 3  # JWT: header.payload.signature

    def test_token_pair_contains_both(self):
        from app.core.security import TOKEN_SCOPE_ADMIN, create_token_pair

        pair = create_token_pair(subject=1, scope=TOKEN_SCOPE_ADMIN)
        assert "access_token" in pair
        assert "refresh_token" in pair
        assert "token_type" in pair
        assert pair["token_type"] == "bearer"
        assert pair["access_token"].count(".") == 2
        assert pair["refresh_token"].count(".") == 2

    def test_access_and_refresh_tokens_differ(self):
        from app.core.security import TOKEN_SCOPE_ADMIN, create_token_pair

        pair = create_token_pair(subject=1, scope=TOKEN_SCOPE_ADMIN)
        assert pair["access_token"] != pair["refresh_token"]

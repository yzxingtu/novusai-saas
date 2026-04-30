"""AuthService 单元测试 / Test.

覆盖：管理员登录、企业管理员登录、Token 刷新、密码修改、密码策略、账户锁定。"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import (
    make_mock_model,
    make_scalar_result,
    make_scalars_result,
)

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


def _make_tenant_user(**overrides):
    defaults = {
        "id": 11,
        "tenant_id": 1,
        "username": "tenant_user",
        "email": "user@example.com",
        "phone": "13800000000",
        "password_hash": "hashed_password",
        "is_active": True,
        "is_deleted": False,
        "login_fail_count": 0,
        "last_fail_at": None,
        "locked_until": None,
        "last_login_at": None,
        "last_login_ip": None,
        "nickname": "Tenant User",
    }
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

        with patch.object(
            service._config_service, "get_platform_config", new_callable=AsyncMock
        ) as mock_cfg:
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

        with patch.object(
            service._config_service, "get_platform_config", new_callable=AsyncMock
        ) as mock_cfg:
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

        with patch.object(
            service._config_service, "get_platform_config", new_callable=AsyncMock
        ) as mock_cfg:
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

        with patch.object(
            service._config_service, "get_platform_config", new_callable=AsyncMock
        ) as mock_cfg:
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

        with patch.object(
            service._config_service, "get_platform_config", new_callable=AsyncMock
        ) as mock_cfg:
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
            patch.object(
                service, "_record_admin_login_failure", new_callable=AsyncMock
            ),
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
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
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                service, "_record_admin_login_failure", new_callable=AsyncMock
            ),
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.common.auth_service.verify_password", return_value=False
            ),
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
            patch.object(
                service, "_is_account_locked", new_callable=AsyncMock, return_value=True
            ),
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
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
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
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                service, "_reset_admin_login_failures", new_callable=AsyncMock
            ),
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.common.auth_service.verify_password", return_value=True
            ),
            patch(
                "app.services.common.auth_service.create_access_token",
                return_value=("access_tok", "jti_ok"),
            ),
            patch(
                "app.services.common.auth_service.create_refresh_token",
                return_value=("refresh_tok", "refresh_jti_ok"),
            ),
        ):
            result = await service.authenticate_admin("admin", "correct_password")

        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"
        assert result["token_type"] == "bearer"


class TestAdminDevBootstrap:
    """开发环境 admin bootstrap 测试 / Dev bootstrap tests for admin."""

    @pytest.mark.asyncio
    async def test_dev_bootstrap_success(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        mock_db.execute.return_value = make_scalar_result(admin)
        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings,
            "DEV_BOOTSTRAP_ALLOWED_HOSTS",
            "localhost,127.0.0.1,.local",
            raising=False,
        )
        monkeypatch.setattr(
            settings, "DEV_ADMIN_BOOTSTRAP_SECRET", "dev-admin-secret", raising=False
        )
        monkeypatch.setattr(
            settings, "DEV_ADMIN_BOOTSTRAP_USERNAME", "admin", raising=False
        )

        with (
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
                return_value=120,
            ),
            patch.object(service, "_record_active_tokens", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.create_access_token",
                return_value=("dev_access", "admin_access_jti"),
            ),
            patch(
                "app.services.common.auth_service.create_refresh_token",
                return_value=("dev_refresh", "admin_refresh_jti"),
            ),
        ):
            result = await service.authenticate_admin_by_dev_bootstrap(
                "dev-admin-secret",
                request_host="localhost",
                client_ip="127.0.0.1",
            )

        assert result["access_token"] == "dev_access"
        assert result["refresh_token"] == "dev_refresh"
        assert admin.last_login_ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_dev_bootstrap_rejects_wrong_secret(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost", raising=False
        )
        monkeypatch.setattr(
            settings, "DEV_ADMIN_BOOTSTRAP_SECRET", "dev-admin-secret", raising=False
        )

        with pytest.raises(AuthenticationException):
            await service.authenticate_admin_by_dev_bootstrap(
                "wrong-secret",
                request_host="localhost",
            )

    @pytest.mark.asyncio
    async def test_dev_bootstrap_rejects_non_local_host(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.exceptions import NotFoundException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost,.local", raising=False
        )

        with pytest.raises(NotFoundException):
            await service.authenticate_admin_by_dev_bootstrap(
                "any-secret",
                request_host="example.com",
            )


class TestTenantAdminDevBootstrap:
    """开发环境 tenant admin bootstrap 测试 / Dev bootstrap tests for tenant admin."""

    @pytest.mark.asyncio
    async def test_dev_bootstrap_success(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.services.common.auth_service import AuthService

        tenant = _make_tenant(code="acme")
        tenant_admin = _make_tenant_admin(username="tenant_admin")
        mock_db.execute.side_effect = [
            make_scalar_result(tenant),
            make_scalar_result(tenant_admin),
            make_scalar_result(tenant),
        ]
        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost,.local", raising=False
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_BOOTSTRAP_SECRET",
            "dev-tenant-secret",
            raising=False,
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_BOOTSTRAP_USERNAME",
            "tenant_admin",
            raising=False,
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_BOOTSTRAP_TENANT_CODE",
            "acme",
            raising=False,
        )

        with (
            patch.object(
                service._config_service,
                "get_tenant_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
                return_value=120,
            ),
            patch.object(service, "_record_active_tokens", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.create_access_token",
                return_value=("tenant_access", "tenant_access_jti"),
            ),
            patch(
                "app.services.common.auth_service.create_refresh_token",
                return_value=("tenant_refresh", "tenant_refresh_jti"),
            ),
        ):
            result = await service.authenticate_tenant_admin_by_dev_bootstrap(
                "dev-tenant-secret",
                request_host="acme.app.local",
                client_ip="127.0.0.1",
            )

        assert result["access_token"] == "tenant_access"
        assert result["refresh_token"] == "tenant_refresh"
        assert tenant_admin.last_login_ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_dev_bootstrap_requires_configured_target(
        self,
        mock_db,
        monkeypatch,
    ):
        from app.core.config import settings
        from app.exceptions import NotFoundException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost,.local", raising=False
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_BOOTSTRAP_SECRET",
            "dev-tenant-secret",
            raising=False,
        )
        monkeypatch.setattr(
            settings, "DEV_TENANT_BOOTSTRAP_USERNAME", "", raising=False
        )
        monkeypatch.setattr(
            settings, "DEV_TENANT_BOOTSTRAP_TENANT_CODE", "", raising=False
        )

        with pytest.raises(NotFoundException):
            await service.authenticate_tenant_admin_by_dev_bootstrap(
                "dev-tenant-secret",
                request_host="tenant.app.local",
            )


class TestTenantAdminLogin:
    """企业管理员登录测试 / Tenant admin login tests."""

    @pytest.mark.asyncio
    async def test_login_inactive_tenant_raises_authentication_exception(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        tenant_admin = _make_tenant_admin()
        inactive_tenant = _make_tenant(is_active=False)
        mock_db.execute.side_effect = [
            make_scalars_result([tenant_admin]),
            make_scalar_result(inactive_tenant),
        ]
        service = AuthService(mock_db)
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_captcha_enabled": False,
                "tenant_captcha_enable_threshold": 2,
            }.get(key, default)
        )

        with (
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(service, "_reset_login_failures", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.verify_password",
                return_value=True,
            ),
            pytest.raises(AuthenticationException),
        ):
            await service.authenticate_tenant_admin(
                "tenant_admin",
                "password",
                tenant_id_from_ctx=tenant_admin.tenant_id,
            )

    @pytest.mark.asyncio
    async def test_issue_login_tokens_uses_tenant_session_timeout(self, mock_db):
        from app.services.common.auth_service import AuthService

        tenant_admin = _make_tenant_admin(id=7, tenant_id=3)
        tenant = _make_tenant(id=3, code="acme")
        mock_db.execute.return_value = make_scalar_result(tenant)
        service = AuthService(mock_db)

        with (
            patch.object(
                service._config_service,
                "get_tenant_config",
                new_callable=AsyncMock,
                return_value=45,
            ) as mock_tenant_config,
            patch.object(
                service._config_service,
                "get_platform_config",
                new_callable=AsyncMock,
            ) as mock_platform_config,
            patch.object(service, "_record_active_tokens", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.create_access_token",
                return_value=("tenant_access", "tenant_access_jti"),
            ) as mock_create_access_token,
            patch(
                "app.services.common.auth_service.create_refresh_token",
                return_value=("tenant_refresh", "tenant_refresh_jti"),
            ) as mock_create_refresh_token,
        ):
            result = await service._issue_tenant_admin_login_tokens(tenant_admin)

        assert result == {
            "access_token": "tenant_access",
            "refresh_token": "tenant_refresh",
            "token_type": "bearer",
        }
        mock_tenant_config.assert_awaited_once_with(
            tenant_admin.tenant_id,
            "tenant_session_timeout",
            default=None,
        )
        mock_platform_config.assert_not_awaited()
        mock_create_access_token.assert_called_once_with(
            subject=tenant_admin.id,
            scope="tenant_admin",
            expires_delta=timedelta(minutes=45),
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )
        mock_create_refresh_token.assert_called_once_with(
            subject=tenant_admin.id,
            scope="tenant_admin",
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )


class TestTenantUserDevBootstrap:
    """开发环境 tenant user bootstrap 测试 / Dev bootstrap tests for tenant user."""

    @pytest.mark.asyncio
    async def test_dev_bootstrap_success(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.services.common.auth_service import AuthService

        tenant = _make_tenant(code="acme")
        tenant_user = _make_tenant_user(username="e2e_user", tenant_id=tenant.id)
        mock_db.execute.side_effect = [
            make_scalar_result(tenant),
            make_scalar_result(tenant_user),
        ]
        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost,.local", raising=False
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_USER_BOOTSTRAP_SECRET",
            "dev-tenant-user-secret",
            raising=False,
        )

        with (
            patch.object(service, "_record_active_tokens", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.create_token_pair",
                return_value={
                    "access_token": "tenant_user_access",
                    "refresh_token": "tenant_user_refresh",
                    "access_jti": "tenant_user_access_jti",
                    "refresh_jti": "tenant_user_refresh_jti",
                    "token_type": "bearer",
                },
            ),
        ):
            result = await service.authenticate_tenant_user_by_dev_bootstrap(
                "dev-tenant-user-secret",
                request_host="acme.app.local",
                username="e2e_user",
                tenant_code="acme",
                client_ip="127.0.0.1",
            )

        assert result["access_token"] == "tenant_user_access"
        assert result["refresh_token"] == "tenant_user_refresh"
        assert tenant_user.last_login_ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_dev_bootstrap_rejects_wrong_secret(self, mock_db, monkeypatch):
        from app.core.config import settings
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)

        monkeypatch.setattr(settings, "APP_ENV", "development", raising=False)
        monkeypatch.setattr(settings, "DEV_BOOTSTRAP_AUTH_ENABLED", True, raising=False)
        monkeypatch.setattr(
            settings, "DEV_BOOTSTRAP_ALLOWED_HOSTS", "localhost", raising=False
        )
        monkeypatch.setattr(
            settings,
            "DEV_TENANT_USER_BOOTSTRAP_SECRET",
            "dev-tenant-user-secret",
            raising=False,
        )

        with pytest.raises(AuthenticationException):
            await service.authenticate_tenant_user_by_dev_bootstrap(
                "wrong-secret",
                request_host="localhost",
                username="e2e_user",
                tenant_code="acme",
            )


class TestChangePassword:
    """密码修改测试 / Test."""

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        service = AuthService(mock_db)

        with (
            patch(
                "app.services.common.auth_service.verify_password", return_value=False
            ),
            pytest.raises(BusinessException),
        ):
            await service.change_admin_password(admin, "wrong_old", "new_pass123!")

    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_db):
        from app.services.common.auth_service import AuthService

        admin = _make_admin()
        service = AuthService(mock_db)

        with (
            patch(
                "app.services.common.auth_service.verify_password", return_value=True
            ),
            patch(
                "app.services.common.auth_service.get_password_hash",
                return_value="new_hash",
            ),
            patch.object(service, "_validate_password_policy", new_callable=AsyncMock),
        ):
            await service.change_admin_password(admin, "old_pass", "new_pass123!")

        assert admin.password_hash == "new_hash"


class TestTenantUserLogin:
    """企业用户登录测试 / Test."""

    @pytest.mark.asyncio
    async def test_login_uses_user_login_captcha_switch(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        user = make_mock_model(
            id=11,
            tenant_id=3,
            username="tenant_user",
            email="user@example.com",
            phone="13800000000",
            password_hash="hashed_password",
            is_active=True,
            is_deleted=False,
            login_fail_count=0,
        )
        mock_db.execute.return_value = make_scalars_result([user])
        service = AuthService(mock_db)

        with (
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                service, "_verify_captcha", new_callable=AsyncMock
            ) as mock_verify_captcha,
            patch.object(service, "_record_login_failure", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.verify_password", return_value=False
            ),
            pytest.raises(AuthenticationException),
        ):
            service._config_service.get_tenant_config = AsyncMock(
                side_effect=lambda _tenant_id, key, default=None: {
                    "user_login_captcha_enabled": True,
                    "user_login_captcha_enable_threshold": 0,
                }.get(key, default)
            )
            await service.authenticate_tenant_user(
                "tenant_user",
                "wrong_password",
                tenant_id_from_ctx=3,
                client_ip="127.0.0.1",
                captcha_challenge_id="challenge-1",
                captcha_solution="solution-1",
                captcha_provider_code="image",
            )

        assert mock_verify_captcha.await_count == 1
        assert any(
            call.args[:2] == (3, "user_login_captcha_enabled")
            for call in service._config_service.get_tenant_config.await_args_list
        )
        assert any(
            call.args[:2] == (3, "user_login_captcha_enable_threshold")
            for call in service._config_service.get_tenant_config.await_args_list
        )
        assert not any(
            call.args[:2] == (3, "tenant_captcha_enabled")
            for call in service._config_service.get_tenant_config.await_args_list
        )
        assert not any(
            call.args[:2] == (3, "tenant_captcha_enable_threshold")
            for call in service._config_service.get_tenant_config.await_args_list
        )

    @pytest.mark.asyncio
    async def test_login_skips_captcha_when_user_login_switch_disabled(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        user = make_mock_model(
            id=12,
            tenant_id=5,
            username="tenant_user_2",
            email="user2@example.com",
            phone="13900000000",
            password_hash="hashed_password",
            is_active=True,
            is_deleted=False,
            login_fail_count=10,
        )
        mock_db.execute.return_value = make_scalars_result([user])
        service = AuthService(mock_db)

        with (
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                service, "_verify_captcha", new_callable=AsyncMock
            ) as mock_verify_captcha,
            patch.object(service, "_record_login_failure", new_callable=AsyncMock),
            patch(
                "app.services.common.auth_service.verify_password", return_value=False
            ),
            pytest.raises(AuthenticationException),
        ):
            service._config_service.get_tenant_config = AsyncMock(
                side_effect=lambda _tenant_id, key, default=None: {
                    "user_login_captcha_enabled": False,
                    "user_login_captcha_enable_threshold": 0,
                }.get(key, default)
            )
            await service.authenticate_tenant_user(
                "tenant_user_2",
                "wrong_password",
                tenant_id_from_ctx=5,
                client_ip="127.0.0.1",
            )

        mock_verify_captcha.assert_not_awaited()


class TestTenantUserCodeLogin:
    """企业用户验证码登录测试 / Tenant user code-login tests."""

    @pytest.mark.asyncio
    async def test_send_login_code_requires_captcha_when_enabled(self, mock_db):
        from app.exceptions import AuthenticationException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_login_methods": ["password", "email"],
                "user_login_captcha_enabled": True,
            }.get(key, default)
        )

        with pytest.raises(AuthenticationException):
            await service.send_tenant_user_login_code(
                channel="email",
                email="user@example.com",
                tenant_id_from_ctx=1,
                client_ip="127.0.0.1",
            )

    @pytest.mark.asyncio
    async def test_send_login_code_returns_uniform_success_for_missing_user(
        self, mock_db
    ):
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_login_methods": ["password", "email"],
                "user_login_captcha_enabled": False,
            }.get(key, default)
        )
        mock_db.execute.return_value = make_scalar_result(None)

        with (
            patch(
                "app.services.common.auth_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.common.auth_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
        ):
            result = await service.send_tenant_user_login_code(
                channel="email",
                email="missing@example.com",
                tenant_id_from_ctx=1,
                client_ip="127.0.0.1",
            )

        assert result["message"]
        assert mock_cache_set.await_count == 1

    @pytest.mark.asyncio
    async def test_send_login_code_success_queues_email(self, mock_db):
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)
        user = _make_tenant_user()
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_login_methods": ["password", "email"],
                "user_login_captcha_enabled": False,
            }.get(key, default)
        )
        mock_db.execute.return_value = make_scalar_result(user)

        with (
            patch(
                "app.services.common.auth_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.common.auth_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
            patch(
                "app.tasks.email.send_email_task.delay",
            ) as mock_delay,
            patch(
                "app.services.common.email_templates.render_login_code_email",
                return_value=("subject", "<p>html</p>", "text"),
            ) as mock_render_email,
        ):
            result = await service.send_tenant_user_login_code(
                channel="email",
                email="user@example.com",
                tenant_id_from_ctx=1,
                client_ip="127.0.0.1",
            )

        assert result["message"]
        assert mock_cache_set.await_count == 2
        mock_render_email.assert_called_once_with(
            user_name=user.nickname,
            code=mock_cache_set.await_args_list[1].args[1]["code"],
            expire_minutes=service.LOGIN_CODE_TTL // 60,
        )
        mock_delay.assert_called_once_with(
            to=["user@example.com"],
            subject="subject",
            html_body="<p>html</p>",
            text_body="text",
            triggered_by="login_code",
            tenant_id=user.tenant_id,
        )

    @pytest.mark.asyncio
    async def test_login_by_code_success(self, mock_db):
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)
        user = _make_tenant_user()
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_login_methods": ["password", "email"],
            }.get(key, default)
        )
        mock_db.execute.return_value = make_scalar_result(user)

        with (
            patch(
                "app.services.common.auth_service.cache_get",
                new_callable=AsyncMock,
                return_value={"code": "123456", "user_id": user.id},
            ),
            patch(
                "app.services.common.auth_service.cache_delete",
                new_callable=AsyncMock,
            ) as mock_cache_delete,
            patch.object(
                service,
                "_is_account_locked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                service,
                "_reset_login_failures",
                new_callable=AsyncMock,
            ),
            patch.object(
                service,
                "_issue_tenant_user_tokens",
                new_callable=AsyncMock,
                return_value={"access_token": "token"},
            ) as mock_issue_tokens,
        ):
            result = await service.authenticate_tenant_user_by_code(
                channel="email",
                code="123456",
                email="user@example.com",
                tenant_id_from_ctx=1,
                client_ip="127.0.0.1",
            )

        assert result == {"access_token": "token"}
        mock_cache_delete.assert_awaited_once()
        mock_issue_tokens.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_login_by_code_sms_not_enabled(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.common.auth_service import AuthService

        service = AuthService(mock_db)
        service._config_service.get_tenant_config = AsyncMock(
            side_effect=lambda _tenant_id, key, default=None: {
                "tenant_login_methods": ["password", "email"],
            }.get(key, default)
        )

        with pytest.raises(BusinessException):
            await service.authenticate_tenant_user_by_code(
                channel="sms",
                code="123456",
                phone="13800000000",
                tenant_id_from_ctx=1,
            )


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

        token, _jti = create_access_token(subject=1, scope=TOKEN_SCOPE_ADMIN)
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

    def test_refresh_token_accepts_extra_claims(self):
        from jose import jwt

        from app.core.config import settings
        from app.core.security import TOKEN_SCOPE_ADMIN, create_refresh_token

        token, _jti = create_refresh_token(
            subject=1,
            scope=TOKEN_SCOPE_ADMIN,
            extra_claims={"tenant_id": 42},
        )
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        assert payload["tenant_id"] == 42
        assert payload["type"] == "refresh"

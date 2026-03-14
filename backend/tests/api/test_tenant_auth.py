#!/usr/bin/env python3
"""
企业管理员认证 API 测试模块

测试 /tenant/auth/* 接口

注意：需要先配置企业管理员账号才能运行此测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import (
    BaseAPITest,
    assert_error,
    assert_has_keys,
    assert_success,
    config,
)


class ManualTestTenantAuth(BaseAPITest):
    """企业管理员认证测试"""

    module_name = "企业管理员认证 (/tenant/auth)"

    def _run_tests(self) -> None:
        """运行所有测试"""
        # 检查是否配置了企业管理员账号
        skip_reason = None
        if not config.TENANT_ADMIN_USERNAME or not config.TENANT_ADMIN_PASSWORD:
            skip_reason = "未配置企业管理员账号，请在 config.py 中设置 TENANT_ADMIN_USERNAME 和 TENANT_ADMIN_PASSWORD"

        # 1. 测试登录 - 正确凭据
        self.run_test("登录 - 正确凭据", self.test_login_success, skip_reason)

        # 2. 测试登录 - 错误密码
        self.run_test("登录 - 错误密码", self.test_login_wrong_password, skip_reason)

        # 3. 测试获取当前用户信息 - 已认证
        self.run_test("获取当前用户信息 - 已认证", self.test_get_me_authenticated, skip_reason)

        # 4. 测试获取当前用户信息 - 未认证
        self.run_test("获取当前用户信息 - 未认证", self.test_get_me_unauthenticated)

        # 5. 测试刷新 Token - 有效 Token
        self.run_test("刷新 Token - 有效 Token", self.test_refresh_token_valid, skip_reason)

        # 6. 测试刷新 Token - 无效 Token
        self.run_test("刷新 Token - 无效 Token", self.test_refresh_token_invalid)

        # 7. 测试 scope 隔离 - TenantAdmin Token 访问平台接口应 401
        self.run_test("scope 隔离 - TenantAdmin Token 访问平台接口应 401", self.test_scope_isolation_tenant_admin_token_to_admin, skip_reason)

        # 8. 测试登出
        self.run_test("登出", self.test_logout, skip_reason)

    def test_login_success(self) -> None:
        """测试正确凭据登录"""
        resp = self.client.post("/tenant/auth/login", data={
            "username": config.TENANT_ADMIN_USERNAME,
            "password": config.TENANT_ADMIN_PASSWORD,
        })
        data = assert_success(resp, "登录失败")
        assert_has_keys(data["data"], ["access_token", "refresh_token", "token_type"])

        # 保存 token
        self._test_data["access_token"] = data["data"]["access_token"]
        self._test_data["refresh_token"] = data["data"]["refresh_token"]
        self.client.set_token(data["data"]["access_token"])

    def test_login_wrong_password(self) -> None:
        """测试错误密码登录"""
        resp = self.client.post("/tenant/auth/login", data={
            "username": config.TENANT_ADMIN_USERNAME,
            "password": "wrong_password",
        })
        assert_error(resp, 401, "应返回 401 错误")

    def test_get_me_authenticated(self) -> None:
        """测试已认证状态获取用户信息"""
        if not self.client.token:
            self._do_login()

        resp = self.client.get("/tenant/auth/me")
        data = assert_success(resp, "获取用户信息失败")
        assert_has_keys(data["data"], ["id", "username", "email", "is_owner", "is_active", "tenant_id"])

    def test_get_me_unauthenticated(self) -> None:
        """测试未认证状态获取用户信息"""
        old_token = self.client.token
        self.client.clear_token()

        try:
            resp = self.client.get("/tenant/auth/me")
            assert_error(resp, 401, "应返回 401 错误")
        finally:
            if old_token:
                self.client.set_token(old_token)

    def test_refresh_token_valid(self) -> None:
        """测试有效 Refresh Token 刷新"""
        refresh_token = self._test_data.get("refresh_token")
        if not refresh_token:
            self._do_login()
            refresh_token = self._test_data.get("refresh_token")

        resp = self.client.post("/tenant/auth/refresh", data={
            "refresh_token": refresh_token,
        })
        data = assert_success(resp, "刷新 Token 失败")
        assert_has_keys(data["data"], ["access_token", "refresh_token"])

        # 更新 token
        self._test_data["access_token"] = data["data"]["access_token"]
        self._test_data["refresh_token"] = data["data"]["refresh_token"]
        self.client.set_token(data["data"]["access_token"])

    def test_refresh_token_invalid(self) -> None:
        """测试无效 Refresh Token 刷新"""
        resp = self.client.post("/tenant/auth/refresh", data={
            "refresh_token": "invalid_refresh_token",
        })
        assert_error(resp, 401, "应返回 401 错误")

    def test_scope_isolation_tenant_admin_token_to_admin(self) -> None:
        """使用企业管理员 Token 访问平台管理员接口应返回 401"""
        if not self.client.token:
            self._do_login()
        resp = self.client.get("/admin/auth/me")
        assert_error(resp, 401, "TenantAdmin token 不应访问平台接口")

    def test_logout(self) -> None:
        """测试登出"""
        if not self.client.token:
            self._do_login()

        resp = self.client.post("/tenant/auth/logout")
        assert_success(resp, "登出失败")

    def _do_login(self) -> None:
        """执行登录"""
        if not config.TENANT_ADMIN_USERNAME or not config.TENANT_ADMIN_PASSWORD:
            raise AssertionError("未配置企业管理员账号")

        resp = self.client.post("/tenant/auth/login", data={
            "username": config.TENANT_ADMIN_USERNAME,
            "password": config.TENANT_ADMIN_PASSWORD,
        })
        data = resp.json()
        self._test_data["access_token"] = data["data"]["access_token"]
        self._test_data["refresh_token"] = data["data"]["refresh_token"]
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestTenantAuth()
    report = test.run_all()
    report.print_summary()


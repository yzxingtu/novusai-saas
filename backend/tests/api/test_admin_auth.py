#!/usr/bin/env python3
"""平台管理员认证 API 测试模块 / API.

测试 /admin/auth/* 接口"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import (
    BaseAPITest,
    assert_error,
    assert_equals,
    assert_has_keys,
    assert_success,
    config,
)


class ManualTestAdminAuth(BaseAPITest):
    """平台管理员认证测试 / Platform admin auth API tests."""

    module_name = "平台管理员认证 (/admin/auth)"

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        # 1. 测试登录 - 正确凭据
        self.run_test("登录 - 正确凭据", self.test_login_success)

        # 2. 测试登录 - 错误密码
        self.run_test("登录 - 错误密码", self.test_login_wrong_password)

        # 3. 测试登录 - 不存在的用户
        self.run_test("登录 - 不存在的用户", self.test_login_user_not_found)

        # 4. 测试获取当前用户信息 - 已认证
        self.run_test("获取当前用户信息 - 已认证", self.test_get_me_authenticated)

        # 5. 测试获取当前用户信息 - 未认证
        self.run_test("获取当前用户信息 - 未认证", self.test_get_me_unauthenticated)

        # 6. 测试刷新 Token - 有效 Token
        self.run_test("刷新 Token - 有效 Token", self.test_refresh_token_valid)

        # 7. 测试刷新 Token - 无效 Token
        self.run_test("刷新 Token - 无效 Token", self.test_refresh_token_invalid)

        # 8. 测试 scope 隔离 - Admin Token 访问企业接口应 401
        self.run_test("scope 隔离 - Admin Token 访问企业接口应 401", self.test_scope_isolation_admin_token_to_tenant)

        # 9. 测试修改密码 - 正确旧密码
        self.run_test("修改密码 - 正确旧密码", self.test_change_password_success)

        # 10. 测试修改密码 - 错误旧密码
        self.run_test("修改密码 - 错误旧密码", self.test_change_password_wrong_old)

        # 11. 测试登出
        self.run_test("登出", self.test_logout)

    def test_login_success(self) -> None:
        """测试正确凭据登录 / Test login with valid credentials."""
        resp = self.post_admin_login_request(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        data = assert_success(resp, "登录失败")
        assert_has_keys(data["data"], ["access_token", "refresh_token", "token_type"])

        # 保存 token 供后续测试使用
        self._test_data["access_token"] = data["data"]["access_token"]
        self._test_data["refresh_token"] = data["data"]["refresh_token"]
        self.client.set_token(data["data"]["access_token"])

    def test_login_wrong_password(self) -> None:
        """测试错误密码登录 / Test login with wrong password."""
        resp = self.post_admin_login_request(config.ADMIN_USERNAME, "wrong_password")
        assert_error(resp, 401, "应返回 401 错误")

    def test_login_user_not_found(self) -> None:
        """测试不存在的用户登录 / Test login with nonexistent user."""
        resp = self.post_admin_login_request("nonexistent_user", "any_password")
        assert_error(resp, 401, "应返回 401 错误")

    def test_get_me_authenticated(self) -> None:
        """测试已认证状态获取用户信息 / Test get me when authenticated."""
        # 确保已设置 token
        if not self.client.token:
            self._do_login()

        resp = self.client.get("/admin/auth/me")
        data = assert_success(resp, "获取用户信息失败")
        assert_has_keys(data["data"], ["id", "username", "email", "is_super", "is_active"])

    def test_get_me_unauthenticated(self) -> None:
        """测试未认证状态获取用户信息 / Test get me when unauthenticated."""
        # 临时清除 token
        old_token = self.client.token
        self.client.clear_token()

        try:
            resp = self.client.get("/admin/auth/me")
            assert_error(resp, 401, "应返回 401 错误")
        finally:
            # 恢复 token
            if old_token:
                self.client.set_token(old_token)

    def test_refresh_token_valid(self) -> None:
        """测试有效 Refresh Token 刷新 / Test valid refresh token."""
        refresh_token = self._test_data.get("refresh_token")
        if not refresh_token:
            self._do_login()
            refresh_token = self._test_data.get("refresh_token")

        resp = self.client.post("/admin/auth/refresh", data={
            "refresh_token": refresh_token,
        })
        data = assert_success(resp, "刷新 Token 失败")
        assert_has_keys(data["data"], ["access_token", "refresh_token"])

        # 更新 token
        self._test_data["access_token"] = data["data"]["access_token"]
        self._test_data["refresh_token"] = data["data"]["refresh_token"]
        self.client.set_token(data["data"]["access_token"])

    def test_refresh_token_invalid(self) -> None:
        """测试无效 Refresh Token 刷新 / Test invalid refresh token."""
        resp = self.client.post("/admin/auth/refresh", data={
            "refresh_token": "invalid_refresh_token",
        })
        assert_error(resp, 401, "应返回 401 错误")

    def test_scope_isolation_admin_token_to_tenant(self) -> None:
        """使用 Admin 的 Access Token 访问企业管理员受保护接口应返回 401 / Admin token to tenant API should 401."""
        if not self.client.token:
            self._do_login()
        # 使用 Admin token 请求企业管理员接口，应被 401 拒绝（scope 不匹配）
        resp = self.client.get("/tenant/auth/me")
        assert_error(resp, 401, "Admin token 不应访问企业接口")

    def test_change_password_success(self) -> None:
        """测试正确旧密码修改密码 / Test change password with correct old password."""
        if not self.client.token:
            self._do_login()

        # 修改密码
        new_password = config.ADMIN_PASSWORD + "_new"
        resp = self.client.put("/admin/auth/password", data={
            "old_password": config.ADMIN_PASSWORD,
            "new_password": new_password,
        })
        assert_success(resp, "修改密码失败")

        # 用新密码登录
        self.client.clear_token()
        resp = self.post_admin_login_request(config.ADMIN_USERNAME, new_password)
        data = assert_success(resp, "新密码登录失败")
        self.client.set_token(data["data"]["access_token"])

        # 改回原密码
        resp = self.client.put("/admin/auth/password", data={
            "old_password": new_password,
            "new_password": config.ADMIN_PASSWORD,
        })
        assert_success(resp, "恢复原密码失败")

    def test_change_password_wrong_old(self) -> None:
        """测试错误旧密码修改密码 / Test change password with wrong old password."""
        if not self.client.token:
            self._do_login()

        resp = self.client.put("/admin/auth/password", data={
            "old_password": "wrong_old_password",
            "new_password": "new_password_123",
        })
        data = assert_error(resp, 422, "应返回 422 业务错误")
        assert_equals(data.get("code"), 4004, "错误旧密码应返回 OLD_PASSWORD_INCORRECT")

    def test_logout(self) -> None:
        """测试登出 / Test logout."""
        if not self.client.token:
            self._do_login()

        resp = self.client.post("/admin/auth/logout")
        assert_success(resp, "登出失败")

    def _do_login(self) -> None:
        """执行登录获取 token / Do login to get token."""
        self.login_admin()


if __name__ == "__main__":
    test = ManualTestAdminAuth()
    report = test.run_all()
    report.print_summary()

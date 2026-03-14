#!/usr/bin/env python3
"""
企业管理员管理 API 测试模块

测试 /tenant/admins/* 接口

注意：需要先配置企业管理员（所有者）账号才能运行此测试
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import contextlib

from tests.api.base import (
    BaseAPITest,
    assert_equals,
    assert_error,
    assert_has_keys,
    assert_success,
    assert_true,
    config,
)


class ManualTestTenantAdmins(BaseAPITest):
    """企业管理员管理测试"""

    module_name = "企业管理员管理 (/tenant/admins)"

    def setup(self) -> None:
        """测试前登录"""
        if config.TENANT_ADMIN_USERNAME and config.TENANT_ADMIN_PASSWORD:
            self._do_login()
            # 生成唯一的测试用户名
            timestamp = int(time.time())
            self._test_data["test_username"] = f"test_tenant_admin_{timestamp}"
            self._test_data["test_email"] = f"tenant_test_{timestamp}@example.com"

    def teardown(self) -> None:
        """测试后清理"""
        admin_id = self._test_data.get("created_admin_id")
        if admin_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/tenant/admins/{admin_id}")

    def _run_tests(self) -> None:
        """运行所有测试"""
        skip_reason = None
        if not config.TENANT_ADMIN_USERNAME or not config.TENANT_ADMIN_PASSWORD:
            skip_reason = "未配置企业管理员账号"

        # 1. 获取管理员列表
        self.run_test("获取管理员列表", self.test_list_admins, skip_reason)

        # 2. 获取管理员列表 - 分页
        self.run_test("获取管理员列表 - 分页", self.test_list_admins_pagination, skip_reason)

        # 3. 创建管理员
        self.run_test("创建管理员", self.test_create_admin, skip_reason)

        # 4. 获取管理员详情
        self.run_test("获取管理员详情", self.test_get_admin_detail, skip_reason)

        # 5. 更新管理员
        self.run_test("更新管理员", self.test_update_admin, skip_reason)

        # 6. 切换管理员状态
        self.run_test("切换管理员状态", self.test_toggle_admin_status, skip_reason)

        # 7. 重置管理员密码
        self.run_test("重置管理员密码", self.test_reset_admin_password, skip_reason)

        # 8. 删除管理员
        self.run_test("删除管理员", self.test_delete_admin, skip_reason)

        # 9. 删除自己 - 应失败
        self.run_test("删除自己 - 应失败", self.test_delete_self, skip_reason)

    def test_list_admins(self) -> None:
        """测试获取管理员列表"""
        resp = self.client.get("/tenant/admins")
        data = assert_success(resp, "获取管理员列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_list_admins_pagination(self) -> None:
        """测试获取管理员列表 - 分页"""
        resp = self.client.get("/tenant/admins", params={"page": 1, "page_size": 5})
        data = assert_success(resp, "获取管理员列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)

    def test_create_admin(self) -> None:
        """测试创建管理员"""
        resp = self.client.post("/tenant/admins", data={
            "username": self._test_data["test_username"],
            "email": self._test_data["test_email"],
            "password": "test123456",
            "nickname": "企业测试管理员",
            "is_active": True,
            "is_owner": False,
        })
        data = assert_success(resp, "创建管理员失败")

        assert_has_keys(data["data"], ["id", "username", "email", "is_active", "tenant_id"])
        assert_equals(data["data"]["username"], self._test_data["test_username"])

        self._test_data["created_admin_id"] = data["data"]["id"]

    def test_get_admin_detail(self) -> None:
        """测试获取管理员详情"""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        resp = self.client.get(f"/tenant/admins/{admin_id}")
        data = assert_success(resp, "获取管理员详情失败")

        assert_has_keys(data["data"], ["id", "username", "email", "is_active", "is_owner"])

    def test_update_admin(self) -> None:
        """测试更新管理员"""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        new_nickname = "更新后的昵称"
        resp = self.client.put(f"/tenant/admins/{admin_id}", data={
            "nickname": new_nickname,
        })
        data = assert_success(resp, "更新管理员失败")
        assert_equals(data["data"]["nickname"], new_nickname)

    def test_toggle_admin_status(self) -> None:
        """测试切换管理员状态"""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        # 禁用
        resp = self.client.put(f"/tenant/admins/{admin_id}/status", params={"is_active": False})
        data = assert_success(resp, "禁用管理员失败")
        assert_equals(data["data"]["is_active"], False)

        # 启用
        resp = self.client.put(f"/tenant/admins/{admin_id}/status", params={"is_active": True})
        data = assert_success(resp, "启用管理员失败")
        assert_equals(data["data"]["is_active"], True)

    def test_reset_admin_password(self) -> None:
        """测试重置管理员密码"""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        new_password = "new_password_123"
        resp = self.client.put(f"/tenant/admins/{admin_id}/reset-password", data={
            "new_password": new_password,
        })
        assert_success(resp, "重置密码失败")

        # 验证新密码可以登录
        login_resp = self.client.post("/tenant/auth/login", data={
            "username": self._test_data["test_username"],
            "password": new_password,
        })
        assert_success(login_resp, "使用新密码登录失败")

    def test_delete_admin(self) -> None:
        """测试删除管理员"""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        resp = self.client.delete(f"/tenant/admins/{admin_id}")
        assert_success(resp, "删除管理员失败")

        # 验证已删除
        check_resp = self.client.get(f"/tenant/admins/{admin_id}")
        assert_error(check_resp, 404, "管理员应已被删除")

        del self._test_data["created_admin_id"]

    def test_delete_self(self) -> None:
        """测试删除自己 - 应失败"""
        # 获取当前管理员信息
        me_resp = self.client.get("/tenant/auth/me")
        me_data = me_resp.json()
        my_id = me_data["data"]["id"]

        # 尝试删除自己
        resp = self.client.delete(f"/tenant/admins/{my_id}")
        assert_error(resp, 400, "不应允许删除自己")

    def _do_login(self) -> None:
        """执行登录"""
        resp = self.client.post("/tenant/auth/login", data={
            "username": config.TENANT_ADMIN_USERNAME,
            "password": config.TENANT_ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestTenantAdmins()
    report = test.run_all()
    report.print_summary()


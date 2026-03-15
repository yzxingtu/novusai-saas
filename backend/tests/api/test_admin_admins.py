#!/usr/bin/env python3
"""平台管理员管理 API 测试模块 / API.

测试 /admin/admins/* 接口"""
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


class ManualTestAdminAdmins(BaseAPITest):
    """平台管理员管理测试 / Platform admin management API tests."""

    module_name = "平台管理员管理 (/admin/admins)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()
        # 生成唯一的测试用户名
        timestamp = int(time.time())
        self._test_data["test_username"] = f"test_admin_{timestamp}"
        self._test_data["test_email"] = f"test_{timestamp}@example.com"

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        # 尝试删除测试创建的管理员
        admin_id = self._test_data.get("created_admin_id")
        if admin_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/admins/{admin_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        # 1. 获取管理员列表
        self.run_test("获取管理员列表", self.test_list_admins)

        # 2. 获取管理员列表 - 分页
        self.run_test("获取管理员列表 - 分页", self.test_list_admins_pagination)

        # 3. 获取管理员列表 - 按状态过滤
        self.run_test("获取管理员列表 - 按状态过滤", self.test_list_admins_filter_status)

        # 4. 创建管理员
        self.run_test("创建管理员", self.test_create_admin)

        # 5. 创建管理员 - 重复用户名
        self.run_test("创建管理员 - 重复用户名", self.test_create_admin_duplicate_username)

        # 6. 获取管理员详情
        self.run_test("获取管理员详情", self.test_get_admin_detail)

        # 7. 获取管理员详情 - 不存在
        self.run_test("获取管理员详情 - 不存在", self.test_get_admin_not_found)

        # 8. 更新管理员
        self.run_test("更新管理员", self.test_update_admin)

        # 9. 切换管理员状态
        self.run_test("切换管理员状态", self.test_toggle_admin_status)

        # 10. 重置管理员密码
        self.run_test("重置管理员密码", self.test_reset_admin_password)

        # 11. 删除管理员
        self.run_test("删除管理员", self.test_delete_admin)

        # 12. 删除自己 - 应失败
        self.run_test("删除自己 - 应失败", self.test_delete_self)

    def test_list_admins(self) -> None:
        """测试获取管理员列表 / Test get admin list."""
        resp = self.client.get("/admin/admins")
        data = assert_success(resp, "获取管理员列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_list_admins_pagination(self) -> None:
        """测试获取管理员列表 - 分页 / Test get admin list with pagination."""
        resp = self.client.get("/admin/admins", params={"page": 1, "page_size": 5})
        data = assert_success(resp, "获取管理员列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)
        assert_true(len(data["data"]["items"]) <= 5, "返回数量应不超过 page_size")

    def test_list_admins_filter_status(self) -> None:
        """测试获取管理员列表 - 按状态过滤 / Test get admin list filtered by status."""
        resp = self.client.get("/admin/admins", params={"is_active": True})
        data = assert_success(resp, "获取管理员列表失败")

        # 验证所有返回的管理员都是激活状态
        for admin in data["data"]["items"]:
            assert_true(admin["is_active"], "管理员应为激活状态")

    def test_create_admin(self) -> None:
        """测试创建管理员 / Test create admin."""
        resp = self.client.post("/admin/admins", data={
            "username": self._test_data["test_username"],
            "email": self._test_data["test_email"],
            "password": "test123456",
            "nickname": "测试管理员",
            "is_active": True,
            "is_super": False,
        })
        data = assert_success(resp, "创建管理员失败")

        assert_has_keys(data["data"], ["id", "username", "email", "is_active"])
        assert_equals(data["data"]["username"], self._test_data["test_username"])

        # 保存管理员ID供后续测试使用
        self._test_data["created_admin_id"] = data["data"]["id"]

    def test_create_admin_duplicate_username(self) -> None:
        """测试创建重复用户名的管理员 / Test create admin with duplicate username."""
        # 使用已存在的超级管理员用户名
        resp = self.client.post("/admin/admins", data={
            "username": config.ADMIN_USERNAME,
            "email": "another@example.com",
            "password": "test123456",
        })
        assert_error(resp, 400, "应返回 400 错误")

    def test_get_admin_detail(self) -> None:
        """测试获取管理员详情 / Test get admin detail."""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        resp = self.client.get(f"/admin/admins/{admin_id}")
        data = assert_success(resp, "获取管理员详情失败")

        assert_has_keys(data["data"], ["id", "username", "email", "is_active", "is_super"])
        assert_equals(data["data"]["id"], admin_id)

    def test_get_admin_not_found(self) -> None:
        """测试获取不存在的管理员详情 / Test get nonexistent admin detail."""
        resp = self.client.get("/admin/admins/999999")
        assert_error(resp, 404, "应返回 404 错误")

    def test_update_admin(self) -> None:
        """测试更新管理员 / Test update admin."""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        new_nickname = "更新后的昵称"
        resp = self.client.put(f"/admin/admins/{admin_id}", data={
            "nickname": new_nickname,
        })
        data = assert_success(resp, "更新管理员失败")
        assert_equals(data["data"]["nickname"], new_nickname)

    def test_toggle_admin_status(self) -> None:
        """测试切换管理员状态 / Test toggle admin status."""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        # 禁用管理员
        resp = self.client.put(f"/admin/admins/{admin_id}/status", params={"is_active": False})
        data = assert_success(resp, "禁用管理员失败")
        assert_equals(data["data"]["is_active"], False)

        # 启用管理员
        resp = self.client.put(f"/admin/admins/{admin_id}/status", params={"is_active": True})
        data = assert_success(resp, "启用管理员失败")
        assert_equals(data["data"]["is_active"], True)

    def test_reset_admin_password(self) -> None:
        """测试重置管理员密码 / Test reset admin password."""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        new_password = "new_password_123"
        resp = self.client.put(f"/admin/admins/{admin_id}/reset-password", data={
            "new_password": new_password,
        })
        assert_success(resp, "重置密码失败")

        # 验证新密码可以登录
        login_resp = self.client.post("/admin/auth/login", data={
            "username": self._test_data["test_username"],
            "password": new_password,
        })
        assert_success(login_resp, "使用新密码登录失败")

    def test_delete_admin(self) -> None:
        """测试删除管理员 / Test delete admin."""
        admin_id = self._test_data.get("created_admin_id")
        if not admin_id:
            raise AssertionError("没有可用的管理员ID")

        resp = self.client.delete(f"/admin/admins/{admin_id}")
        assert_success(resp, "删除管理员失败")

        # 验证已删除
        check_resp = self.client.get(f"/admin/admins/{admin_id}")
        assert_error(check_resp, 404, "管理员应已被删除")

        # 清除ID，避免 teardown 再次尝试删除
        del self._test_data["created_admin_id"]

    def test_delete_self(self) -> None:
        """测试删除自己 - 应失败 / Test delete self should fail."""
        # 获取当前管理员信息
        me_resp = self.client.get("/admin/auth/me")
        me_data = me_resp.json()
        my_id = me_data["data"]["id"]

        # 尝试删除自己
        resp = self.client.delete(f"/admin/admins/{my_id}")
        assert_error(resp, 400, "不应允许删除自己")

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestAdminAdmins()
    report = test.run_all()
    report.print_summary()


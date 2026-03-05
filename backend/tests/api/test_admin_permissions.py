#!/usr/bin/env python3
"""
平台管理员权限 API 测试模块

测试 /admin/permissions/* 接口
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import (
    BaseAPITest,
    assert_error,
    assert_has_keys,
    assert_success,
    assert_true,
    config,
)


class ManualTestAdminPermissions(BaseAPITest):
    """平台管理员权限测试"""

    module_name = "平台权限管理 (/admin/permissions)"

    def setup(self) -> None:
        """测试前登录"""
        self._do_login()

    def _run_tests(self) -> None:
        """运行所有测试"""
        # 1. 获取权限树
        self.run_test("获取权限树", self.test_get_permission_tree)

        # 2. 获取权限列表（平铺）
        self.run_test("获取权限列表（平铺）", self.test_get_permission_list)

        # 3. 获取权限列表 - 按类型过滤（menu）
        self.run_test("获取权限列表 - 按类型过滤（menu）", self.test_get_permission_list_filter_menu)

        # 4. 获取权限列表 - 按类型过滤（operation）
        self.run_test("获取权限列表 - 按类型过滤（operation）", self.test_get_permission_list_filter_operation)

        # 5. 获取当前用户菜单
        self.run_test("获取当前用户菜单", self.test_get_current_user_menus)

        # 6. 获取权限树 - 未认证
        self.run_test("获取权限树 - 未认证", self.test_get_permission_tree_unauthenticated)

    def test_get_permission_tree(self) -> None:
        """测试获取权限树"""
        resp = self.client.get("/admin/permissions")
        data = assert_success(resp, "获取权限树失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "权限树应为列表")

    def test_get_permission_list(self) -> None:
        """测试获取权限列表（平铺）"""
        resp = self.client.get("/admin/permissions/list")
        data = assert_success(resp, "获取权限列表失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "权限列表应为列表")

        # 如果有数据，验证结构
        if data["data"]:
            first_perm = data["data"][0]
            assert_has_keys(first_perm, ["id", "code", "name", "type", "scope"])

    def test_get_permission_list_filter_menu(self) -> None:
        """测试获取菜单类型权限"""
        resp = self.client.get("/admin/permissions/list", params={"type": "menu"})
        data = assert_success(resp, "获取菜单权限列表失败")

        # 验证所有返回项都是菜单类型
        for perm in data["data"]:
            assert_true(perm["type"] == "menu", f"权限类型应为 menu，实际为 {perm['type']}")

    def test_get_permission_list_filter_operation(self) -> None:
        """测试获取操作类型权限"""
        resp = self.client.get("/admin/permissions/list", params={"type": "operation"})
        data = assert_success(resp, "获取操作权限列表失败")

        # 验证所有返回项都是操作类型
        for perm in data["data"]:
            assert_true(perm["type"] == "operation", f"权限类型应为 operation，实际为 {perm['type']}")

    def test_get_current_user_menus(self) -> None:
        """测试获取当前用户菜单"""
        resp = self.client.get("/admin/permissions/menus")
        data = assert_success(resp, "获取用户菜单失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "菜单应为列表")

        # 超级管理员应该能看到菜单
        # 注意：如果没有初始化菜单数据，列表可能为空

    def test_get_permission_tree_unauthenticated(self) -> None:
        """测试未认证获取权限树"""
        old_token = self.client.token
        self.client.clear_token()

        try:
            resp = self.client.get("/admin/permissions")
            assert_error(resp, 401, "应返回 401 错误")
        finally:
            self.client.set_token(old_token)

    def _do_login(self) -> None:
        """执行登录"""
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestAdminPermissions()
    report = test.run_all()
    report.print_summary()


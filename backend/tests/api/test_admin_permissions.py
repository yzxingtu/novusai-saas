#!/usr/bin/env python3
"""平台管理员权限 API 测试模块 / API.

测试 /admin/permissions/* 接口"""

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from tests.api.base import (
    BaseAPITest,
    assert_error,
    assert_has_keys,
    assert_success,
    assert_true,
)


class ManualTestAdminPermissions(BaseAPITest):
    """平台管理员权限测试 / Test."""

    module_name = "平台权限管理 (/admin/permissions)"

    def setup(self) -> None:
        """测试前登录 / Test."""
        self._do_login()

    def _run_tests(self) -> None:
        """运行所有测试 / Test."""
        # 1. 获取权限树
        self.run_test("获取权限树", self.test_get_permission_tree)

        # 2. 获取权限树并展平校验
        self.run_test("获取权限树并展平校验", self.test_get_permission_list)

        # 3. 权限树包含菜单节点
        self.run_test("权限树包含菜单节点", self.test_get_permission_list_filter_menu)

        # 4. 权限树包含操作节点
        self.run_test(
            "权限树包含操作节点", self.test_get_permission_list_filter_operation
        )

        # 5. 获取当前用户菜单
        self.run_test("获取当前用户菜单", self.test_get_current_user_menus)

        # 6. 获取权限树 - 未认证
        self.run_test(
            "获取权限树 - 未认证", self.test_get_permission_tree_unauthenticated
        )

    def test_get_permission_tree(self) -> None:
        """测试获取权限树 / Test."""
        resp = self.client.get("/admin/permissions")
        data = assert_success(resp, "获取权限树失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "权限树应为列表")

    def test_get_permission_list(self) -> None:
        """测试获取权限树并展平校验 / Test."""
        data = self._get_permission_tree_data()
        flat_permissions = self._flatten_permission_tree(data["data"])

        assert_true(isinstance(flat_permissions, list), "展平后的权限列表应为列表")

        # 如果有数据，验证结构
        if flat_permissions:
            first_perm = flat_permissions[0]
            assert_has_keys(first_perm, ["id", "code", "name", "type", "scope"])

    def test_get_permission_list_filter_menu(self) -> None:
        """测试权限树包含菜单类型权限 / Test."""
        data = self._get_permission_tree_data()
        menu_permissions = [
            permission
            for permission in self._flatten_permission_tree(data["data"])
            if permission.get("type") == "menu"
        ]

        assert_true(bool(menu_permissions), "权限树中应至少包含一个 menu 类型权限")
        for perm in menu_permissions:
            assert_true(
                perm["type"] == "menu", f"权限类型应为 menu，实际为 {perm['type']}"
            )

    def test_get_permission_list_filter_operation(self) -> None:
        """测试权限树包含操作类型权限 / Test."""
        data = self._get_permission_tree_data()
        operation_permissions = [
            permission
            for permission in self._flatten_permission_tree(data["data"])
            if permission.get("type") == "operation"
        ]

        assert_true(
            bool(operation_permissions), "权限树中应至少包含一个 operation 类型权限"
        )
        for perm in operation_permissions:
            assert_true(
                perm["type"] == "operation",
                f"权限类型应为 operation，实际为 {perm['type']}",
            )

    def test_get_current_user_menus(self) -> None:
        """测试获取当前用户菜单 / Test."""
        resp = self.client.get("/admin/permissions/menus")
        data = assert_success(resp, "获取用户菜单失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "菜单应为列表")

        # 超级管理员应该能看到菜单
        # 注意：如果没有初始化菜单数据，列表可能为空

    def test_get_permission_tree_unauthenticated(self) -> None:
        """测试未认证获取权限树 / Test."""
        old_token = self.client.token
        self.client.clear_token()

        try:
            resp = self.client.get("/admin/permissions")
            assert_error(resp, 401, "应返回 401 错误")
        finally:
            self.client.set_token(old_token)

    def _do_login(self) -> None:
        """执行登录 / Description."""
        self.login_admin()

    def _get_permission_tree_data(self) -> dict:
        resp = self.client.get("/admin/permissions")
        return assert_success(resp, "获取权限树失败")

    def _flatten_permission_tree(self, nodes: list[dict]) -> list[dict]:
        flattened: list[dict] = []

        def collect(items: list[dict]) -> None:
            for item in items:
                flattened.append(item)
                children = item.get("children") or []
                if children:
                    collect(children)

        collect(nodes)
        return flattened


if __name__ == "__main__":
    test = ManualTestAdminPermissions()
    report = test.run_all()
    report.print_summary()

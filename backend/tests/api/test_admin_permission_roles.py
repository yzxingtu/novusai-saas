#!/usr/bin/env python3
"""平台权限角色管理 API 测试模块 / API.

测试 /admin/permission-roles/* 接口
"""
import contextlib
import os
import sys
import time

try:
    from tests.api.base import (  # noqa: I001
        BaseAPITest,
        assert_error,
        assert_equals,
        assert_has_keys,
        assert_success,
        assert_true,
        config,
    )
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tests.api.base import (  # noqa: I001
        BaseAPITest,
        assert_error,
        assert_equals,
        assert_has_keys,
        assert_success,
        assert_true,
        config,
    )


class ManualTestAdminPermissionRoles(BaseAPITest):
    """平台权限角色管理测试 / Platform permission role API tests."""

    module_name = "平台权限角色管理 (/admin/permission-roles)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()
        timestamp = int(time.time())
        self._test_data["role_name"] = f"测试权限角色_{timestamp}"

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        role_id = self._test_data.get("created_role_id")
        if role_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/permission-roles/{role_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        self.run_test("获取权限角色列表", self.test_list_permission_roles)
        self.run_test("创建权限角色", self.test_create_permission_role)
        self.run_test("获取权限角色详情", self.test_get_permission_role_detail)
        self.run_test("更新权限角色", self.test_update_permission_role)
        self.run_test("分配权限", self.test_assign_permissions)
        self.run_test("获取有效权限", self.test_get_effective_permissions)
        self.run_test("删除权限角色", self.test_delete_permission_role)

    def _get_permission_ids(self, count: int = 3) -> list[int]:
        resp = self.client.get("/admin/permissions")
        data = assert_success(resp, "获取平台权限树失败")

        permission_ids: list[int] = []

        def collect(nodes: list[dict]) -> None:
            for node in nodes:
                node_id = node.get("id")
                if node_id is not None:
                    permission_ids.append(node_id)
                children = node.get("children") or []
                if children:
                    collect(children)

        collect(data.get("data", []))
        permission_ids = permission_ids[:count]
        if not permission_ids:
            raise AssertionError("平台权限列表为空，无法测试权限角色分配")
        return permission_ids

    def test_list_permission_roles(self) -> None:
        """测试获取权限角色列表 / Test list permission roles."""
        resp = self.client.get(
            "/admin/permission-roles",
            params={"page[number]": 1, "page[size]": 10},
        )
        data = assert_success(resp, "获取权限角色列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_create_permission_role(self) -> None:
        """测试创建权限角色 / Test create permission role."""
        resp = self.client.post(
            "/admin/permission-roles",
            data={
                "name": self._test_data["role_name"],
                "description": "API 测试创建的平台权限角色",
                "is_active": True,
                "sort_order": 100,
            },
        )
        data = assert_success(resp, "创建权限角色失败")

        assert_has_keys(data["data"], ["id", "code", "name", "permission_ids", "permission_codes"])
        assert_equals(data["data"]["name"], self._test_data["role_name"])
        self._test_data["created_role_id"] = data["data"]["id"]

    def test_get_permission_role_detail(self) -> None:
        """测试获取权限角色详情 / Test get permission role detail."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        resp = self.client.get(f"/admin/permission-roles/{role_id}")
        data = assert_success(resp, "获取权限角色详情失败")

        assert_has_keys(data["data"], ["id", "code", "name", "permission_ids", "permission_codes"])
        assert_equals(data["data"]["id"], role_id)

    def test_update_permission_role(self) -> None:
        """测试更新权限角色 / Test update permission role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        new_name = f"{self._test_data['role_name']}_已更新"
        resp = self.client.put(
            f"/admin/permission-roles/{role_id}",
            data={
                "name": new_name,
                "description": "已更新的平台权限角色",
            },
        )
        data = assert_success(resp, "更新权限角色失败")

        assert_equals(data["data"]["name"], new_name)
        self._test_data["role_name"] = new_name

    def test_assign_permissions(self) -> None:
        """测试分配权限 / Test assign permissions."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        permission_ids = self._get_permission_ids()
        resp = self.client.put(
            f"/admin/permission-roles/{role_id}/permissions",
            data={"permission_ids": permission_ids},
        )
        data = assert_success(resp, "分配权限失败")

        assert_true(
            set(permission_ids).issubset(set(data["data"]["permission_ids"])),
            "权限未正确分配到平台权限角色",
        )

    def test_get_effective_permissions(self) -> None:
        """测试获取有效权限 / Test get effective permissions."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        resp = self.client.get(f"/admin/permission-roles/{role_id}/permissions/effective")
        data = assert_success(resp, "获取有效权限失败")
        assert_true(isinstance(data["data"], list), "有效权限应为列表")
        assert_true(len(data["data"]) >= 1, "有效权限结果不应为空")

    def test_delete_permission_role(self) -> None:
        """测试删除权限角色 / Test delete permission role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        resp = self.client.delete(f"/admin/permission-roles/{role_id}")
        assert_success(resp, "删除权限角色失败")

        check_resp = self.client.get(f"/admin/permission-roles/{role_id}")
        assert_error(check_resp, 404, "权限角色应已被删除")
        del self._test_data["created_role_id"]

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        self.login_admin()


if __name__ == "__main__":
    test = ManualTestAdminPermissionRoles()
    report = test.run_all()
    report.print_summary()

#!/usr/bin/env python3
"""企业权限角色管理 API 测试模块 / API.

测试 /tenant/permission-roles/* 接口
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import contextlib

from tests.api.base import (
    BaseAPITest,
    assert_error,
    assert_equals,
    assert_has_keys,
    assert_success,
    assert_tenant_login_success,
    assert_true,
    config,
)


class ManualTestTenantPermissionRoles(BaseAPITest):
    """企业权限角色管理测试 / Tenant permission role API tests."""

    module_name = "企业权限角色管理 (/tenant/permission-roles)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        if config.TENANT_ADMIN_USERNAME and config.TENANT_ADMIN_PASSWORD:
            self._do_login()
            timestamp = int(time.time())
            self._test_data["role_name"] = f"企业权限角色_{timestamp}"

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        role_id = self._test_data.get("created_role_id")
        if role_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/tenant/permission-roles/{role_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        skip_reason = None
        if not config.TENANT_ADMIN_USERNAME or not config.TENANT_ADMIN_PASSWORD:
            skip_reason = "未配置企业管理员账号"

        self.run_test("获取权限角色列表", self.test_list_permission_roles, skip_reason)
        self.run_test("创建权限角色", self.test_create_permission_role, skip_reason)
        self.run_test("获取权限角色详情", self.test_get_permission_role_detail, skip_reason)
        self.run_test("更新权限角色", self.test_update_permission_role, skip_reason)
        self.run_test("分配权限", self.test_assign_permissions, skip_reason)
        self.run_test("删除权限角色", self.test_delete_permission_role, skip_reason)

    def _get_permission_ids(self, count: int = 3) -> list[int]:
        resp = self.client.get("/tenant/permissions")
        data = assert_success(resp, "获取企业权限树失败")

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
            raise AssertionError("企业权限列表为空，无法测试权限角色分配")
        return permission_ids

    def test_list_permission_roles(self) -> None:
        """测试获取权限角色列表 / Test list permission roles."""
        resp = self.client.get(
            "/tenant/permission-roles",
            params={"page[number]": 1, "page[size]": 10},
        )
        data = assert_success(resp, "获取权限角色列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_create_permission_role(self) -> None:
        """测试创建权限角色 / Test create permission role."""
        resp = self.client.post(
            "/tenant/permission-roles",
            data={
                "name": self._test_data["role_name"],
                "description": "API 测试创建的企业权限角色",
                "is_active": True,
                "sort_order": 100,
            },
        )
        data = assert_success(resp, "创建权限角色失败")

        assert_has_keys(data["data"], ["id", "tenant_id", "name", "permission_ids", "permission_codes"])
        assert_equals(data["data"]["name"], self._test_data["role_name"])
        self._test_data["created_role_id"] = data["data"]["id"]

    def test_get_permission_role_detail(self) -> None:
        """测试获取权限角色详情 / Test get permission role detail."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        resp = self.client.get(f"/tenant/permission-roles/{role_id}")
        data = assert_success(resp, "获取权限角色详情失败")

        assert_has_keys(data["data"], ["id", "tenant_id", "name", "permission_ids", "permission_codes"])
        assert_equals(data["data"]["id"], role_id)

    def test_update_permission_role(self) -> None:
        """测试更新权限角色 / Test update permission role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        new_name = f"{self._test_data['role_name']}_已更新"
        resp = self.client.put(
            f"/tenant/permission-roles/{role_id}",
            data={
                "name": new_name,
                "description": "已更新的企业权限角色",
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
            f"/tenant/permission-roles/{role_id}/permissions",
            data={"permission_ids": permission_ids},
        )
        data = assert_success(resp, "分配权限失败")

        assert_true(
            set(permission_ids).issubset(set(data["data"]["permission_ids"])),
            "权限未正确分配到企业权限角色",
        )

    def test_delete_permission_role(self) -> None:
        """测试删除权限角色 / Test delete permission role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的权限角色 ID")

        resp = self.client.delete(f"/tenant/permission-roles/{role_id}")
        assert_success(resp, "删除权限角色失败")

        check_resp = self.client.get(f"/tenant/permission-roles/{role_id}")
        assert_error(check_resp, 404, "权限角色应已被删除")
        del self._test_data["created_role_id"]

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        self.login_tenant_admin()


if __name__ == "__main__":
    test = ManualTestTenantPermissionRoles()
    report = test.run_all()
    report.print_summary()

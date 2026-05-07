#!/usr/bin/env python3
"""平台权限绑定 API 测试模块 / API.

覆盖当前已暴露的 /admin/permissions 与 /admin/organization 上的权限绑定能力。
"""

import contextlib
import os
import sys
import time

try:
    from tests.api.base import (  # noqa: I001
        BaseAPITest,
        assert_equals,
        assert_has_keys,
        assert_success,
        assert_true,
    )
except ModuleNotFoundError:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    from tests.api.base import (  # noqa: I001
        BaseAPITest,
        assert_equals,
        assert_has_keys,
        assert_success,
        assert_true,
    )


class ManualTestAdminPermissionRoles(BaseAPITest):
    """平台权限绑定测试 / Platform permission binding API tests."""

    module_name = "平台权限绑定 (/admin/permissions + /admin/organization)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()
        timestamp = int(time.time())
        self._test_data["org_node_name"] = f"权限绑定节点_{timestamp}"

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        org_node_id = self._test_data.get("created_org_node_id")
        if org_node_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/organization/{org_node_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        self.run_test("获取平台权限树", self.test_get_permission_tree)
        self.run_test(
            "创建带权限的组织节点", self.test_create_org_node_with_permissions
        )
        self.run_test("获取组织节点权限详情", self.test_get_org_node_detail)
        self.run_test("更新组织节点权限绑定", self.test_update_permission_bindings)
        self.run_test("清空组织节点权限绑定", self.test_clear_permission_bindings)
        self.run_test("删除权限绑定测试节点", self.test_delete_org_node)

    def test_get_permission_tree(self) -> None:
        """测试获取平台权限树 / Test get permission tree."""
        resp = self.client.get("/admin/permissions")
        data = assert_success(resp, "获取平台权限树失败")
        assert_true(isinstance(data["data"], list), "权限树应为列表")
        permission_ids = self._collect_permission_ids(data["data"])
        assert_true(bool(permission_ids), "权限树不应为空")
        self._test_data["permission_ids"] = permission_ids

    def test_create_org_node_with_permissions(self) -> None:
        """测试创建带权限的组织节点 / Test create organization node with permissions."""
        permission_ids = self._ensure_permission_ids()
        initial_permission_ids = permission_ids[:2]

        resp = self.client.post(
            "/admin/organization",
            data={
                "name": self._test_data["org_node_name"],
                "description": "权限绑定 API 测试节点",
                "type": "department",
                "allow_members": True,
                "is_active": True,
                "sort_order": 10,
                "data_scope": "dept_children",
                "permission_ids": initial_permission_ids,
            },
        )
        data = assert_success(resp, "创建带权限的组织节点失败")

        assert_has_keys(data["data"], ["id", "name", "permissions_count"])
        assert_equals(data["data"]["name"], self._test_data["org_node_name"])
        self._test_data["created_org_node_id"] = data["data"]["id"]
        self._test_data["expected_permission_ids"] = initial_permission_ids

    def test_get_org_node_detail(self) -> None:
        """测试获取组织节点权限详情 / Test get organization node permission detail."""
        org_node_id = self._test_data.get("created_org_node_id")
        expected_permission_ids = self._test_data.get("expected_permission_ids")
        if not org_node_id or expected_permission_ids is None:
            raise AssertionError("没有可用的组织节点 ID 或权限绑定信息")

        resp = self.client.get(f"/admin/organization/{org_node_id}")
        data = assert_success(resp, "获取组织节点详情失败")

        assert_has_keys(data["data"], ["id", "permission_ids", "permission_codes"])
        assert_true(
            set(expected_permission_ids).issubset(set(data["data"]["permission_ids"])),
            "组织节点权限绑定与预期不一致",
        )

    def test_update_permission_bindings(self) -> None:
        """测试更新组织节点权限绑定 / Test update permission bindings."""
        org_node_id = self._test_data.get("created_org_node_id")
        permission_ids = self._ensure_permission_ids()
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        updated_permission_ids = permission_ids[1:4] or permission_ids[:1]
        resp = self.client.put(
            f"/admin/organization/{org_node_id}",
            data={"permission_ids": updated_permission_ids},
        )
        data = assert_success(resp, "更新组织节点权限绑定失败")

        assert_equals(data["data"]["id"], org_node_id)
        self._test_data["expected_permission_ids"] = updated_permission_ids

    def test_clear_permission_bindings(self) -> None:
        """测试清空组织节点权限绑定 / Test clear permission bindings."""
        org_node_id = self._test_data.get("created_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}",
            data={"permission_ids": []},
        )
        assert_success(resp, "清空组织节点权限绑定失败")

        detail_resp = self.client.get(f"/admin/organization/{org_node_id}")
        detail_data = assert_success(detail_resp, "获取清空后的组织节点详情失败")
        assert_equals(detail_data["data"]["permission_ids"], [])
        self._test_data["expected_permission_ids"] = []

    def test_delete_org_node(self) -> None:
        """测试删除权限绑定测试节点 / Test delete organization node."""
        org_node_id = self._test_data.get("created_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}")
        assert_success(resp, "删除权限绑定测试节点失败")
        self._test_data.pop("created_org_node_id", None)

    def _collect_permission_ids(self, nodes: list[dict]) -> list[int]:
        permission_ids: list[int] = []

        def walk(items: list[dict]) -> None:
            for item in items:
                node_id = item.get("id")
                if node_id is not None:
                    permission_ids.append(node_id)
                children = item.get("children") or []
                if children:
                    walk(children)

        walk(nodes)
        return permission_ids

    def _ensure_permission_ids(self) -> list[int]:
        permission_ids = self._test_data.get("permission_ids")
        if permission_ids:
            return permission_ids

        resp = self.client.get("/admin/permissions")
        data = assert_success(resp, "获取平台权限树失败")
        permission_ids = self._collect_permission_ids(data["data"])
        if not permission_ids:
            raise AssertionError("平台权限树为空，无法测试权限绑定")
        self._test_data["permission_ids"] = permission_ids
        return permission_ids

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        self.login_admin()


if __name__ == "__main__":
    test = ManualTestAdminPermissionRoles()
    report = test.run_all()
    report.print_summary()

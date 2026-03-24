#!/usr/bin/env python3
"""平台组织架构管理 API 测试模块 / API.

测试 /admin/organization/* 接口
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import contextlib

from tests.api.base import (
    BaseAPITest,
    assert_equals,
    assert_has_keys,
    assert_success,
    assert_true,
    config,
)


class ManualTestAdminOrganization(BaseAPITest):
    """平台组织架构管理测试 / Platform organization API tests."""

    module_name = "平台组织架构管理 (/admin/organization)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()
        timestamp = int(time.time())
        self._test_data.update(
            {
                "primary_name": f"测试部门_{timestamp}",
                "secondary_name": f"转移部门_{timestamp}",
                "member_username": f"test_org_admin_{timestamp}",
                "member_email": f"test_org_admin_{timestamp}@example.com",
            }
        )

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        admin_id = self._test_data.get("created_admin_id")
        if admin_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/admins/{admin_id}")

        for key in ("secondary_org_node_id", "primary_org_node_id"):
            org_node_id = self._test_data.get(key)
            if org_node_id:
                with contextlib.suppress(Exception):
                    self.client.delete(f"/admin/organization/{org_node_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        self.run_test("获取组织根节点和组织树", self.test_list_organization)
        self.run_test("创建主组织节点", self.test_create_primary_org_node)
        self.run_test("创建目标组织节点", self.test_create_secondary_org_node)
        self.run_test("获取组织节点详情", self.test_get_org_node_detail)
        self.run_test("更新组织节点", self.test_update_org_node)
        self.run_test("更新组织权限范围", self.test_update_org_authority)
        self.run_test("在组织节点下创建成员", self.test_create_member)
        self.run_test("获取组织节点成员列表", self.test_get_org_members)
        self.run_test("更新成员组织归属", self.test_update_member_org_assignment)
        self.run_test("设置负责人", self.test_set_leader)
        self.run_test("清空负责人", self.test_clear_leader)
        self.run_test("移除成员", self.test_remove_member)
        self.run_test("删除主组织节点", self.test_delete_primary_org_node)
        self.run_test("删除目标组织节点", self.test_delete_secondary_org_node)

    def _get_any_permission_id(self) -> int | None:
        resp = self.client.get("/admin/permissions/list")
        data = assert_success(resp, "获取平台权限列表失败")
        items = data["data"]
        return items[0]["id"] if items else None

    def _assert_member_mapping(self, member: dict, expected_org_node_id: int | None) -> None:
        assert_equals(member["org_node_id"], expected_org_node_id)

    def test_list_organization(self) -> None:
        """测试获取组织根节点和组织树 / Test get organization roots and tree."""
        roots_resp = self.client.get("/admin/organization")
        roots_data = assert_success(roots_resp, "获取组织根节点失败")
        assert_true(isinstance(roots_data["data"], list), "组织根节点应为列表")

        tree_resp = self.client.get("/admin/organization/tree")
        tree_data = assert_success(tree_resp, "获取组织树失败")
        assert_true(isinstance(tree_data["data"], list), "组织树应为列表")

    def test_create_primary_org_node(self) -> None:
        """测试创建主组织节点 / Test create primary organization node."""
        resp = self.client.post(
            "/admin/organization",
            data={
                "name": self._test_data["primary_name"],
                "description": "组织范围测试主节点",
                "type": "department",
                "allow_members": True,
                "is_active": True,
                "sort_order": 10,
                "data_scope": "dept_children",
                "permission_ids": [permission_id]
                if (permission_id := self._get_any_permission_id()) is not None
                else None,
            },
        )
        data = assert_success(resp, "创建主组织节点失败")

        assert_has_keys(data["data"], ["id", "name", "type", "allow_members", "data_scope"])
        assert_equals(data["data"]["name"], self._test_data["primary_name"])
        self._test_data["primary_org_node_id"] = data["data"]["id"]

    def test_create_secondary_org_node(self) -> None:
        """测试创建目标组织节点 / Test create secondary organization node."""
        resp = self.client.post(
            "/admin/organization",
            data={
                "name": self._test_data["secondary_name"],
                "description": "成员转移目标节点",
                "type": "department",
                "allow_members": True,
                "is_active": True,
                "sort_order": 20,
                "data_scope": "dept_children",
            },
        )
        data = assert_success(resp, "创建目标组织节点失败")

        assert_equals(data["data"]["name"], self._test_data["secondary_name"])
        self._test_data["secondary_org_node_id"] = data["data"]["id"]

    def test_get_org_node_detail(self) -> None:
        """测试获取组织节点详情 / Test get organization node detail."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.get(f"/admin/organization/{org_node_id}")
        data = assert_success(resp, "获取组织节点详情失败")

        assert_has_keys(
            data["data"],
            [
                "id",
                "name",
                "type",
                "allow_members",
                "data_scope",
                "children_count",
                "member_count",
                "permission_ids",
            ],
        )
        assert_equals(data["data"]["id"], org_node_id)

    def test_update_org_node(self) -> None:
        """测试更新组织节点 / Test update organization node."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        new_name = f"{self._test_data['primary_name']}_已更新"
        resp = self.client.put(
            f"/admin/organization/{org_node_id}",
            data={
                "name": new_name,
                "description": "已更新的主组织节点",
                "sort_order": 30,
            },
        )
        data = assert_success(resp, "更新组织节点失败")

        assert_equals(data["data"]["name"], new_name)
        self._test_data["primary_name"] = new_name

    def test_update_org_authority(self) -> None:
        """测试更新组织权限范围 / Test update organization authority scope."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/authority",
            data={"data_scope": "dept_only"},
        )
        data = assert_success(resp, "更新组织权限范围失败")
        assert_equals(data["data"]["data_scope"], "dept_only")

    def test_create_member(self) -> None:
        """测试在组织节点下创建成员 / Test create member under organization node."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        payload = {
            "username": self._test_data["member_username"],
            "email": self._test_data["member_email"],
            "password": "test123456",
            "nickname": "组织成员",
            "is_active": True,
        }

        resp = self.client.post(f"/admin/organization/{org_node_id}/members/create", data=payload)
        data = assert_success(resp, "创建组织成员失败")

        assert_has_keys(data["data"], ["id", "username", "org_node_id"])
        assert_equals(data["data"]["username"], self._test_data["member_username"])
        self._assert_member_mapping(data["data"], org_node_id)
        self._test_data["created_admin_id"] = data["data"]["id"]

    def test_get_org_members(self) -> None:
        """测试获取组织节点成员列表 / Test get organization members."""
        org_node_id = self._test_data.get("primary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.get(
            f"/admin/organization/{org_node_id}/members",
            params={"page[number]": 1, "page[size]": 20, "include_descendants": True},
        )
        data = assert_success(resp, "获取组织节点成员列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        member = next((item for item in data["data"]["items"] if item["id"] == admin_id), None)
        assert_true(member is not None, "创建的成员未出现在组织节点成员列表中")
        self._assert_member_mapping(member, org_node_id)

    def test_update_member_org_assignment(self) -> None:
        """测试更新成员组织归属 / Test update member organization assignment."""
        source_org_node_id = self._test_data.get("primary_org_node_id")
        target_org_node_id = self._test_data.get("secondary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not source_org_node_id or not target_org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        payload = {
            "nickname": "已转移成员",
            "org_node_id": target_org_node_id,
        }

        resp = self.client.put(
            f"/admin/organization/{source_org_node_id}/members/{admin_id}",
            data=payload,
        )
        data = assert_success(resp, "更新成员组织归属失败")

        self._assert_member_mapping(data["data"], target_org_node_id)
        assert_equals(data["data"]["nickname"], "已转移成员")

    def test_set_leader(self) -> None:
        """测试设置负责人 / Test set organization leader."""
        org_node_id = self._test_data.get("secondary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/leader",
            data={"leader_id": admin_id},
        )
        data = assert_success(resp, "设置负责人失败")

        assert_equals(data["data"]["leader_id"], admin_id)
        assert_true(data["data"]["leader"] is not None, "负责人信息不应为空")

    def test_clear_leader(self) -> None:
        """测试清空负责人 / Test clear organization leader."""
        org_node_id = self._test_data.get("secondary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/leader",
            data={"leader_id": None},
        )
        data = assert_success(resp, "清空负责人失败")
        assert_equals(data["data"]["leader_id"], None)

    def test_remove_member(self) -> None:
        """测试移除成员 / Test remove organization member."""
        org_node_id = self._test_data.get("secondary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}/members/{admin_id}")
        data = assert_success(resp, "移除成员失败")
        self._assert_member_mapping(data["data"], None)

    def test_delete_primary_org_node(self) -> None:
        """测试删除主组织节点 / Test delete primary organization node."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}")
        assert_success(resp, "删除主组织节点失败")
        del self._test_data["primary_org_node_id"]

    def test_delete_secondary_org_node(self) -> None:
        """测试删除目标组织节点 / Test delete secondary organization node."""
        org_node_id = self._test_data.get("secondary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的组织节点 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}")
        assert_success(resp, "删除目标组织节点失败")
        del self._test_data["secondary_org_node_id"]

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        self.login_admin()


if __name__ == "__main__":
    test = ManualTestAdminOrganization()
    report = test.run_all()
    report.print_summary()

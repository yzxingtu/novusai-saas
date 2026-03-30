#!/usr/bin/env python3
"""平台管理员成员管理 API 测试模块 / API.

覆盖当前经 /admin/organization/* 暴露的平台管理员成员管理能力。
"""
import contextlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import (
    BaseAPITest,
    assert_equals,
    assert_has_keys,
    assert_success,
    assert_true,
)


class ManualTestAdminAdmins(BaseAPITest):
    """平台管理员成员管理测试 / Platform admin member management API tests."""

    module_name = "平台管理员成员管理 (/admin/organization/*)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()
        timestamp = int(time.time())
        self._test_data.update(
            {
                "primary_org_name": f"管理员主节点_{timestamp}",
                "secondary_org_name": f"管理员目标节点_{timestamp}",
                "member_username": f"admin_member_{timestamp}",
                "member_email": f"admin_member_{timestamp}@example.com",
                "member_password": "test123456",
                "member_new_password": "new_password_123",
            }
        )

    def teardown(self) -> None:
        """测试后清理 / Cleanup after tests."""
        admin_id = self._test_data.get("created_admin_id")
        member_org_node_id = self._test_data.get("member_org_node_id")
        if admin_id and member_org_node_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/organization/{member_org_node_id}/members/{admin_id}")

        for key in ("secondary_org_node_id", "primary_org_node_id"):
            org_node_id = self._test_data.get(key)
            if org_node_id:
                with contextlib.suppress(Exception):
                    self.client.delete(f"/admin/organization/{org_node_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        self.run_test("创建主组织节点", self.test_create_primary_org_node)
        self.run_test("创建目标组织节点", self.test_create_secondary_org_node)
        self.run_test("在组织节点下创建成员", self.test_create_admin_member)
        self.run_test("获取组织节点成员列表", self.test_list_org_members)
        self.run_test("更新成员资料", self.test_update_admin_member)
        self.run_test("重置成员密码", self.test_reset_admin_member_password)
        self.run_test("切换成员状态", self.test_toggle_admin_member_status)
        self.run_test("迁移成员到目标节点", self.test_move_admin_member)
        self.run_test("移除成员", self.test_remove_admin_member)
        self.run_test("删除主组织节点", self.test_delete_primary_org_node)
        self.run_test("删除目标组织节点", self.test_delete_secondary_org_node)

    def test_create_primary_org_node(self) -> None:
        """测试创建主组织节点 / Test create primary organization node."""
        resp = self.client.post(
            "/admin/organization",
            data={
                "name": self._test_data["primary_org_name"],
                "description": "管理员成员管理主节点",
                "type": "department",
                "allow_members": True,
                "is_active": True,
                "sort_order": 10,
                "data_scope": "dept_children",
            },
        )
        data = assert_success(resp, "创建主组织节点失败")
        self._test_data["primary_org_node_id"] = data["data"]["id"]

    def test_create_secondary_org_node(self) -> None:
        """测试创建目标组织节点 / Test create secondary organization node."""
        resp = self.client.post(
            "/admin/organization",
            data={
                "name": self._test_data["secondary_org_name"],
                "description": "管理员成员迁移目标节点",
                "type": "department",
                "allow_members": True,
                "is_active": True,
                "sort_order": 20,
                "data_scope": "dept_children",
            },
        )
        data = assert_success(resp, "创建目标组织节点失败")
        self._test_data["secondary_org_node_id"] = data["data"]["id"]

    def test_create_admin_member(self) -> None:
        """测试在组织节点下创建成员 / Test create admin member under organization."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的主组织节点 ID")

        resp = self.client.post(
            f"/admin/organization/{org_node_id}/members/create",
            data={
                "username": self._test_data["member_username"],
                "email": self._test_data["member_email"],
                "password": self._test_data["member_password"],
                "nickname": "测试管理员成员",
                "is_active": True,
            },
        )
        data = assert_success(resp, "创建管理员成员失败")

        assert_has_keys(data["data"], ["id", "username", "email", "org_node_id", "is_active"])
        assert_equals(data["data"]["username"], self._test_data["member_username"])
        assert_equals(data["data"]["org_node_id"], org_node_id)
        self._test_data["created_admin_id"] = data["data"]["id"]
        self._test_data["member_org_node_id"] = org_node_id

    def test_list_org_members(self) -> None:
        """测试获取组织节点成员列表 / Test list organization members."""
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
        assert_equals(member["org_node_id"], org_node_id)

    def test_update_admin_member(self) -> None:
        """测试更新成员资料 / Test update admin member profile."""
        org_node_id = self._test_data.get("primary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/members/{admin_id}",
            data={"nickname": "更新后的管理员成员"},
        )
        data = assert_success(resp, "更新管理员成员失败")
        assert_equals(data["data"]["nickname"], "更新后的管理员成员")

    def test_reset_admin_member_password(self) -> None:
        """测试重置成员密码 / Test reset admin member password."""
        org_node_id = self._test_data.get("primary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/members/{admin_id}/reset-password",
            data={"new_password": self._test_data["member_new_password"]},
        )
        assert_success(resp, "重置成员密码失败")

        login_resp = self.post_admin_login_request(
            self._test_data["member_username"],
            self._test_data["member_new_password"],
        )
        assert_success(login_resp, "使用重置后的密码登录失败")
        self._do_login()

    def test_toggle_admin_member_status(self) -> None:
        """测试切换成员状态 / Test toggle admin member status."""
        org_node_id = self._test_data.get("primary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/members/{admin_id}/status",
            data={"is_active": False},
        )
        data = assert_success(resp, "禁用管理员成员失败")
        assert_equals(data["data"]["is_active"], False)

        resp = self.client.put(
            f"/admin/organization/{org_node_id}/members/{admin_id}/status",
            data={"is_active": True},
        )
        data = assert_success(resp, "启用管理员成员失败")
        assert_equals(data["data"]["is_active"], True)

    def test_move_admin_member(self) -> None:
        """测试迁移成员到目标节点 / Test move admin member to target organization."""
        source_org_node_id = self._test_data.get("primary_org_node_id")
        target_org_node_id = self._test_data.get("secondary_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not source_org_node_id or not target_org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.put(
            f"/admin/organization/{source_org_node_id}/members/{admin_id}",
            data={"org_node_id": target_org_node_id},
        )
        data = assert_success(resp, "迁移管理员成员失败")
        assert_equals(data["data"]["org_node_id"], target_org_node_id)
        self._test_data["member_org_node_id"] = target_org_node_id

    def test_remove_admin_member(self) -> None:
        """测试移除成员 / Test remove admin member."""
        org_node_id = self._test_data.get("member_org_node_id")
        admin_id = self._test_data.get("created_admin_id")
        if not org_node_id or not admin_id:
            raise AssertionError("没有可用的组织节点 ID 或成员 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}/members/{admin_id}")
        data = assert_success(resp, "移除管理员成员失败")
        assert_equals(data["data"]["org_node_id"], None)
        self._test_data.pop("member_org_node_id", None)

    def test_delete_primary_org_node(self) -> None:
        """测试删除主组织节点 / Test delete primary organization node."""
        org_node_id = self._test_data.get("primary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的主组织节点 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}")
        assert_success(resp, "删除主组织节点失败")
        self._test_data.pop("primary_org_node_id", None)

    def test_delete_secondary_org_node(self) -> None:
        """测试删除目标组织节点 / Test delete secondary organization node."""
        org_node_id = self._test_data.get("secondary_org_node_id")
        if not org_node_id:
            raise AssertionError("没有可用的目标组织节点 ID")

        resp = self.client.delete(f"/admin/organization/{org_node_id}")
        assert_success(resp, "删除目标组织节点失败")
        self._test_data.pop("secondary_org_node_id", None)

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        self.login_admin()


if __name__ == "__main__":
    test = ManualTestAdminAdmins()
    report = test.run_all()
    report.print_summary()

#!/usr/bin/env python3
"""平台管理员角色 API 测试模块 / API.

测试 /admin/roles/* 接口"""
import os
import sys

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


class ManualTestAdminRoles(BaseAPITest):
    """平台管理员角色测试（含多级角色功能） / Platform admin role API tests (with hierarchy)."""

    module_name = "平台角色管理 (/admin/roles)"

    def setup(self) -> None:
        """测试前登录 / Login before tests."""
        self._do_login()

    def teardown(self) -> None:
        """测试后清理（从叶子节点开始删除） / Cleanup after tests (delete from leaf)."""
        # 先删除孙角色
        grandchild_id = self._test_data.get("grandchild_role_id")
        if grandchild_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/roles/{grandchild_id}")

        # 再删除子角色
        child_id = self._test_data.get("child_role_id")
        if child_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/roles/{child_id}")

        # 最后删除父角色
        role_id = self._test_data.get("created_role_id")
        if role_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/roles/{role_id}")

        # 清理组织架构测试数据
        for key in ["functional_role_id", "position_role_id", "department_role_id"]:
            role_id = self._test_data.get(key)
            if role_id:
                with contextlib.suppress(Exception):
                    self.client.delete(f"/admin/roles/{role_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Run all tests."""
        # ========== 基础测试 ==========
        # 1. 获取角色列表
        self.run_test("获取角色列表", self.test_list_roles)

        # 2. 创建角色
        self.run_test("创建角色", self.test_create_role)

        # 3. 创建角色 - 重复名称（允许）
        self.run_test("创建角色 - 重复名称", self.test_create_role_duplicate_name)

        # 4. 获取角色详情
        self.run_test("获取角色详情", self.test_get_role_detail)

        # 5. 获取角色详情 - 不存在
        self.run_test("获取角色详情 - 不存在", self.test_get_role_not_found)

        # 6. 更新角色
        self.run_test("更新角色", self.test_update_role)

        # 7. 分配角色权限
        self.run_test("分配角色权限", self.test_assign_permissions)

        # ========== 多级角色测试 ==========
        # 8. 获取角色树
        self.run_test("获取角色树", self.test_get_role_tree)

        # 9. 创建子角色
        self.run_test("创建子角色", self.test_create_child_role)

        # 10. 创建孙角色（多层级）
        self.run_test("创建孙角色", self.test_create_grandchild_role)

        # 11. 获取子角色列表
        self.run_test("获取子角色列表", self.test_get_children)

        # 12. 获取有效权限（继承）
        self.run_test("获取有效权限", self.test_get_effective_permissions)

        # 13. 移动角色节点
        self.run_test("移动角色节点", self.test_move_role)

        # 14. 循环引用检测
        self.run_test("循环引用检测", self.test_circular_reference)

        # 15. 删除有子角色的角色 - 应失败
        self.run_test("删除有子角色的角色 - 应失败", self.test_delete_role_with_children)

        # ========== 清理测试 ==========
        # 16. 删除孙角色
        self.run_test("删除孙角色", self.test_delete_grandchild_role)

        # 17. 删除子角色
        self.run_test("删除子角色", self.test_delete_child_role)

        # 18. 删除角色
        self.run_test("删除角色", self.test_delete_role)

        # 19. 删除角色 - 不存在
        self.run_test("删除角色 - 不存在", self.test_delete_role_not_found)

        # ========== 组织架构管理测试 ==========
        # 20. 创建部门类型角色
        self.run_test("创建部门类型角色", self.test_create_department_role)

        # 21. 创建岗位类型角色
        self.run_test("创建岗位类型角色", self.test_create_position_role)

        # 22. 创建职能角色类型
        self.run_test("创建职能角色类型", self.test_create_functional_role)

        # 23. 获取组织架构树
        self.run_test("获取组织架构树", self.test_get_organization_tree)

        # 24. 获取节点成员列表
        self.run_test("获取节点成员列表", self.test_get_role_members)

        # 25. 添加成员到节点
        self.run_test("添加成员到节点", self.test_add_member_to_role)

        # 26. 设置节点负责人
        self.run_test("设置节点负责人", self.test_set_role_leader)

        # 27. 从节点移除成员
        self.run_test("从节点移除成员", self.test_remove_member_from_role)

        # 28. 岗位类型不能设置负责人
        self.run_test("岗位类型不能设置负责人", self.test_position_cannot_set_leader)

        # 29. 部门下不能创建职能角色子节点
        self.run_test("部门下不能创建职能角色子节点", self.test_department_cannot_add_role_child)

        # ========== 组织架构清理 ==========
        # 30. 删除职能角色
        self.run_test("删除职能角色", self.test_delete_functional_role)

        # 31. 删除岗位角色
        self.run_test("删除岗位角色", self.test_delete_position_role)

        # 32. 删除部门角色
        self.run_test("删除部门角色", self.test_delete_department_role)

    def test_list_roles(self) -> None:
        """测试获取角色列表 / Test get role list."""
        resp = self.client.get("/admin/roles")
        data = assert_success(resp, "获取角色列表失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "角色列表应为列表")

        # 如果有数据，验证结构（含新增的层级字段）
        if data["data"]:
            first_role = data["data"][0]
            assert_has_keys(first_role, ["id", "code", "name", "is_active", "parent_id", "level"])

    def test_create_role(self) -> None:
        """测试创建角色 / Test create role."""
        resp = self.client.post("/admin/roles", data={
            "name": "测试角色",
            "description": "API测试创建的角色",
            "is_active": True,
            "sort_order": 100,
        })
        data = assert_success(resp, "创建角色失败")

        assert_has_keys(data["data"], ["id", "code", "name"])
        # code 应该是自动生成的，以 role_ 开头
        assert_true(data["data"]["code"].startswith("role_"), "角色代码应以 role_ 开头")

        # 保存角色ID供后续测试使用
        self._test_data["created_role_id"] = data["data"]["id"]

    def test_create_role_duplicate_name(self) -> None:
        """测试创建重复名称的角色（允许，因为 code 是自动生成的） / Test create role with duplicate name (allowed)."""
        resp = self.client.post("/admin/roles", data={
            "name": "测试角色",  # 同名
            "description": "这个角色名称已存在，但应该允许",
        })
        data = assert_success(resp, "同名角色应该允许创建")

        # 清理创建的重复角色
        if data.get("data", {}).get("id"):
            self.client.delete(f"/admin/roles/{data['data']['id']}")

    def test_get_role_detail(self) -> None:
        """测试获取角色详情 / Test get role detail."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的角色ID")

        resp = self.client.get(f"/admin/roles/{role_id}")
        data = assert_success(resp, "获取角色详情失败")

        # 验证基础字段和新增的层级字段
        assert_has_keys(data["data"], [
            "id", "code", "name", "permission_ids", "permission_codes",
            "parent_id", "path", "level", "children_count", "has_children"
        ])
        assert_equals(data["data"]["id"], role_id)
        # 根角色的 parent_id 应为 None
        assert_equals(data["data"]["parent_id"], None)
        assert_equals(data["data"]["level"], 1)

    def test_get_role_not_found(self) -> None:
        """测试获取不存在的角色详情 / Test get nonexistent role detail."""
        resp = self.client.get("/admin/roles/999999")
        assert_error(resp, 404, "应返回 404 错误")

    def test_update_role(self) -> None:
        """测试更新角色 / Test update role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的角色ID")

        new_name = "更新后的测试角色"
        resp = self.client.put(f"/admin/roles/{role_id}", data={
            "name": new_name,
            "description": "已更新的描述",
        })
        data = assert_success(resp, "更新角色失败")
        assert_equals(data["data"]["name"], new_name)

    def test_assign_permissions(self) -> None:
        """测试分配角色权限 / Test assign role permissions."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的角色ID")

        # 先获取权限列表
        perm_resp = self.client.get("/admin/permissions/list")
        perm_data = perm_resp.json()

        # 取前几个权限ID
        perm_ids = [p["id"] for p in perm_data.get("data", [])[:3]]

        resp = self.client.put(f"/admin/roles/{role_id}/permissions", data={
            "permission_ids": perm_ids,
        })
        assert_success(resp, "分配权限失败")

        # 验证权限已分配
        detail_resp = self.client.get(f"/admin/roles/{role_id}")
        detail_data = detail_resp.json()
        assert_true(
            set(perm_ids).issubset(set(detail_data["data"]["permission_ids"])),
            "权限未正确分配"
        )

    def test_delete_role(self) -> None:
        """测试删除角色 / Test delete role."""
        role_id = self._test_data.get("created_role_id")
        if not role_id:
            raise AssertionError("没有可用的角色ID")

        resp = self.client.delete(f"/admin/roles/{role_id}")
        assert_success(resp, "删除角色失败")

        # 验证已删除
        check_resp = self.client.get(f"/admin/roles/{role_id}")
        assert_error(check_resp, 404, "角色应已被删除")

        # 清除ID，避免 teardown 再次尝试删除
        del self._test_data["created_role_id"]

    def test_delete_role_not_found(self) -> None:
        """测试删除不存在的角色 / Test delete nonexistent role."""
        resp = self.client.delete("/admin/roles/999999")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 多级角色测试方法 ==========

    def test_get_role_tree(self) -> None:
        """测试获取角色树 / Test get role tree."""
        resp = self.client.get("/admin/roles/tree")
        data = assert_success(resp, "获取角色树失败")

        # 验证返回的是列表（树节点列表）
        assert_true(isinstance(data["data"], list), "角色树应为列表")

    def test_create_child_role(self) -> None:
        """测试创建子角色 / Test create child role."""
        parent_id = self._test_data.get("created_role_id")
        if not parent_id:
            raise AssertionError("没有可用的父角色ID")

        resp = self.client.post("/admin/roles", data={
            "name": "测试子角色",
            "description": "父角色下的子角色",
            "is_active": True,
            "parent_id": parent_id,
        })
        data = assert_success(resp, "创建子角色失败")

        # 验证父子关系
        assert_equals(data["data"]["parent_id"], parent_id)
        assert_equals(data["data"]["level"], 2)  # 子角色是第二层

        self._test_data["child_role_id"] = data["data"]["id"]

    def test_create_grandchild_role(self) -> None:
        """测试创建孙角色（多层级） / Test create grandchild role."""
        parent_id = self._test_data.get("child_role_id")
        if not parent_id:
            raise AssertionError("没有可用的子角色ID")

        resp = self.client.post("/admin/roles", data={
            "name": "测试孙角色",
            "description": "子角色下的孙角色",
            "is_active": True,
            "parent_id": parent_id,
        })
        data = assert_success(resp, "创建孙角色失败")

        # 验证父子关系
        assert_equals(data["data"]["parent_id"], parent_id)
        assert_equals(data["data"]["level"], 3)  # 孙角色是第三层

        self._test_data["grandchild_role_id"] = data["data"]["id"]

    def test_get_children(self) -> None:
        """测试获取子角色列表 / Test get child role list."""
        parent_id = self._test_data.get("created_role_id")
        if not parent_id:
            raise AssertionError("没有可用的父角色ID")

        resp = self.client.get(f"/admin/roles/{parent_id}/children")
        data = assert_success(resp, "获取子角色列表失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "子角色列表应为列表")
        # 应该有一个子角色
        assert_true(len(data["data"]) >= 1, "应该至少有一个子角色")

        # 验证子角色的 parent_id
        for child in data["data"]:
            assert_equals(child["parent_id"], parent_id)

    def test_get_effective_permissions(self) -> None:
        """测试获取有效权限（含继承） / Test get effective permissions (with inheritance)."""
        child_id = self._test_data.get("child_role_id")
        if not child_id:
            raise AssertionError("没有可用的子角色ID")

        resp = self.client.get(f"/admin/roles/{child_id}/permissions/effective")
        data = assert_success(resp, "获取有效权限失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "有效权限应为列表")

    def test_move_role(self) -> None:
        """测试移动角色节点 / Test move role node."""
        grandchild_id = self._test_data.get("grandchild_role_id")
        parent_id = self._test_data.get("created_role_id")
        if not grandchild_id or not parent_id:
            raise AssertionError("没有可用的角色ID")

        # 将孙角色移动到根角色下（从第3层移动到第2层）
        resp = self.client.put(f"/admin/roles/{grandchild_id}/move", data={
            "new_parent_id": parent_id,
        })
        data = assert_success(resp, "移动角色失败")

        # 验证移动后的父角色和层级
        assert_equals(data["data"]["parent_id"], parent_id)
        assert_equals(data["data"]["level"], 2)

        # 移动回原位置（回到子角色下）
        child_id = self._test_data.get("child_role_id")
        resp = self.client.put(f"/admin/roles/{grandchild_id}/move", data={
            "new_parent_id": child_id,
        })
        data = assert_success(resp, "移动角色回原位置失败")
        assert_equals(data["data"]["level"], 3)

    def test_circular_reference(self) -> None:
        """测试循环引用检测 / Test circular reference detection."""
        parent_id = self._test_data.get("created_role_id")
        child_id = self._test_data.get("child_role_id")
        if not parent_id or not child_id:
            raise AssertionError("没有可用的角色ID")

        # 尝试将父角色移动到子角色下（应该失败）
        resp = self.client.put(f"/admin/roles/{parent_id}/move", data={
            "new_parent_id": child_id,
        })
        assert_error(resp, 400, "循环引用应返回 400 错误")

    def test_delete_role_with_children(self) -> None:
        """测试删除有子角色的角色 - 应失败 / Test delete role with children should fail."""
        parent_id = self._test_data.get("created_role_id")
        if not parent_id:
            raise AssertionError("没有可用的父角色ID")

        resp = self.client.delete(f"/admin/roles/{parent_id}")
        assert_error(resp, 400, "删除有子角色的角色应返回 400 错误")

    def test_delete_grandchild_role(self) -> None:
        """测试删除孙角色 / Test delete grandchild role."""
        grandchild_id = self._test_data.get("grandchild_role_id")
        if not grandchild_id:
            raise AssertionError("没有可用的孙角色ID")

        resp = self.client.delete(f"/admin/roles/{grandchild_id}")
        assert_success(resp, "删除孙角色失败")

        del self._test_data["grandchild_role_id"]

    def test_delete_child_role(self) -> None:
        """测试删除子角色 / Test delete child role."""
        child_id = self._test_data.get("child_role_id")
        if not child_id:
            raise AssertionError("没有可用的子角色ID")

        resp = self.client.delete(f"/admin/roles/{child_id}")
        assert_success(resp, "删除子角色失败")

        del self._test_data["child_role_id"]

    # ========== 组织架构管理测试方法 ==========

    def test_create_department_role(self) -> None:
        """测试创建部门类型角色 / Test create department type role."""
        resp = self.client.post("/admin/roles", data={
            "name": "测试部门",
            "description": "部门类型节点",
            "is_active": True,
            "type": "department",
            "allow_members": True,
        })
        data = assert_success(resp, "创建部门角色失败")

        assert_has_keys(data["data"], ["id", "code", "name", "type"])
        assert_equals(data["data"]["type"], "department")
        assert_equals(data["data"]["allow_members"], True)

        self._test_data["department_role_id"] = data["data"]["id"]

    def test_create_position_role(self) -> None:
        """测试创建岗位类型角色 / Test create position type role."""
        dept_id = self._test_data.get("department_role_id")
        if not dept_id:
            raise AssertionError("没有可用的部门角色ID")

        resp = self.client.post("/admin/roles", data={
            "name": "测试岗位",
            "description": "岗位类型节点",
            "is_active": True,
            "type": "position",
            "parent_id": dept_id,
            "allow_members": True,
        })
        data = assert_success(resp, "创建岗位角色失败")

        assert_equals(data["data"]["type"], "position")
        assert_equals(data["data"]["parent_id"], dept_id)

        self._test_data["position_role_id"] = data["data"]["id"]

    def test_create_functional_role(self) -> None:
        """测试创建职能角色类型 / Test create function role type."""
        resp = self.client.post("/admin/roles", data={
            "name": "测试职能角色",
            "description": "职能角色类型节点",
            "is_active": True,
            "type": "role",
            "allow_members": True,
        })
        data = assert_success(resp, "创建职能角色失败")

        assert_equals(data["data"]["type"], "role")

        self._test_data["functional_role_id"] = data["data"]["id"]

    def test_get_organization_tree(self) -> None:
        """测试获取组织架构树 / Test get org tree."""
        resp = self.client.get("/admin/roles/organization")
        data = assert_success(resp, "获取组织架构树失败")

        # 验证返回的是列表
        assert_true(isinstance(data["data"], list), "组织架构树应为列表")

    def test_get_role_members(self) -> None:
        """测试获取节点成员列表 / Test get node member list."""
        dept_id = self._test_data.get("department_role_id")
        if not dept_id:
            raise AssertionError("没有可用的部门角色ID")

        resp = self.client.get(f"/admin/roles/{dept_id}/members")
        data = assert_success(resp, "获取成员列表失败")

        # 验证返回的是列表（可能为空）
        assert_true(isinstance(data["data"], list), "成员列表应为列表")

    def test_add_member_to_role(self) -> None:
        """测试添加成员到节点 / Test add member to node."""
        dept_id = self._test_data.get("department_role_id")
        if not dept_id:
            raise AssertionError("没有可用的部门角色ID")

        # 先获取一个管理员ID（获取当前登录管理员的信息）
        me_resp = self.client.get("/admin/auth/me")
        me_data = me_resp.json()
        admin_id = me_data["data"]["id"]
        self._test_data["test_admin_id"] = admin_id

        resp = self.client.post(f"/admin/roles/{dept_id}/members", data={
            "admin_id": admin_id,
        })
        assert_success(resp, "添加成员失败")

        # 验证成员已添加
        members_resp = self.client.get(f"/admin/roles/{dept_id}/members")
        members_data = members_resp.json()
        member_ids = [m["id"] for m in members_data["data"]]
        assert_true(admin_id in member_ids, "成员应已添加到节点")

    def test_set_role_leader(self) -> None:
        """测试设置节点负责人 / Test set node leader."""
        dept_id = self._test_data.get("department_role_id")
        admin_id = self._test_data.get("test_admin_id")
        if not dept_id or not admin_id:
            raise AssertionError("没有可用的部门角色ID或管理员ID")

        resp = self.client.put(f"/admin/roles/{dept_id}/leader", data={
            "leader_id": admin_id,
        })
        assert_success(resp, "设置负责人失败")

        # 验证负责人已设置
        members_resp = self.client.get(f"/admin/roles/{dept_id}/members")
        members_data = members_resp.json()
        leader = [m for m in members_data["data"] if m.get("is_leader")]
        assert_true(len(leader) == 1, "应该有且仅有一个负责人")
        assert_equals(leader[0]["id"], admin_id)

    def test_remove_member_from_role(self) -> None:
        """测试从节点移除成员 / Test remove member from node."""
        dept_id = self._test_data.get("department_role_id")
        admin_id = self._test_data.get("test_admin_id")
        if not dept_id or not admin_id:
            raise AssertionError("没有可用的部门角色ID或管理员ID")

        resp = self.client.delete(f"/admin/roles/{dept_id}/members/{admin_id}")
        assert_success(resp, "移除成员失败")

        # 验证成员已移除
        members_resp = self.client.get(f"/admin/roles/{dept_id}/members")
        members_data = members_resp.json()
        member_ids = [m["id"] for m in members_data["data"]]
        assert_true(admin_id not in member_ids, "成员应已从节点移除")

    def test_position_cannot_set_leader(self) -> None:
        """测试岗位类型不能设置负责人 / Test position type cannot set leader."""
        position_id = self._test_data.get("position_role_id")
        admin_id = self._test_data.get("test_admin_id")
        if not position_id or not admin_id:
            raise AssertionError("没有可用的岗位角色ID或管理员ID")

        # 先添加成员到岗位
        self.client.post(f"/admin/roles/{position_id}/members", data={
            "admin_id": admin_id,
        })

        # 尝试设置负责人（应该失败）
        resp = self.client.put(f"/admin/roles/{position_id}/leader", data={
            "leader_id": admin_id,
        })
        assert_error(resp, 400, "岗位类型设置负责人应返回 400 错误")

        # 清理：移除成员
        self.client.delete(f"/admin/roles/{position_id}/members/{admin_id}")

    def test_department_cannot_add_role_child(self) -> None:
        """测试部门下不能创建职能角色子节点 / Test cannot create function role under department."""
        dept_id = self._test_data.get("department_role_id")
        if not dept_id:
            raise AssertionError("没有可用的部门角色ID")

        # 尝试在部门下创建职能角色子节点（应该失败）
        resp = self.client.post("/admin/roles", data={
            "name": "不应该创建的职能角色",
            "type": "role",
            "parent_id": dept_id,
        })
        assert_error(resp, 400, "部门下创建职能角色子节点应返回 400 错误")

    def test_delete_functional_role(self) -> None:
        """测试删除职能角色 / Test delete function role."""
        role_id = self._test_data.get("functional_role_id")
        if not role_id:
            raise AssertionError("没有可用的职能角色ID")

        resp = self.client.delete(f"/admin/roles/{role_id}")
        assert_success(resp, "删除职能角色失败")

        del self._test_data["functional_role_id"]

    def test_delete_position_role(self) -> None:
        """测试删除岗位角色 / Test delete position role."""
        role_id = self._test_data.get("position_role_id")
        if not role_id:
            raise AssertionError("没有可用的岗位角色ID")

        resp = self.client.delete(f"/admin/roles/{role_id}")
        assert_success(resp, "删除岗位角色失败")

        del self._test_data["position_role_id"]

    def test_delete_department_role(self) -> None:
        """测试删除部门角色 / Test delete department role."""
        role_id = self._test_data.get("department_role_id")
        if not role_id:
            raise AssertionError("没有可用的部门角色ID")

        resp = self.client.delete(f"/admin/roles/{role_id}")
        assert_success(resp, "删除部门角色失败")

        del self._test_data["department_role_id"]

    def _do_login(self) -> None:
        """执行登录 / Do login."""
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestAdminRoles()
    report = test.run_all()
    report.print_summary()


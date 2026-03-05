#!/usr/bin/env python3
"""
套餐管理 API 测试模块

测试 /admin/plans/* 接口
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


class ManualTestAdminPlans(BaseAPITest):
    """套餐管理测试"""

    module_name = "套餐管理 (/admin/plans)"

    def setup(self) -> None:
        """测试前登录"""
        self._do_login()
        # 生成唯一的测试套餐名称（代码由后端自动生成）
        timestamp = int(time.time())
        self._test_data["plan_name"] = f"测试套餐_{timestamp}"

    def teardown(self) -> None:
        """测试后清理"""
        # 尝试删除测试创建的套餐
        plan_id = self._test_data.get("created_plan_id")
        if plan_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/plans/{plan_id}")

    def _run_tests(self) -> None:
        """运行所有测试"""
        # ========== 基本 CRUD 测试 ==========

        # 1. 获取套餐列表
        self.run_test("获取套餐列表", self.test_list_plans)

        # 2. 获取套餐列表 - 分页
        self.run_test("获取套餐列表 - 分页", self.test_list_plans_pagination)

        # 3. 获取套餐下拉选项
        self.run_test("获取套餐下拉选项", self.test_select_plans)

        # 4. 获取可分配权限列表
        self.run_test("获取可分配权限列表", self.test_get_available_permissions)

        # 5. 创建套餐
        self.run_test("创建套餐", self.test_create_plan)

        # 6. 获取套餐详情
        self.run_test("获取套餐详情", self.test_get_plan_detail)

        # 7. 获取套餐详情 - 不存在
        self.run_test("获取套餐详情 - 不存在", self.test_get_plan_not_found)

        # 8. 更新套餐
        self.run_test("更新套餐", self.test_update_plan)

        # ========== 权限管理测试 ==========

        # 9. 获取套餐权限
        self.run_test("获取套餐权限", self.test_get_plan_permissions)

        # 10. 设置套餐权限
        self.run_test("设置套餐权限", self.test_assign_plan_permissions)

        # ========== 删除测试 ==========

        # 11. 删除套餐
        self.run_test("删除套餐", self.test_delete_plan)

        # 12. 删除套餐 - 不存在
        self.run_test("删除套餐 - 不存在", self.test_delete_plan_not_found)

    # ========== 列表和查询测试 ==========

    def test_list_plans(self) -> None:
        """测试获取套餐列表"""
        resp = self.client.get("/admin/plans")
        data = assert_success(resp, "获取套餐列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_list_plans_pagination(self) -> None:
        """测试获取套餐列表 - 分页"""
        resp = self.client.get("/admin/plans", params={"page[number]": 1, "page[size]": 5})
        data = assert_success(resp, "获取套餐列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)
        assert_true(len(data["data"]["items"]) <= 5, "返回数量应不超过 page_size")

    def test_select_plans(self) -> None:
        """测试获取套餐下拉选项"""
        resp = self.client.get("/admin/plans/select")
        data = assert_success(resp, "获取套餐下拉选项失败")

        assert_has_keys(data["data"], ["items"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_get_available_permissions(self) -> None:
        """测试获取可分配权限树"""
        resp = self.client.get("/admin/plans/available-permissions")
        data = assert_success(resp, "获取可分配权限树失败")

        assert_true(isinstance(data["data"], list), "data 应为列表")

        # 收集所有权限 ID（包括子节点）
        def collect_permission_ids(nodes: list, ids: list) -> None:
            """递归收集权限 ID"""
            for node in nodes:
                assert_has_keys(node, ["id", "code", "name", "type", "children"])
                assert_equals(node["type"], "menu", "应只返回 menu 类型权限")
                ids.append(node["id"])
                if node.get("children"):
                    collect_permission_ids(node["children"], ids)

        permission_ids = []
        collect_permission_ids(data["data"], permission_ids)

        # 保存权限用于后续测试
        if permission_ids:
            self._test_data["available_permission_ids"] = permission_ids[:3]

    # ========== 创建测试 ==========

    def test_create_plan(self) -> None:
        """测试创建套餐（代码由后端自动生成）"""
        resp = self.client.post("/admin/plans", data={
            "name": self._test_data["plan_name"],
            "description": "测试套餐描述",
            "price": "99.99",
            "billing_cycle": "monthly",
            "is_active": True,
            "sort_order": 10,
            "quota": {
                "storage_limit_gb": 10,
                "max_users": 50,
                "max_admins": 5,
                "max_custom_domains": 2,
            },
            "features": {
                "ai_enabled": True,
                "advanced_analytics": False,
            },
        })
        data = assert_success(resp, "创建套餐失败")

        assert_has_keys(data["data"], ["id", "code", "name", "price", "billing_cycle", "is_active"])
        # 验证代码是自动生成的格式: plan_ + 6位字符
        code = data["data"]["code"]
        assert_true(code.startswith("plan_"), "套餐代码应以 plan_ 开头")
        assert_true(len(code) >= 11, "套餐代码长度应不少于 11 位")
        assert_equals(data["data"]["name"], self._test_data["plan_name"])
        assert_equals(data["data"]["billing_cycle"], "monthly")
        assert_equals(data["data"]["is_active"], True)

        # 保存套餐ID和代码供后续测试使用
        self._test_data["created_plan_id"] = data["data"]["id"]
        self._test_data["created_plan_code"] = code

    # ========== 详情测试 ==========

    def test_get_plan_detail(self) -> None:
        """测试获取套餐详情"""
        plan_id = self._test_data.get("created_plan_id")
        if not plan_id:
            raise AssertionError("没有可用的套餐ID")

        resp = self.client.get(f"/admin/plans/{plan_id}")
        data = assert_success(resp, "获取套餐详情失败")

        assert_has_keys(data["data"], [
            "id", "code", "name", "description", "price",
            "billing_cycle", "is_active", "quota", "features", "permissions"
        ])
        assert_equals(data["data"]["id"], plan_id)
        assert_equals(data["data"]["code"], self._test_data["created_plan_code"])

        # 验证 permissions 是列表
        assert_true(isinstance(data["data"]["permissions"], list), "permissions 应为列表")

    def test_get_plan_not_found(self) -> None:
        """测试获取不存在的套餐详情"""
        resp = self.client.get("/admin/plans/999999")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 更新测试 ==========

    def test_update_plan(self) -> None:
        """测试更新套餐"""
        plan_id = self._test_data.get("created_plan_id")
        if not plan_id:
            raise AssertionError("没有可用的套餐ID")

        new_name = "更新后的套餐名称"
        new_price = "199.99"

        resp = self.client.put(f"/admin/plans/{plan_id}", data={
            "name": new_name,
            "price": new_price,
            "description": "更新后的描述",
            "quota": {
                "storage_limit_gb": 20,
                "max_users": 100,
            },
        })
        data = assert_success(resp, "更新套餐失败")

        assert_equals(data["data"]["name"], new_name)
        # 价格可能是字符串或数字，做兼容处理
        actual_price = str(data["data"]["price"])
        assert_true(actual_price.startswith("199"), f"价格应更新为 199.99，实际: {actual_price}")

    # ========== 权限管理测试 ==========

    def test_get_plan_permissions(self) -> None:
        """测试获取套餐权限"""
        plan_id = self._test_data.get("created_plan_id")
        if not plan_id:
            raise AssertionError("没有可用的套餐ID")

        resp = self.client.get(f"/admin/plans/{plan_id}/permissions")
        data = assert_success(resp, "获取套餐权限失败")

        assert_true(isinstance(data["data"], list), "data 应为列表")

    def test_assign_plan_permissions(self) -> None:
        """测试设置套餐权限"""
        plan_id = self._test_data.get("created_plan_id")
        if not plan_id:
            raise AssertionError("没有可用的套餐ID")

        # 获取可分配的权限 ID
        permission_ids = self._test_data.get("available_permission_ids", [])
        if not permission_ids:
            # 尝试获取可分配权限
            resp = self.client.get("/admin/plans/available-permissions")
            if resp.status_code == 200:
                perm_data = resp.json()
                if perm_data.get("data"):
                    permission_ids = [p["id"] for p in perm_data["data"][:3]]

        if not permission_ids:
            # 如果没有可用权限，使用空列表测试
            permission_ids = []

        resp = self.client.put(f"/admin/plans/{plan_id}/permissions", data={
            "permission_ids": permission_ids,
        })
        data = assert_success(resp, "设置套餐权限失败")

        assert_has_keys(data["data"], ["id", "permissions"])

        # 验证权限数量
        actual_count = len(data["data"]["permissions"])
        expected_count = len(permission_ids)
        # 由于只有 menu 类型权限可分配，实际数量可能小于等于请求数量
        assert_true(actual_count <= expected_count or expected_count == 0,
                   f"权限数量不匹配: 期望 <= {expected_count}，实际 {actual_count}")

    # ========== 删除测试 ==========

    def test_delete_plan(self) -> None:
        """测试删除套餐"""
        plan_id = self._test_data.get("created_plan_id")
        if not plan_id:
            raise AssertionError("没有可用的套餐ID")

        resp = self.client.delete(f"/admin/plans/{plan_id}")
        assert_success(resp, "删除套餐失败")

        # 验证已删除
        check_resp = self.client.get(f"/admin/plans/{plan_id}")
        assert_error(check_resp, 404, "套餐应已被删除")

        # 清除ID，避免 teardown 再次尝试删除
        del self._test_data["created_plan_id"]

    def test_delete_plan_not_found(self) -> None:
        """测试删除不存在的套餐"""
        resp = self.client.delete("/admin/plans/999999")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 辅助方法 ==========

    def _do_login(self) -> None:
        """执行登录"""
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestAdminPlans()
    report = test.run_all()
    report.print_summary()


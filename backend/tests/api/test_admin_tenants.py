#!/usr/bin/env python3
"""
租户管理 API 测试模块

测试 /admin/tenants/* 接口
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


class ManualTestAdminTenants(BaseAPITest):
    """租户管理测试"""

    module_name = "租户管理 (/admin/tenants)"

    def setup(self) -> None:
        """测试前登录"""
        self._do_login()
        # 生成唯一的测试租户名称
        timestamp = int(time.time())
        self._test_data["tenant_name"] = f"测试租户_{timestamp}"

    def teardown(self) -> None:
        """测试后清理"""
        # 尝试删除测试创建的租户
        tenant_id = self._test_data.get("created_tenant_id")
        if tenant_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/tenants/{tenant_id}")

    def _run_tests(self) -> None:
        """运行所有测试"""
        # 1. 获取租户列表
        self.run_test("获取租户列表", self.test_list_tenants)

        # 2. 获取租户列表 - 分页
        self.run_test("获取租户列表 - 分页", self.test_list_tenants_pagination)

        # 3. 获取租户列表 - 按状态过滤
        self.run_test("获取租户列表 - 按状态过滤", self.test_list_tenants_filter_status)

        # 4. 创建租户（编码自动生成）
        self.run_test("创建租户", self.test_create_tenant)

        # 5. 获取租户详情
        self.run_test("获取租户详情", self.test_get_tenant_detail)

        # 6. 获取租户详情 - 不存在
        self.run_test("获取租户详情 - 不存在", self.test_get_tenant_not_found)

        # 7. 更新租户
        self.run_test("更新租户", self.test_update_tenant)

        # 8. 切换租户状态
        self.run_test("切换租户状态", self.test_toggle_tenant_status)

        # 9. 删除租户
        self.run_test("删除租户", self.test_delete_tenant)

    def test_list_tenants(self) -> None:
        """测试获取租户列表"""
        resp = self.client.get("/admin/tenants")
        data = assert_success(resp, "获取租户列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_list_tenants_pagination(self) -> None:
        """测试获取租户列表 - 分页"""
        resp = self.client.get("/admin/tenants", params={"page": 1, "page_size": 5})
        data = assert_success(resp, "获取租户列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)
        assert_true(len(data["data"]["items"]) <= 5, "返回数量应不超过 page_size")

    def test_list_tenants_filter_status(self) -> None:
        """测试获取租户列表 - 按状态过滤"""
        resp = self.client.get("/admin/tenants", params={"is_active": True})
        data = assert_success(resp, "获取租户列表失败")

        # 验证所有返回的租户都是激活状态
        for tenant in data["data"]["items"]:
            assert_true(tenant["is_active"], "租户应为激活状态")

    def test_create_tenant(self) -> None:
        """测试创建租户（编码自动生成）"""
        resp = self.client.post("/admin/tenants", data={
            "name": self._test_data["tenant_name"],
            "contact_name": "测试联系人",
            "contact_phone": "13800138000",
            "contact_email": "test@example.com",
            "plan": "basic",
            "quota": {"max_users": 100},
        })
        data = assert_success(resp, "创建租户失败")

        assert_has_keys(data["data"], ["id", "code", "name", "is_active"])
        # 验证编码是自动生成的格式: t + 8位字符
        code = data["data"]["code"]
        assert_true(code.startswith("t"), "租户编码应以 t 开头")
        assert_true(len(code) == 9, "租户编码长度应为 9 位")

        # 保存租户ID和编码供后续测试使用
        self._test_data["created_tenant_id"] = data["data"]["id"]
        self._test_data["created_tenant_code"] = code

    def test_get_tenant_detail(self) -> None:
        """测试获取租户详情"""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的租户ID")

        resp = self.client.get(f"/admin/tenants/{tenant_id}")
        data = assert_success(resp, "获取租户详情失败")

        assert_has_keys(data["data"], ["id", "code", "name", "is_active", "plan"])
        assert_equals(data["data"]["id"], tenant_id)

    def test_get_tenant_not_found(self) -> None:
        """测试获取不存在的租户详情"""
        resp = self.client.get("/admin/tenants/999999")
        assert_error(resp, 404, "应返回 404 错误")

    def test_update_tenant(self) -> None:
        """测试更新租户"""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的租户ID")

        new_name = "更新后的租户名称"
        resp = self.client.put(f"/admin/tenants/{tenant_id}", data={
            "name": new_name,
            "remark": "已更新备注",
        })
        data = assert_success(resp, "更新租户失败")
        assert_equals(data["data"]["name"], new_name)

    def test_toggle_tenant_status(self) -> None:
        """测试切换租户状态"""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的租户ID")

        # 禁用租户
        resp = self.client.put(f"/admin/tenants/{tenant_id}/status", data={"is_active": False})
        data = assert_success(resp, "禁用租户失败")
        assert_equals(data["data"]["is_active"], False)

        # 启用租户
        resp = self.client.put(f"/admin/tenants/{tenant_id}/status", data={"is_active": True})
        data = assert_success(resp, "启用租户失败")
        assert_equals(data["data"]["is_active"], True)

    def test_delete_tenant(self) -> None:
        """测试删除租户"""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的租户ID")

        resp = self.client.delete(f"/admin/tenants/{tenant_id}")
        assert_success(resp, "删除租户失败")

        # 验证已删除
        check_resp = self.client.get(f"/admin/tenants/{tenant_id}")
        assert_error(check_resp, 404, "租户应已被删除")

        # 清除ID，避免 teardown 再次尝试删除
        del self._test_data["created_tenant_id"]

    def _do_login(self) -> None:
        """执行登录"""
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        data = resp.json()
        self.client.set_token(data["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestAdminTenants()
    report = test.run_all()
    report.print_summary()


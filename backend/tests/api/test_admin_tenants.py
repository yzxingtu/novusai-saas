#!/usr/bin/env python3
"""企业管理 API 测试模块 / API.

测试 /admin/tenants/* 接口"""
import contextlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text

from app.core.database import sync_engine
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
    """企业管理测试 / Test."""

    module_name = "企业管理 (/admin/tenants)"

    def setup(self) -> None:
        """测试前登录 / Test."""
        self._do_login()
        # 生成唯一的测试企业名称
        timestamp = int(time.time())
        self._test_data["tenant_name"] = f"测试企业_{timestamp}"
        self._test_data["admin_username"] = f"tenant_owner_{timestamp}"
        self._test_data["admin_email"] = f"tenant_owner_{timestamp}@example.com"

    def teardown(self) -> None:
        """测试后清理 / Test."""
        # 尝试删除测试创建的企业
        tenant_id = self._test_data.get("created_tenant_id")
        if tenant_id:
            self._soft_delete_test_tenant_admins(tenant_id)
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/tenants/{tenant_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Test."""
        # 1. 获取企业列表
        self.run_test("获取企业列表", self.test_list_tenants)

        # 2. 获取企业列表 - 分页
        self.run_test("获取企业列表 - 分页", self.test_list_tenants_pagination)

        # 3. 获取企业列表 - 按状态过滤
        self.run_test("获取企业列表 - 按状态过滤", self.test_list_tenants_filter_status)

        # 4. 创建企业（编码自动生成）
        self.run_test("创建企业", self.test_create_tenant)

        # 5. 获取企业详情
        self.run_test("获取企业详情", self.test_get_tenant_detail)

        # 6. 获取企业详情 - 不存在
        self.run_test("获取企业详情 - 不存在", self.test_get_tenant_not_found)

        # 7. 更新企业
        self.run_test("更新企业", self.test_update_tenant)

        # 8. 切换企业状态
        self.run_test("切换企业状态", self.test_toggle_tenant_status)

        # 9. 删除企业（当前会被 owner 依赖阻塞）
        self.run_test("删除企业 - owner 依赖阻塞", self.test_delete_tenant)

    def test_list_tenants(self) -> None:
        """测试获取企业列表 / Test."""
        resp = self.client.get("/admin/tenants")
        data = assert_success(resp, "获取企业列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_list_tenants_pagination(self) -> None:
        """测试获取企业列表 - 分页 / Test."""
        resp = self.client.get(
            "/admin/tenants",
            params={"page[number]": 1, "page[size]": 5},
        )
        data = assert_success(resp, "获取企业列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)
        assert_true(len(data["data"]["items"]) <= 5, "返回数量应不超过 page_size")

    def test_list_tenants_filter_status(self) -> None:
        """测试获取企业列表 - 按状态过滤 / Test."""
        resp = self.client.get("/admin/tenants", params={"filter[is_active][eq]": "true"})
        data = assert_success(resp, "获取企业列表失败")

        # 验证所有返回的企业都是激活状态
        for tenant in data["data"]["items"]:
            assert_true(tenant["is_active"], "企业应为激活状态")

    def test_create_tenant(self) -> None:
        """测试创建企业（编码自动生成） / Test."""
        resp = self.client.post("/admin/tenants", data={
            "name": self._test_data["tenant_name"],
            "contact_name": "测试联系人",
            "contact_phone": "13800138000",
            "contact_email": "test@example.com",
            "quota": {"max_users": 100},
            "admin_username": self._test_data["admin_username"],
            "admin_email": self._test_data["admin_email"],
            "admin_password": "test123456",
        })
        data = assert_success(resp, "创建企业失败")

        assert_has_keys(data["data"], ["id", "code", "name", "is_active"])
        # 验证编码是自动生成的格式: t + 8位字符
        code = data["data"]["code"]
        assert_true(code.startswith("t"), "企业编码应以 t 开头")
        assert_true(len(code) >= 9, "企业编码长度至少应为 9 位")

        # 保存企业ID和编码供后续测试使用
        self._test_data["created_tenant_id"] = data["data"]["id"]
        self._test_data["created_tenant_code"] = code

    def test_get_tenant_detail(self) -> None:
        """测试获取企业详情 / Test."""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的企业ID")

        resp = self.client.get(f"/admin/tenants/{tenant_id}")
        data = assert_success(resp, "获取企业详情失败")

        assert_has_keys(data["data"], ["id", "code", "name", "is_active", "plan_id"])
        assert_equals(data["data"]["id"], tenant_id)

    def test_get_tenant_not_found(self) -> None:
        """测试获取不存在的企业详情 / Test."""
        resp = self.client.get("/admin/tenants/999999")
        assert_error(resp, 404, "应返回 404 错误")

    def test_update_tenant(self) -> None:
        """测试更新企业 / Test."""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的企业ID")

        new_name = "更新后的企业名称"
        resp = self.client.put(f"/admin/tenants/{tenant_id}", data={
            "name": new_name,
            "remark": "已更新备注",
        })
        data = assert_success(resp, "更新企业失败")
        assert_equals(data["data"]["name"], new_name)

    def test_toggle_tenant_status(self) -> None:
        """测试切换企业状态 / Test."""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的企业ID")

        # 禁用企业
        resp = self.client.put(f"/admin/tenants/{tenant_id}/status", data={"is_active": False})
        data = assert_success(resp, "禁用企业失败")
        assert_equals(data["data"]["is_active"], False)

        # 启用企业
        resp = self.client.put(f"/admin/tenants/{tenant_id}/status", data={"is_active": True})
        data = assert_success(resp, "启用企业失败")
        assert_equals(data["data"]["is_active"], True)

    def test_delete_tenant(self) -> None:
        """测试删除企业在 owner 依赖下被阻塞 / Test."""
        tenant_id = self._test_data.get("created_tenant_id")
        if not tenant_id:
            raise AssertionError("没有可用的企业ID")

        resp = self.client.delete(f"/admin/tenants/{tenant_id}")
        data = assert_error(resp, 422, "企业删除应返回依赖阻塞错误")
        assert_equals(data.get("code"), 4221, "企业删除阻塞应返回依赖错误码")

        dependencies = data.get("dependencies") or []
        tenant_admin_dep = next(
            (dependency for dependency in dependencies if dependency.get("type") == "tenant_admin"),
            None,
        )
        assert_true(tenant_admin_dep is not None, "阻塞依赖中应包含 tenant_admin")
        assert_true(int(tenant_admin_dep.get("count") or 0) >= 1, "tenant_admin 依赖数量应至少为 1")

    def _do_login(self) -> None:
        """执行登录 / Description."""
        self.login_admin()

    @staticmethod
    def _soft_delete_test_tenant_admins(tenant_id: int) -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE tenant_admins
                    SET is_deleted = TRUE,
                        deleted_at = NOW(),
                        updated_at = NOW()
                    WHERE tenant_id = :tenant_id
                      AND is_deleted = FALSE
                    """
                ),
                {"tenant_id": tenant_id},
            )


if __name__ == "__main__":
    test = ManualTestAdminTenants()
    report = test.run_all()
    report.print_summary()


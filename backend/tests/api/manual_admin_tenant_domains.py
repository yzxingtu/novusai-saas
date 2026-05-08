#!/usr/bin/env python3
"""企业域名管理 API 测试模块 / API.

测试 /admin/tenants/{tenant_id}/domains/* 接口"""

import os
import sys
import time

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

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


class ManualTestAdminTenantDomains(BaseAPITest):
    """企业域名管理测试 / Test."""

    module_name = "企业域名管理 (/admin/tenants/{tenant_id}/domains)"

    def setup(self) -> None:
        """测试前登录并创建测试企业 / Test."""
        self._do_login()
        # 生成唯一的测试数据
        timestamp = int(time.time())
        self._test_data["tenant_name"] = f"测试企业_{timestamp}"
        self._test_data["admin_username"] = f"tenant_owner_{timestamp}"
        self._test_data["admin_email"] = f"tenant_owner_{timestamp}@example.com"
        self._test_data["custom_domain"] = f"test{timestamp}.example.com"
        self._test_data["custom_domain_2"] = f"test{timestamp}b.example.com"

        # 创建测试企业
        self._create_test_tenant()

    def teardown(self) -> None:
        """测试后清理 / Test."""
        # 尝试删除测试创建的企业
        tenant_id = self._test_data.get("created_tenant_id")
        if tenant_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/tenants/{tenant_id}")

    def _run_tests(self) -> None:
        """运行所有测试 / Test."""
        # ========== 列表和查询测试 ==========

        # 1. 获取企业域名列表（应包含默认域名）
        self.run_test("获取企业域名列表", self.test_list_domains)

        # 2. 获取域名列表 - 分页
        self.run_test("获取域名列表 - 分页", self.test_list_domains_pagination)

        # ========== 创建测试 ==========

        # 3. 为企业添加自定义域名
        self.run_test("添加自定义域名", self.test_create_custom_domain)

        # 4. 添加重复域名
        self.run_test("添加重复域名 - 应失败", self.test_create_duplicate_domain)

        # ========== 详情测试 ==========

        # 5. 获取域名详情
        self.run_test("获取域名详情", self.test_get_domain_detail)

        # 6. 获取域名详情 - 不存在
        self.run_test("获取域名详情 - 不存在", self.test_get_domain_not_found)

        # ========== 更新测试 ==========

        # 7. 更新域名信息
        self.run_test("更新域名信息", self.test_update_domain)

        # ========== 验证测试 ==========

        # 8. 验证域名
        self.run_test("验证域名", self.test_verify_domain)

        # 9. 重复验证域名 - 应失败
        self.run_test("重复验证域名 - 应失败", self.test_verify_domain_already_verified)

        # ========== 主域名测试 ==========

        # 10. 设置主域名
        self.run_test("设置主域名", self.test_set_primary_domain)

        # 11. 设置主域名 - 未验证域名应失败
        self.run_test(
            "设置未验证域名为主域名 - 应失败", self.test_set_primary_unverified_domain
        )

        # ========== 删除测试 ==========

        # 12. 删除主域名 - 应失败
        self.run_test("删除主域名 - 应失败", self.test_delete_primary_domain)

        # 13. 删除默认域名 - 应失败
        self.run_test("删除默认域名 - 应失败", self.test_delete_default_domain)

        # 14. 删除自定义域名
        self.run_test("删除自定义域名", self.test_delete_custom_domain)

        # 15. 删除域名 - 不存在
        self.run_test("删除域名 - 不存在", self.test_delete_domain_not_found)

        # ========== 企业验证测试 ==========

        # 16. 操作不存在的企业
        self.run_test("操作不存在的企业域名 - 应失败", self.test_tenant_not_found)

    # ========== 列表和查询测试 ==========

    def test_list_domains(self) -> None:
        """测试获取企业域名列表 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        resp = self.client.get(f"/admin/tenants/{tenant_id}/domains")
        data = assert_success(resp, "获取企业域名列表失败")

        assert_has_keys(data["data"], ["items", "total", "page", "page_size", "pages"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

        # 应至少有一个默认域名
        assert_true(data["data"]["total"] >= 1, "应至少有一个默认域名")

        # 保存默认域名信息
        for domain in data["data"]["items"]:
            if domain["is_primary"]:
                self._test_data["default_domain_id"] = domain["id"]
                self._test_data["default_domain"] = domain["domain"]
                break

    def test_list_domains_pagination(self) -> None:
        """测试获取域名列表 - 分页 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        resp = self.client.get(
            f"/admin/tenants/{tenant_id}/domains",
            params={"page[number]": 1, "page[size]": 5},
        )
        data = assert_success(resp, "获取企业域名列表失败")

        assert_equals(data["data"]["page"], 1)
        assert_equals(data["data"]["page_size"], 5)
        assert_true(len(data["data"]["items"]) <= 5, "返回数量应不超过 page_size")

    # ========== 创建测试 ==========

    def test_create_custom_domain(self) -> None:
        """测试添加自定义域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        custom_domain = self._test_data["custom_domain"]

        resp = self.client.post(
            f"/admin/tenants/{tenant_id}/domains",
            data={
                "domain": custom_domain,
                "remark": "测试自定义域名",
            },
        )
        data = assert_success(resp, "添加自定义域名失败")

        assert_has_keys(
            data["data"],
            [
                "id",
                "tenant_id",
                "domain",
                "is_verified",
                "is_primary",
                "ssl_status",
                "verification_token",
                "created_at",
            ],
        )
        assert_equals(data["data"]["domain"], custom_domain)
        assert_equals(data["data"]["is_verified"], False, "新域名应为未验证状态")
        assert_equals(data["data"]["is_primary"], False, "新域名应不是主域名")
        assert_true(data["data"]["verification_token"] is not None, "应有验证 Token")

        # 保存域名ID供后续测试使用
        self._test_data["created_domain_id"] = data["data"]["id"]

    def test_create_duplicate_domain(self) -> None:
        """测试添加重复域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        custom_domain = self._test_data["custom_domain"]  # 使用已存在的域名

        resp = self.client.post(
            f"/admin/tenants/{tenant_id}/domains",
            data={
                "domain": custom_domain,
            },
        )

        # 应返回业务错误
        data = resp.json()
        assert_true(
            data.get("code") != 0, f"重复域名应返回错误，实际 code={data.get('code')}"
        )

    # ========== 详情测试 ==========

    def test_get_domain_detail(self) -> None:
        """测试获取域名详情 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        resp = self.client.get(f"/admin/tenants/{tenant_id}/domains/{domain_id}")
        data = assert_success(resp, "获取域名详情失败")

        assert_has_keys(
            data["data"],
            [
                "id",
                "tenant_id",
                "domain",
                "is_verified",
                "is_primary",
                "ssl_status",
                "verification_token",
                "created_at",
                "updated_at",
            ],
        )
        assert_equals(data["data"]["id"], domain_id)
        assert_equals(data["data"]["tenant_id"], tenant_id)

    def test_get_domain_not_found(self) -> None:
        """测试获取不存在的域名详情 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        resp = self.client.get(f"/admin/tenants/{tenant_id}/domains/999999")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 更新测试 ==========

    def test_update_domain(self) -> None:
        """测试更新域名信息 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        new_remark = "更新后的备注"
        resp = self.client.put(
            f"/admin/tenants/{tenant_id}/domains/{domain_id}",
            data={
                "remark": new_remark,
            },
        )
        data = assert_success(resp, "更新域名信息失败")

        assert_equals(data["data"]["remark"], new_remark)

    # ========== 验证测试 ==========

    def test_verify_domain(self) -> None:
        """测试验证域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        resp = self.client.post(
            f"/admin/tenants/{tenant_id}/domains/{domain_id}/verify"
        )
        data = assert_success(resp, "验证域名失败")

        assert_equals(data["data"]["is_verified"], True, "域名应已验证")
        assert_true(data["data"]["verified_at"] is not None, "应有验证时间")

    def test_verify_domain_already_verified(self) -> None:
        """测试重复验证已验证的域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        resp = self.client.post(
            f"/admin/tenants/{tenant_id}/domains/{domain_id}/verify"
        )

        # 应返回业务错误
        data = resp.json()
        assert_true(
            data.get("code") != 0, f"重复验证应返回错误，实际 code={data.get('code')}"
        )

    # ========== 主域名测试 ==========

    def test_set_primary_domain(self) -> None:
        """测试设置主域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        resp = self.client.put(
            f"/admin/tenants/{tenant_id}/domains/{domain_id}/primary"
        )
        data = assert_success(resp, "设置主域名失败")

        assert_equals(data["data"]["is_primary"], True, "域名应已设为主域名")

        # 验证原主域名已不再是主域名
        default_domain_id = self._test_data.get("default_domain_id")
        if default_domain_id:
            resp2 = self.client.get(
                f"/admin/tenants/{tenant_id}/domains/{default_domain_id}"
            )
            data2 = assert_success(resp2, "获取默认域名详情失败")
            assert_equals(data2["data"]["is_primary"], False, "原主域名应不再是主域名")

    def test_set_primary_unverified_domain(self) -> None:
        """测试设置未验证域名为主域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        custom_domain_2 = self._test_data["custom_domain_2"]

        # 先添加一个新的未验证域名
        resp = self.client.post(
            f"/admin/tenants/{tenant_id}/domains",
            data={
                "domain": custom_domain_2,
            },
        )
        data = assert_success(resp, "添加第二个自定义域名失败")
        new_domain_id = data["data"]["id"]
        self._test_data["created_domain_id_2"] = new_domain_id

        # 尝试设置未验证域名为主域名
        resp2 = self.client.put(
            f"/admin/tenants/{tenant_id}/domains/{new_domain_id}/primary"
        )

        # 应返回业务错误
        data2 = resp2.json()
        assert_true(
            data2.get("code") != 0,
            f"设置未验证域名为主域名应返回错误，实际 code={data2.get('code')}",
        )

    # ========== 删除测试 ==========

    def test_delete_primary_domain(self) -> None:
        """测试删除主域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        domain_id = self._test_data.get("created_domain_id")  # 当前主域名
        if not domain_id:
            raise AssertionError("没有可用的域名ID")

        resp = self.client.delete(f"/admin/tenants/{tenant_id}/domains/{domain_id}")

        # 应返回业务错误
        data = resp.json()
        assert_true(
            data.get("code") != 0, f"删除主域名应返回错误，实际 code={data.get('code')}"
        )

    def test_delete_default_domain(self) -> None:
        """测试删除默认域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        default_domain_id = self._test_data.get("default_domain_id")
        if not default_domain_id:
            raise AssertionError("没有可用的默认域名ID")

        resp = self.client.delete(
            f"/admin/tenants/{tenant_id}/domains/{default_domain_id}"
        )

        # 应返回业务错误
        data = resp.json()
        assert_true(
            data.get("code") != 0,
            f"删除默认域名应返回错误，实际 code={data.get('code')}",
        )

    def test_delete_custom_domain(self) -> None:
        """测试删除自定义域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]

        # 删除第二个未验证的自定义域名
        domain_id = self._test_data.get("created_domain_id_2")
        if not domain_id:
            raise AssertionError("没有可用的第二个域名ID")

        resp = self.client.delete(f"/admin/tenants/{tenant_id}/domains/{domain_id}")
        assert_success(resp, "删除自定义域名失败")

        # 验证已删除
        check_resp = self.client.get(f"/admin/tenants/{tenant_id}/domains/{domain_id}")
        assert_error(check_resp, 404, "域名应已被删除")

        # 清除ID
        del self._test_data["created_domain_id_2"]

    def test_delete_domain_not_found(self) -> None:
        """测试删除不存在的域名 / Test."""
        tenant_id = self._test_data["created_tenant_id"]
        resp = self.client.delete(f"/admin/tenants/{tenant_id}/domains/999999")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 企业验证测试 ==========

    def test_tenant_not_found(self) -> None:
        """测试操作不存在的企业域名 / Test."""
        resp = self.client.get("/admin/tenants/999999/domains")
        assert_error(resp, 404, "应返回 404 错误")

    # ========== 辅助方法 ==========

    def _do_login(self) -> None:
        """执行登录 / Description."""
        resp = self.client.post(
            "/admin/auth/login",
            data={
                "username": config.ADMIN_USERNAME,
                "password": config.ADMIN_PASSWORD,
            },
        )
        data = assert_success(resp, "平台管理员登录失败")
        self.client.set_token(data["data"]["access_token"])

    def _create_test_tenant(self) -> None:
        """创建测试企业 / Test."""
        resp = self.client.post(
            "/admin/tenants",
            data={
                "name": self._test_data["tenant_name"],
                "contact_name": "测试联系人",
                "contact_phone": "13800138000",
                "contact_email": "test@example.com",
                "quota": {"max_users": 100},
                "admin_username": self._test_data["admin_username"],
                "admin_email": self._test_data["admin_email"],
                "admin_password": "test123456",
            },
        )
        data = assert_success(resp, "创建测试企业失败")

        self._test_data["created_tenant_id"] = data["data"]["id"]
        self._test_data["created_tenant_code"] = data["data"]["code"]


if __name__ == "__main__":
    test = ManualTestAdminTenantDomains()
    report = test.run_all()
    report.print_summary()

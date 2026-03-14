#!/usr/bin/env python3
"""
API 测试运行入口

运行所有模块的 API 测试

使用方法:
    # 运行所有测试
    python -m tests.api.run_all

    # 运行特定模块测试
    python -m tests.api.test_admin_auth
    python -m tests.api.test_admin_permissions
    python -m tests.api.test_admin_roles
    python -m tests.api.test_admin_admins
    python -m tests.api.test_admin_tenants
    python -m tests.api.test_tenant_auth
    python -m tests.api.test_tenant_roles
    python -m tests.api.test_tenant_admins

环境变量配置:
    TEST_API_BASE_URL=http://localhost:8000  # API 基础地址
    TEST_ADMIN_USERNAME=admin                # 平台管理员用户名
    TEST_ADMIN_PASSWORD=admin123456          # 平台管理员密码
    TEST_TENANT_ADMIN_USERNAME=              # 企业管理员用户名
    TEST_TENANT_ADMIN_PASSWORD=              # 企业管理员密码
    TEST_LANGUAGE=zh-cn                      # 语言设置
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import TestReport, TestStatus


def run_admin_tests() -> list[TestReport]:
    """运行平台管理端测试"""
    reports = []

    # Admin Auth
    from tests.api.test_admin_auth import TestAdminAuth
    test = TestAdminAuth()
    reports.append(test.run_all())

    # Admin Permissions
    from tests.api.test_admin_permissions import TestAdminPermissions
    test = TestAdminPermissions()
    reports.append(test.run_all())

    # Admin Roles
    from tests.api.test_admin_roles import TestAdminRoles
    test = TestAdminRoles()
    reports.append(test.run_all())

    # Admin Admins
    from tests.api.test_admin_admins import TestAdminAdmins
    test = TestAdminAdmins()
    reports.append(test.run_all())

    # Admin Tenants
    from tests.api.test_admin_tenants import TestAdminTenants
    test = TestAdminTenants()
    reports.append(test.run_all())

    return reports


def run_tenant_tests() -> list[TestReport]:
    """运行企业管理端测试"""
    reports = []

    # Tenant Auth
    from tests.api.test_tenant_auth import TestTenantAuth
    test = TestTenantAuth()
    reports.append(test.run_all())

    # Tenant Roles
    from tests.api.test_tenant_roles import TestTenantRoles
    test = TestTenantRoles()
    reports.append(test.run_all())

    # Tenant Admins
    from tests.api.test_tenant_admins import TestTenantAdmins
    test = TestTenantAdmins()
    reports.append(test.run_all())

    return reports


def print_summary(reports: list[TestReport]) -> int:
    """打印总体测试摘要"""
    total_tests = sum(r.total for r in reports)
    total_passed = sum(r.passed for r in reports)
    total_failed = sum(r.failed for r in reports)
    total_skipped = sum(r.skipped for r in reports)
    total_duration = sum(r.duration for r in reports)

    print("\n")
    print("=" * 70)
    print("📊 API 测试总体报告")
    print("=" * 70)

    for report in reports:
        status = "✅" if report.failed == 0 else "❌"
        print(f"{status} {report.module}: {report.passed}/{report.total} 通过 ({report.duration:.2f}s)")

    print("-" * 70)
    print(f"📈 总计测试: {total_tests}")
    print(f"✅ 通过: {total_passed}")
    print(f"❌ 失败: {total_failed}")
    print(f"⏭️  跳过: {total_skipped}")
    print(f"⏱️  总耗时: {total_duration:.2f}s")
    print("=" * 70)

    if total_failed > 0:
        print("\n❌ 有测试失败，详细信息如下：")
        for report in reports:
            for result in report.results:
                if result.status == TestStatus.FAILED:
                    print(f"\n  📍 {report.module} > {result.name}")
                    print(f"     {result.message}")

    return 1 if total_failed > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="运行 API 测试")
    parser.add_argument(
        "--module",
        choices=["admin", "tenant", "all"],
        default="all",
        help="选择要测试的模块 (默认: all)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出"
    )
    args = parser.parse_args()

    print("🚀 开始 API 测试...")
    print(f"📍 测试目标: {os.environ.get('TEST_API_BASE_URL', 'http://localhost:8000')}")
    print()

    reports = []

    if args.module in ("admin", "all"):
        print("=" * 70)
        print("🔧 平台管理端测试")
        print("=" * 70)
        admin_reports = run_admin_tests()
        for report in admin_reports:
            report.print_summary()
        reports.extend(admin_reports)

    if args.module in ("tenant", "all"):
        print("\n")
        print("=" * 70)
        print("🏢 企业管理端测试")
        print("=" * 70)
        tenant_reports = run_tenant_tests()
        for report in tenant_reports:
            report.print_summary()
        reports.extend(tenant_reports)

    # 打印总体摘要
    exit_code = print_summary(reports)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

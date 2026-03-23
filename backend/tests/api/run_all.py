#!/usr/bin/env python3
"""API 测试运行入口 / API.

运行所有模块的 API 测试

使用方法:
    # 运行所有测试
    python -m tests.api.run_all

    # 运行特定模块测试
    python -m tests.api.test_admin_auth
    python -m tests.api.test_admin_permissions
    python -m tests.api.test_admin_permission_roles
    python -m tests.api.test_admin_organization
    python -m tests.api.test_admin_admins
    python -m tests.api.test_admin_tenants
    python -m tests.api.test_tenant_auth
    python -m tests.api.test_tenant_permission_roles
    python -m tests.api.test_tenant_organization
    python -m tests.api.test_tenant_admins

环境变量配置:
    TEST_API_BASE_URL=http://localhost:8000  # API 基础地址
    TEST_ADMIN_USERNAME=admin                # 平台管理员用户名
    TEST_ADMIN_PASSWORD=admin123456          # 平台管理员密码
    TEST_TENANT_ADMIN_USERNAME=              # 企业管理员用户名
    TEST_TENANT_ADMIN_PASSWORD=              # 企业管理员密码
    TEST_LANGUAGE=zh-cn                      # 语言设置"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import TestReport, TestStatus


def run_admin_tests() -> list[TestReport]:
    """运行平台管理端测试 / Test."""
    reports = []

    # Admin Auth
    from tests.api.test_admin_auth import ManualTestAdminAuth
    test = ManualTestAdminAuth()
    reports.append(test.run_all())

    # Admin Permissions
    from tests.api.test_admin_permissions import ManualTestAdminPermissions
    test = ManualTestAdminPermissions()
    reports.append(test.run_all())

    # Admin Permission Roles
    from tests.api.test_admin_permission_roles import ManualTestAdminPermissionRoles
    test = ManualTestAdminPermissionRoles()
    reports.append(test.run_all())

    # Admin Organization
    from tests.api.test_admin_organization import ManualTestAdminOrganization
    test = ManualTestAdminOrganization()
    reports.append(test.run_all())

    # Admin Admins
    from tests.api.test_admin_admins import ManualTestAdminAdmins
    test = ManualTestAdminAdmins()
    reports.append(test.run_all())

    # Admin Tenants
    from tests.api.test_admin_tenants import ManualTestAdminTenants
    test = ManualTestAdminTenants()
    reports.append(test.run_all())

    return reports


def run_tenant_tests() -> list[TestReport]:
    """运行企业管理端测试 / Test."""
    reports = []

    # Tenant Auth
    from tests.api.test_tenant_auth import ManualTestTenantAuth
    test = ManualTestTenantAuth()
    reports.append(test.run_all())

    # Tenant Permission Roles
    from tests.api.test_tenant_permission_roles import ManualTestTenantPermissionRoles
    test = ManualTestTenantPermissionRoles()
    reports.append(test.run_all())

    # Tenant Organization
    from tests.api.test_tenant_organization import ManualTestTenantOrganization
    test = ManualTestTenantOrganization()
    reports.append(test.run_all())

    # Tenant Admins
    from tests.api.test_tenant_admins import ManualTestTenantAdmins
    test = ManualTestTenantAdmins()
    reports.append(test.run_all())

    return reports


def print_summary(reports: list[TestReport]) -> int:
    """打印总体测试摘要 / Test."""
    total_tests = sum(r.total for r in reports)
    total_passed = sum(r.passed for r in reports)
    total_failed = sum(r.failed for r in reports)
    total_skipped = sum(r.skipped for r in reports)
    total_duration = sum(r.duration for r in reports)

    print("\n")
    print("=" * 70)
    print("API TEST SUMMARY")
    print("=" * 70)

    for report in reports:
        status = "[OK]" if report.failed == 0 else "[FAIL]"
        print(f"{status} {report.module}: {report.passed}/{report.total} 通过 ({report.duration:.2f}s)")

    print("-" * 70)
    print(f"TOTAL TESTS: {total_tests}")
    print(f"PASSED: {total_passed}")
    print(f"FAILED: {total_failed}")
    print(f"SKIPPED: {total_skipped}")
    print(f"DURATION: {total_duration:.2f}s")
    print("=" * 70)

    if total_failed > 0:
        print("\nFAILED TEST DETAILS:")
        for report in reports:
            for result in report.results:
                if result.status == TestStatus.FAILED:
                    print(f"\n  {report.module} > {result.name}")
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

    print("START API TESTS")
    print(f"TARGET: {os.environ.get('TEST_API_BASE_URL', 'http://localhost:8000')}")
    print()

    reports = []

    if args.module in ("admin", "all"):
        print("=" * 70)
        print("ADMIN TESTS")
        print("=" * 70)
        admin_reports = run_admin_tests()
        for report in admin_reports:
            report.print_summary(exit_on_failure=False)
        reports.extend(admin_reports)

    if args.module in ("tenant", "all"):
        print("\n")
        print("=" * 70)
        print("TENANT TESTS")
        print("=" * 70)
        tenant_reports = run_tenant_tests()
        for report in tenant_reports:
            report.print_summary(exit_on_failure=False)
        reports.extend(tenant_reports)

    # 打印总体摘要
    exit_code = print_summary(reports)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

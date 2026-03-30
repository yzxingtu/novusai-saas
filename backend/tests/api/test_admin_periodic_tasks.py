#!/usr/bin/env python3
"""平台定时任务 API 测试模块 / API.

测试 /admin/periodic-tasks/* 接口"""
import contextlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text

from app.core.database import sync_engine
from tests.api.base import (  # noqa: I001
    BaseAPITest,
    assert_equals,
    assert_error,
    assert_has_keys,
    assert_success,
    assert_true,
)


class ManualTestAdminPeriodicTasks(BaseAPITest):
    """平台定时任务测试 / Platform periodic task API tests."""

    module_name = "平台定时任务管理 (/admin/periodic-tasks)"

    def setup(self) -> None:
        self._do_login()
        self._test_data["created_task_ids"] = []
        self._test_data["timestamp"] = int(time.time())
        self._ensure_tenant_aware_base_task()

    def teardown(self) -> None:
        self._restore_tenant_aware_base_task()
        for task_id in self._test_data.get("created_task_ids", []):
            with contextlib.suppress(Exception):
                self.client.delete(f"/admin/periodic-tasks/{task_id}")
        # Best-effort cleanup by name prefix in case a previous assertion interrupted ID bookkeeping.
        timestamp = self._test_data.get("timestamp")
        if not timestamp:
            return
        with contextlib.suppress(Exception):
            resp = self.client.get("/admin/periodic-tasks")
            data = assert_success(resp, "获取定时任务列表失败")
            for item in data["data"]["items"]:
                name = str(item.get("name") or "")
                if name.startswith("api-") and str(timestamp) in name:
                    self.client.delete(f"/admin/periodic-tasks/{item['id']}")
        self._hard_cleanup_api_tasks(timestamp)

    def _run_tests(self) -> None:
        self.run_test("获取定时任务列表", self.test_list_periodic_tasks)
        self.run_test("配置 selected_tenants 待绑定任务", self.test_create_selected_pending_task)
        self.run_test("待绑定 selected_tenants 手动触发报错", self.test_trigger_selected_pending_task)
        self.run_test("省略 scope 更新 bindings 保留显式作用域", self.test_bindings_update_without_scope_preserves_scope)
        self.run_test("切换为 all_tenants 时清空显式 bindings", self.test_update_scope_to_all_tenants_clears_explicit_bindings)
        self.run_test("非 tenant-aware 处理器禁止写入 tenant 分发作用域", self.test_reject_non_tenant_handler_for_selected_scope)
        self.run_test("禁用插件任务触发返回明确错误", self.test_trigger_disabled_plugin_task_returns_clear_error)

    def test_list_periodic_tasks(self) -> None:
        resp = self.client.get("/admin/periodic-tasks")
        data = assert_success(resp, "获取定时任务列表失败")
        assert_has_keys(data["data"], ["items", "total", "page", "page_size"])
        assert_true(isinstance(data["data"]["items"], list), "items 应为列表")

    def test_create_selected_pending_task(self) -> None:
        task_id = self._configure_tenant_aware_task(
            scope="selected_tenants",
            tenant_ids=[],
        )
        resp = self.client.get(f"/admin/periodic-tasks/{task_id}")
        data = assert_success(resp, "获取 selected_tenants 待绑定任务失败")
        assert_has_keys(
            data["data"],
            [
                "id",
                "scope",
                "binding_count",
                "binding_required",
                "binding_configured",
                "assigned_tenant_ids",
            ],
        )
        assert_equals(data["data"]["scope"], "selected_tenants")
        assert_equals(data["data"]["binding_count"], 0)
        assert_true(data["data"]["binding_required"], "selected_tenants 应要求显式绑定")
        assert_true(
            data["data"]["binding_configured"] is False,
            "空绑定 selected_tenants 应标记为待配置",
        )
        self._test_data["selected_task_id"] = task_id

    def test_trigger_selected_pending_task(self) -> None:
        task_id = self._configure_tenant_aware_task(
            scope="selected_tenants",
            tenant_ids=[],
        )
        self._test_data["selected_task_id"] = task_id

        resp = self.client.post(f"/admin/periodic-tasks/{task_id}/trigger")
        data = assert_error(resp, 422, "待绑定任务触发应返回 422")
        assert_true(
            "至少绑定一个企业" in str(data.get("message", "")),
            "错误提示应明确说明需要先绑定企业",
        )

    def test_bindings_update_without_scope_preserves_scope(self) -> None:
        task_id = self._configure_tenant_aware_task(
            scope="admin_and_selected_tenants",
            tenant_ids=[1],
        )

        resp = self.client.put(
            f"/admin/periodic-tasks/{task_id}/bindings",
            data={"tenant_ids": [1, 2]},
        )
        assert_success(resp, "省略 scope 更新 bindings 失败")

        detail = assert_success(
            self.client.get(f"/admin/periodic-tasks/{task_id}"),
            "获取任务详情失败",
        )
        assert_equals(detail["data"]["scope"], "admin_and_selected_tenants")
        assert_equals(sorted(detail["data"]["assigned_tenant_ids"]), [1, 2])
        assert_equals(detail["data"]["binding_count"], 2)
        assert_true(detail["data"]["binding_configured"], "绑定后应标记为已配置")

    def test_update_scope_to_all_tenants_clears_explicit_bindings(self) -> None:
        task_id = self._configure_tenant_aware_task(
            scope="admin_and_selected_tenants",
            tenant_ids=[1],
        )

        resp = self.client.put(
            f"/admin/periodic-tasks/{task_id}",
            data={"scope": "all_tenants"},
        )
        data = assert_success(resp, "切换为 all_tenants 失败")
        assert_equals(data["data"]["scope"], "all_tenants")
        assert_equals(data["data"]["binding_count"], 0)
        assert_true(data["data"]["binding_required"] is False, "all_tenants 不要求显式绑定")
        assert_true(data["data"]["binding_configured"], "all_tenants 应视为已配置")

        bindings = assert_success(
            self.client.get(f"/admin/periodic-tasks/{task_id}/bindings"),
            "获取 all_tenants 绑定列表失败",
        )
        assert_equals(bindings["data"], [])

    def test_reject_non_tenant_handler_for_selected_scope(self) -> None:
        suffix = self._test_data["timestamp"]
        resp = self.client.post(
            "/admin/periodic-tasks",
            data={
                "name": f"api-invalid-tenant-scope-{suffix}",
                "task_path": f"app.tasks.codex.invalid_scope_{suffix}",
                "schedule_type": "interval",
                "interval_seconds": 3600,
                "is_active": False,
                "scope": "selected_tenants",
                "tenant_ids": [],
            },
        )
        data = assert_error(resp, 422, "非 tenant-aware handler 应被拒绝")
        assert_true(
            "不支持企业分发作用域" in str(data.get("message", "")),
            "错误提示应明确说明 handler 不支持 tenant 分发",
        )

    def test_trigger_disabled_plugin_task_returns_clear_error(self) -> None:
        resp = self.client.get("/admin/periodic-tasks")
        data = assert_success(resp, "获取定时任务列表失败")
        disabled_plugin_task = next(
            (
                item
                for item in data["data"]["items"]
                if item.get("definition_type") == "plugin"
                and item.get("plugin_enabled") is False
            ),
            None,
        )
        if not disabled_plugin_task:
            return

        error = assert_error(
            self.client.post(f"/admin/periodic-tasks/{disabled_plugin_task['id']}/trigger"),
            422,
            "禁用插件任务触发应返回 422",
        )
        assert_true(
            "未启用" in str(error.get("message", "")) or "disabled" in str(error.get("message", "")).lower(),
            "错误提示应明确说明插件未启用",
        )

    def _do_login(self) -> None:
        self.login_admin()

    def _ensure_tenant_aware_base_task(self) -> None:
        self._cleanup_deleted_tenant_aware_rows()
        resp = self.client.get("/admin/periodic-tasks")
        data = assert_success(resp, "获取定时任务列表失败")
        existing = next(
            (
                item
                for item in data["data"]["items"]
                if item.get("task_path") == "app.ai.rag.processor.process_document"
            ),
            None,
        )
        if existing:
            self._test_data["tenant_aware_task_id"] = existing["id"]
            self._test_data["tenant_aware_created"] = False
            self._test_data["tenant_aware_original_scope"] = existing["scope"]
            self._test_data["tenant_aware_original_name"] = existing["name"]
            self._test_data["tenant_aware_original_is_active"] = existing["is_active"]
            self._test_data["tenant_aware_original_tenant_ids"] = existing["assigned_tenant_ids"]
            return

        suffix = self._test_data["timestamp"]
        resp = self.client.post(
            "/admin/periodic-tasks",
            data={
                "name": f"api-tenant-aware-base-{suffix}",
                "task_path": "app.ai.rag.processor.process_document",
                "schedule_type": "interval",
                "interval_seconds": 3600,
                "is_active": False,
                "scope": "admin_only",
                "tenant_ids": [],
            },
        )
        data = assert_success(resp, "创建 tenant-aware 基础任务失败")
        self._test_data["tenant_aware_task_id"] = data["data"]["id"]
        self._test_data["tenant_aware_created"] = True
        self._test_data["created_task_ids"].append(data["data"]["id"])

    @staticmethod
    def _cleanup_deleted_tenant_aware_rows() -> None:
        with sync_engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, is_deleted
                    FROM task_definitions
                    WHERE handler_path = :handler_path
                    """
                ),
                {"handler_path": "app.ai.rag.processor.process_document"},
            ).fetchall()
            if not rows:
                return

            deleted_ids = [
                int(row[0])
                for row in rows
                if bool(row[1])
            ]
            if not deleted_ids:
                return

            conn.execute(
                text(
                    """
                    DELETE FROM tenant_task_bindings
                    WHERE task_definition_id IN (
                        SELECT id
                        FROM task_definitions
                        WHERE handler_path = :handler_path
                          AND is_deleted IS true
                    )
                    """
                ),
                {"handler_path": "app.ai.rag.processor.process_document"},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM task_definitions
                    WHERE handler_path = :handler_path
                      AND is_deleted IS true
                    """
                ),
                {"handler_path": "app.ai.rag.processor.process_document"},
            )

    @staticmethod
    def _hard_cleanup_api_tasks(timestamp: int) -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM tenant_task_bindings
                    WHERE task_definition_id IN (
                        SELECT id FROM task_definitions WHERE name LIKE :pattern
                    )
                    """
                ),
                {"pattern": f"api-%{timestamp}%"},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM task_definitions
                    WHERE name LIKE :pattern
                    """
                ),
                {"pattern": f"api-%{timestamp}%"},
            )

    def _configure_tenant_aware_task(self, *, scope: str, tenant_ids: list[int]) -> int:
        task_id = self._test_data.get("tenant_aware_task_id")
        if not task_id:
            raise AssertionError("没有可用的 tenant-aware 基础任务")

        resp = self.client.put(
            f"/admin/periodic-tasks/{task_id}",
            data={
                "scope": scope,
                "tenant_ids": tenant_ids,
                "is_active": False,
            },
        )
        assert_success(resp, "配置 tenant-aware 基础任务失败")
        return task_id

    def _restore_tenant_aware_base_task(self) -> None:
        task_id = self._test_data.get("tenant_aware_task_id")
        if not task_id or self._test_data.get("tenant_aware_created"):
            return

        original_scope = self._test_data.get("tenant_aware_original_scope")
        original_tenant_ids = self._test_data.get("tenant_aware_original_tenant_ids", [])
        original_is_active = self._test_data.get("tenant_aware_original_is_active", False)

        with contextlib.suppress(Exception):
            self.client.put(
                f"/admin/periodic-tasks/{task_id}",
                data={
                    "scope": original_scope,
                    "tenant_ids": original_tenant_ids,
                    "is_active": original_is_active,
                },
            )


if __name__ == "__main__":
    test = ManualTestAdminPeriodicTasks()
    report = test.run_all()
    report.print_summary()

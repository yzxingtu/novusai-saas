"""
批量生成审计日志 — 单元测试

覆盖：
- AuditEvent 创建与序列化
- compute_project_hash 稳定性
- AuditStore 记录/查询/过滤/清空
- create_audit_event 工厂函数
- run_id 关联查询
- 环形缓冲区溢出
"""

import pytest

from app.codegen.audit import (
    AuditEvent,
    AuditEventType,
    AuditStatus,
    AuditStore,
    AuditSummary,
    compute_project_hash,
    create_audit_event,
)


# ============================================================
# compute_project_hash
# ============================================================


class TestProjectHash:
    """项目配置指纹"""

    def test_deterministic(self):
        """同一输入 hash 一致"""
        project = {"project_name": "test", "entities": []}
        h1 = compute_project_hash(project)
        h2 = compute_project_hash(project)
        assert h1 == h2
        assert len(h1) == 12

    def test_different_input(self):
        """不同输入 hash 不同"""
        h1 = compute_project_hash({"project_name": "a"})
        h2 = compute_project_hash({"project_name": "b"})
        assert h1 != h2

    def test_key_order_independent(self):
        """key 顺序不影响 hash"""
        h1 = compute_project_hash({"a": 1, "b": 2})
        h2 = compute_project_hash({"b": 2, "a": 1})
        assert h1 == h2


# ============================================================
# create_audit_event
# ============================================================


class TestCreateAuditEvent:
    """审计事件工厂"""

    def test_basic_event(self):
        event = create_audit_event(
            AuditEventType.PREVIEW,
            entity_count=3,
            file_count=15,
            entities=["order", "product", "customer"],
        )
        assert event.event_type == AuditEventType.PREVIEW
        assert event.status == AuditStatus.SUCCESS
        assert event.summary.entity_count == 3
        assert event.summary.file_count == 15
        assert len(event.run_id) == 12

    def test_error_event(self):
        event = create_audit_event(
            AuditEventType.ERROR,
            status=AuditStatus.FAILED,
            error_message="Something went wrong" * 100,
        )
        assert event.status == AuditStatus.FAILED
        assert len(event.error_message) <= 300

    def test_write_event(self):
        event = create_audit_event(
            AuditEventType.WRITE,
            written=10,
            skipped=2,
            merged=3,
            conflicts=1,
        )
        assert event.summary.written == 10
        assert event.summary.skipped == 2
        assert event.summary.merged == 3
        assert event.summary.conflicts == 1

    def test_custom_run_id(self):
        event = create_audit_event(
            AuditEventType.GENERATE,
            run_id="custom123456",
        )
        assert event.run_id == "custom123456"


# ============================================================
# AuditStore
# ============================================================


class TestAuditStore:
    """审计存储"""

    def test_record_and_count(self):
        store = AuditStore(max_events=100)
        event = create_audit_event(AuditEventType.PREVIEW)
        store.record(event)
        assert store.count() == 1

    def test_query_all(self):
        store = AuditStore()
        for _ in range(5):
            store.record(create_audit_event(AuditEventType.PREVIEW))
        results = store.query(limit=10)
        assert len(results) == 5

    def test_query_by_event_type(self):
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW))
        store.record(create_audit_event(AuditEventType.WRITE))
        store.record(create_audit_event(AuditEventType.PREVIEW))

        results = store.query(event_type=AuditEventType.PREVIEW)
        assert len(results) == 2

    def test_query_by_actor(self):
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW, actor="alice"))
        store.record(create_audit_event(AuditEventType.PREVIEW, actor="bob"))

        results = store.query(actor="alice")
        assert len(results) == 1
        assert results[0].actor == "alice"

    def test_query_by_run_id(self):
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW, run_id="run_001"))
        store.record(create_audit_event(AuditEventType.WRITE, run_id="run_001"))
        store.record(create_audit_event(AuditEventType.PREVIEW, run_id="run_002"))

        results = store.query(run_id="run_001")
        assert len(results) == 2

    def test_query_pagination(self):
        store = AuditStore()
        for i in range(10):
            store.record(create_audit_event(
                AuditEventType.PREVIEW, actor=f"user_{i}",
            ))

        page1 = store.query(limit=3, offset=0)
        page2 = store.query(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].actor != page2[0].actor

    def test_query_newest_first(self):
        """查询结果按新→旧排列"""
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW, actor="first"))
        store.record(create_audit_event(AuditEventType.PREVIEW, actor="second"))

        results = store.query()
        assert results[0].actor == "second"
        assert results[1].actor == "first"

    def test_clear(self):
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW))
        store.clear()
        assert store.count() == 0

    def test_ring_buffer_overflow(self):
        """环形缓冲区溢出：旧事件被丢弃"""
        store = AuditStore(max_events=5)
        for i in range(10):
            store.record(create_audit_event(
                AuditEventType.PREVIEW, actor=f"user_{i}",
            ))

        assert store.count() == 5
        results = store.query()
        # 最新的 5 条
        actors = [r.actor for r in results]
        assert "user_9" in actors
        assert "user_0" not in actors

    def test_get_run_events(self):
        """获取同一 run 的所有事件"""
        store = AuditStore()
        store.record(create_audit_event(AuditEventType.PREVIEW, run_id="run_x"))
        store.record(create_audit_event(AuditEventType.GENERATE, run_id="run_x"))
        store.record(create_audit_event(AuditEventType.WRITE, run_id="run_x"))
        store.record(create_audit_event(AuditEventType.PREVIEW, run_id="run_y"))

        run_events = store.get_run_events("run_x")
        assert len(run_events) == 3
        types = [e.event_type for e in run_events]
        assert AuditEventType.PREVIEW in types
        assert AuditEventType.GENERATE in types
        assert AuditEventType.WRITE in types


# ============================================================
# 序列化
# ============================================================


class TestSerialization:
    """审计事件序列化"""

    def test_event_to_dict(self):
        event = create_audit_event(
            AuditEventType.WRITE,
            actor="admin",
            written=5,
            errors=1,
        )
        d = event.model_dump(mode="json")
        assert d["event_type"] == "write"
        assert d["summary"]["written"] == 5
        assert d["actor"] == "admin"

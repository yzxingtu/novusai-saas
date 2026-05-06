"""TaskRun reliability tests / TaskRun 可靠性测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from celery.exceptions import Ignore

from app.tasks.base import BaseTask, TenantTask, build_task_run_key


class _RecordingTask(BaseTask):
    name = "tests.recording"

    def _apply_db_config(self) -> None:
        return None


class _RecordingTenantTask(TenantTask):
    name = "tests.tenant_recording"

    def _apply_db_config(self) -> None:
        return None


class _FakeQuery:
    def __init__(self, existing) -> None:
        self._existing = existing

    def filter(self, *_args):
        return self

    def first(self):
        return self._existing


class _FakeSession:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added: list = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def query(self, _model):
        return _FakeQuery(self.existing)

    def add(self, item) -> None:
        self.added.append(item)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class _ClosableSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _headers(**overrides):
    headers = {
        "task_definition_id": 12,
        "binding_id": 34,
        "task_code_snapshot": "tenant.cleanup",
        "task_name_snapshot": "Tenant Cleanup",
        "handler_path_snapshot": "app.tasks.demo.cleanup",
        "trigger_source": "scheduler",
        "run_kind": "tenant_binding",
        "owner_tenant_id": None,
        "effective_tenant_id": 56,
        "trigger_slot": "interval:60:12345",
    }
    headers.update(overrides)
    return headers


def _patch_tenant_eligibility(monkeypatch, result):
    sessions: list[_ClosableSession] = []

    def session_factory() -> _ClosableSession:
        session = _ClosableSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        "app.tasks.base.sync_session_factory",
        session_factory,
    )
    monkeypatch.setattr(
        "app.services.system.task_tenant_eligibility_service."
        "TaskTenantEligibilityService.resolve_tenant_eligibility_sync",
        classmethod(lambda _cls, _session, _tenant_id: result),
    )
    return sessions


def test_build_task_run_key_uses_business_identity_without_celery_id() -> None:
    run_key = build_task_run_key(
        task_definition_id=12,
        binding_id=34,
        owner_tenant_id=None,
        effective_tenant_id=56,
        trigger_source="scheduler",
        trigger_slot="interval:60:12345",
    )

    assert run_key == (
        "task_definition:12|binding:34|source:scheduler|"
        "trigger:interval:60:12345"
    )


def test_record_task_run_start_writes_run_key_and_trace(monkeypatch) -> None:
    task = _RecordingTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers=_headers()))
    fake_session = _FakeSession()
    monkeypatch.setattr(
        "app.tasks.base.sync_session_factory",
        lambda: fake_session,
    )

    task.before_start("celery-task-1", (), {"tenant_id": 56})

    assert fake_session.committed is True
    assert len(fake_session.added) == 1
    run = fake_session.added[0]
    assert run.celery_task_id == "celery-task-1"
    assert run.run_key == (
        "task_definition:12|binding:34|source:scheduler|"
        "trigger:interval:60:12345"
    )
    assert run.trace_id


def test_duplicate_run_key_raises_ignore_before_business_execution(monkeypatch) -> None:
    run_key = (
        "task_definition:12|binding:34|source:scheduler|"
        "trigger:interval:60:12345"
    )
    task = _RecordingTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers=_headers()))
    fake_session = _FakeSession(existing=SimpleNamespace(id=99, run_key=run_key))
    monkeypatch.setattr(
        "app.tasks.base.sync_session_factory",
        lambda: fake_session,
    )

    with pytest.raises(Ignore):
        task.before_start("celery-task-duplicate", (), {"tenant_id": 56})

    assert fake_session.added == []


def test_tenant_task_rejects_missing_tenant_id_before_business_execution() -> None:
    task = _RecordingTenantTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers={}))

    with pytest.raises(Ignore):
        task.before_start("tenant-task-missing", (), {})

    assert task.tenant_id is None


def test_tenant_task_rejects_mismatched_effective_tenant_header() -> None:
    task = _RecordingTenantTask()
    task.request_stack = SimpleNamespace(
        top=SimpleNamespace(headers={"effective_tenant_id": 57})
    )

    with pytest.raises(Ignore):
        task.before_start("tenant-task-mismatch", (), {"tenant_id": 56})

    assert task.tenant_id is None


def test_tenant_task_rejects_ineligible_tenant(monkeypatch) -> None:
    task = _RecordingTenantTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers={}))
    sessions = _patch_tenant_eligibility(
        monkeypatch,
        SimpleNamespace(is_eligible=False, reason="tenant_inactive"),
    )

    with pytest.raises(Ignore):
        task.before_start("tenant-task-ineligible", (), {"tenant_id": 56})

    assert task.tenant_id is None
    assert sessions[0].closed is True


def test_tenant_task_accepts_eligible_tenant(monkeypatch) -> None:
    task = _RecordingTenantTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers={}))
    sessions = _patch_tenant_eligibility(
        monkeypatch,
        SimpleNamespace(is_eligible=True, reason=None),
    )

    task.before_start("tenant-task-ok", (), {"tenant_id": 56})

    assert task.tenant_id == 56
    assert sessions[0].closed is True

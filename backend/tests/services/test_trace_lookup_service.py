"""TraceLookupService tests / TraceLookupService 单元测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services.system.trace_lookup_service import TraceLookupService


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _FakeResult(self._rows)


def test_lookup_aggregates_db_and_logs_with_redaction(tmp_path: Path) -> None:
    trace_id = "tid-001"
    log_file = tmp_path / "error.log"
    log_file.write_text(
        "\n".join(
            [
                "hello",
                f"2026-01-01 | ERROR | [trace_id={trace_id}] | Authorization: Bearer abc.def.ghi",
                "Traceback (most recent call last):",
                "ValueError: bad value",
            ]
        ),
        encoding="utf-8",
    )
    row = SimpleNamespace(
        id=1,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        tenant_id=1,
        user_type="tenant_admin",
        user_id=10,
        username="alice",
        module="ai",
        action="chat",
        method="POST",
        path="/tenant/ai/conversations",
        status_code=500,
        response_code=5000,
        response_message="failed",
        duration_ms=120,
        query_params={"token": "abc"},
        request_body={"password": "secret"},
    )
    service = TraceLookupService(db=_FakeDB([row]), log_dir=tmp_path)

    payload = asyncio.run(
        service.lookup(
            trace_id,
            source="all",
            context=1,
            max_blocks=5,
            since_hours=None,
            redact=True,
        )
    ).to_dict()

    assert payload["summary"]["operation_logs"] == 1
    assert payload["summary"]["log_matches"] >= 1
    assert payload["primary_error"] is not None
    assert payload["operation_logs"][0]["query_params"]["token"] == "***REDACTED***"
    assert payload["operation_logs"][0]["request_body"]["password"] == "***REDACTED***"
    block = "\n".join(payload["primary_error"]["block"])
    assert "***REDACTED***" in block


def test_lookup_without_redaction_keeps_raw_values(tmp_path: Path) -> None:
    trace_id = "tid-002"
    log_file = tmp_path / "app.log"
    log_file.write_text(
        f"2026-01-01 | INFO | [trace_id={trace_id}] | token=raw-token",
        encoding="utf-8",
    )
    service = TraceLookupService(db=_FakeDB([]), log_dir=tmp_path)

    payload = asyncio.run(
        service.lookup(
            trace_id,
            source="logs",
            context=0,
            max_blocks=2,
            since_hours=None,
            redact=False,
        )
    ).to_dict()

    assert payload["summary"]["operation_logs"] == 0
    assert payload["summary"]["log_matches"] == 1
    assert "raw-token" in "\n".join(payload["log_matches"][0]["block"])

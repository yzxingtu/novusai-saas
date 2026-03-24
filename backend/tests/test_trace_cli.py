"""Trace CLI tests / trace CLI 测试。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from click.testing import CliRunner


def test_trace_show_json_success(monkeypatch) -> None:
    from app.cli import cli
    from app.services.system.trace_lookup_service import TraceLookupResult

    class _FakeTraceLookupService:
        def __init__(self, db=None, log_dir=None):
            self.db = db
            self.log_dir = log_dir

        async def lookup(self, trace_id: str, **_kwargs):
            return TraceLookupResult(
                trace_id=trace_id,
                operation_logs=[],
                log_matches=[{"file": "error.log", "line": 3, "start_line": 1, "end_line": 5, "block": ["x"]}],
                primary_error={"file": "error.log", "line": 3, "start_line": 1, "end_line": 5, "block": ["x"]},
                summary={
                    "operation_logs": 0,
                    "log_matches": 1,
                    "log_files": ["error.log"],
                    "source": "logs",
                },
                redacted=True,
            )

    monkeypatch.setattr(
        "app.services.system.trace_lookup_service.TraceLookupService",
        _FakeTraceLookupService,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["trace", "show", "trace-abc", "--source", "logs", "--json"],
    )

    assert result.exit_code == 0
    assert '"trace_id": "trace-abc"' in result.output
    assert '"log_matches": 1' in result.output


def test_trace_show_blocks_unsafe_output_in_production(monkeypatch) -> None:
    from app.cli import cli
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.delenv("NOVUSAI_ALLOW_UNSAFE_TRACE", raising=False)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["trace", "show", "trace-abc", "--source", "logs", "--no-redact"],
    )

    assert result.exit_code == 2
    assert "Unsafe trace output is blocked" in result.output


def test_trace_show_auto_falls_back_to_logs_when_db_lookup_fails(monkeypatch) -> None:
    from app.cli import cli
    from app.services.system.trace_lookup_service import TraceLookupResult

    class _FakeTraceLookupService:
        def __init__(self, db=None, log_dir=None):
            self.db = db
            self.log_dir = log_dir

        async def lookup(self, trace_id: str, **_kwargs):
            if self.db is not None:
                raise RuntimeError("db unavailable")
            return TraceLookupResult(
                trace_id=trace_id,
                operation_logs=[],
                log_matches=[{"file": "error.log", "line": 3, "start_line": 1, "end_line": 5, "block": ["x"]}],
                primary_error={"file": "error.log", "line": 3, "start_line": 1, "end_line": 5, "block": ["x"]},
                summary={
                    "operation_logs": 0,
                    "log_matches": 1,
                    "log_files": ["error.log"],
                    "source": "logs",
                },
                redacted=True,
            )

    @asynccontextmanager
    async def _fake_db_context():
        yield object()

    monkeypatch.setattr(
        "app.services.system.trace_lookup_service.TraceLookupService",
        _FakeTraceLookupService,
    )
    monkeypatch.setattr("app.core.database.get_db_context", _fake_db_context)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["trace", "show", "trace-auto", "--json"],
    )

    assert result.exit_code == 0
    assert '"trace_id": "trace-auto"' in result.output
    assert '"source": "logs"' in result.output

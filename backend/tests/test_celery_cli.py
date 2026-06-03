"""Celery CLI tests / Celery CLI 测试。"""

from __future__ import annotations

from click.testing import CliRunner


def test_celery_dev_fails_fast_when_broker_unavailable(monkeypatch) -> None:
    """celery dev 在 broker 不可达时给出明确提示，避免进入 Celery 重试循环。"""
    from app.cli import cli

    subprocess_calls: list[object] = []

    monkeypatch.setattr(
        "app.cli_commands.core_commands.runtime_helpers.check_celery_broker_url",
        lambda *_args, **_kwargs: False,
    )

    def _unexpected_subprocess_run(*args, **_kwargs):
        subprocess_calls.append(args)
        raise AssertionError("Celery subprocess should not start")

    monkeypatch.setattr(
        "app.cli_commands.core_commands.subprocess.run",
        _unexpected_subprocess_run,
    )

    result = CliRunner().invoke(cli, ["celery", "dev"])

    assert result.exit_code == 1
    assert "Celery broker is not reachable" in result.output
    assert "docker compose -f docker-compose.dev.yml up -d redis" in result.output
    assert "Starting Celery Worker + Beat" not in result.output
    assert subprocess_calls == []


def test_celery_worker_checks_broker_before_launch(monkeypatch) -> None:
    """celery worker 启动前探测 broker，并在可达时继续调用 Celery。"""
    from app.cli import cli

    checked_urls: list[str] = []
    celery_runs: list[tuple[object, object, list[str]]] = []

    def _fake_check(broker_url, *_args, **_kwargs):
        checked_urls.append(broker_url)
        return True

    def _fake_run_celery(backend_dir, celery_app, args):
        celery_runs.append((backend_dir, celery_app, args))

    monkeypatch.setattr(
        "app.cli_commands.core_commands.runtime_helpers.check_celery_broker_url",
        _fake_check,
    )
    monkeypatch.setattr(
        "app.cli_commands.core_commands.runtime_helpers.run_celery",
        _fake_run_celery,
    )

    result = CliRunner().invoke(
        cli,
        ["celery", "worker", "-Q", "default", "--loglevel", "warning"],
    )

    assert result.exit_code == 0
    assert checked_urls
    assert len(celery_runs) == 1
    assert celery_runs[0][1] == "app.celery_app:celery_app"
    assert celery_runs[0][2] == ["worker", "--loglevel=warning", "-Q", "default"]


def test_redact_url_hides_broker_password() -> None:
    """redact_url 隐藏连接串密码，CLI 错误提示不泄露敏感信息。"""
    from app.cli_runtime_helpers import redact_url

    assert (
        redact_url("redis://:secret@localhost:6379/1")
        == "redis://:***@localhost:6379/1"
    )
    assert (
        redact_url("redis://user:secret@localhost:6379/1")
        == "redis://user:***@localhost:6379/1"
    )
    assert redact_url("redis://localhost:6379/1") == "redis://localhost:6379/1"

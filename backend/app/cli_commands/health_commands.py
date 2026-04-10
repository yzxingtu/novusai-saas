"""Health and info CLI command domain."""

from __future__ import annotations

import os
import sys

import click

from app import cli_runtime_helpers as runtime_helpers
from app.cli_commands import state as S

logger = S.logger
settings = S.settings
_BACKEND_DIR = S._BACKEND_DIR
_STATUS_OK = S._STATUS_OK
_STATUS_FAIL = S._STATUS_FAIL
_CHECK_DB = S._CHECK_DB
_CHECK_REDIS = S._CHECK_REDIS
_CHECK_CELERY = S._CHECK_CELERY
_CHECK_CELERY_BROKER = S._CHECK_CELERY_BROKER


def _check_db() -> bool:
    return runtime_helpers.check_db(logger)


def _check_redis() -> bool:
    return runtime_helpers.check_redis(logger)


def _check_celery() -> bool:
    return runtime_helpers.check_celery(logger)


@click.group("check", help="Environment connectivity check", invoke_without_command=True)
@click.pass_context
def check_cmd(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(check_all)


@check_cmd.command("all")
def check_all() -> None:
    """Check all services (DB, Redis, Celery) / 检查所有服务（DB、Redis、Celery）"""
    os.chdir(_BACKEND_DIR)
    checks = [
        (_CHECK_DB, _check_db),
        (_CHECK_REDIS, _check_redis),
        (_CHECK_CELERY_BROKER, _check_celery),
    ]
    for name, fn in checks:
        ok = fn()
        status = (
            click.style(_STATUS_OK, fg="green")
            if ok
            else click.style(_STATUS_FAIL, fg="red")
        )
        click.echo(f"{name}: {status}")
    failed = sum(1 for _, fn in checks if not fn())
    if failed:
        sys.exit(1)


@check_cmd.command()
def db() -> None:
    """Check database connection / 检查数据库连接"""
    ok = _check_db()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
    click.echo(f"{_CHECK_DB}: {status}")
    sys.exit(0 if ok else 1)


@check_cmd.command()
def redis() -> None:
    """Check Redis connection / 检查 Redis 连接"""
    ok = _check_redis()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
    click.echo(f"{_CHECK_REDIS}: {status}")
    sys.exit(0 if ok else 1)


@check_cmd.command()
def celery() -> None:
    """Check Celery broker connection / 检查 Celery Broker 连接"""
    ok = _check_celery()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
    click.echo(f"{_CHECK_CELERY}: {status}")
    sys.exit(0 if ok else 1)


@click.command("info")
def info() -> None:
    """Show version, environment, and config summary (sensitive values masked) / 显示版本、环境与配置摘要（敏感项脱敏）"""

    click.echo("NovusAI SaaS")
    click.echo(f"  Version:  {settings.APP_VERSION}")
    click.echo(f"  Env:      {settings.APP_ENV}")
    click.echo(f"  Python:   {sys.version.split()[0]}")
    click.echo(
        f"  Database: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )
    click.echo(f"  Redis:    {settings.REDIS_HOST}:{settings.REDIS_PORT}")

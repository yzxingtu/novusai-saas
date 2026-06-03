"""CLI command entrypoint shell.

This module assembles the supported CLI command group while delegating command
logic to focused modules under `app.cli_commands.*`.
"""

from __future__ import annotations

import os

import click

os.environ.setdefault("NOVUSAI_CLI_DISABLE_FILE_LOGGING", "1")

from app.cli_commands import ai_commands as _ai
from app.cli_commands import codegen_core as _codegen_core
from app.cli_commands import core_commands as _core
from app.cli_commands import health_commands as _health
from app.cli_commands import trace_commands as _trace
from app.core.config import settings


@click.group()
@click.version_option(
    version=settings.APP_VERSION,
    prog_name="NovusAI",
)
def cli() -> None:
    """NovusAI SaaS Management CLI / NovusAI SaaS 管理命令行工具"""
    pass


def _register_commands() -> None:
    cli.add_command(_core.run_cmd)
    cli.add_command(_core.celery_cmd)
    cli.add_command(_core.db_cmd)
    cli.add_command(_core.plugin_cmd)
    cli.add_command(_core.license_cmd)
    cli.add_command(_trace.trace_cmd)
    cli.add_command(_ai.ai_cmd)
    cli.add_command(_codegen_core.codegen_cmd)
    cli.add_command(_health.check_cmd)
    cli.add_command(_health.info)


_register_commands()
__all__ = ["cli"]


if __name__ == "__main__":
    cli()

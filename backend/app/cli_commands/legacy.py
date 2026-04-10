"""Legacy CLI compatibility shell.

This module preserves the original `app.cli_commands.legacy` import surface while
delegating command logic to focused modules under `app.cli_commands.*`.
"""

from __future__ import annotations

import sys
import types

import click

from app.cli_commands import ai_commands as _ai
from app.cli_commands import ai_norm as _ai_norm
from app.cli_commands import ai_render as _ai_render
from app.cli_commands import ai_snapshot as _ai_snapshot
from app.cli_commands import codegen_core as _codegen_core
from app.cli_commands import codegen_manage as _codegen_manage
from app.cli_commands import core_commands as _core
from app.cli_commands import health_commands as _health
from app.cli_commands import state as _state
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


def _export_module_symbols(module: object) -> None:
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        globals()[name] = value


_register_commands()
_OVERRIDE_TARGET_MODULES = (
    _state,
    _core,
    _trace,
    _ai_norm,
    _ai_snapshot,
    _ai_render,
    _ai,
    _codegen_core,
    _codegen_manage,
    _health,
)
for _module in (
    _state,
    _core,
    _trace,
    _ai_norm,
    _ai_snapshot,
    _ai_render,
    _ai,
    _codegen_core,
    _codegen_manage,
    _health,
):
    _export_module_symbols(_module)


class _LegacyCompatModule(types.ModuleType):
    """Propagate patched legacy symbols into split command modules."""

    def __setattr__(self, name: str, value: object) -> None:
        for module in _OVERRIDE_TARGET_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)
        super().__setattr__(name, value)


_MODULE = sys.modules[__name__]
_MODULE.__class__ = _LegacyCompatModule

# Preserve this module's root group after bulk exports and class swap.
setattr(_MODULE, "cli", cli)

__all__ = [name for name in globals() if not name.startswith("__")]


if __name__ == "__main__":
    cli()

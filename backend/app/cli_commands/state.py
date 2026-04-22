"""Shared CLI runtime state and helpers."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import click

from app import cli_runtime_helpers as _runtime_helpers
from app.core.config import settings as _settings
from app.core.logging import LogManager, suppress_console_logging

logger = LogManager.get_logger("cli")

runtime_helpers = _runtime_helpers
settings = _settings

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_CELERY_APP = "app.celery_app:celery_app"
_ALL_QUEUES = "default,high_priority,ai_gateway,scheduled,notification"
_CODEGEN_PROJECT_ROOT = _BACKEND_DIR.parent

_STATUS_OK = "OK"
_STATUS_FAIL = "FAIL"
_CHECK_DB = "Database"
_CHECK_REDIS = "Redis"
_CHECK_CELERY = "Celery"
_CHECK_CELERY_BROKER = "Celery Broker"


def _load_config_from_file(path: str) -> dict:
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_config_stdin() -> dict:
    import yaml

    data = sys.stdin.read()
    return yaml.safe_load(data) or {}


def _deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)


def _json_default(value: object) -> object:
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _ensure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                continue


def _echo_json(data: dict) -> None:
    import json

    _ensure_utf8_stdio()
    click.echo(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default))


def _echo_compact_json(data: object) -> None:
    import json

    _ensure_utf8_stdio()
    click.echo(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )
    )


def _json_error(
    message: str, *, code: str | None = None, data: dict | None = None
) -> dict:
    payload: dict = {
        "success": False,
        "data": data,
        "error": {"message": message},
    }
    if code:
        payload["error"]["code"] = code
    return payload


def _json_success(data: dict | list | None = None) -> dict:
    return {"success": True, "data": data, "error": None}


def _codegen_delete_hint(reason_code: str | None, config_id: int) -> str | None:
    if reason_code in {
        "manifest_present",
        "generated_state",
        "generation_history_present",
    }:
        return f"Hint: run `novusai codegen rollback --id {config_id}` first."
    return None


@contextmanager
def _suppress_logging(enabled: bool):
    if not enabled:
        yield
        return

    import logging

    with suppress_console_logging(True):
        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            yield
        finally:
            logging.disable(previous_disable)


def _run_quietly(enabled: bool, func, *args, **kwargs):
    with _suppress_logging(enabled):
        return func(*args, **kwargs)

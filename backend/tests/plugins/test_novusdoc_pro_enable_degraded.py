"""novusdoc-pro 启用降级回归测试。"""

from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from app.plugins.module_loader import load_plugin_module


@pytest.mark.asyncio
async def test_novusdoc_pro_enable_degrades_when_y_py_missing(monkeypatch) -> None:
    module = load_plugin_module("novusdoc-pro", "main")
    assert module is not None

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "y_py":
            raise ImportError("mocked missing y_py")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    log_records: list[tuple[str, str]] = []
    logger = SimpleNamespace(
        info=lambda msg, *args, **kwargs: log_records.append(("info", str(msg))),
        warning=lambda msg, *args, **kwargs: log_records.append(("warning", str(msg))),
    )
    ctx = SimpleNamespace(get_logger=lambda: logger)

    plugin = module.NovusdocProPlugin()
    await plugin.on_enable(ctx)

    assert any(
        level == "warning" and "enabled in degraded mode" in message
        for level, message in log_records
    )

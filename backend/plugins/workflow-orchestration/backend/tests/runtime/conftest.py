from __future__ import annotations

import pytest

from app.plugins.module_loader import load_plugin_module, unload_plugin_modules

PLUGIN_NAME = "workflow-orchestration"


@pytest.fixture(autouse=True)
def _reset_plugin_modules() -> None:
    unload_plugin_modules(PLUGIN_NAME)
    yield
    unload_plugin_modules(PLUGIN_NAME)


@pytest.fixture()
def load_plugin_backend_module():
    def _load(dotted_path: str):
        module = load_plugin_module(PLUGIN_NAME, dotted_path)
        assert module is not None
        return module

    return _load

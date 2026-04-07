"""Loader regression tests for the weather plugin compatibility module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_MODULE_FILE = Path(__file__).parent.parent / "_loader.py"
_MODULE_NAME = "plugins.weather_widget_test.loader"

spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_FILE)
assert spec and spec.loader
loader_mod = importlib.util.module_from_spec(spec)
sys.modules[_MODULE_NAME] = loader_mod
spec.loader.exec_module(loader_mod)


class TestLoader:
    def teardown_method(self):
        sys.modules.pop(loader_mod._MODULE_NAME, None)

    def test_module_is_ready_requires_expected_exports(self):
        partial = SimpleNamespace(get_current_weather=lambda *_args, **_kwargs: None)
        assert loader_mod._module_is_ready(partial) is False

    def test_get_open_meteo_reloads_partial_cached_module(self):
        sys.modules[loader_mod._MODULE_NAME] = SimpleNamespace(
            get_current_weather=lambda *_args, **_kwargs: None
        )

        module = loader_mod.get_open_meteo()

        assert hasattr(module, "get_weather_all")
        assert hasattr(module, "get_air_quality")

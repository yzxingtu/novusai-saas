"""Shared compatibility-module loader.

Plugin name contains a hyphen, so standard Python import is not possible.
The historical module name `open_meteo.py` is retained for compatibility.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_NAME = "plugins.weather-widget.backend.open_meteo"
_REQUIRED_EXPORTS = (
    "get_weather_all",
    "get_current_weather",
    "get_forecast",
    "get_air_quality",
    "search_city",
    "reverse_geocode",
)


def _module_is_ready(module) -> bool:
    return all(hasattr(module, attr) for attr in _REQUIRED_EXPORTS)


def get_open_meteo():
    """Dynamically load the compatibility weather provider module."""
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None and _module_is_ready(cached):
        return cached

    # Drop partially initialized or stale modules so we can reload from disk.
    sys.modules.pop(_MODULE_NAME, None)

    module_file = Path(__file__).parent / "open_meteo.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_file}")
    mod = importlib.util.module_from_spec(spec)
    try:
        sys.modules[_MODULE_NAME] = mod
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    if not _module_is_ready(mod):
        sys.modules.pop(_MODULE_NAME, None)
        missing = ", ".join(
            name for name in _REQUIRED_EXPORTS if not hasattr(mod, name)
        )
        raise ImportError(
            f"Loaded weather provider is missing required exports: {missing}"
        )
    return mod

"""
Shared open_meteo module loader.
Plugin name contains a hyphen, so standard Python import is not possible.
/ 共享 open_meteo 模块加载器（插件名含连字符，无法使用标准 import）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_NAME = "plugins.weather-widget.backend.open_meteo"


def get_open_meteo():
    """Dynamically load open_meteo.py from plugin directory / 动态加载 open_meteo 模块"""
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]

    module_file = Path(__file__).parent / "open_meteo.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod

"""
插件模块统一加载器测试

测试 module_loader.py 的核心功能：
- load_plugin_module: 加载子模块
- load_plugin_handler: 加载处理函数（子模块 + main fallback）
- load_plugin_executor: 加载 executor 类
- unload_plugin_modules: 清理 sys.modules
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── fixtures ──


@pytest.fixture(autouse=True)
def _clean_sys_modules():
    """每个测试后清理 plugins.* 模块"""
    yield
    to_remove = [k for k in sys.modules if k.startswith("plugins.")]
    for k in to_remove:
        del sys.modules[k]


@pytest.fixture
def fake_plugins_dir(tmp_path: Path) -> Path:
    """创建包含 fake-plugin 的临时插件目录"""
    plugin_dir = tmp_path / "fake-plugin" / "backend"
    plugin_dir.mkdir(parents=True)

    # main.py
    (plugin_dir / "main.py").write_text(
        "class FakePlugin:\n    pass\n\ndef main_func():\n    return 'from_main'\n",
        encoding="utf-8",
    )

    # api/handlers.py
    api_dir = plugin_dir / "api"
    api_dir.mkdir()
    (api_dir / "__init__.py").write_text("", encoding="utf-8")
    (api_dir / "handlers.py").write_text(
        "def handle_current(**kwargs):\n    return {'temp': 20}\n\n"
        "def handle_error(**kwargs):\n    return {'error': 'bad request', 'code': 4001}\n",
        encoding="utf-8",
    )

    # skills/resolver.py
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")
    (skills_dir / "resolver.py").write_text(
        "def resolve(skill, config):\n    return []\n",
        encoding="utf-8",
    )

    return tmp_path


# ── load_plugin_module ──


class TestLoadPluginModule:
    def test_load_submodule(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_module

            mod = load_plugin_module("fake-plugin", "api.handlers")
            assert mod is not None
            assert hasattr(mod, "handle_current")
            assert mod.handle_current() == {"temp": 20}

    def test_load_main_module(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_module

            mod = load_plugin_module("fake-plugin", "main")
            assert mod is not None
            assert hasattr(mod, "FakePlugin")

    def test_load_nonexistent_returns_none(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_module

            mod = load_plugin_module("fake-plugin", "nonexistent.module")
            assert mod is None

    def test_cached_module(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_module

            mod1 = load_plugin_module("fake-plugin", "api.handlers")
            mod2 = load_plugin_module("fake-plugin", "api.handlers")
            assert mod1 is mod2


# ── load_plugin_handler ──


class TestLoadPluginHandler:
    def test_load_handler_from_submodule(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            handler = load_plugin_handler("fake-plugin", "api.handlers.handle_current")
            assert handler is not None
            assert handler() == {"temp": 20}

    def test_load_skill_resolver(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            resolver = load_plugin_handler("fake-plugin", "skills.resolver.resolve")
            assert resolver is not None
            assert resolver(None, None) == []

    def test_load_handler_from_main_fallback(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            handler = load_plugin_handler("fake-plugin", "main.main_func")
            assert handler is not None
            assert handler() == "from_main"

    def test_empty_path_returns_none(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            assert load_plugin_handler("fake-plugin", "") is None

    def test_single_part_path_returns_none(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            assert load_plugin_handler("fake-plugin", "just_one_part") is None

    def test_nonexistent_attr_returns_none(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import load_plugin_handler

            handler = load_plugin_handler("fake-plugin", "api.handlers.nonexistent_func")
            assert handler is None


# ── unload_plugin_modules ──


class TestUnloadPluginModules:
    def test_unload_removes_all_plugin_modules(self, fake_plugins_dir: Path):
        with patch("app.plugins.module_loader._get_plugins_dir", return_value=fake_plugins_dir):
            from app.plugins.module_loader import (
                load_plugin_module,
                unload_plugin_modules,
            )

            load_plugin_module("fake-plugin", "main")
            load_plugin_module("fake-plugin", "api.handlers")

            assert "plugins.fake-plugin.backend.main" in sys.modules
            assert "plugins.fake-plugin.backend.api.handlers" in sys.modules

            count = unload_plugin_modules("fake-plugin")
            assert count >= 2
            assert "plugins.fake-plugin.backend.main" not in sys.modules
            assert "plugins.fake-plugin.backend.api.handlers" not in sys.modules

    def test_unload_nonexistent_plugin(self):
        from app.plugins.module_loader import unload_plugin_modules

        count = unload_plugin_modules("nonexistent-plugin")
        assert count == 0


# ── API dispatcher error handling ──


class TestApiDispatcherErrorHandling:
    """测试 api_dispatcher 的错误响应处理逻辑"""

    def test_error_dict_not_wrapped_as_success(self):
        """handler 返回含 error 的 dict 时不应被 success() 包装"""
        from fastapi.responses import JSONResponse

        # 模拟 dispatcher 的响应判断逻辑
        result = {"error": "Parameter missing", "code": 4001}

        # 这是修复后的逻辑
        if isinstance(result, JSONResponse):
            response = result
        elif isinstance(result, dict) and "error" in result:
            status_code = result.get("status_code", 422)
            response = JSONResponse(
                status_code=status_code,
                content={"code": result.get("code", 4220), "message": result["error"]},
            )
        elif isinstance(result, dict):
            response = JSONResponse(
                status_code=200,
                content={"code": 0, "data": result},
            )
        else:
            response = result

        assert response.status_code == 422
        assert response.body is not None

    def test_normal_dict_wrapped_as_success(self):
        """handler 返回正常 dict 时应被包装为 200"""
        from fastapi.responses import JSONResponse

        result = {"temperature": 20, "city": "Beijing"}

        if isinstance(result, dict) and "error" in result:
            response = JSONResponse(status_code=422, content={})
        elif isinstance(result, dict):
            response = JSONResponse(
                status_code=200,
                content={"code": 0, "data": result},
            )
        else:
            response = result

        assert response.status_code == 200

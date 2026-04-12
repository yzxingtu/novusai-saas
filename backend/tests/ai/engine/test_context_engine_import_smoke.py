from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    ("first_module", "second_module"),
    [
        ("app.ai.context.engine", "app.ai.engine.base"),
        ("app.ai.engine.base", "app.ai.context.engine"),
        ("app.ai.runtime.context_capability_bridge", "app.ai.engine.base"),
        ("app.ai.engine.base", "app.ai.runtime.context_capability_bridge"),
    ],
)
def test_context_and_base_modules_import_without_cycle(
    first_module: str,
    second_module: str,
) -> None:
    importlib.import_module(first_module)
    importlib.import_module(second_module)


def test_context_engine_import_does_not_eager_load_service_backed_dependencies() -> None:
    module_names = (
        "app.ai.context.engine",
        "app.ai.runtime.context_capability_bridge",
        "app.ai.rag_injector",
        "app.ai.context.long_term_memory",
        "app.services.ai.long_term_memory_provider",
        "app.services.ai.long_term_memory_service",
    )
    preserved_modules = {
        module_name: sys.modules.get(module_name) for module_name in module_names
    }

    try:
        for module_name in module_names:
            sys.modules.pop(module_name, None)

        importlib.import_module("app.ai.context.engine")

        assert "app.ai.runtime.context_capability_bridge" not in sys.modules
        assert "app.ai.rag_injector" not in sys.modules
        assert "app.ai.context.long_term_memory" not in sys.modules
        assert "app.services.ai.long_term_memory_provider" not in sys.modules
        assert "app.services.ai.long_term_memory_service" not in sys.modules
    finally:
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        for module_name, module in preserved_modules.items():
            if module is not None:
                sys.modules[module_name] = module


def test_long_term_memory_module_import_is_service_lazy() -> None:
    module_names = (
        "app.ai.context.long_term_memory",
        "app.services.ai.long_term_memory_provider",
        "app.services.ai.long_term_memory_service",
    )
    preserved_modules = {
        module_name: sys.modules.get(module_name) for module_name in module_names
    }

    try:
        for module_name in module_names:
            sys.modules.pop(module_name, None)

        importlib.import_module("app.ai.context.long_term_memory")

        assert "app.services.ai.long_term_memory_provider" not in sys.modules
        assert "app.services.ai.long_term_memory_service" not in sys.modules
    finally:
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        for module_name, module in preserved_modules.items():
            if module is not None:
                sys.modules[module_name] = module


def test_long_term_memory_provider_resolves_service_on_instantiation() -> None:
    module_names = (
        "app.services.ai.long_term_memory_provider",
        "app.services.ai.long_term_memory_service",
    )
    preserved_modules = {
        module_name: sys.modules.get(module_name) for module_name in module_names
    }

    try:
        for module_name in module_names:
            sys.modules.pop(module_name, None)

        module = importlib.import_module("app.services.ai.long_term_memory_provider")
        assert "app.services.ai.long_term_memory_service" not in sys.modules

        provider = module.get_long_term_memory_provider(db=object(), tenant_id=1)

        assert isinstance(provider, module.DatabaseLongTermMemoryProvider)
        assert "app.services.ai.long_term_memory_service" in sys.modules
    finally:
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        for module_name, module in preserved_modules.items():
            if module is not None:
                sys.modules[module_name] = module

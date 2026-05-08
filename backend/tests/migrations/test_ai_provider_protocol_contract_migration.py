"""Test type: structural
Scope: AI provider protocol contract Alembic migration.
Mock strategy: no mocks; static source inspection and pure helper assertions.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260508_0035_ai_proto_cfg.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_ai_provider_protocol_contract_migration_module",
        MIGRATION,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ai_provider_protocol_contract_migration_targets_provider_config() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260508_0035_ai_proto_cfg"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260508_0034_task_contract"'
        in source
    )
    assert "ai_providers" in source
    assert "protocol_capabilities" in source
    assert "primary_wire_api" in source
    assert "allowed_wire_apis" in source
    assert "wire_api" in source
    assert "web_search" in source
    assert "allow_adapter_cross_protocol_fallback" in source
    assert "def downgrade() -> None:\n    pass" in source


def test_ai_provider_protocol_contract_migration_uses_safe_alembic_patterns() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "text(f" not in source
    assert 'f"""' not in source
    assert "sa.inspect(bind).has_table" in source
    assert '_columns(bind, "ai_providers")' in source
    assert ".values(config=canonical_config" in source


def test_ai_provider_protocol_contract_migration_moves_top_level_wire_api() -> None:
    module = _load_migration_module()

    canonical = module._canonicalize_provider_config(
        {
            "wire_api": "responses",
            "allow_adapter_cross_protocol_fallback": True,
            "allowed_cross_protocol_fallbacks": {
                "responses": ["chat_completions"],
            },
            "web_search": {
                "enabled": True,
                "fallback_provider": "baidu",
            },
            "extra_models": [
                {
                    "code": "qwen-plus",
                    "web_search_options": {"enabled": True},
                },
                {"code": "qwen-max"},
            ],
        }
    )

    assert canonical == {
        "extra_models": [
            {"code": "qwen-plus"},
            {"code": "qwen-max"},
        ],
        "protocol_capabilities": {
            "primary_wire_api": "responses",
            "allowed_wire_apis": ["responses"],
        },
    }
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=canonical,
        configured_wire_api=None,
    )
    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses",)


def test_ai_provider_protocol_contract_migration_preserves_nested_primary() -> None:
    module = _load_migration_module()

    canonical = module._canonicalize_provider_config(
        {
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "primary_wire_api": "responses",
                "wire_api": "chat_completions",
                "allowed_wire_apis": ["chat_completions", "responses", "bad-token"],
                "allow_adapter_cross_protocol_fallback": True,
                "allowed_cross_protocol_fallbacks": {
                    "responses": ["chat_completions"],
                },
            },
            "extra_models": [{"code": "deepseek-chat"}],
        }
    )

    assert canonical == {
        "extra_models": [{"code": "deepseek-chat"}],
        "protocol_capabilities": {
            "primary_wire_api": "responses",
            "allowed_wire_apis": ["responses", "chat_completions"],
        },
    }
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=canonical,
        configured_wire_api=None,
    )
    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses", "chat_completions")


def test_ai_provider_protocol_contract_migration_is_idempotent() -> None:
    module = _load_migration_module()
    canonical = {
        "extra_models": [{"code": "dashscope-qwen"}],
        "protocol_capabilities": {
            "primary_wire_api": "chat_completions",
            "allowed_wire_apis": ["chat_completions"],
        },
    }

    assert module._canonicalize_provider_config(canonical) == canonical


def test_ai_provider_protocol_contract_migration_empty_retired_config_becomes_null() -> (
    None
):
    module = _load_migration_module()

    assert (
        module._canonicalize_provider_config(
            {
                "web_search_runtime": {"mode": "native"},
                "allow_adapter_cross_protocol_fallback": True,
            }
        )
        is None
    )

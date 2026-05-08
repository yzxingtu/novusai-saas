"""Test type: behavioral
Scope: plugin manifest schema validation and startup preview metadata normalization.
Real dependencies: PluginManifest pydantic validation.
Mocked dependencies: none.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.plugins.manifest import PluginManifest


def _base_manifest() -> dict:
    return {
        "name": "demo-plugin",
        "version": "1.0.0",
        "display_name": {"en": "Demo Plugin"},
        "scope": "all_tenants",
    }


def test_api_route_rejects_invalid_method() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "api": {
            "tenant_routes": [
                {
                    "method": "TRACE",
                    "path": "docs/{doc_id}",
                    "handler": "api.docs.get_doc",
                }
            ]
        }
    }

    with pytest.raises(ValidationError, match="Invalid API method"):
        PluginManifest.model_validate(payload)


def test_api_route_rejects_invalid_auth() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "api": {
            "tenant_routes": [
                {
                    "method": "GET",
                    "path": "docs/{doc_id}",
                    "handler": "api.docs.get_doc",
                    "auth": "token",
                }
            ]
        }
    }

    with pytest.raises(ValidationError, match="Invalid API auth"):
        PluginManifest.model_validate(payload)


def test_api_route_rejects_invalid_path_parameter_name() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "api": {
            "tenant_routes": [
                {
                    "method": "GET",
                    "path": "docs/{1doc}",
                    "handler": "api.docs.get_doc",
                }
            ]
        }
    }

    with pytest.raises(ValidationError, match="invalid path parameter name"):
        PluginManifest.model_validate(payload)


@pytest.mark.parametrize("handler", ["api..docs.get_doc", "api.docs.", ".api.docs"])
def test_api_route_rejects_invalid_handler_path_segments(handler: str) -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "api": {
            "tenant_routes": [
                {
                    "method": "GET",
                    "path": "docs/{doc_id}",
                    "handler": handler,
                }
            ]
        }
    }

    with pytest.raises(ValidationError, match="api.handler"):
        PluginManifest.model_validate(payload)


def test_webhook_rejects_invalid_method() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "webhooks": [
            {
                "path": "/notify/{event_id}",
                "method": "PATCH",
                "handler": "webhooks.notify.handle",
            }
        ]
    }

    with pytest.raises(ValidationError, match="Invalid webhook method"):
        PluginManifest.model_validate(payload)


def test_webhook_rejects_invalid_auth_type() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "webhooks": [
            {
                "path": "/notify/{event_id}",
                "method": "POST",
                "handler": "webhooks.notify.handle",
                "auth": {"type": "basic"},
            }
        ]
    }

    with pytest.raises(ValidationError, match="Invalid webhook auth type"):
        PluginManifest.model_validate(payload)


def test_socketio_rejects_illegal_segment() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "socketio": [
            {
                "path": "collab$",
                "handler": "sio.collab_namespace.CollabNamespace",
            }
        ]
    }

    with pytest.raises(ValidationError, match="socketio.path can only contain"):
        PluginManifest.model_validate(payload)


def test_manifest_normalizes_api_webhook_socket_paths() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "api": {
            "tenant_routes": [
                {
                    "method": "get",
                    "path": "/docs/{doc_id}/",
                    "handler": "api.docs.get_doc",
                    "auth": "required",
                }
            ]
        },
        "webhooks": [
            {
                "path": "notify/{event_id}",
                "method": "post",
                "handler": "webhooks.notify.handle",
                "auth": {"type": "hmac"},
            }
        ],
        "socketio": [
            {
                "path": "/collab/main/",
                "handler": "sio.collab_namespace.CollabNamespace",
            }
        ],
    }

    manifest = PluginManifest.model_validate(payload)

    route = manifest.extensions.api.tenant_routes[0]
    webhook = manifest.extensions.webhooks[0]
    socketio = manifest.extensions.socketio[0]

    assert route.method == "GET"
    assert route.path == "docs/{doc_id}"
    assert webhook.method == "POST"
    assert webhook.path == "/notify/{event_id}"
    assert socketio.path == "collab/main"


def test_frontend_page_scope_must_match_route_prefix() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "frontend": {
            "pages": [
                {
                    "name": "docs",
                    "path": "/tenant/plugins/demo-plugin/docs",
                    "component": "DemoDocsPage",
                    "scope": "admin",
                    "title": {"en": "Docs"},
                }
            ]
        }
    }

    with pytest.raises(ValidationError, match="path must match scope prefix"):
        PluginManifest.model_validate(payload)


def test_frontend_dev_release_paths_reject_traversal() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "frontend": {
            "dev": {"entry": "../src/index.ts"},
            "release": {"manifest": "../plugin.manifest.json"},
        }
    }

    with pytest.raises(ValidationError, match="safe relative path"):
        PluginManifest.model_validate(payload)


def test_dependencies_plugins_accepts_versioned_object() -> None:
    payload = _base_manifest()
    payload["dependencies"] = {
        "python": [],
        "plugins": [
            {"plugin": "base-plugin", "version": ">=1.2.0,<2.0.0"},
        ],
    }

    manifest = PluginManifest.model_validate(payload)

    assert len(manifest.dependencies.plugins) == 1
    assert manifest.dependencies.plugins[0].plugin == "base-plugin"
    assert manifest.dependencies.plugins[0].version == ">=1.2.0,<2.0.0"


def test_manifest_rejects_legacy_compatibility_requires() -> None:
    payload = _base_manifest()
    payload["compatibility"] = {
        "requires": [{"plugin": "base-plugin", "version": ">=1.0.0"}],
    }

    with pytest.raises(
        ValidationError, match="compatibility.requires has been removed"
    ):
        PluginManifest.model_validate(payload)


def test_manifest_rejects_legacy_system_dependencies() -> None:
    payload = _base_manifest()
    payload["dependencies"] = {
        "python": [],
        "plugins": [],
        "system": ["redis"],
    }

    with pytest.raises(ValidationError, match="dependencies.system is not supported"):
        PluginManifest.model_validate(payload)


def test_manifest_rejects_legacy_top_level_plugin_fields() -> None:
    payload = _base_manifest()
    payload["tenant_plugins"] = []
    payload["module_path"] = "legacy.module"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PluginManifest.model_validate(payload)


@pytest.mark.parametrize(
    "compatibility_payload",
    [
        {"editions": ["single-management"]},
        {"surfaces": ["platform-admin"]},
        {"tenant_exposure": "tenant-scoped"},
    ],
)
def test_manifest_rejects_compatibility_aliases(
    compatibility_payload: dict[str, object],
) -> None:
    payload = _base_manifest()
    payload["compatibility"] = compatibility_payload

    with pytest.raises(ValidationError, match="Invalid compatibility"):
        PluginManifest.model_validate(payload)


@pytest.mark.parametrize(
    "section,payload",
    [
        (
            "features",
            [
                {
                    "code": "feature-demo",
                    "legacy_runtime_feature_code": "old.feature",
                }
            ],
        ),
        (
            "ai_requirements",
            {
                "features": [
                    {
                        "feature_code": "ai-demo",
                        "fallback_policy": "legacy-default",
                    }
                ]
            },
        ),
    ],
)
def test_manifest_rejects_legacy_feature_fields(
    section: str,
    payload: object,
) -> None:
    manifest_payload = _base_manifest()
    manifest_payload[section] = payload

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PluginManifest.model_validate(manifest_payload)


def test_manifest_accepts_empty_plugin_metadata_icon() -> None:
    payload = _base_manifest()
    payload["icon"] = ""

    manifest = PluginManifest.model_validate(payload)

    assert manifest.icon == ""


def test_manifest_rejects_non_png_plugin_metadata_icon() -> None:
    payload = _base_manifest()
    payload["icon"] = "lucide:file-text"

    with pytest.raises(ValidationError, match="icon.png"):
        PluginManifest.model_validate(payload)


def test_manifest_skill_extensions_accept_startup_preview_metadata() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": "neutral-skill",
                "type": "toolkit",
                "entry_point": "skills.neutral",
                "executor_entry_point": "executors.neutral.NeutralExecutor",
                "display_name": {"en": "Neutral Skill"},
                "preview_tool_names": [" crm_lookup ", "crm_lookup", ""],
                "preview_semantic_families": [" data_ops ", "data_ops", ""],
            }
        ]
    }

    manifest = PluginManifest.model_validate(payload)

    skill = manifest.extensions.skills[0]
    assert skill.executor_entry_point == "executors.neutral.NeutralExecutor"
    assert skill.preview_tool_names == ["crm_lookup"]
    assert skill.preview_semantic_families == ["data_ops"]


def test_manifest_skill_extensions_require_entry_point() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": "neutral-skill",
                "type": "toolkit",
            }
        ]
    }

    with pytest.raises(ValidationError, match="entry_point"):
        PluginManifest.model_validate(payload)


def test_manifest_skill_extensions_reject_invalid_executor_entry_point() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": "neutral-skill",
                "type": "toolkit",
                "entry_point": "skills.neutral",
                "executor_entry_point": "../executors.neutral.Executor",
            }
        ]
    }

    with pytest.raises(ValidationError, match="executor_entry_point"):
        PluginManifest.model_validate(payload)


@pytest.mark.parametrize(
    "skill_name",
    [
        "WeatherRealtime",
        "weather realtime",
        "weather_realtime",
        "weather-realtime-",
    ],
)
def test_manifest_skill_extensions_require_stable_kebab_case_name(
    skill_name: str,
) -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": skill_name,
                "type": "toolkit",
                "entry_point": "skills.neutral",
            }
        ]
    }

    with pytest.raises(ValidationError, match="skill.name must be lowercase"):
        PluginManifest.model_validate(payload)


def test_manifest_skill_extensions_reject_too_long_name() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": f"skill-{'a' * 101}",
                "type": "toolkit",
                "entry_point": "skills.neutral",
            }
        ]
    }

    with pytest.raises(ValidationError, match="String should have at most 100"):
        PluginManifest.model_validate(payload)


def test_manifest_skill_extensions_reject_unknown_type() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": "neutral-skill",
                "type": "unknown",
                "entry_point": "skills.neutral",
            }
        ]
    }

    with pytest.raises(ValidationError, match="Invalid skill.type"):
        PluginManifest.model_validate(payload)


def test_manifest_skill_extensions_reject_duplicate_names() -> None:
    payload = _base_manifest()
    payload["extensions"] = {
        "skills": [
            {
                "name": "neutral-skill",
                "type": "toolkit",
                "entry_point": "skills.neutral",
            },
            {
                "name": "neutral-skill",
                "type": "builtin",
                "entry_point": "skills.other",
            },
        ]
    }

    with pytest.raises(ValidationError, match="must be unique"):
        PluginManifest.model_validate(payload)

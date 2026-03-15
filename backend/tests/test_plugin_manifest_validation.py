"""插件 manifest 强校验回归测试。 / Plugin."""

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

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _first_attr(obj, keys, default=None):
    if obj is None:
        return default
    for key in keys:
        if hasattr(obj, key):
            value = getattr(obj, key)
            if value is not None:
                return value
    return default


class _FakeSelect:
    def where(self, *_args, **_kwargs):
        return self


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeRunModel:
    id = object()
    tenant_id = object()


@pytest.mark.asyncio
async def test_download_artifact_storage_path_uses_artifact_tenant_context(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.artifact_service")
    artifact = SimpleNamespace(
        id=1,
        tenant_id=12,
        storage_path="reports/output.csv",
        mime_type="text/csv",
        download_filename="artifact.csv",
        name="Quarterly Report",
    )
    storage_requests: list[int | None] = []
    storage_paths: list[str] = []

    class FakeStorage:
        async def get(self, path: str):
            storage_paths.append(path)
            return b"csv-bytes"

    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: {
            "errors": SimpleNamespace(WorkflowNotFoundError=RuntimeError),
            "model_access": SimpleNamespace(
                first_attr=_first_attr,
                try_resolve_model=lambda _model_key: None,
            ),
            "storage_access": SimpleNamespace(
                get_plugin_storage=AsyncMock(
                    side_effect=lambda _db, tenant_id=None: storage_requests.append(tenant_id) or FakeStorage()
                )
            ),
        }[name],
    )

    service = service_module.ArtifactService(object(), tenant_id=999)
    service._get_artifact = AsyncMock(return_value=artifact)

    payload = await service.download_artifact(1)

    assert storage_requests == [12]
    assert storage_paths == ["reports/output.csv"]
    assert payload == {
        "content": b"csv-bytes",
        "filename": "artifact.csv",
        "mime_type": "text/csv",
    }


@pytest.mark.asyncio
async def test_download_artifact_storage_uri_resolves_tenant_from_run_context(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.artifact_service")
    artifact = SimpleNamespace(
        id=2,
        tenant_id=None,
        run_id=55,
        storage_uri="artifact://exports/run-55.json",
        mime_type="application/json",
        name="Run Export",
    )
    storage_requests: list[int | None] = []
    storage_paths: list[str] = []

    class FakeStorage:
        async def get(self, path: str):
            storage_paths.append(path)
            return '{"ok": true}'

    class FakeDb:
        async def execute(self, _stmt):
            return _FakeResult(SimpleNamespace(id=55, tenant_id=44))

    monkeypatch.setattr(service_module, "select", lambda *_args, **_kwargs: _FakeSelect())
    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: {
            "errors": SimpleNamespace(WorkflowNotFoundError=RuntimeError),
            "model_access": SimpleNamespace(
                first_attr=_first_attr,
                try_resolve_model=lambda model_key: _FakeRunModel if model_key == "workflow_run" else None,
            ),
            "storage_access": SimpleNamespace(
                get_plugin_storage=AsyncMock(
                    side_effect=lambda _db, tenant_id=None: storage_requests.append(tenant_id) or FakeStorage()
                )
            ),
        }[name],
    )

    service = service_module.ArtifactService(FakeDb(), tenant_id=44)
    service._get_artifact = AsyncMock(return_value=artifact)

    payload = await service.download_artifact(2)

    assert storage_requests == [44]
    assert storage_paths == ["exports/run-55.json"]
    assert payload["content"] == b'{"ok": true}'
    assert payload["filename"] == "Run Export.bin"
    assert payload["mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_download_artifact_falls_back_to_text_payload(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.artifact_service")
    artifact = SimpleNamespace(
        id=3,
        name="Transcript",
        content_text="hello workflow",
    )

    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: {
            "errors": SimpleNamespace(WorkflowNotFoundError=RuntimeError),
            "model_access": SimpleNamespace(first_attr=_first_attr),
        }[name],
    )

    service = service_module.ArtifactService(object(), tenant_id=8)
    service._get_artifact = AsyncMock(return_value=artifact)

    payload = await service.download_artifact(3)

    assert payload["content"] == b"hello workflow"
    assert payload["filename"] == "Transcript.txt"
    assert payload["mime_type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_download_artifact_falls_back_to_json_payload(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.artifact_service")
    artifact = SimpleNamespace(
        id=4,
        title="Structured Artifact",
        content_json={"status": "ready", "count": 2},
    )

    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: {
            "errors": SimpleNamespace(WorkflowNotFoundError=RuntimeError),
            "model_access": SimpleNamespace(first_attr=_first_attr),
        }[name],
    )

    service = service_module.ArtifactService(object(), tenant_id=None)
    service._get_artifact = AsyncMock(return_value=artifact)

    payload = await service.download_artifact(4)

    assert json.loads(payload["content"].decode("utf-8")) == {"status": "ready", "count": 2}
    assert payload["filename"] == "Structured Artifact.json"
    assert payload["mime_type"] == "application/json"

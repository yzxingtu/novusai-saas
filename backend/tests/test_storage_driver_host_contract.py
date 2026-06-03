from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.shared._storage_helpers import get_known_plugin_storage_drivers
from app.plugins.host_read_facade import HostReadFacade
from app.storage.manager import StorageManager


def _scalars_result(items: list[object]):
    scalars = SimpleNamespace(all=lambda: items)
    return SimpleNamespace(scalars=lambda: scalars)


def _rows_result(rows: list[tuple[object, ...]]):
    return SimpleNamespace(all=lambda: rows)


@pytest.mark.asyncio
async def test_get_known_plugin_storage_drivers_extracts_plugin_manifest_metadata() -> (
    None
):
    plugin_with_storage = SimpleNamespace(
        manifest={
            "extensions": {
                "storage_drivers": [
                    {
                        "code": "s3",
                        "display_name": {
                            "en": "S3 Compatible Storage",
                            "zh-CN": "S3 兼容存储",
                        },
                    }
                ]
            }
        },
        name="amazon-s3",
        status="enabled",
    )
    plugin_without_storage = SimpleNamespace(
        manifest={"extensions": {"custom": [{"type": "demo"}]}},
        name="demo-plugin",
        status="enabled",
    )
    plugin_with_string_display = SimpleNamespace(
        manifest={
            "extensions": {
                "storage_drivers": [
                    {
                        "code": "aliyun-oss",
                        "display_name": "Alibaba Cloud OSS",
                    }
                ]
            }
        },
        name="aliyun-oss",
        status="disabled",
    )
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_scalars_result(
            [
                plugin_with_storage,
                plugin_without_storage,
                plugin_with_string_display,
            ]
        )
    )

    drivers = await get_known_plugin_storage_drivers(db)

    assert drivers == [
        {
            "display_name": "S3 兼容存储",
            "name": "s3",
            "plugin_name": "amazon-s3",
            "plugin_status": "enabled",
        },
        {
            "display_name": "Alibaba Cloud OSS",
            "name": "aliyun-oss",
            "plugin_name": "aliyun-oss",
            "plugin_status": "disabled",
        },
    ]


@pytest.mark.asyncio
async def test_host_read_facade_get_enabled_storage_drivers_merges_plugin_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_rows_result(
            [
                (
                    "amazon-s3",
                    "enabled",
                    {
                        "extensions": {
                            "storage_drivers": [
                                {
                                    "code": "s3",
                                    "display_name": {"en": "S3 Compatible Storage"},
                                }
                            ]
                        }
                    },
                ),
                (
                    "aliyun-oss",
                    "disabled",
                    {
                        "extensions": {
                            "storage_drivers": [
                                {
                                    "code": "aliyun-oss",
                                    "display_name": {
                                        "en": "Alibaba Cloud OSS",
                                        "zh-CN": "阿里云 OSS",
                                    },
                                }
                            ]
                        }
                    },
                ),
            ]
        )
    )
    monkeypatch.setattr(
        "app.plugins.host_read_facade.storage_manager.get_driver_info_list",
        lambda: [
            {
                "display_name": "Local Storage",
                "is_available": True,
                "is_builtin": True,
                "name": "local",
            },
            {
                "display_name": "S3 Compatible Storage",
                "is_available": True,
                "is_builtin": False,
                "name": "s3",
            },
        ],
    )

    drivers = await HostReadFacade(db).get_enabled_storage_drivers()

    assert drivers == [
        {
            "code": "local",
            "display_name": "Local Storage",
            "is_available": True,
            "is_builtin": True,
            "plugin_name": None,
            "plugin_status": None,
        },
        {
            "code": "s3",
            "display_name": "S3 Compatible Storage",
            "is_available": True,
            "is_builtin": False,
            "plugin_name": "amazon-s3",
            "plugin_status": "enabled",
        },
    ]


def test_storage_manager_get_all_driver_info_list_marks_disabled_plugin_drivers_unavailable() -> (
    None
):
    StorageManager._instance = None
    manager = StorageManager()
    local_info = manager.get_driver_info_list()[0]

    try:
        drivers = manager.get_all_driver_info_list(
            known_plugin_drivers=[
                {
                    "display_name": "Alibaba Cloud OSS",
                    "name": "aliyun-oss",
                    "plugin_name": "aliyun-oss",
                    "plugin_status": "disabled",
                }
            ]
        )
    finally:
        StorageManager._instance = None

    assert drivers == [
        {
            "config_schema": local_info["config_schema"],
            "display_name": local_info["display_name"],
            "is_available": True,
            "is_builtin": True,
            "name": "local",
        },
        {
            "config_schema": None,
            "display_name": "Alibaba Cloud OSS",
            "is_available": False,
            "is_builtin": False,
            "name": "aliyun-oss",
            "plugin_name": "aliyun-oss",
            "plugin_status": "disabled",
        },
    ]

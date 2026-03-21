from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tasks import scheduled


def _make_sync_redis(
    *,
    scan_keys: list[str],
    ttl_map: dict[str, int],
) -> MagicMock:
    client = MagicMock()
    client.scan.side_effect = [
        (0, scan_keys),
    ]
    client.ttl.side_effect = lambda key: ttl_map[key]
    client.delete.return_value = sum(
        1 for key in scan_keys if ttl_map.get(key) == -1
    )
    return client


def test_clean_expired_session_memories_deletes_only_no_ttl_keys() -> None:
    client = _make_sync_redis(
        scan_keys=[
            "mem:sess:1:tenant_chat:ai_chat_page:10:20:100",
            "mem:sess:1:user_chat:ai_chat_page:10:30:101",
        ],
        ttl_map={
            "mem:sess:1:tenant_chat:ai_chat_page:10:20:100": -1,
            "mem:sess:1:user_chat:ai_chat_page:10:30:101": 86400,
        },
    )

    with patch("app.tasks.scheduled._get_sync_redis", return_value=client):
        result = scheduled.clean_expired_session_memories.run()

    client.delete.assert_called_once_with(
        "mem:sess:1:tenant_chat:ai_chat_page:10:20:100",
    )
    assert result["cleaned"] == 1


def test_clean_expired_session_memories_keeps_ttl_keys() -> None:
    client = _make_sync_redis(
        scan_keys=[
            "mem:sess:1:tenant_chat:ai_chat_page:10:20:100",
        ],
        ttl_map={
            "mem:sess:1:tenant_chat:ai_chat_page:10:20:100": 3600,
        },
    )

    with patch("app.tasks.scheduled._get_sync_redis", return_value=client):
        result = scheduled.clean_expired_session_memories.run()

    client.delete.assert_not_called()
    assert result["cleaned"] == 0

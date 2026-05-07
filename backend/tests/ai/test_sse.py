from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from app.ai.sse import SSEChunkEncoder


class _Status(Enum):
    OK = "ok"


@dataclass
class _NestedPayload:
    amount: Decimal
    created_at: datetime


def _decode_sse_payload(raw: str) -> dict:
    assert raw.startswith("data: ")
    return json.loads(raw[len("data: ") :].strip())


def test_sse_chunk_encoder_keeps_done_marker_strings_untouched():
    assert SSEChunkEncoder.encode("[DONE]") == "data: [DONE]\n\n"


def test_sse_chunk_encoder_normalizes_nested_runtime_values():
    payload = {
        "event": "done",
        "turn_record": {
            "cost": Decimal("1.25"),
            "usage": {"prompt_tokens": Decimal("2")},
            "status": _Status.OK,
            "payload": _NestedPayload(
                amount=Decimal("3"),
                created_at=datetime(2026, 4, 7, 13, 47, 25),
            ),
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "tags": {"alpha", "beta"},
            "raw": b"hello",
        },
    }

    decoded = _decode_sse_payload(SSEChunkEncoder.encode(payload))

    assert decoded["turn_record"]["cost"] == 1.25
    assert decoded["turn_record"]["usage"]["prompt_tokens"] == 2
    assert decoded["turn_record"]["status"] == "ok"
    assert decoded["turn_record"]["payload"]["amount"] == 3
    assert (
        decoded["turn_record"]["payload"]["created_at"] == "2026-04-07T13:47:25+00:00"
    )
    assert decoded["turn_record"]["uuid"] == "12345678-1234-5678-1234-567812345678"
    assert sorted(decoded["turn_record"]["tags"]) == ["alpha", "beta"]
    assert decoded["turn_record"]["raw"] == "hello"

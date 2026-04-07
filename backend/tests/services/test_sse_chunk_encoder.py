from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum

from app.ai.sse import SSEChunkEncoder


class _SampleEnum(Enum):
    READY = "ready"


@dataclass
class _NestedPayload:
    amount: Decimal
    status: _SampleEnum


class _ModelDumpPayload:
    def model_dump(self, mode: str = "python") -> dict[str, object]:
        assert mode == "python"
        return {
            "score": Decimal("8.5"),
            "generated_at": datetime(2026, 4, 7, 5, 47, 26, tzinfo=UTC),
        }


class _DictPayload:
    def dict(self) -> dict[str, object]:
        return {
            "day": date(2026, 4, 7),
            "at": time(5, 47, 26),
        }


class _ObjectPayload:
    def __init__(self) -> None:
        self.value = Decimal("3")
        self.label = "ok"
        self._internal = "hidden"


def _decode_sse(raw: str) -> object:
    assert raw.startswith("data: ")
    assert raw.endswith("\n\n")
    return json.loads(raw[6:].strip())


def test_encode_keeps_done_marker_as_plain_text() -> None:
    assert SSEChunkEncoder.encode("[DONE]") == "data: [DONE]\n\n"


def test_encode_normalizes_nested_decimal_enum_and_dataclass() -> None:
    payload = {
        "event": "done",
        "turn_record": {
            "cost": Decimal("12.5"),
            "nested": _NestedPayload(
                amount=Decimal("2"),
                status=_SampleEnum.READY,
            ),
        },
    }

    decoded = _decode_sse(SSEChunkEncoder.encode(payload))

    assert decoded == {
        "event": "done",
        "turn_record": {
            "cost": 12.5,
            "nested": {"amount": 2, "status": "ready"},
        },
    }


def test_encode_normalizes_datetime_date_and_time_values() -> None:
    payload = {
        "created_at": datetime(2026, 4, 7, 5, 47, 26),
        "day": date(2026, 4, 7),
        "clock": time(5, 47, 26),
    }

    decoded = _decode_sse(SSEChunkEncoder.encode(payload))

    assert decoded == {
        "created_at": "2026-04-07T05:47:26+00:00",
        "day": "2026-04-07",
        "clock": "05:47:26",
    }


def test_encode_normalizes_model_dump_payloads() -> None:
    decoded = _decode_sse(SSEChunkEncoder.encode({"payload": _ModelDumpPayload()}))

    assert decoded == {
        "payload": {
            "score": 8.5,
            "generated_at": "2026-04-07T05:47:26+00:00",
        }
    }


def test_encode_normalizes_dict_method_payloads() -> None:
    decoded = _decode_sse(SSEChunkEncoder.encode({"payload": _DictPayload()}))

    assert decoded == {
        "payload": {
            "day": "2026-04-07",
            "at": "05:47:26",
        }
    }


def test_encode_normalizes_plain_object_payloads() -> None:
    decoded = _decode_sse(SSEChunkEncoder.encode({"payload": _ObjectPayload()}))

    assert decoded == {
        "payload": {
            "value": 3,
            "label": "ok",
        }
    }

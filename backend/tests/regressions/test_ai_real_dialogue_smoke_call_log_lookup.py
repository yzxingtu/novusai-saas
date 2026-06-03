"""中文: AI real-dialogue smoke call-log 证据链回归测试。

EN: Regression tests for AI real-dialogue smoke call-log evidence lookup.

Test type: behavioral
Regression for: AI-SMOKE-provider-call-log-id-missing-after-provider-success
Original symptom: real-dialogue smoke receives an assistant response and the
provider call has succeeded, but `provider_call_log_id` is missing because the
lookup excludes the persisted call log.
Scope: RuntimeRealDialogueSmokeService call-log lookup fallback.
Mocked dependencies: DB lookup method only; no LLM/provider response is mocked.
Why this mock is not self-fulfilling: the test asserts the lookup sequence and
the fallback evidence id, not an LLM-generated answer.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.ai import runtime_real_dialogue_smoke_service as smoke_module
from app.services.ai.runtime_real_dialogue_smoke_service import (
    RuntimeRealDialogueSmokeService,
)


@pytest.mark.asyncio
async def test_wait_for_call_log_falls_back_to_conversation_evidence_after_time_window_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: worker 写入时间早于 smoke 进程窗口时，仍按同一 conversation 找到成功调用。

    EN: When the worker timestamp predates the smoke process window, the same
    conversation still supplies the successful provider-call evidence.
    """
    lookups: list[dict[str, Any]] = []
    fallback_log = SimpleNamespace(
        id=8801,
        status="success",
        provider_name_snapshot="provider",
        model_name_snapshot="model",
        request_type="chat",
        call_type="main_chat",
    )

    async def fake_latest_call_log(self: Any, **kwargs: Any) -> Any:
        del self
        lookups.append(dict(kwargs))
        if kwargs["created_after"] is None:
            return fallback_log
        return None

    monkeypatch.setattr(smoke_module, "_CALL_LOG_LOOKUP_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(smoke_module, "_CALL_LOG_LOOKUP_DELAY_SECONDS", 0)
    monkeypatch.setattr(
        RuntimeRealDialogueSmokeService,
        "_latest_call_log",
        fake_latest_call_log,
    )

    service = RuntimeRealDialogueSmokeService(db=object())

    call_log, attempts = await service._wait_for_call_log(
        conversation_id=441,
        agent_id=59,
        created_after=datetime(2026, 5, 9, 12, 0, 0),
    )

    assert getattr(call_log, "id", None) == 8801
    assert attempts == 3
    assert [item["created_after"] is None for item in lookups] == [
        False,
        False,
        True,
    ]
    assert {item["conversation_id"] for item in lookups} == {441}
    assert {item["agent_id"] for item in lookups} == {59}

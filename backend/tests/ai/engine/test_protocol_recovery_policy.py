from __future__ import annotations

from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.runtime.protocol_recovery_policy import (
    ObservedStream,
    ProtocolRecoveryPolicy,
)
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatChunk


def test_fallback_block_reason_maps_provider_failures() -> None:
    assert (
        ProtocolRecoveryPolicy.fallback_block_reason(
            ProviderRateLimitError("too many requests")
        )
        == "provider_rate_limit"
    )
    assert (
        ProtocolRecoveryPolicy.fallback_block_reason(
            ProviderTimeoutError(
                "provider timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        )
        == "provider_timeout"
    )
    assert (
        ProtocolRecoveryPolicy.fallback_block_reason(
            ProviderConnectionError("connection failed")
        )
        == "provider_connection_error"
    )


def test_fallback_block_reason_maps_status_timeouts() -> None:
    timeout_408 = type("Status408", (Exception,), {"status_code": 408})("timed out")
    timeout_504 = type("Status504", (Exception,), {"status_code": 504})(
        "gateway timed out"
    )

    assert ProtocolRecoveryPolicy.fallback_block_reason(timeout_408) == "provider_timeout"
    assert ProtocolRecoveryPolicy.fallback_block_reason(timeout_504) == "provider_timeout"


def test_chunk_should_emit_immediately_for_progress_only_signal() -> None:
    chunk = ChatChunk(delta="", metadata={"web_search_in_progress": True})

    assert ProtocolRecoveryPolicy.chunk_should_emit_immediately(chunk) is True


def test_empty_stream_reason_distinguishes_progress_before_exception() -> None:
    observed = ObservedStream(has_progress_signal=True)

    assert (
        ProtocolRecoveryPolicy.empty_stream_reason(
            observed,
            error_type="RuntimeError",
        )
        == "stream_exception_after_progress_before_meaningful_chunk:RuntimeError"
    )


def test_record_stream_failure_metadata_marks_reasoning_only_path() -> None:
    policy = ProtocolRecoveryPolicy()
    turn_record = TurnRecord()
    observed = ObservedStream(
        chunk_count=1,
        has_reasoning_output=True,
        has_progress_signal=True,
    )

    policy.record_stream_failure_metadata(
        turn_record,
        observed=observed,
        cause=RuntimeError("stream interrupted"),
    )

    assert turn_record.metadata["stream_failure_chunk_count"] == 1
    assert turn_record.metadata["stream_failure_has_meaningful_chunk"] is True
    assert turn_record.metadata["stream_failure_blocks_fallback"] is False
    assert turn_record.metadata["stream_failure_after_progress_only"] is False
    assert (
        turn_record.metadata["stream_failure_reasoning_only_before_visible_output"]
        is True
    )

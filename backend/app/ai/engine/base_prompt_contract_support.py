"""
Contract-recovery and retry policy bindings for BaseEngine prompt/runtime support.
"""

from __future__ import annotations

from .contract_diagnostics_helpers import (
    build_contract_recovery_system_message as _build_contract_recovery_system_message_impl,
)
from .contract_diagnostics_helpers import (
    merge_contract_diagnostics_into_turn_record as _merge_contract_diagnostics_into_turn_record_impl,
)
from .tool_contract_retry_helpers import (
    analyze_post_tool_contract_breach as _analyze_post_tool_contract_breach_impl,
)
from .tool_contract_retry_helpers import (
    build_post_tool_retry_policy as _build_post_tool_retry_policy_impl,
)
from .tool_contract_retry_helpers import (
    collect_tool_family_evidence as _collect_tool_family_evidence_impl,
)
from .tool_contract_retry_helpers import (
    resolve_breach_retry_policy as _resolve_breach_retry_policy_impl,
)
from .tool_contract_retry_helpers import (
    should_retry_tool_contract_breach as _should_retry_tool_contract_breach_impl,
)


class BasePromptContractSupportMixin:
    """Binds contract diagnostics and recovery helpers onto BaseEngine."""

    _build_post_tool_retry_policy = staticmethod(_build_post_tool_retry_policy_impl)
    _analyze_post_tool_contract_breach = staticmethod(
        _analyze_post_tool_contract_breach_impl
    )
    _build_contract_recovery_system_message = staticmethod(
        _build_contract_recovery_system_message_impl
    )
    _merge_contract_diagnostics_into_turn_record = staticmethod(
        _merge_contract_diagnostics_into_turn_record_impl
    )
    _resolve_breach_retry_policy = staticmethod(_resolve_breach_retry_policy_impl)
    _should_retry_tool_contract_breach = staticmethod(
        _should_retry_tool_contract_breach_impl
    )
    _collect_tool_family_evidence = staticmethod(_collect_tool_family_evidence_impl)


__all__ = ["BasePromptContractSupportMixin"]

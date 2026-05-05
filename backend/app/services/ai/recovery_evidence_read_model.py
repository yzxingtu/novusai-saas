"""中文: 保留旧导入入口，但不再执行公网检索恢复证据修复。

EN: Keeps the legacy import seam without applying online-search recovery repairs.
"""

from __future__ import annotations

from typing import Any

LEGACY_RECOVERY_EVIDENCE_REPAIR_SCOPE = "legacy_recovery_evidence_read_model_disabled"


def patch_recovery_evidence_answer_payload(
    message: dict[str, Any],
) -> dict[str, Any]:
    return message


__all__ = [
    "LEGACY_RECOVERY_EVIDENCE_REPAIR_SCOPE",
    "patch_recovery_evidence_answer_payload",
]

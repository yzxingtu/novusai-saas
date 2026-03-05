"""merge_session_memory_heads

Revision ID: c1a4f0e2b9d3
Revises: 9f2d1e34c7a1, 20260302_sess_mem_cleanup
Create Date: 2026-03-03 16:30:00.000000+00:00
"""

from collections.abc import Sequence

revision: str = "c1a4f0e2b9d3"
down_revision: str | Sequence[str] | None = (
    "9f2d1e34c7a1",
    "20260302_sess_mem_cleanup",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """合并分支，不执行结构变更。"""
    pass


def downgrade() -> None:
    """回滚合并分支，不执行结构变更。"""
    pass

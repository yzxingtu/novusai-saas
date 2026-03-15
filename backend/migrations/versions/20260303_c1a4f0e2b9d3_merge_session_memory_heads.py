"""[MERGE] merge_session_memory_heads

Merges two branches: agent_memory_switch (9f2d1e34c7a1), sess_mem_cleanup.
No schema changes.

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
    """合并分支，不执行结构变更。 / Merge heads, no schema change."""
    pass


def downgrade() -> None:
    """回滚合并分支，不执行结构变更。 / Rollback merge, no schema change."""
    pass

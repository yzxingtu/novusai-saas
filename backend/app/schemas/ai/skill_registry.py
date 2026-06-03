"""
Skill registry schemas / 技能注册表相关 Schema
"""

from pydantic import BaseModel, ConfigDict, Field


class StarterPackSyncRequest(BaseModel):
    """Official starter pack sync/install request payload."""

    model_config = ConfigDict(extra="forbid")

    pack_keys: list[str] | None = Field(
        default=None,
        description="Optional starter-pack keys; omit to target all official packs.",
    )
    install_missing: bool = Field(
        default=True,
        description="Install missing package slugs from selected starter packs.",
    )
    upgrade_existing: bool = Field(
        default=False,
        description="Upgrade already installed package slugs when a newer version exists.",
    )
    dry_run: bool = Field(
        default=False,
        description="Plan-only mode without install/upgrade side effects.",
    )

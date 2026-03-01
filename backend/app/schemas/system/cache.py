"""
缓存管理相关 Schema
"""

from pydantic import Field, field_validator

from app.core.base_schema import BaseSchema
from app.enums.cache import CacheCategoryEnum


class CacheCategorySummary(BaseSchema):
    """单个缓存分类的统计信息"""

    category: str = Field(..., description="Cache category code")
    label: str = Field(..., description="Cache category i18n label")
    key_count: int = Field(0, description="Number of keys or files")
    size_bytes: int = Field(0, description="Total size in bytes")
    size_human: str = Field("0 B", description="Human-readable size")


class CacheSummaryResponse(BaseSchema):
    """缓存统计汇总响应"""

    categories: list[CacheCategorySummary] = Field(
        default_factory=list, description="Cache category summaries"
    )
    total_size_bytes: int = Field(0, description="Total size in bytes")
    total_size_human: str = Field("0 B", description="Human-readable total size")


class CacheClearRequest(BaseSchema):
    """缓存清理请求"""

    categories: list[str] = Field(
        ..., min_length=1, description="List of cache category codes to clear"
    )

    @field_validator("categories", mode="before")
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        """Validate that all categories are valid CacheCategoryEnum values"""
        valid_values = CacheCategoryEnum.values()
        for category in v:
            if category not in valid_values:
                raise ValueError(
                    f"Invalid cache category: '{category}'. "
                    f"Valid values: {valid_values}"
                )
        return v


class CacheClearResponse(BaseSchema):
    """缓存清理结果响应"""

    cleared_categories: list[str] = Field(
        default_factory=list, description="Categories that were cleared"
    )
    cleared_keys: int = Field(0, description="Total number of keys/files cleared")
    cleared_size_bytes: int = Field(0, description="Total size cleared in bytes")
    cleared_size_human: str = Field("0 B", description="Human-readable cleared size")
    duration_ms: int = Field(0, description="Operation duration in milliseconds")


__all__ = [
    "CacheCategorySummary",
    "CacheSummaryResponse",
    "CacheClearRequest",
    "CacheClearResponse",
]

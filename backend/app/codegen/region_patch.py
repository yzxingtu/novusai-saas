"""
受控区域 Patch 引擎 v1

M58-T18: 批量增量生成 — 仅更新受控区域，保留用户手改

锚点格式：
  // BEGIN CRUD-GEN:<region_id>
  ... generated content ...
  // END CRUD-GEN:<region_id>

或 Python 风格：
  # BEGIN CRUD-GEN:<region_id>
  ... generated content ...
  # END CRUD-GEN:<region_id>

规则：
- 仅替换锚点内内容，锚点外的用户手改保留
- 重复执行幂等（同一 region_id 只有一个实例）
- 锚点缺失 → 降级策略（append 或 error）
- 与原子写盘兼容（patch 失败不留半成品）
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 配置
# ============================================================


class FallbackStrategy(str, Enum):
    """锚点缺失时的降级策略"""

    APPEND = "append"
    ERROR = "error"
    SKIP = "skip"


# ============================================================
# 锚点正则
# ============================================================

# 匹配 // BEGIN CRUD-GEN:<id> 或 # BEGIN CRUD-GEN:<id>
_BEGIN_RE = re.compile(
    r"^(\s*(?://|#)\s*BEGIN\s+CRUD-GEN:(\S+)\s*)$",
    re.MULTILINE,
)

_END_RE_TEMPLATE = r"^(\s*(?://|#)\s*END\s+CRUD-GEN:{region_id}\s*)$"


# ============================================================
# Patch 操作模型
# ============================================================


class RegionPatch(BaseModel):
    """单个受控区域的 patch"""

    region_id: str = Field(..., description="区域 ID")
    content: str = Field(..., description="新的区域内容")


class PatchResult(BaseModel):
    """Patch 应用结果"""

    success: bool = Field(True)
    patched_content: str = Field("")
    regions_updated: list[str] = Field(default_factory=list)
    regions_appended: list[str] = Field(default_factory=list)
    regions_skipped: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================
# 核心函数
# ============================================================


def find_regions(content: str) -> dict[str, tuple[int, int, int, int]]:
    """查找所有受控区域

    Returns:
        {region_id: (begin_start, begin_end, end_start, end_end)}
        begin_start/end = BEGIN 行的 span
        end_start/end = END 行的 span
    """
    regions: dict[str, tuple[int, int, int, int]] = {}

    for match in _BEGIN_RE.finditer(content):
        region_id = match.group(2)
        begin_start = match.start()
        begin_end = match.end()

        # 查找对应的 END
        end_pattern = re.compile(
            _END_RE_TEMPLATE.format(region_id=re.escape(region_id)),
            re.MULTILINE,
        )
        end_match = end_pattern.search(content, begin_end)
        if end_match:
            regions[region_id] = (
                begin_start, begin_end,
                end_match.start(), end_match.end(),
            )

    return regions


def apply_region_patch(
    existing_content: str,
    patches: list[RegionPatch],
    fallback: FallbackStrategy = FallbackStrategy.APPEND,
    comment_style: str = "//",
) -> PatchResult:
    """应用受控区域 patch

    Args:
        existing_content: 现有文件内容
        patches: 要应用的 patch 列表
        fallback: 锚点缺失时的降级策略
        comment_style: 注释风格 ("//", "#")

    Returns:
        PatchResult
    """
    result = PatchResult()
    content = existing_content
    errors: list[str] = []

    # 处理每个 patch（每轮重新扫描 region 位置以适应内容偏移）
    for patch in patches:
        current_regions = find_regions(content)

        if patch.region_id in current_regions:
            # 替换已有区域
            begin_start, begin_end, end_start, end_end = current_regions[patch.region_id]

            # 保留 BEGIN 行和 END 行，只替换中间内容
            new_content = patch.content
            if not new_content.startswith("\n"):
                new_content = "\n" + new_content
            if not new_content.endswith("\n"):
                new_content = new_content + "\n"

            content = (
                content[:begin_end]
                + new_content
                + content[end_start:]
            )
            result.regions_updated.append(patch.region_id)

        elif fallback == FallbackStrategy.APPEND:
            # 追加新区域
            begin_marker = f"{comment_style} BEGIN CRUD-GEN:{patch.region_id}"
            end_marker = f"{comment_style} END CRUD-GEN:{patch.region_id}"

            new_block = f"\n{begin_marker}\n{patch.content}\n{end_marker}\n"

            content = content.rstrip("\n") + new_block
            result.regions_appended.append(patch.region_id)

        elif fallback == FallbackStrategy.ERROR:
            errors.append(
                f"Region '{patch.region_id}' not found in file. "
                f"Cannot apply patch without existing anchor."
            )

        elif fallback == FallbackStrategy.SKIP:
            result.regions_skipped.append(patch.region_id)

    if errors:
        result.success = False
        result.errors = errors

    result.patched_content = content
    return result


def create_region_block(
    region_id: str,
    content: str,
    comment_style: str = "//",
) -> str:
    """创建带锚点的受控区域块

    Args:
        region_id: 区域 ID
        content: 区域内容
        comment_style: 注释风格

    Returns:
        带锚点的完整块
    """
    begin = f"{comment_style} BEGIN CRUD-GEN:{region_id}"
    end = f"{comment_style} END CRUD-GEN:{region_id}"
    return f"{begin}\n{content}\n{end}"


def strip_regions(content: str) -> str:
    """移除所有受控区域（包括锚点和内容）

    用于清理已生成的内容。
    """
    regions = find_regions(content)
    if not regions:
        return content

    # 按位置从后向前删除
    sorted_regions = sorted(
        regions.values(),
        key=lambda x: x[0],
        reverse=True,
    )

    for begin_start, _, _, end_end in sorted_regions:
        content = content[:begin_start] + content[end_end:]

    return content


__all__ = [
    "FallbackStrategy",
    "PatchResult",
    "RegionPatch",
    "apply_region_patch",
    "create_region_block",
    "find_regions",
    "strip_regions",
]

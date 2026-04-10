"""Generator shared types. / 生成器共享类型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeneratedFile:
    """生成文件描述 / Generated file descriptor."""

    path: str
    content: str
    action: str
    appended_content: str | None = None
    insert_before_last_marker: str | None = None
    merged_keys: list[str] | None = None
    route_meta: dict | None = None
    model_meta: dict | None = None


@dataclass
class GenerateResult:
    """生成结果（含文件列表与渲染异常）/ Generate result (files + render errors)."""

    files: list[GeneratedFile]
    errors: list[str]


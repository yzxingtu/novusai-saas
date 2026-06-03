"""
Codegen preset loader / 代码生成器预设加载器

Centralizes preset discovery and metadata parsing for Web API and CLI.
统一 Web API 与 CLI 的预设发现和元数据解析。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PRESET_META: dict[str, dict[str, Any]] = {
    "simple": {
        "label_zh": "基础 CRUD",
        "label_en": "Basic CRUD",
        "description_zh": "单端基础 CRUD，适合作为最小起手模板",
        "description_en": "Single-scope baseline CRUD template for the smallest starting point",
        "category": "crud",
        "tags": ["basic", "single_scope"],
        "recommended_for": ["new_resource"],
        "sort_order": 10,
    },
    "tree": {
        "label_zh": "树形 CRUD",
        "label_en": "Tree CRUD",
        "description_zh": "带父子层级的树形资源模板",
        "description_en": "CRUD template for tree-structured resources",
        "category": "crud",
        "tags": ["tree", "hierarchy"],
        "recommended_for": ["category", "org_tree"],
        "sort_order": 20,
    },
    "dual_scope": {
        "label_zh": "双端 CRUD",
        "label_en": "Dual Scope CRUD",
        "description_zh": "同时包含 Admin 和 Tenant 入口的双端模板",
        "description_en": "Template with both Admin and Tenant entry points",
        "category": "crud",
        "tags": ["admin", "tenant", "dual_scope"],
        "recommended_for": ["shared_resource"],
        "sort_order": 30,
    },
    "workflow": {
        "label_zh": "工作流 CRUD",
        "label_en": "Workflow CRUD",
        "description_zh": "带状态流转与流程动作的资源模板",
        "description_en": "Resource template with status transitions and workflow actions",
        "category": "workflow",
        "tags": ["workflow", "status"],
        "recommended_for": ["approval_flow"],
        "sort_order": 40,
    },
    "sub_form_embedded": {
        "label_zh": "子表单（嵌入）",
        "label_en": "Sub Form Embedded",
        "description_zh": "主从数据嵌入同一表单，适合轻量嵌套录入",
        "description_en": "Master-detail form with embedded child records for lightweight nested input",
        "category": "sub_form",
        "tags": ["sub_form", "embedded"],
        "recommended_for": ["nested_input"],
        "sort_order": 50,
    },
    "sub_form_standard": {
        "label_zh": "子表单（标准）",
        "label_en": "Sub Form Standard",
        "description_zh": "标准主子表录入模板，主表与子表一起提交",
        "description_en": "Standard master-detail template with a shared submit flow",
        "category": "sub_form",
        "tags": ["sub_form", "standard", "master_detail"],
        "recommended_for": ["order", "invoice"],
        "sort_order": 60,
    },
    "sub_form_erp": {
        "label_zh": "子表单（ERP）",
        "label_en": "Sub Form ERP",
        "description_zh": "更贴近 ERP 场景的主子表模板",
        "description_en": "Master-detail template tailored for ERP-like business flows",
        "category": "sub_form",
        "tags": ["sub_form", "erp", "master_detail"],
        "recommended_for": ["erp"],
        "sort_order": 70,
    },
}


def get_presets_dir() -> Path:
    """Return the preset directory / 返回预设目录."""
    return Path(__file__).resolve().parent / "templates" / "presets"


def _titleize(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def _parse_preset_file(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        data = {}
    return data, content


def _extract_metadata(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    fallback = _DEFAULT_PRESET_META.get(name, {})
    label_zh = str(meta.get("label_zh") or fallback.get("label_zh") or _titleize(name))
    label_en = str(meta.get("label_en") or fallback.get("label_en") or _titleize(name))
    description_zh = str(
        meta.get("description_zh") or fallback.get("description_zh") or ""
    )
    description_en = str(
        meta.get("description_en") or fallback.get("description_en") or ""
    )
    category = str(meta.get("category") or fallback.get("category") or "general")
    tags = meta.get("tags") or fallback.get("tags") or []
    recommended_for = (
        meta.get("recommended_for") or fallback.get("recommended_for") or []
    )
    sort_order = int(meta.get("sort_order") or fallback.get("sort_order") or 999)
    return {
        "name": name,
        "label_zh": label_zh,
        "label_en": label_en,
        "description_zh": description_zh,
        "description_en": description_en,
        "category": category,
        "tags": [str(tag) for tag in tags if str(tag).strip()],
        "recommended_for": [str(item) for item in recommended_for if str(item).strip()],
        "sort_order": sort_order,
    }


def _strip_meta(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if k != "meta"}


def list_presets(presets_dir: Path | None = None) -> list[dict[str, Any]]:
    """List all presets with metadata / 列出全部预设及其元数据."""
    base_dir = presets_dir or get_presets_dir()
    if not base_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(base_dir.glob("*.yaml")):
        raw, _content = _parse_preset_file(path)
        items.append(_extract_metadata(path.stem, raw))
    items.sort(
        key=lambda item: (int(item.get("sort_order", 999)), str(item.get("name", "")))
    )
    return items


def get_preset(name: str, presets_dir: Path | None = None) -> dict[str, Any] | None:
    """Get a single preset with parsed content / 获取单个预设及其解析结果."""
    base_dir = presets_dir or get_presets_dir()
    path = (base_dir / f"{name}.yaml").resolve()
    if not path.exists():
        return None
    raw, content = _parse_preset_file(path)
    meta = _extract_metadata(name, raw)
    return {
        **meta,
        "content": content,
        "parsed": _strip_meta(raw),
    }

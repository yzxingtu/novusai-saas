"""
代码生成器选项配置 / Codegen Options Config

集中管理 parent_resources、system_modules、field_templates 等，供 API 和向导使用。
Central config for parent_resources, system_modules, field_templates.
"""

from __future__ import annotations

from typing import Any

# 父资源列表（树形关联用）/ Parent resources for tree relations
PARENT_RESOURCES: list[str] = [
    "department",
    "tenant",
    "plan",
    "role",
    "permission",
]

# 系统模块列表 / System modules
SYSTEM_MODULES: list[str] = [
    "system",
    "auth",
    "tenant",
    "ai",
    "plugin",
]

# 字段模板 / Field templates: key -> list of field configs
FIELD_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "name_code": [
        {"name": "name", "type": "String(100)", "required": True, "comment": "名称"},
        {"name": "code", "type": "String(50)", "required": True, "unique": True, "comment": "编码"},
    ],
    "status_sort": [
        {"name": "status", "type": "String(20)", "default": "active", "comment": "状态"},
        {"name": "sort_order", "type": "Integer", "default": 0, "comment": "排序"},
    ],
    "description": [{"name": "description", "type": "Text", "nullable": True, "comment": "描述"}],
    "audit": [
        {"name": "created_by", "type": "Integer", "nullable": True, "comment": "创建人"},
        {"name": "updated_by", "type": "Integer", "nullable": True, "comment": "更新人"},
    ],
    "status_active": [
        {"name": "status", "type": "String(20)", "default": "active", "comment": "状态"},
        {"name": "is_active", "type": "Boolean", "default": True, "comment": "启用"},
    ],
    "sort_order": [{"name": "sort_order", "type": "Integer", "default": 0, "comment": "排序"}],
    "name_code_desc_remark": [
        {"name": "name", "type": "String(100)", "required": True, "comment": "名称"},
        {"name": "code", "type": "String(50)", "required": True, "unique": True, "comment": "编码"},
        {"name": "description", "type": "Text", "nullable": True, "comment": "描述"},
        {"name": "remark", "type": "Text", "nullable": True, "comment": "备注"},
    ],
    "file_fields": [
        {"name": "avatar", "type": "ImageUpload", "nullable": True, "comment": "头像"},
        {"name": "cover", "type": "ImageUpload", "nullable": True, "comment": "封面"},
        {"name": "attachment", "type": "FilePicker", "nullable": True, "comment": "附件"},
    ],
}


def get_codegen_options() -> dict[str, Any]:
    """
    获取代码生成器所有选项 / Get all codegen options.

    Returns:
        { parent_resources, system_modules, field_templates }
    """
    return {
        "parent_resources": PARENT_RESOURCES,
        "system_modules": SYSTEM_MODULES,
        "field_templates": FIELD_TEMPLATES,
    }

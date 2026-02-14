"""
CRUD 代码生成器 — 配置模板存储

将 CrudConfig 配置持久化为 JSON 文件，支持 save/load/list/delete。
存储目录: backend/app/codegen/config_templates/
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from app.codegen.schemas import CrudConfig


# ============================================================
# 常量
# ============================================================

_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "config_templates")


# ============================================================
# 数据类型
# ============================================================


@dataclass
class TemplateMeta:
    """模板元信息"""

    name: str
    description: str
    module: str
    scope: str
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "module": self.module,
            "scope": self.scope,
            "updated_at": self.updated_at,
        }


# ============================================================
# TemplateStore
# ============================================================


class TemplateStore:
    """配置模板文件存储

    用法::

        store = TemplateStore()
        store.save("order", config, description="订单模块")
        config = store.load("order")
        templates = store.list_all()
        store.delete("order")
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        self._dir = storage_dir or _STORAGE_DIR
        os.makedirs(self._dir, exist_ok=True)

    def _filepath(self, name: str) -> str:
        """构建安全的模板文件路径

        安全规则:
        - 拒绝空名称
        - 拒绝 null 字节
        - 拒绝路径穿越 (..)
        - 拒绝路径分隔符 (/ \\)
        - 确保最终路径在 storage_dir 内
        """
        if not name:
            raise ValueError("Template name cannot be empty")
        if "\x00" in name:
            raise ValueError("Template name contains null byte")
        # Strip path separators and traversal sequences
        safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        filepath = os.path.join(self._dir, f"{safe_name}.json")
        # Final containment check
        real_path = os.path.realpath(filepath)
        real_dir = os.path.realpath(self._dir)
        if not real_path.startswith(real_dir + os.sep) and real_path != real_dir:
            raise ValueError(f"Path escapes storage directory: {name}")
        return filepath

    # ---- save ----

    def save(
        self,
        name: str,
        config: CrudConfig,
        description: str = "",
    ) -> str:
        """保存配置模板

        Args:
            name: 模板名称（唯一标识）
            config: CrudConfig 配置
            description: 模板描述

        Returns:
            保存的文件路径
        """
        filepath = self._filepath(name)
        data = {
            "name": name,
            "description": description,
            "config": config.model_dump(mode="json"),
            "saved_at": time.time(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    # ---- load ----

    def load(self, name: str) -> CrudConfig | None:
        """加载配置模板

        Args:
            name: 模板名称

        Returns:
            CrudConfig 或 None（不存在时）
        """
        filepath = self._filepath(name)
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CrudConfig(**data["config"])

    # ---- load_raw ----

    def load_raw(self, name: str) -> dict[str, Any] | None:
        """加载配置模板原始数据（含元信息）

        Args:
            name: 模板名称

        Returns:
            完整 JSON 数据或 None
        """
        filepath = self._filepath(name)
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---- list ----

    def list_all(self) -> list[TemplateMeta]:
        """列出所有配置模板

        Returns:
            模板元信息列表
        """
        templates: list[TemplateMeta] = []

        for filename in sorted(os.listdir(self._dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self._dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = data.get("config", {})
                templates.append(
                    TemplateMeta(
                        name=data.get("name", filename[:-5]),
                        description=data.get("description", ""),
                        module=cfg.get("module", ""),
                        scope=cfg.get("scope", ""),
                        updated_at=data.get("saved_at", os.path.getmtime(filepath)),
                    )
                )
            except (json.JSONDecodeError, OSError):
                continue

        return templates

    # ---- delete ----

    def delete(self, name: str) -> bool:
        """删除配置模板

        Args:
            name: 模板名称

        Returns:
            True 已删除，False 不存在
        """
        filepath = self._filepath(name)
        if not os.path.exists(filepath):
            return False
        os.remove(filepath)
        return True

    # ---- exists ----

    def exists(self, name: str) -> bool:
        """检查模板是否存在"""
        return os.path.exists(self._filepath(name))


__all__ = [
    "TemplateMeta",
    "TemplateStore",
]

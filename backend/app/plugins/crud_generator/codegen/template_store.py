"""
CRUD Generator — 配置模板文件存储

将 CrudConfig 模板以 JSON 文件形式持久化到 codegen/config_templates/ 目录。
"""

from __future__ import annotations

import json
import os
import re

from app.core.i18n import _
from app.exceptions import NotFoundException, ValidationException

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_DEFAULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "config_templates",
)


class TemplateStore:
    """配置模板文件存储"""

    def __init__(self, base_dir: str = _DEFAULT_DIR) -> None:
        self._dir = base_dir
        os.makedirs(self._dir, exist_ok=True)

    def _path(self, name: str) -> str:
        self._validate_name(name)
        return os.path.join(self._dir, f"{name}.json")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not _SAFE_NAME_RE.match(name):
            raise ValidationException(
                _("codegen.error.invalid_template_name")
            )

    def list_all(self) -> list[dict[str, str | float]]:
        items: list[dict[str, str | float]] = []
        for filename in sorted(os.listdir(self._dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self._dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append({
                    "name": data.get("name", filename[:-5]),
                    "description": data.get("description", ""),
                    "module": data.get("config", {}).get("module", ""),
                    "scope": data.get("config", {}).get("scope", ""),
                    "updated_at": os.path.getmtime(filepath),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return items

    def get(self, name: str) -> dict[str, object]:
        filepath = self._path(name)
        if not os.path.exists(filepath):
            raise NotFoundException(_("codegen.error.template_not_found"))
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def save(self, name: str, data: dict[str, object]) -> str:
        filepath = self._path(name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    def update(
        self,
        name: str,
        *,
        description: str | None = None,
        tags: list[str] | None = None,
        config: object | None = None,
    ) -> None:
        filepath = self._path(name)
        if not os.path.exists(filepath):
            raise NotFoundException(_("codegen.error.template_not_found"))
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if description is not None:
            data["description"] = description
        if tags is not None:
            data["tags"] = tags
        if config is not None:
            if hasattr(config, "model_dump"):
                data["config"] = config.model_dump(mode="json")
            else:
                data["config"] = config
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self, name: str) -> None:
        filepath = self._path(name)
        if not os.path.exists(filepath):
            raise NotFoundException(_("codegen.error.template_not_found"))
        os.remove(filepath)


__all__ = ["TemplateStore", "_SAFE_NAME_RE"]

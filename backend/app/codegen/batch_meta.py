"""
批量元数据 v2 — shared 文件归属 + 多 owner + 版本化

M58-T11: 升级 __entity_file_map__.json 为 batch meta v2

v1 格式 (entity_file_map):
  { "path": "module" }  — 只能单归属

v2 格式 (batch_meta):
  {
    "version": "2.0.0",
    "project_name": "...",
    "generation_order": [...],
    "files": {
      "path": {
        "owners": ["module1", "module2"],
        "role": "entity" | "shared",
        "kind": "router" | "api" | "i18n" | "model" | "controller" | ...
      }
    }
  }
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


META_VERSION = "2.0.0"
"""当前 batch meta 版本"""


# ============================================================
# 枚举
# ============================================================


class FileRole(str, Enum):
    """文件角色"""

    ENTITY = "entity"
    SHARED = "shared"


class FileKind(str, Enum):
    """文件类型"""

    ROUTER = "router"
    API = "api"
    I18N = "i18n"
    MODEL = "model"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    VIEW = "view"
    FORM = "form"
    DATA = "data"
    ENUM = "enum"
    MIGRATION = "migration"
    OTHER = "other"


# ============================================================
# 文件元数据
# ============================================================


class FileMeta(BaseModel):
    """单个文件的元数据"""

    owners: list[str] = Field(
        default_factory=list,
        description="文件归属的实体 module 列表（共享文件可有多个 owner）",
    )
    role: FileRole = Field(
        FileRole.ENTITY,
        description="文件角色：entity（实体专属）或 shared（共享）",
    )
    kind: FileKind = Field(
        FileKind.OTHER,
        description="文件类型分类",
    )


class BatchMeta(BaseModel):
    """批量生成元数据 v2"""

    version: str = Field(META_VERSION)
    project_name: str = Field("")
    generation_order: list[str] = Field(default_factory=list)
    files: dict[str, FileMeta] = Field(default_factory=dict)

    def entity_files(self, module: str) -> dict[str, FileMeta]:
        """获取指定实体的文件"""
        return {
            path: meta
            for path, meta in self.files.items()
            if module in meta.owners and meta.role == FileRole.ENTITY
        }

    def shared_files(self) -> dict[str, FileMeta]:
        """获取所有共享文件"""
        return {
            path: meta
            for path, meta in self.files.items()
            if meta.role == FileRole.SHARED
        }

    def files_by_owner(self) -> dict[str, list[str]]:
        """按 owner 分组的文件路径

        Returns:
            {"module1": ["path1", "path2"], "__shared__": ["path3"]}
        """
        groups: dict[str, list[str]] = {}
        for path, meta in self.files.items():
            if meta.role == FileRole.SHARED:
                groups.setdefault("__shared__", []).append(path)
            else:
                for owner in meta.owners:
                    groups.setdefault(owner, []).append(path)
        return groups

    def summary(self) -> dict[str, Any]:
        """元数据摘要"""
        entity_count = len({
            o for m in self.files.values()
            for o in m.owners if m.role == FileRole.ENTITY
        })
        shared_count = sum(
            1 for m in self.files.values() if m.role == FileRole.SHARED
        )
        multi_owner = sum(
            1 for m in self.files.values() if len(m.owners) > 1
        )
        kinds = {}
        for m in self.files.values():
            kinds[m.kind.value] = kinds.get(m.kind.value, 0) + 1

        return {
            "version": self.version,
            "total_files": len(self.files),
            "entity_count": entity_count,
            "shared_files": shared_count,
            "multi_owner_files": multi_owner,
            "kinds": kinds,
        }


# ============================================================
# Kind 推断
# ============================================================

_KIND_PATTERNS: list[tuple[str, FileKind]] = [
    ("router", FileKind.ROUTER),
    ("route", FileKind.ROUTER),
    ("/api/", FileKind.API),
    ("api.ts", FileKind.API),
    ("api.py", FileKind.API),
    ("i18n", FileKind.I18N),
    ("locale", FileKind.I18N),
    ("model", FileKind.MODEL),
    ("controller", FileKind.CONTROLLER),
    ("service", FileKind.SERVICE),
    ("repository", FileKind.REPOSITORY),
    ("schema", FileKind.SCHEMA),
    ("index.vue", FileKind.VIEW),
    ("list.vue", FileKind.VIEW),
    ("form.vue", FileKind.FORM),
    ("drawer.vue", FileKind.FORM),
    ("data.ts", FileKind.DATA),
    ("enum", FileKind.ENUM),
    ("migration", FileKind.MIGRATION),
    ("alembic", FileKind.MIGRATION),
]


def infer_file_kind(path: str) -> FileKind:
    """从文件路径推断 FileKind"""
    lower = path.lower().replace("\\", "/")
    for pattern, kind in _KIND_PATTERNS:
        if pattern in lower:
            return kind
    return FileKind.OTHER


# ============================================================
# 从 entity_file_map (v1) 构建 BatchMeta (v2)
# ============================================================


def from_entity_file_map(
    entity_file_map: dict[str, str],
    project_name: str = "",
    generation_order: list[str] | None = None,
) -> BatchMeta:
    """从 v1 entity_file_map 转换为 v2 BatchMeta

    v1 格式: {"path": "module"}
    如果 module 为空字符串或 "__shared__"，标记为 shared。

    Args:
        entity_file_map: v1 格式的文件→模块映射
        project_name: 项目名称
        generation_order: 生成顺序

    Returns:
        BatchMeta v2
    """
    files: dict[str, FileMeta] = {}

    for path, module in entity_file_map.items():
        is_shared = not module or module == "__shared__"
        kind = infer_file_kind(path)

        files[path] = FileMeta(
            owners=[] if is_shared else [module],
            role=FileRole.SHARED if is_shared else FileRole.ENTITY,
            kind=kind,
        )

    return BatchMeta(
        project_name=project_name,
        generation_order=generation_order or [],
        files=files,
    )


def from_generated_files(
    entity_files: dict[str, list[dict[str, str]]],
    shared_files: list[dict[str, str]] | None = None,
    project_name: str = "",
    generation_order: list[str] | None = None,
) -> BatchMeta:
    """从生成结果构建 BatchMeta v2

    Args:
        entity_files: {module: [{path: ..., content: ...}, ...]}
        shared_files: [{path: ..., content: ...}, ...]  — 共享文件
        project_name: 项目名称
        generation_order: 生成顺序

    Returns:
        BatchMeta v2
    """
    files: dict[str, FileMeta] = {}

    # 实体文件
    for module, file_list in entity_files.items():
        for f in file_list:
            path = f.get("path", f.get("rel_path", ""))
            if not path:
                continue
            kind = infer_file_kind(path)

            if path in files:
                # 多 owner: 已被其他实体登记过
                existing = files[path]
                if module not in existing.owners:
                    existing.owners.append(module)
                # 多 owner → shared
                if len(existing.owners) > 1:
                    existing.role = FileRole.SHARED
            else:
                files[path] = FileMeta(
                    owners=[module],
                    role=FileRole.ENTITY,
                    kind=kind,
                )

    # 共享文件
    if shared_files:
        for f in shared_files:
            path = f.get("path", f.get("rel_path", ""))
            if not path:
                continue
            kind = infer_file_kind(path)

            if path in files:
                files[path].role = FileRole.SHARED
            else:
                files[path] = FileMeta(
                    owners=[],
                    role=FileRole.SHARED,
                    kind=kind,
                )

    return BatchMeta(
        project_name=project_name,
        generation_order=generation_order or [],
        files=files,
    )


__all__ = [
    "META_VERSION",
    "BatchMeta",
    "FileKind",
    "FileMeta",
    "FileRole",
    "from_entity_file_map",
    "from_generated_files",
    "infer_file_kind",
]

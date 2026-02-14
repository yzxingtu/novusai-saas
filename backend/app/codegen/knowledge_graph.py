"""
项目知识图谱 — 跨模块智能感知

扫描 app/models/ 下所有 SQLAlchemy Model，提取元数据：
  - 表名、类名、基类 (BaseModel / TenantModel)
  - 列定义 (名称、类型、nullable、FK、comment)
  - __filterable__ / __sortable__ / __selectable__
  - relationship 关联

结果缓存在进程内存中，供 CrudGeneratorExecutor 注入 AI Prompt
使 AI 感知项目已有模块，避免生成重复表名或不一致的关联。

提供 get_project_graph() 获取完整图谱，
提供 get_graph_summary() 获取 token 友好的摘要文本。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import RelationshipProperty

from app.core.base_model import Base, BaseModel, TenantModel


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ColumnMeta:
    """列元数据"""

    __slots__ = ("name", "type", "nullable", "primary_key", "foreign_key", "comment")

    def __init__(
        self,
        name: str,
        type: str,
        nullable: bool,
        primary_key: bool,
        foreign_key: str | None,
        comment: str | None,
    ) -> None:
        self.name = name
        self.type = type
        self.nullable = nullable
        self.primary_key = primary_key
        self.foreign_key = foreign_key
        self.comment = comment

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "nullable": self.nullable,
        }
        if self.primary_key:
            d["primary_key"] = True
        if self.foreign_key:
            d["foreign_key"] = self.foreign_key
        if self.comment:
            d["comment"] = self.comment
        return d


class RelationMeta:
    """关联元数据"""

    __slots__ = ("name", "target", "direction", "uselist")

    def __init__(
        self,
        name: str,
        target: str,
        direction: str,
        uselist: bool,
    ) -> None:
        self.name = name
        self.target = target
        self.direction = direction
        self.uselist = uselist

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "direction": self.direction,
            "uselist": self.uselist,
        }


class ModelMeta:
    """模型元数据"""

    __slots__ = (
        "class_name",
        "table_name",
        "base_class",
        "columns",
        "relations",
        "filterable",
        "sortable",
        "selectable",
    )

    def __init__(
        self,
        class_name: str,
        table_name: str,
        base_class: str,
        columns: list[ColumnMeta],
        relations: list[RelationMeta],
        filterable: dict[str, str] | None,
        sortable: dict[str, str] | None,
        selectable: dict[str, Any] | None,
    ) -> None:
        self.class_name = class_name
        self.table_name = table_name
        self.base_class = base_class
        self.columns = columns
        self.relations = relations
        self.filterable = filterable
        self.sortable = sortable
        self.selectable = selectable

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "class_name": self.class_name,
            "table_name": self.table_name,
            "base_class": self.base_class,
            "columns": [c.to_dict() for c in self.columns],
        }
        if self.relations:
            d["relations"] = [r.to_dict() for r in self.relations]
        if self.filterable:
            d["filterable"] = (
                list(self.filterable.keys())
                if isinstance(self.filterable, dict)
                else list(self.filterable)
            )
        if self.sortable:
            d["sortable"] = (
                list(self.sortable.keys())
                if isinstance(self.sortable, dict)
                else list(self.sortable)
            )
        if self.selectable:
            d["selectable"] = self.selectable
        return d


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

_SYSTEM_COLUMNS = frozenset({
    "id", "created_at", "updated_at", "is_deleted",
    "deleted_at", "delete_level", "tenant_id",
})


def _col_type_str(col_type: Any) -> str:
    """将 SQLAlchemy 列类型转为简短字符串"""
    type_name = type(col_type).__name__
    mapping = {
        "String": "string",
        "Text": "text",
        "Integer": "integer",
        "BigInteger": "bigint",
        "Float": "float",
        "Numeric": "decimal",
        "Boolean": "boolean",
        "DateTime": "datetime",
        "Date": "date",
        "JSON": "json",
        "LargeBinary": "binary",
        "Enum": "enum",
    }
    result = mapping.get(type_name, type_name.lower())
    if type_name == "String" and hasattr(col_type, "length") and col_type.length:
        result = f"string({col_type.length})"
    return result


def _inspect_model(model_cls: type) -> ModelMeta:
    """从 SQLAlchemy Model 类提取元数据"""
    mapper = sa_inspect(model_cls)

    # 基类判断
    if issubclass(model_cls, TenantModel):
        base_class = "TenantModel"
    else:
        base_class = "BaseModel"

    # 列
    columns: list[ColumnMeta] = []
    for col_attr in mapper.column_attrs:
        col = col_attr.columns[0]
        col_name = col.name

        # 提取 FK
        fk_str: str | None = None
        if col.foreign_keys:
            fk = next(iter(col.foreign_keys))
            fk_str = str(fk.target_fullname)

        columns.append(ColumnMeta(
            name=col_name,
            type=_col_type_str(col.type),
            nullable=col.nullable if col.nullable is not None else True,
            primary_key=col.primary_key,
            foreign_key=fk_str,
            comment=col.comment,
        ))

    # 关联关系
    relations: list[RelationMeta] = []
    for rel in mapper.relationships:
        assert isinstance(rel, RelationshipProperty)
        target_cls = rel.mapper.class_
        relations.append(RelationMeta(
            name=rel.key,
            target=target_cls.__name__,
            direction=rel.direction.name,
            uselist=rel.uselist,
        ))

    # __filterable__ / __sortable__ / __selectable__
    filterable = getattr(model_cls, "__filterable__", None)
    sortable = getattr(model_cls, "__sortable__", None)
    selectable = getattr(model_cls, "__selectable__", None)

    return ModelMeta(
        class_name=model_cls.__name__,
        table_name=str(mapper.local_table),
        base_class=base_class,
        columns=columns,
        relations=relations,
        filterable=filterable,
        sortable=sortable,
        selectable=selectable,
    )


def _scan_all_models() -> list[ModelMeta]:
    """扫描 Base 的所有子类，提取元数据"""
    # 确保所有模型已被导入（触发 register）
    import app.models  # noqa: F401

    results: list[ModelMeta] = []
    seen: set[str] = set()

    for mapper in list(Base.registry.mappers):
        cls = mapper.class_
        # 跳过 association table proxies (无 __tablename__)
        if not hasattr(cls, "__tablename__"):
            continue
        table_name = cls.__tablename__
        if table_name in seen:
            continue
        seen.add(table_name)

        try:
            meta = _inspect_model(cls)
            results.append(meta)
        except Exception as exc:
            logger.warning("Failed to inspect model %s: %s", cls.__name__, exc)
            continue

    results.sort(key=lambda m: m.table_name)
    return results


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_cache: list[ModelMeta] | None = None


def get_project_graph(*, force_refresh: bool = False) -> list[ModelMeta]:
    """获取项目知识图谱（带缓存）

    Returns:
        ModelMeta 列表，按 table_name 排序
    """
    global _cache
    if _cache is not None and not force_refresh:
        return _cache
    with _lock:
        if _cache is not None and not force_refresh:
            return _cache
        _cache = _scan_all_models()
        return _cache


def get_project_graph_dict(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """获取项目知识图谱（dict 格式，用于 API 响应）"""
    return [m.to_dict() for m in get_project_graph(force_refresh=force_refresh)]


def invalidate_cache() -> None:
    """清除缓存（用于测试）"""
    global _cache
    with _lock:
        _cache = None


# ---------------------------------------------------------------------------
# AI Prompt 摘要
# ---------------------------------------------------------------------------

_MAX_SUMMARY_CHARS = 4000  # Token-friendly limit


def get_graph_summary(*, force_refresh: bool = False) -> str:
    """生成 token 友好的项目模型摘要，用于注入 AI Prompt

    格式示例::

        ## 项目已有模型 (37 tables)

        ### BaseModel (平台级)
        - admins: Admin (username, email, role_id, is_active, ...)
        - tenants: Tenant (name, code, plan_id, is_active, ...)

        ### TenantModel (租户级)
        - agents: Agent → ai_models (name, status, scope, model_id, ...)
        - skills: Skill → skill_packages (name, type, scope, package_id, ...)
    """
    models = get_project_graph(force_refresh=force_refresh)
    if not models:
        return "## 项目已有模型\n\n暂无模型数据。"

    base_models: list[ModelMeta] = []
    tenant_models: list[ModelMeta] = []
    for m in models:
        if m.base_class == "TenantModel":
            tenant_models.append(m)
        else:
            base_models.append(m)

    lines: list[str] = [f"## 项目已有模型 ({len(models)} tables)\n"]

    def _render_group(title: str, group: list[ModelMeta]) -> None:
        if not group:
            return
        lines.append(f"### {title}")
        for m in group:
            # 列出非系统列（紧凑）
            user_cols = [
                c.name for c in m.columns
                if c.name not in _SYSTEM_COLUMNS and not c.primary_key
            ]
            col_str = ", ".join(user_cols[:8])
            if len(user_cols) > 8:
                col_str += f", ... (+{len(user_cols) - 8})"

            # FK 标记
            fk_targets = []
            for c in m.columns:
                if c.foreign_key:
                    fk_targets.append(c.foreign_key.split(".")[0])
            fk_str = " → " + ", ".join(fk_targets) if fk_targets else ""

            lines.append(f"- **{m.table_name}**: {m.class_name}{fk_str} ({col_str})")
        lines.append("")

    _render_group("BaseModel (平台级)", base_models)
    _render_group("TenantModel (租户级)", tenant_models)

    summary = "\n".join(lines)

    # 如果超过限制，截断
    if len(summary) > _MAX_SUMMARY_CHARS:
        summary = summary[:_MAX_SUMMARY_CHARS] + "\n... (truncated)"

    return summary


__all__ = [
    "ColumnMeta",
    "RelationMeta",
    "ModelMeta",
    "get_project_graph",
    "get_project_graph_dict",
    "get_graph_summary",
    "invalidate_cache",
]

"""
CRUD 代码生成器 — Mock 数据生成器

根据 CrudConfig 字段类型生成 Mock 数据，用于前端预览。
支持所有字段类型、枚举、关联字段展示值。
"""

from __future__ import annotations

import random
import string
import time
from datetime import datetime, timedelta
from typing import Any

from app.codegen.schemas import (
    CrudConfig,
    EnumDefinition,
    FieldConfig,
    FieldType,
    RelationConfig,
    RelationType,
)


# ============================================================
# 常量
# ============================================================

_DEFAULT_COUNT = 50

# 中文姓名池
_CN_SURNAMES = ["张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴"]
_CN_GIVEN = ["伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "洋"]

# 公司名池
_CN_COMPANIES = [
    "科技", "信息", "网络", "电子", "数据", "智能", "云计算", "物联网",
]

# Lorem 词池
_LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur",
    "adipiscing", "elit", "sed", "do", "eiusmod", "tempor",
]

# 文件扩展名
_FILE_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".png", ".jpg"]


# ============================================================
# 字段值生成器
# ============================================================


def _rand_string(prefix: str = "", length: int = 8) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}{suffix}" if prefix else suffix


def _rand_cn_name() -> str:
    return random.choice(_CN_SURNAMES) + random.choice(_CN_GIVEN)


def _rand_text(words: int = 20) -> str:
    return " ".join(random.choices(_LOREM_WORDS, k=words)) + "."


def _rand_datetime(days_back: int = 365) -> str:
    dt = datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _rand_date(days_back: int = 365) -> str:
    dt = datetime.now() - timedelta(days=random.randint(0, days_back))
    return dt.strftime("%Y-%m-%d")


def _generate_field_value(
    field: FieldConfig,
    index: int,
    enum_map: dict[str, EnumDefinition],
) -> Any:
    """为单个字段生成 Mock 值"""
    ft = field.type.value

    if ft == "string":
        if "name" in field.name.lower():
            return _rand_cn_name() if index % 3 == 0 else _rand_string("item_", 6)
        if "no" in field.name.lower() or "code" in field.name.lower():
            return f"{field.name.upper()}-{index + 1:06d}"
        if "email" in field.name.lower():
            return f"user{index}@example.com"
        if "phone" in field.name.lower():
            return f"138{random.randint(10000000, 99999999)}"
        if "url" in field.name.lower() or "link" in field.name.lower():
            return f"https://example.com/{_rand_string('', 8)}"
        return _rand_string(f"{field.name}_", 6)

    if ft == "text":
        return _rand_text(random.randint(10, 30))

    if ft == "integer":
        return random.randint(1, 1000)

    if ft == "float":
        return round(random.uniform(0.01, 9999.99), 2)

    if ft == "decimal":
        return round(random.uniform(10.0, 99999.99), 2)

    if ft == "boolean":
        return random.choice([True, False])

    if ft == "datetime":
        return _rand_datetime()

    if ft == "date":
        return _rand_date()

    if ft == "json":
        return {"key": _rand_string("val_", 4), "count": random.randint(1, 100)}

    if ft == "enum":
        enum_def = enum_map.get(field.enum_ref or "")
        if enum_def and enum_def.values:
            opt = random.choice(enum_def.values)
            return opt.value
        return "default"

    if ft == "file":
        ext = random.choice(_FILE_EXTENSIONS)
        return f"/files/uploads/{_rand_string('', 12)}{ext}"

    return _rand_string("val_", 6)


def _generate_relation_value(
    rel: RelationConfig,
    index: int,
) -> dict[str, Any]:
    """为关联字段生成 Mock 值（FK + 展示值）"""
    fk_name = rel.foreign_key or f"{rel.name}_id"
    fk_value = random.randint(1, 20)

    label_field = rel.label_field or "name"
    label_value = _rand_cn_name() if "name" in label_field else _rand_string(f"{rel.name}_", 6)

    return {
        fk_name: fk_value,
        f"{rel.name}_{label_field}": label_value,
    }


# ============================================================
# MockDataGenerator
# ============================================================


class MockDataGenerator:
    """Mock 数据生成器

    用法::

        gen = MockDataGenerator(config)
        items = gen.generate(count=50)
    """

    def __init__(self, config: CrudConfig) -> None:
        self._config = config
        self._enum_map: dict[str, EnumDefinition] = {
            e.name: e for e in config.enums
        }

    def generate(self, count: int = _DEFAULT_COUNT) -> list[dict[str, Any]]:
        """生成 Mock 数据列表

        Args:
            count: 生成数量（默认 50）

        Returns:
            Mock 数据字典列表
        """
        items: list[dict[str, Any]] = []
        now = datetime.now()

        for i in range(count):
            item: dict[str, Any] = {"id": i + 1}

            # 字段值
            for field in self._config.fields:
                if field.required or not field.nullable or random.random() > 0.1:
                    item[field.name] = _generate_field_value(
                        field, i, self._enum_map
                    )
                else:
                    item[field.name] = None

            # 关联字段
            for rel in self._config.relations:
                if rel.type.value == "belongs_to":
                    rel_data = _generate_relation_value(rel, i)
                    item.update(rel_data)

            # is_active
            if self._config.has_status_toggle:
                item["is_active"] = random.random() > 0.2

            # sort_order
            if self._config.drag_sort:
                item["sort_order"] = i + 1

            # 基础字段
            created = now - timedelta(
                days=random.randint(0, 90),
                hours=random.randint(0, 23),
            )
            item["created_at"] = created.strftime("%Y-%m-%dT%H:%M:%S")
            item["updated_at"] = (
                created + timedelta(hours=random.randint(0, 48))
            ).strftime("%Y-%m-%dT%H:%M:%S")

            items.append(item)

        return items

    def generate_single(self) -> dict[str, Any]:
        """生成单条 Mock 数据"""
        return self.generate(count=1)[0]


__all__ = [
    "MockDataGenerator",
]

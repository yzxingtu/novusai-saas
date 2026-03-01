"""
NovusDoc 插件枚举
"""

from app.enums.base import LabeledStrEnum


class DocStatus(LabeledStrEnum):
    """文档状态"""

    DRAFT = ("draft", "enum.doc_status.draft")
    PUBLISHED = ("published", "enum.doc_status.published")
    ARCHIVED = ("archived", "enum.doc_status.archived")

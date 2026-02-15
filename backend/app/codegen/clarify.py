"""
AI 缺失信息自动追问 — 最小问题集 + 追问协议

M58-T31: 当 validate 发现缺少关键信息时，
生成结构化追问问题集，引导用户补全后再继续生成。

问题分类：
- blocking: 阻塞生成（缺主键、缺外键、多对多缺 join entity）
- ambiguous: 可能导致不良结果（类型歧义、命名不明确）

协议：
- questions[]: id, priority, category, question, options?, affects_paths?
- 最多 MAX_QUESTIONS 个问题
- 按优先级排序（blocking > ambiguous）
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 配置
# ============================================================

MAX_QUESTIONS = 5
"""单次最大追问数"""


# ============================================================
# 问题分类
# ============================================================


class QuestionCategory(str, Enum):
    """问题分类"""

    BLOCKING = "blocking"
    AMBIGUOUS = "ambiguous"


class QuestionPriority(int, Enum):
    """问题优先级（越小越优先）"""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


# ============================================================
# 问题模型
# ============================================================


class ClarifyQuestion(BaseModel):
    """追问问题"""

    id: str = Field(..., description="问题唯一 ID")
    priority: QuestionPriority = Field(QuestionPriority.MEDIUM)
    category: QuestionCategory = Field(QuestionCategory.BLOCKING)
    question: str = Field(..., description="问题文本")
    options: list[str] = Field(
        default_factory=list,
        description="可选答案（空 = 自由填写）",
    )
    affects_paths: list[str] = Field(
        default_factory=list,
        description="影响的 project 路径（如 entities[0].fields）",
    )
    context: str = Field("", description="问题上下文/原因")


class ClarifyResult(BaseModel):
    """追问结果"""

    needs_clarification: bool = Field(False)
    questions: list[ClarifyQuestion] = Field(default_factory=list)
    blocking_count: int = Field(0)
    ambiguous_count: int = Field(0)

    def to_tool_output(self) -> dict[str, Any]:
        """序列化为工具输出"""
        return self.model_dump(mode="json")


# ============================================================
# 问题检测器
# ============================================================


def detect_missing_info(project_dict: dict[str, Any]) -> ClarifyResult:
    """检测项目配置中的缺失/歧义信息

    检查项：
    1. 缺少实体（entities 为空）
    2. 实体缺少字段
    3. 缺少主键字段
    4. many_to_many 关系缺少 join entity
    5. 外键字段未指定
    6. 字段类型歧义

    Args:
        project_dict: CrudConfig JSON

    Returns:
        ClarifyResult
    """
    questions: list[ClarifyQuestion] = []
    entities = project_dict.get("entities", [])
    cross_relations = project_dict.get("cross_relations", [])

    # 1. 无实体
    if not entities:
        questions.append(ClarifyQuestion(
            id="no_entities",
            priority=QuestionPriority.CRITICAL,
            category=QuestionCategory.BLOCKING,
            question="No entities defined. What tables/modules do you need?",
            affects_paths=["entities"],
            context="At least one entity is required to generate code.",
        ))
        return _build_result(questions)

    entity_modules = {e.get("module", "") for e in entities}

    # 2. 实体缺少字段
    for i, entity in enumerate(entities):
        module = entity.get("module", f"entity_{i}")
        fields = entity.get("fields", [])

        if not fields:
            questions.append(ClarifyQuestion(
                id=f"no_fields_{module}",
                priority=QuestionPriority.CRITICAL,
                category=QuestionCategory.BLOCKING,
                question=f"Entity '{module}' has no fields. What columns does this table need?",
                affects_paths=[f"entities[{i}].fields"],
                context=f"Entity '{module}' requires at least one field to generate code.",
            ))

    # 3. many_to_many 缺少 join entity
    for i, rel in enumerate(cross_relations):
        rel_type = rel.get("relation_type", "")
        source = rel.get("source_entity", "")
        target = rel.get("target_entity", "")

        if rel_type == "many_to_many":
            join_name = f"{source}_{target}"
            if join_name not in entity_modules:
                questions.append(ClarifyQuestion(
                    id=f"m2m_join_{source}_{target}",
                    priority=QuestionPriority.HIGH,
                    category=QuestionCategory.BLOCKING,
                    question=(
                        f"Many-to-many between '{source}' and '{target}' requires "
                        f"a join entity. Should I create '{join_name}' with two "
                        f"belongs_to relations?"
                    ),
                    options=["Yes, create join entity", "No, I'll define it manually"],
                    affects_paths=[
                        "entities",
                        f"cross_relations[{i}]",
                    ],
                    context=(
                        f"many_to_many is not directly supported. An explicit join "
                        f"entity '{join_name}' with belongs_to to both sides is required."
                    ),
                ))

        # 4. belongs_to 缺少外键
        if rel_type == "belongs_to" and not rel.get("foreign_key"):
            questions.append(ClarifyQuestion(
                id=f"missing_fk_{source}_{target}",
                priority=QuestionPriority.MEDIUM,
                category=QuestionCategory.AMBIGUOUS,
                question=(
                    f"Relation '{source}' belongs_to '{target}': "
                    f"what should the foreign key column be named?"
                ),
                options=[f"{target}_id"],
                affects_paths=[f"cross_relations[{i}].foreign_key"],
                context=f"Default: '{target}_id'. Confirm or specify a different name.",
            ))

    # 5. 关系引用不存在的实体
    for i, rel in enumerate(cross_relations):
        source = rel.get("source_entity", "")
        target = rel.get("target_entity", "")
        rel_type = rel.get("relation_type", "")

        if rel_type == "many_to_many":
            continue  # already handled above

        if source and source not in entity_modules:
            questions.append(ClarifyQuestion(
                id=f"missing_entity_{source}",
                priority=QuestionPriority.HIGH,
                category=QuestionCategory.BLOCKING,
                question=(
                    f"Relation references entity '{source}' which is not defined. "
                    f"Should I add this entity?"
                ),
                options=["Yes, add it", "No, remove the relation"],
                affects_paths=["entities", f"cross_relations[{i}]"],
                context=f"Entity '{source}' must exist for the relation to be valid.",
            ))

        if target and target not in entity_modules:
            questions.append(ClarifyQuestion(
                id=f"missing_entity_{target}",
                priority=QuestionPriority.HIGH,
                category=QuestionCategory.BLOCKING,
                question=(
                    f"Relation references entity '{target}' which is not defined. "
                    f"Should I add this entity?"
                ),
                options=["Yes, add it", "No, remove the relation"],
                affects_paths=["entities", f"cross_relations[{i}]"],
                context=f"Entity '{target}' must exist for the relation to be valid.",
            ))

    return _build_result(questions)


def _build_result(questions: list[ClarifyQuestion]) -> ClarifyResult:
    """构建结果，排序并截断"""
    # 按优先级排序
    sorted_q = sorted(questions, key=lambda q: q.priority.value)

    # 去重（按 id）
    seen: set[str] = set()
    unique: list[ClarifyQuestion] = []
    for q in sorted_q:
        if q.id not in seen:
            seen.add(q.id)
            unique.append(q)

    # 截断到 MAX_QUESTIONS
    truncated = unique[:MAX_QUESTIONS]

    blocking = sum(1 for q in truncated if q.category == QuestionCategory.BLOCKING)
    ambiguous = sum(1 for q in truncated if q.category == QuestionCategory.AMBIGUOUS)

    return ClarifyResult(
        needs_clarification=len(truncated) > 0,
        questions=truncated,
        blocking_count=blocking,
        ambiguous_count=ambiguous,
    )


__all__ = [
    "MAX_QUESTIONS",
    "ClarifyQuestion",
    "ClarifyResult",
    "QuestionCategory",
    "QuestionPriority",
    "detect_missing_info",
]

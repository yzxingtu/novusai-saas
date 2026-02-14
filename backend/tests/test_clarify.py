"""
AI 缺失信息自动追问 — 单元测试

覆盖：
- 无实体时触发追问
- 实体缺少字段
- many_to_many 缺少 join entity
- belongs_to 缺少外键
- 引用不存在的实体
- 有效项目不追问
- 优先级排序（blocking > ambiguous）
- 最大问题数截断
- 去重
- 序列化
"""

import pytest

from app.codegen.clarify import (
    MAX_QUESTIONS,
    ClarifyQuestion,
    ClarifyResult,
    QuestionCategory,
    QuestionPriority,
    detect_missing_info,
)


def _entity(module: str, with_fields: bool = True) -> dict:
    base = {
        "module": module,
        "table_name": f"{module}s",
        "display_name": module.title(),
        "display_name_en": module.title(),
        "parent_menu": "test",
    }
    if with_fields:
        base["fields"] = [
            {"name": "title", "type": "string", "label": "Title",
             "label_zh": "标题", "label_en": "Title"},
        ]
    else:
        base["fields"] = []
    return base


class TestNoEntities:
    """无实体"""

    def test_empty_entities(self):
        result = detect_missing_info({"entities": []})
        assert result.needs_clarification is True
        assert result.blocking_count == 1
        assert result.questions[0].id == "no_entities"

    def test_missing_entities_key(self):
        result = detect_missing_info({})
        assert result.needs_clarification is True


class TestMissingFields:
    """实体缺少字段"""

    def test_entity_no_fields(self):
        result = detect_missing_info({
            "entities": [_entity("order", with_fields=False)],
        })
        assert result.needs_clarification is True
        q = result.questions[0]
        assert q.id == "no_fields_order"
        assert q.category == QuestionCategory.BLOCKING

    def test_entity_with_fields_ok(self):
        result = detect_missing_info({
            "entities": [_entity("order", with_fields=True)],
        })
        assert result.needs_clarification is False


class TestManyToMany:
    """many_to_many 缺少 join entity"""

    def test_m2m_missing_join(self):
        result = detect_missing_info({
            "entities": [_entity("user"), _entity("role")],
            "cross_relations": [{
                "source_entity": "user",
                "target_entity": "role",
                "relation_type": "many_to_many",
            }],
        })
        assert result.needs_clarification is True
        m2m_q = [q for q in result.questions if "m2m_join" in q.id]
        assert len(m2m_q) == 1
        assert "join entity" in m2m_q[0].question.lower()

    def test_m2m_with_join_entity_no_question(self):
        """join entity 已存在时不追问"""
        result = detect_missing_info({
            "entities": [
                _entity("user"),
                _entity("role"),
                _entity("user_role"),
            ],
            "cross_relations": [{
                "source_entity": "user",
                "target_entity": "role",
                "relation_type": "many_to_many",
            }],
        })
        m2m_q = [q for q in result.questions if "m2m_join" in q.id]
        assert len(m2m_q) == 0


class TestMissingForeignKey:
    """belongs_to 缺少外键"""

    def test_missing_fk(self):
        result = detect_missing_info({
            "entities": [_entity("order"), _entity("customer")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
            }],
        })
        fk_q = [q for q in result.questions if "missing_fk" in q.id]
        assert len(fk_q) == 1
        assert fk_q[0].category == QuestionCategory.AMBIGUOUS
        assert "customer_id" in fk_q[0].options

    def test_fk_provided_no_question(self):
        result = detect_missing_info({
            "entities": [_entity("order"), _entity("customer")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
                "foreign_key": "customer_id",
            }],
        })
        fk_q = [q for q in result.questions if "missing_fk" in q.id]
        assert len(fk_q) == 0


class TestMissingEntity:
    """引用不存在的实体"""

    def test_missing_target(self):
        result = detect_missing_info({
            "entities": [_entity("order")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
            }],
        })
        missing_q = [q for q in result.questions if "missing_entity_customer" in q.id]
        assert len(missing_q) == 1
        assert missing_q[0].category == QuestionCategory.BLOCKING

    def test_missing_source(self):
        result = detect_missing_info({
            "entities": [_entity("customer")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
            }],
        })
        missing_q = [q for q in result.questions if "missing_entity_order" in q.id]
        assert len(missing_q) == 1


class TestValidProject:
    """有效项目不追问"""

    def test_complete_project(self):
        result = detect_missing_info({
            "entities": [_entity("order"), _entity("customer")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
                "foreign_key": "customer_id",
            }],
        })
        assert result.needs_clarification is False
        assert result.blocking_count == 0
        assert result.ambiguous_count == 0


class TestPriorityAndLimits:
    """优先级排序和数量限制"""

    def test_blocking_before_ambiguous(self):
        """blocking 问题排在 ambiguous 前面"""
        result = detect_missing_info({
            "entities": [_entity("order", with_fields=False), _entity("customer")],
            "cross_relations": [{
                "source_entity": "order",
                "target_entity": "customer",
                "relation_type": "belongs_to",
            }],
        })
        # First should be blocking (no fields), then ambiguous (missing FK)
        if len(result.questions) >= 2:
            blocking_idx = next(
                (i for i, q in enumerate(result.questions) if q.category == QuestionCategory.BLOCKING),
                999,
            )
            ambiguous_idx = next(
                (i for i, q in enumerate(result.questions) if q.category == QuestionCategory.AMBIGUOUS),
                999,
            )
            if blocking_idx != 999 and ambiguous_idx != 999:
                assert blocking_idx < ambiguous_idx

    def test_max_questions_truncation(self):
        """超过 MAX_QUESTIONS 时截断"""
        entities = [_entity(f"e{i}", with_fields=False) for i in range(10)]
        result = detect_missing_info({"entities": entities})
        assert len(result.questions) <= MAX_QUESTIONS

    def test_dedup(self):
        """同一实体的重复问题去重"""
        result = detect_missing_info({
            "entities": [_entity("order")],
            "cross_relations": [
                {"source_entity": "order", "target_entity": "customer", "relation_type": "belongs_to"},
                {"source_entity": "order", "target_entity": "customer", "relation_type": "belongs_to"},
            ],
        })
        ids = [q.id for q in result.questions]
        assert len(ids) == len(set(ids))


class TestSerialization:
    """序列化"""

    def test_to_tool_output(self):
        result = detect_missing_info({"entities": []})
        output = result.to_tool_output()
        assert output["needs_clarification"] is True
        assert "questions" in output
        assert "blocking_count" in output

"""
AI 自动修复 Loop — 单元测试

覆盖：
- validate_project: 有效/无效项目
- build_fix_instructions: 指令生成
- suggest_human_steps: 人工步骤建议
- run_fix_loop: 无 fix_fn / 可修复 / 不可修复 / 重试上限
- apply_fix_patch: patch 应用
- FixContext / AutoFixResult 序列化
"""

import pytest

from app.codegen.auto_fix import (
    MAX_FIX_RETRIES,
    AutoFixResult,
    FixAttempt,
    FixContext,
    apply_fix_patch,
    build_fix_context,
    build_fix_instructions,
    run_fix_loop,
    suggest_human_steps,
    validate_project,
)


# ============================================================
# 辅助
# ============================================================


def _entity(module: str, table: str, display: str, display_en: str = "") -> dict:
    return {
        "module": module,
        "table_name": table,
        "display_name": display,
        "display_name_en": display_en or module.title(),
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label": "Title",
                "label_zh": "标题",
                "label_en": "Title",
            },
        ],
    }


def _valid_project() -> dict:
    return {
        "project_name": "test",
        "entities": [_entity("order", "orders", "订单")],
    }


def _project_with_cycle() -> dict:
    return {
        "project_name": "cycle_test",
        "entities": [
            _entity("a", "a_table", "A"),
            _entity("b", "b_table", "B"),
        ],
        "cross_relations": [
            {"source_entity": "a", "target_entity": "b", "relation_type": "belongs_to"},
            {"source_entity": "b", "target_entity": "a", "relation_type": "belongs_to"},
        ],
    }


def _project_with_missing_ref() -> dict:
    return {
        "project_name": "missing_ref",
        "entities": [
            _entity("order", "orders", "订单"),
        ],
        "cross_relations": [
            {"source_entity": "order", "target_entity": "customer", "relation_type": "belongs_to"},
        ],
    }


# ============================================================
# validate_project
# ============================================================


class TestValidateProject:
    """项目校验"""

    def test_valid_project(self):
        valid, issues, warnings = validate_project(_valid_project())
        assert valid is True
        assert len(issues) == 0

    def test_invalid_project_extra_field(self):
        data = _valid_project()
        data["fake_field"] = "bad"
        valid, issues, _ = validate_project(data)
        assert valid is False
        assert len(issues) > 0

    def test_cycle_detected(self):
        valid, issues, _ = validate_project(_project_with_cycle())
        assert valid is False
        cycle_issues = [i for i in issues if "cycle" in i.get("code", "").lower()]
        assert len(cycle_issues) > 0

    def test_missing_entity_ref(self):
        valid, issues, _ = validate_project(_project_with_missing_ref())
        assert valid is False
        assert len(issues) > 0


# ============================================================
# build_fix_instructions
# ============================================================


class TestBuildFixInstructions:
    """修复指令生成"""

    def test_empty_issues(self):
        result = build_fix_instructions([])
        assert result == ""

    def test_with_issues(self):
        issues = [
            {"code": "cycle_detected", "message": "Cycle: a → b → a", "related_nodes": ["a", "b"]},
            {"code": "missing_entity", "message": "Entity 'customer' not found"},
        ]
        result = build_fix_instructions(issues)
        assert "cycle_detected" in result
        assert "missing_entity" in result
        assert "a, b" in result


# ============================================================
# suggest_human_steps
# ============================================================


class TestSuggestHumanSteps:
    """人工步骤建议"""

    def test_cycle_suggestion(self):
        issues = [{"code": "cycle_detected", "message": "Cycle", "related_nodes": ["a", "b"]}]
        steps = suggest_human_steps(issues)
        assert len(steps) > 0
        assert any("circular" in s.lower() or "cycle" in s.lower() for s in steps)

    def test_missing_suggestion(self):
        issues = [{"code": "missing_entity", "message": "Entity X not found"}]
        steps = suggest_human_steps(issues)
        assert len(steps) > 0
        assert any("missing" in s.lower() or "add" in s.lower() for s in steps)

    def test_empty_issues(self):
        steps = suggest_human_steps([])
        assert len(steps) > 0  # 至少有一个通用建议


# ============================================================
# run_fix_loop
# ============================================================


class TestRunFixLoop:
    """自动修复循环"""

    def test_already_valid(self):
        """已经有效的项目不需要修复"""
        result = run_fix_loop(_valid_project())
        assert result.success is True
        assert result.total_attempts == 0

    def test_no_fix_fn(self):
        """没有 fix_fn 时仅返回校验结果"""
        result = run_fix_loop(_project_with_cycle(), fix_fn=None)
        assert result.success is False
        assert len(result.remaining_issues) > 0
        assert len(result.human_steps) > 0

    def test_fix_fn_succeeds(self):
        """fix_fn 成功修复"""
        # 模拟：missing ref -> fix_fn 添加 customer entity
        project = _project_with_missing_ref()

        def fix_fn(ctx: FixContext) -> dict:
            return {
                "entities": [_entity("customer", "customers", "客户")],
            }

        result = run_fix_loop(project, fix_fn=fix_fn)
        assert result.success is True
        assert result.total_attempts >= 1
        assert len(result.attempts) >= 1

    def test_fix_fn_fails_exhausts_retries(self):
        """fix_fn 无法修复，耗尽重试"""
        # 循环依赖无法通过添加实体修复
        project = _project_with_cycle()

        def bad_fix_fn(ctx: FixContext) -> dict:
            # 返回无用 patch
            return {}

        result = run_fix_loop(project, fix_fn=bad_fix_fn, max_retries=2)
        assert result.success is False
        assert result.total_attempts <= 2
        assert len(result.remaining_issues) > 0
        assert len(result.human_steps) > 0

    def test_fix_fn_raises_exception(self):
        """fix_fn 抛异常时安全退出"""
        project = _project_with_cycle()

        def raise_fn(ctx: FixContext) -> dict:
            raise RuntimeError("AI failed")

        result = run_fix_loop(project, fix_fn=raise_fn, max_retries=2)
        assert result.success is False
        assert len(result.attempts) >= 1

    def test_max_retries_respected(self):
        """重试次数上限"""
        project = _project_with_cycle()
        call_count = 0

        def counting_fn(ctx: FixContext) -> dict:
            nonlocal call_count
            call_count += 1
            return {}

        run_fix_loop(project, fix_fn=counting_fn, max_retries=3)
        assert call_count <= 3


# ============================================================
# apply_fix_patch
# ============================================================


class TestApplyFixPatch:
    """Patch 应用"""

    def test_add_entity(self):
        project = _valid_project()
        patch = {"entities": [_entity("product", "products", "产品")]}

        result = apply_fix_patch(project, patch)
        modules = [e["module"] for e in result["entities"]]
        assert "product" in modules
        assert "order" in modules

    def test_empty_patch(self):
        project = _valid_project()
        result = apply_fix_patch(project, {})
        assert result["project_name"] == "test"


# ============================================================
# 序列化
# ============================================================


class TestSerialization:
    """结果序列化"""

    def test_auto_fix_result_to_tool_output(self):
        result = AutoFixResult(
            success=False,
            remaining_issues=[{"code": "test", "message": "msg"}],
            human_steps=["Fix manually"],
        )
        output = result.to_tool_output()
        assert output["success"] is False
        assert len(output["remaining_issues"]) == 1
        assert len(output["human_steps"]) == 1

    def test_fix_context_serialization(self):
        ctx = build_fix_context(
            project_dict=_valid_project(),
            issues=[{"code": "test", "message": "msg"}],
            attempt=2,
        )
        assert ctx.attempt == 2
        assert ctx.max_attempts == MAX_FIX_RETRIES
        assert "test" in ctx.fix_instructions

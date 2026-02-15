"""
CRUD Generator — Skill 定义 & Resolver 测试

覆盖:
- skill_definitions: 8 个 ToolDefinition, build_skill_input_schema
- resolver: _resolve_crud_generator, dev_only 检查
- ai_prompts: 8 套 Prompt 常量导入
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from app.ai.skills.resolver import SkillResolver, SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.codegen.ai_prompts import (
    CRUD_AGENT_SYSTEM_PROMPT,
    CRUD_CONFIG_GEN_PROMPT,
    CODE_PREVIEW_PROMPT,
    FIELD_SUGGEST_PROMPT,
    I18N_TRANSLATE_PROMPT,
    INTENT_ANALYZE_PROMPT,
    SLOT_CODE_GEN_PROMPT,
    STYLE_RECOMMEND_PROMPT,
)
from app.codegen.skill_definitions import (
    CRUD_TOOL_DEFINITIONS,
    build_skill_input_schema,
)
from app.enums.agent import ToolTypeEnum


# ============================================================
# Mock Skill 对象
# ============================================================


@dataclass
class MockSkill:
    """模拟 Skill ORM 模型"""

    id: int = 1
    name: str = "crud_generator"
    description: str = "CRUD 代码生成器"
    type: str = "builtin"
    scope: str = "admin"
    is_system: bool = True
    is_active: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, Any] | None = None
    toolkit_content: str | None = None
    toolkit_meta: dict | None = None
    timeout: int = 120


# ============================================================
# Skill Definitions 测试
# ============================================================


class TestSkillDefinitions:
    def test_tool_count(self):
        """8 个 Tool 定义"""
        assert len(CRUD_TOOL_DEFINITIONS) == 8

    def test_tool_names(self):
        """所有 Tool 名称正确"""
        names = {t.name for t in CRUD_TOOL_DEFINITIONS}
        expected = {
            "crud_generate_config",
            "crud_preview_code",
            "crud_generate_files",
            "crud_translate_i18n",
            "crud_suggest_fields",
            "crud_generate_slot",
            "crud_recommend_style",
            "crud_analyze_intent",
        }
        assert names == expected

    def test_tool_type(self):
        """所有 Tool 的 tool_type 为 crud_generator"""
        for tool in CRUD_TOOL_DEFINITIONS:
            assert tool.tool_type == ToolTypeEnum.CRUD_GENERATOR.value

    def test_generate_files_has_confirmed(self):
        """crud_generate_files 包含 confirmed 参数"""
        tool = next(t for t in CRUD_TOOL_DEFINITIONS if t.name == "crud_generate_files")
        param_names = {p.name for p in tool.parameters}
        assert "confirmed" in param_names
        assert "config" in param_names

    def test_generate_files_conflict_action_enum(self):
        """crud_generate_files 的 conflict_action 有 enum"""
        tool = next(t for t in CRUD_TOOL_DEFINITIONS if t.name == "crud_generate_files")
        param = next(p for p in tool.parameters if p.name == "conflict_action")
        assert param.enum == ["skip", "overwrite", "merge"]

    def test_all_tools_have_required_params(self):
        """所有 Tool 至少有一个必填参数"""
        for tool in CRUD_TOOL_DEFINITIONS:
            required = [p for p in tool.parameters if p.required]
            assert len(required) >= 1, f"{tool.name} has no required params"

    def test_openai_schema(self):
        """OpenAI schema 格式正确"""
        for tool in CRUD_TOOL_DEFINITIONS:
            schema = tool.to_openai_schema()
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]

    def test_build_skill_input_schema(self):
        """build_skill_input_schema 格式正确"""
        schema = build_skill_input_schema()
        assert schema["multi_tool"] is True
        assert len(schema["tools"]) == 8

        for tool_name, tool_spec in schema["tools"].items():
            assert "description" in tool_spec
            assert "parameters" in tool_spec
            assert tool_spec["parameters"]["type"] == "object"

    def test_input_schema_has_required(self):
        """input_schema 中每个 Tool 有 required 字段"""
        schema = build_skill_input_schema()
        for tool_name, tool_spec in schema["tools"].items():
            params = tool_spec["parameters"]
            assert "required" in params, f"{tool_name} missing required"
            assert len(params["required"]) >= 1


# ============================================================
# Resolver 测试
# ============================================================


class TestResolverCrudGenerator:
    def _make_skill(self, **kwargs) -> MockSkill:
        """创建带 input_schema 的 MockSkill"""
        skill = MockSkill(
            config={
                "builtin_type": "crud_generator",
                "dev_only": True,
            },
            input_schema=build_skill_input_schema(),
            **kwargs,
        )
        return skill

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_resolve_8_tools(self):
        """development 环境下解析出 8 个 Tool"""
        skill = self._make_skill()
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        assert len(result.tools) == 8

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_tool_types_all_crud_generator(self):
        """所有解析出的 Tool 类型为 crud_generator"""
        skill = self._make_skill()
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        for tool in result.tools:
            assert tool.tool_type == ToolTypeEnum.CRUD_GENERATOR.value

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_tool_source_skill_info(self):
        """解析出的 Tool 保留 source_skill 信息"""
        skill = self._make_skill(id=42, name="crud_generator")
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        for tool in result.tools:
            assert tool.source_skill_id == 42
            assert tool.source_skill_name == "crud_generator"
            assert tool.source_skill_type == "builtin"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "production"})
    async def test_dev_only_skipped_in_production(self):
        """production 环境下 dev_only=True 时不解析"""
        skill = self._make_skill()
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        assert len(result.tools) == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "production"})
    async def test_dev_only_false_resolves_in_production(self):
        """dev_only=False 时 production 环境也解析"""
        skill = self._make_skill()
        skill.config["dev_only"] = False
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        assert len(result.tools) == 8

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_inactive_skill_skipped(self):
        """is_active=False 的 Skill 不解析"""
        skill = self._make_skill(is_active=False)
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        assert len(result.tools) == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_empty_input_schema(self):
        """input_schema 为空时不解析"""
        skill = self._make_skill()
        skill.input_schema = {}
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        assert len(result.tools) == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"APP_ENV": "development"})
    async def test_parameters_preserved(self):
        """参数正确传递到 ToolDefinition"""
        skill = self._make_skill()
        resolver = SkillResolver()
        result = await resolver.resolve([skill])

        config_tool = next(
            t for t in result.tools if t.name == "crud_generate_config"
        )
        param_names = {p.name for p in config_tool.parameters}
        assert "description" in param_names

        required_params = {p.name for p in config_tool.parameters if p.required}
        assert "description" in required_params


# ============================================================
# AI Prompts 测试
# ============================================================


class TestCrudGeneratorExecutor:
    """CrudGeneratorExecutor 单元测试"""

    _MINIMAL_CONFIG = {
        "module": "test-item",
        "table_name": "test_items",
        "display_name": "测试项",
        "display_name_en": "Test Item",
        "scope": "tenant",
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label_zh": "标题",
                "label_en": "Title",
                "required": True,
                "max_length": 200,
            }
        ],
    }

    def _make_definition(self, name: str) -> ToolDefinition:
        tool = next(
            (t for t in CRUD_TOOL_DEFINITIONS if t.name == name), None
        )
        assert tool is not None, f"Tool {name} not found"
        return tool

    @pytest.mark.asyncio
    async def test_validate_known_tool(self):
        """已知 Tool 校验通过"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        valid = await executor.validate(defn, {"config": {}})
        assert valid is True

    @pytest.mark.asyncio
    async def test_validate_unknown_tool(self):
        """未知 Tool 校验失败"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = ToolDefinition(name="unknown_tool", tool_type="crud_generator")
        valid = await executor.validate(defn, {})
        assert valid is False

    @pytest.mark.asyncio
    async def test_validate_missing_required(self):
        """缺少必填参数校验失败"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_config")
        valid = await executor.validate(defn, {})
        assert valid is False

    @pytest.mark.asyncio
    async def test_preview_code(self):
        """crud_preview_code 直接执行"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="tc_1",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert "files" in data
        assert len(data["files"]) > 0

    @pytest.mark.asyncio
    async def test_preview_code_with_content(self):
        """crud_preview_code include_content=True"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="tc_2",
            arguments={
                "config": self._MINIMAL_CONFIG,
                "include_content": True,
            },
        )

        assert result.success is True
        data = json.loads(result.output)
        has_content = any(f.get("content") for f in data["files"])
        assert has_content

    @pytest.mark.asyncio
    async def test_generate_files_unconfirmed(self):
        """crud_generate_files confirmed=False 返回预览"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="tc_3",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert data["requires_confirmation"] is True
        assert "files" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_ai_tool_no_gateway(self):
        """AI 工具无 gateway 时返回提示"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor(gateway=None)
        defn = self._make_definition("crud_generate_config")
        result = await executor.execute(
            defn,
            tool_call_id="tc_4",
            arguments={"description": "test module"},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert "error" in data
        assert "Gateway" in data["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """未知 Tool 执行失败"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = ToolDefinition(name="crud_unknown", tool_type="crud_generator")
        result = await executor.execute(
            defn,
            tool_call_id="tc_5",
            arguments={},
        )

        assert result.success is False
        assert "Unknown" in result.error

    @pytest.mark.asyncio
    async def test_duration_recorded(self):
        """执行结果包含 duration_ms"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="tc_6",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_config_as_string(self):
        """config 参数为 JSON 字符串时也能解析"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="tc_7",
            arguments={"config": json.dumps(self._MINIMAL_CONFIG)},
        )

        assert result.success is True


# ============================================================
# AI Prompts 测试
# ============================================================


class TestConfirmationMechanism:
    """确认机制对齐测试 — crud_generate_files 复用平台 requires_confirmation 流程"""

    _MINIMAL_CONFIG = {
        "module": "test-item",
        "table_name": "test_items",
        "display_name": "测试项",
        "display_name_en": "Test Item",
        "scope": "tenant",
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label_zh": "标题",
                "label_en": "Title",
                "required": True,
                "max_length": 200,
            }
        ],
    }

    def _make_definition(self, name: str) -> ToolDefinition:
        tool = next(
            (t for t in CRUD_TOOL_DEFINITIONS if t.name == name), None
        )
        assert tool is not None
        return tool

    @pytest.mark.asyncio
    async def test_unconfirmed_returns_requires_confirmation(self):
        """未确认调用返回 requires_confirmation=True"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="tc_confirm_1",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert data["requires_confirmation"] is True
        assert "files" in data
        assert "message" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) > 0

    @pytest.mark.asyncio
    async def test_confirmed_false_explicit(self):
        """confirmed=False 同样返回预览"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="tc_confirm_2",
            arguments={"config": self._MINIMAL_CONFIG, "confirmed": False},
        )

        data = json.loads(result.output)
        assert data["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_confirmation_output_parseable_by_find_pending(self):
        """输出格式与 _find_pending_confirmation 兼容"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="tc_confirm_3",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        # _find_pending_confirmation 需要: json.loads → dict → .get("requires_confirmation")
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)
        assert parsed.get("requires_confirmation") is True

    @pytest.mark.asyncio
    async def test_confirmation_injects_confirmed_true(self):
        """模拟 _find_pending_confirmation 注入 confirmed=True 后执行写入"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )
        import tempfile
        import os

        # 使用临时目录避免污染项目
        with tempfile.TemporaryDirectory() as tmpdir:
            # Monkey-patch _PROJECT_ROOT
            import app.ai.tools.executors.crud_generator_executor as mod
            original_root = mod._PROJECT_ROOT
            mod._PROJECT_ROOT = tmpdir

            try:
                executor = CrudGeneratorExecutor()
                defn = self._make_definition("crud_generate_files")

                # 模拟注入 confirmed=True（与 _find_pending_confirmation 行为一致）
                args = {"config": self._MINIMAL_CONFIG, "confirmed": True}
                result = await executor.execute(
                    defn,
                    tool_call_id="tc_confirm_4",
                    arguments=args,
                )

                assert result.success is True
                data = json.loads(result.output)
                assert data["success"] is True
                assert data["total_written"] > 0
                assert "requires_confirmation" not in data
            finally:
                mod._PROJECT_ROOT = original_root

    @pytest.mark.asyncio
    async def test_preview_has_file_count_fields(self):
        """预览输出包含 total_new/total_conflict（用于 SSE confirmation_request）"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="tc_confirm_5",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        data = json.loads(result.output)
        assert "total_new" in data
        assert "total_conflict" in data
        assert isinstance(data["total_new"], int)


# ============================================================
# AI Prompts 测试
# ============================================================


class TestToolOutputContracts:
    """Tool 输出契约验证 — 确保 executor 实际输出符合契约定义"""

    _MINIMAL_CONFIG = {
        "module": "test-item",
        "table_name": "test_items",
        "display_name": "测试项",
        "display_name_en": "Test Item",
        "scope": "tenant",
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label_zh": "标题",
                "label_en": "Title",
                "required": True,
                "max_length": 200,
            }
        ],
    }

    def _make_definition(self, name: str) -> ToolDefinition:
        tool = next(
            (t for t in CRUD_TOOL_DEFINITIONS if t.name == name), None
        )
        assert tool is not None
        return tool

    @pytest.mark.asyncio
    async def test_preview_code_matches_contract(self):
        """crud_preview_code 输出符合 PreviewCodeOutput 契约"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn, tool_call_id="tc_c1",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        data = json.loads(result.output)
        # PreviewCodeOutput 必须有 files, total_new, total_conflict
        assert "files" in data
        assert "total_new" in data
        assert "total_conflict" in data
        assert isinstance(data["files"], list)
        # PreviewFileItem: path, size, exists, is_i18n, operation
        for f in data["files"]:
            assert "path" in f
            assert "size" in f
            assert "exists" in f
            assert "is_i18n" in f
            assert "operation" in f
            assert f["operation"] in ("create", "merge", "conflict")

    @pytest.mark.asyncio
    async def test_generate_files_preview_matches_contract(self):
        """crud_generate_files 未确认输出符合 GenerateFilesPreview 契约"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn, tool_call_id="tc_c2",
            arguments={"config": self._MINIMAL_CONFIG},
        )

        data = json.loads(result.output)
        # GenerateFilesPreview 字段
        assert data["requires_confirmation"] is True
        assert isinstance(data["files"], list)
        assert isinstance(data["total_new"], int)
        assert isinstance(data["total_conflict"], int)
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    @pytest.mark.asyncio
    async def test_generate_files_result_matches_contract(self):
        """crud_generate_files 确认后输出符合 GenerateFilesResult 契约"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )
        import tempfile
        import app.ai.tools.executors.crud_generator_executor as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = mod._PROJECT_ROOT
            mod._PROJECT_ROOT = tmpdir
            try:
                executor = CrudGeneratorExecutor()
                defn = self._make_definition("crud_generate_files")
                result = await executor.execute(
                    defn, tool_call_id="tc_c3",
                    arguments={"config": self._MINIMAL_CONFIG, "confirmed": True},
                )

                data = json.loads(result.output)
                # GenerateFilesResult 字段
                assert data["success"] is True
                assert isinstance(data["written"], list)
                assert isinstance(data["skipped"], list)
                assert isinstance(data["merged"], list)
                assert isinstance(data["errors"], list)
                assert isinstance(data["total_written"], int)
                assert isinstance(data["total_skipped"], int)
                assert isinstance(data["total_merged"], int)
                assert isinstance(data["total_errors"], int)
            finally:
                mod._PROJECT_ROOT = original_root

    @pytest.mark.asyncio
    async def test_ai_error_matches_contract(self):
        """AI 工具无 gateway 时输出符合 AIErrorOutput 契约"""
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )

        executor = CrudGeneratorExecutor(gateway=None)
        defn = self._make_definition("crud_generate_config")
        result = await executor.execute(
            defn, tool_call_id="tc_c4",
            arguments={"description": "test"},
        )

        data = json.loads(result.output)
        # AIErrorOutput 字段
        assert "error" in data
        assert isinstance(data["error"], str)
        assert "hint" in data
        assert isinstance(data["hint"], str)

    def test_tool_output_map_covers_all_tools(self):
        """TOOL_OUTPUT_MAP 覆盖全部 11 个 Tool"""
        from app.codegen.tool_output_contracts import TOOL_OUTPUT_MAP

        expected = {
            "crud_generate_config",
            "crud_preview_code",
            "crud_generate_files",
            "crud_translate_i18n",
            "crud_suggest_fields",
            "crud_generate_slot",
            "crud_recommend_style",
            "crud_analyze_intent",
        }
        assert set(TOOL_OUTPUT_MAP.keys()) == expected

    def test_all_contracts_importable(self):
        """所有契约类型可导入"""
        from app.codegen.tool_output_contracts import (
            GenerateConfigOutput,
            PreviewCodeOutput,
            PreviewFileItem,
            GenerateFilesPreview,
            GenerateFilesResult,
            TranslateI18nOutput,
            SuggestedField,
            SuggestedEnum,
            SuggestFieldsOutput,
            GenerateSlotOutput,
            RecommendStyleOutput,
            AnalyzedEntity,
            AnalyzeIntentOutput,
            AIErrorOutput,
        )
        assert GenerateConfigOutput is not None
        assert PreviewCodeOutput is not None
        assert PreviewFileItem is not None
        assert GenerateFilesPreview is not None
        assert GenerateFilesResult is not None
        assert TranslateI18nOutput is not None
        assert SuggestedField is not None
        assert SuggestedEnum is not None
        assert SuggestFieldsOutput is not None
        assert GenerateSlotOutput is not None
        assert RecommendStyleOutput is not None
        assert AnalyzedEntity is not None
        assert AnalyzeIntentOutput is not None
        assert AIErrorOutput is not None


# ============================================================
# AI Prompts 测试
# ============================================================


class TestAIPrompts:
    def test_all_prompts_non_empty(self):
        """8 套 Prompt 均非空"""
        prompts = [
            CRUD_CONFIG_GEN_PROMPT,
            I18N_TRANSLATE_PROMPT,
            SLOT_CODE_GEN_PROMPT,
            STYLE_RECOMMEND_PROMPT,
            FIELD_SUGGEST_PROMPT,
            INTENT_ANALYZE_PROMPT,
            CODE_PREVIEW_PROMPT,
            CRUD_AGENT_SYSTEM_PROMPT,
        ]
        for prompt in prompts:
            assert len(prompt) > 100

    def test_config_gen_has_tech_stack(self):
        """配置生成 Prompt 包含技术栈上下文"""
        assert "FastAPI" in CRUD_CONFIG_GEN_PROMPT
        assert "Vue 3" in CRUD_CONFIG_GEN_PROMPT
        assert "SQLAlchemy" in CRUD_CONFIG_GEN_PROMPT

    def test_config_gen_has_naming(self):
        """配置生成 Prompt 包含命名规范"""
        assert "snake_case" in CRUD_CONFIG_GEN_PROMPT
        assert "PascalCase" in CRUD_CONFIG_GEN_PROMPT

    def test_agent_prompt_has_tools(self):
        """Agent 系统提示词包含 8 个工具说明"""
        assert "crud_generate_config" in CRUD_AGENT_SYSTEM_PROMPT
        assert "crud_preview_code" in CRUD_AGENT_SYSTEM_PROMPT
        assert "crud_generate_files" in CRUD_AGENT_SYSTEM_PROMPT
        assert "crud_translate_i18n" in CRUD_AGENT_SYSTEM_PROMPT

    def test_agent_prompt_has_workflow(self):
        """Agent 系统提示词包含工作流程"""
        assert "工作流程" in CRUD_AGENT_SYSTEM_PROMPT
        assert "确认" in CRUD_AGENT_SYSTEM_PROMPT

    def test_i18n_prompt_has_rules(self):
        """翻译 Prompt 包含规则"""
        assert "JSON" in I18N_TRANSLATE_PROMPT
        assert "翻译" in I18N_TRANSLATE_PROMPT

    def test_slot_prompt_has_ant_design(self):
        """Slot 生成 Prompt 提到 Ant Design Vue"""
        assert "Ant Design Vue" in SLOT_CODE_GEN_PROMPT

    def test_style_prompt_has_layouts(self):
        """样式推荐 Prompt 列出布局变体"""
        assert "standard" in STYLE_RECOMMEND_PROMPT
        assert "card_list" in STYLE_RECOMMEND_PROMPT
        assert "kanban" in STYLE_RECOMMEND_PROMPT




# ============================================================
# 知识图谱测试
# ============================================================


class TestKnowledgeGraph:
    """knowledge_graph 模块测试"""

    def test_scan_finds_models(self):
        """扫描到项目中的 Model"""
        from app.codegen.knowledge_graph import get_project_graph, invalidate_cache

        invalidate_cache()
        models = get_project_graph()
        assert len(models) > 20
        table_names = {m.table_name for m in models}
        # 验证核心表存在
        assert "agents" in table_names
        assert "skills" in table_names
        assert "tenants" in table_names
        assert "admins" in table_names

    def test_model_meta_structure(self):
        """ModelMeta 包含必要字段"""
        from app.codegen.knowledge_graph import get_project_graph

        models = get_project_graph()
        agent_meta = next((m for m in models if m.table_name == "agents"), None)
        assert agent_meta is not None
        assert agent_meta.class_name == "Agent"
        assert agent_meta.base_class == "TenantModel"
        assert len(agent_meta.columns) > 5
        assert agent_meta.filterable is not None
        assert "name" in agent_meta.filterable

    def test_model_meta_to_dict(self):
        """to_dict() 可序列化"""
        from app.codegen.knowledge_graph import get_project_graph

        models = get_project_graph()
        for m in models:
            d = m.to_dict()
            assert isinstance(d, dict)
            assert "class_name" in d
            assert "table_name" in d
            assert "columns" in d
            json.dumps(d)  # 验证可 JSON 序列化

    def test_graph_summary_not_empty(self):
        """get_graph_summary() 返回非空摘要"""
        from app.codegen.knowledge_graph import get_graph_summary

        summary = get_graph_summary()
        assert "项目已有模型" in summary
        assert "agents" in summary
        assert "tables" in summary
        assert len(summary) > 200

    def test_cache_works(self):
        """缓存可正常工作"""
        from app.codegen.knowledge_graph import (
            get_project_graph,
            invalidate_cache,
        )

        invalidate_cache()
        g1 = get_project_graph()
        g2 = get_project_graph()
        assert g1 is g2  # 同一对象引用

        invalidate_cache()
        g3 = get_project_graph()
        assert g1 is not g3  # 清缓存后重新扫描

    def test_tenant_model_detected(self):
        """TenantModel 子类正确识别"""
        from app.codegen.knowledge_graph import get_project_graph

        models = get_project_graph()
        skill_meta = next((m for m in models if m.table_name == "skills"), None)
        assert skill_meta is not None
        assert skill_meta.base_class == "TenantModel"

        admin_meta = next((m for m in models if m.table_name == "admins"), None)
        assert admin_meta is not None
        assert admin_meta.base_class == "BaseModel"

    def test_foreign_keys_detected(self):
        """外键关系可检测"""
        from app.codegen.knowledge_graph import get_project_graph

        models = get_project_graph()
        skill_meta = next((m for m in models if m.table_name == "skills"), None)
        assert skill_meta is not None
        fk_cols = [c for c in skill_meta.columns if c.foreign_key]
        assert len(fk_cols) > 0
        fk_targets = [c.foreign_key for c in fk_cols]
        assert any("skill_packages" in t for t in fk_targets)


# ============================================================
# 端到端测试：Agent 对话驱动 CRUD 生成
# ============================================================


class _MockModelInfo:
    """模拟 AI 模型信息"""
    provider_id = 1
    model_id = "deepseek-chat"


class _MockProvider:
    """模拟 AI Provider"""
    code = "deepseek"


class _MockMessage:
    """模拟 LLM 响应消息"""
    def __init__(self, content: str) -> None:
        self.content = content


class _MockResponse:
    """模拟 AIGateway.chat() 响应"""
    def __init__(self, content: str) -> None:
        self.message = _MockMessage(content)


class _MockModelRepo:
    """模拟模型仓库"""
    async def get_default_chat_model(self):
        return _MockModelInfo()


class _MockProviderRepo:
    """模拟 Provider 仓库"""
    async def get_by_id(self, provider_id: int):
        return _MockProvider()


class _MockGateway:
    """模拟 AIGateway，返回预设的 AI 响应"""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}
        self._call_count = 0
        self._last_system_prompt = ""
        self._last_user_message = ""
        self.model_repo = _MockModelRepo()
        self.provider_repo = _MockProviderRepo()

    async def chat(self, **kwargs) -> _MockResponse:
        self._call_count += 1
        messages = kwargs.get("messages", [])
        if messages:
            self._last_system_prompt = messages[0].content
            self._last_user_message = messages[-1].content

        # 根据 user message 关键字匹配响应
        user_msg = self._last_user_message.lower()
        for key, response in self._responses.items():
            if key.lower() in user_msg:
                return _MockResponse(response)

        # 默认返回空 JSON
        return _MockResponse("{}")


class TestE2ECrudGeneration:
    """端到端测试：通过 Executor 模拟完整 CRUD 生成流程"""

    # 真实的 CrudConfig JSON（AI 会生成类似的输出）
    _AI_CONFIG_RESPONSE = json.dumps({
        "module": "notice",
        "table_name": "notices",
        "display_name": "系统通知",
        "display_name_en": "Notice",
        "scope": "tenant",
        "parent_menu": "system",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label_zh": "标题",
                "label_en": "Title",
                "required": True,
                "max_length": 200,
                "searchable": True,
            },
            {
                "name": "content",
                "type": "text",
                "label_zh": "内容",
                "label_en": "Content",
                "required": True,
            },
            {
                "name": "notice_type",
                "type": "string",
                "label_zh": "类型",
                "label_en": "Type",
                "required": True,
                "max_length": 20,
            },
            {
                "name": "is_published",
                "type": "boolean",
                "label_zh": "已发布",
                "label_en": "Published",
                "default_value": False,
            },
        ],
    }, ensure_ascii=False)

    _AI_TRANSLATE_RESPONSE = json.dumps({
        "notice": {
            "title": "Title",
            "content": "Content",
            "notice_type": "Type",
            "is_published": "Published",
        }
    })

    _AI_SUGGEST_RESPONSE = json.dumps({
        "suggested_fields": [
            {"name": "priority", "type": "integer", "label_zh": "优先级", "label_en": "Priority"},
            {"name": "expired_at", "type": "datetime", "label_zh": "过期时间", "label_en": "Expired At"},
        ]
    })

    _AI_INTENT_RESPONSE = json.dumps({
        "entities": [
            {"name": "notice", "display_name": "系统通知"},
            {"name": "notice_category", "display_name": "通知分类"},
        ],
        "relations": [
            {"source": "notice", "target": "notice_category", "type": "belongs_to"},
        ],
        "is_batch": True,
    })

    def _make_executor(self, responses: dict[str, str] | None = None):
        from app.ai.tools.executors.crud_generator_executor import (
            CrudGeneratorExecutor,
        )
        gw = _MockGateway(responses or {})
        return CrudGeneratorExecutor(gateway=gw), gw

    def _make_definition(self, name: str) -> ToolDefinition:
        tool = next(
            (t for t in CRUD_TOOL_DEFINITIONS if t.name == name), None
        )
        assert tool is not None, f"Tool {name} not found"
        return tool

    # ----- Step 1: AI generates CrudConfig from natural language -----

    @pytest.mark.asyncio
    async def test_step1_generate_config_via_ai(self):
        """Step 1: crud_generate_config 通过 AI 生成可解析的 CrudConfig"""
        executor, gw = self._make_executor({
            "crudconfig": self._AI_CONFIG_RESPONSE,
        })
        defn = self._make_definition("crud_generate_config")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_1",
            arguments={"description": "请生成一个系统通知模块的 CrudConfig"},
        )

        assert result.success is True
        assert gw._call_count == 1
        # AI 响应是有效 JSON
        config_data = json.loads(result.output)
        assert config_data["module"] == "notice"
        assert config_data["table_name"] == "notices"
        assert len(config_data["fields"]) == 4

    @pytest.mark.asyncio
    async def test_step1_graph_injected(self):
        """Step 1: AI system_prompt 中注入了项目知识图谱"""
        executor, gw = self._make_executor({
            "crudconfig": self._AI_CONFIG_RESPONSE,
        })
        defn = self._make_definition("crud_generate_config")
        await executor.execute(
            defn,
            tool_call_id="e2e_graph",
            arguments={"description": "生成通知模块 CrudConfig"},
        )

        # 验证 system_prompt 包含知识图谱摘要
        assert "项目已有模型" in gw._last_system_prompt
        assert "agents" in gw._last_system_prompt

    # ----- Step 2: Preview generated code -----

    @pytest.mark.asyncio
    async def test_step2_preview_code(self):
        """Step 2: crud_preview_code 返回文件清单"""
        config = json.loads(self._AI_CONFIG_RESPONSE)

        executor, _ = self._make_executor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_2",
            arguments={"config": config},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert "files" in data
        assert len(data["files"]) > 5  # model, schema, repo, service, controller, etc.
        assert data["total_new"] + data["total_conflict"] == len(data["files"])

        # 验证关键文件路径
        file_paths = {f["path"] for f in data["files"]}
        assert any("notice" in p and "model" in p for p in file_paths)
        assert any("notice" in p and "schema" in p for p in file_paths)

    @pytest.mark.asyncio
    async def test_step2_preview_with_content(self):
        """Step 2: preview 包含文件内容"""
        config = json.loads(self._AI_CONFIG_RESPONSE)

        executor, _ = self._make_executor()
        defn = self._make_definition("crud_preview_code")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_2b",
            arguments={"config": config, "include_content": True},
        )

        data = json.loads(result.output)
        contents = [f.get("content", "") for f in data["files"] if f.get("content")]
        assert len(contents) > 0

        # Model 文件应包含 class 定义
        model_content = next(
            (f["content"] for f in data["files"] if "model" in f["path"] and f.get("content")),
            "",
        )
        assert "class Notice" in model_content or "class" in model_content.lower()

    # ----- Step 3: Generate files (confirmation flow) -----

    @pytest.mark.asyncio
    async def test_step3_generate_files_requires_confirmation(self):
        """Step 3a: crud_generate_files 未确认 → requires_confirmation"""
        config = json.loads(self._AI_CONFIG_RESPONSE)

        executor, _ = self._make_executor()
        defn = self._make_definition("crud_generate_files")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_3a",
            arguments={"config": config, "confirmed": False},
        )

        assert result.success is True
        data = json.loads(result.output)
        assert data["requires_confirmation"] is True
        assert "files" in data
        assert "message" in data
        assert "confirm" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_step3_generate_files_confirmed(self, tmp_path):
        """Step 3b: crud_generate_files confirmed=True → 写入文件"""
        config = json.loads(self._AI_CONFIG_RESPONSE)

        # 使用 tmp_path 避免污染项目目录
        executor, _ = self._make_executor()
        defn = self._make_definition("crud_generate_files")

        # 猴子补丁 _PROJECT_ROOT 到 tmp_path
        import app.ai.tools.executors.crud_generator_executor as executor_mod
        original_root = executor_mod._PROJECT_ROOT
        executor_mod._PROJECT_ROOT = str(tmp_path)

        try:
            result = await executor.execute(
                defn,
                tool_call_id="e2e_3b",
                arguments={
                    "config": config,
                    "confirmed": True,
                    "conflict_action": "skip",
                },
            )

            assert result.success is True
            data = json.loads(result.output)
            assert data["success"] is True
            assert data["total_written"] > 0
            assert data["total_errors"] == 0

            # 验证文件确实写入到 tmp_path
            written_files = data["written"]
            assert len(written_files) > 0
            for fpath in written_files:
                full = tmp_path / fpath.lstrip("/")
                assert full.exists(), f"Expected file not found: {full}"
        finally:
            executor_mod._PROJECT_ROOT = original_root

    # ----- Step 4: Translation works -----

    @pytest.mark.asyncio
    async def test_step4_translate_i18n(self):
        """Step 4: crud_translate_i18n 通过 AI 翻译"""
        executor, gw = self._make_executor({
            "翻译": self._AI_TRANSLATE_RESPONSE,
        })
        defn = self._make_definition("crud_translate_i18n")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_4",
            arguments={
                "source_json": {"notice": {"title": "标题", "content": "内容"}},
                "target_language": "en",
            },
        )

        assert result.success is True
        assert gw._call_count == 1
        data = json.loads(result.output)
        assert "notice" in data

    # ----- Step 5: Field suggestion works -----

    @pytest.mark.asyncio
    async def test_step5_suggest_fields(self):
        """Step 5: crud_suggest_fields 通过 AI 推荐"""
        executor, gw = self._make_executor({
            "推荐": self._AI_SUGGEST_RESPONSE,
        })
        defn = self._make_definition("crud_suggest_fields")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_5",
            arguments={
                "module_name": "notice",
                "existing_fields": ["title", "content"],
            },
        )

        assert result.success is True
        assert gw._call_count == 1
        data = json.loads(result.output)
        assert "suggested_fields" in data
        assert len(data["suggested_fields"]) == 2

    # ----- Step 6: Intent analysis -----

    @pytest.mark.asyncio
    async def test_step6_analyze_intent(self):
        """Step 6: crud_analyze_intent 返回多实体分析"""
        executor, gw = self._make_executor({
            "分析": self._AI_INTENT_RESPONSE,
        })
        defn = self._make_definition("crud_analyze_intent")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_6",
            arguments={
                "description": "需要系统通知和通知分类两个模块，请分析业务意图",
            },
        )

        assert result.success is True
        data = json.loads(result.output)
        assert data["is_batch"] is True
        assert len(data["entities"]) == 2

    # ----- Full flow: config → preview → generate -----

    @pytest.mark.asyncio
    async def test_full_flow_config_preview_generate(self, tmp_path):
        """完整流程：generate_config → preview_code → generate_files"""
        executor, gw = self._make_executor({
            "crudconfig": self._AI_CONFIG_RESPONSE,
        })

        import app.ai.tools.executors.crud_generator_executor as executor_mod
        original_root = executor_mod._PROJECT_ROOT
        executor_mod._PROJECT_ROOT = str(tmp_path)

        try:
            # Step 1: AI 生成配置
            defn1 = self._make_definition("crud_generate_config")
            r1 = await executor.execute(
                defn1,
                tool_call_id="flow_1",
                arguments={"description": "系统通知 CrudConfig"},
            )
            assert r1.success is True
            config = json.loads(r1.output)
            assert config["module"] == "notice"

            # Step 2: 预览代码
            defn2 = self._make_definition("crud_preview_code")
            r2 = await executor.execute(
                defn2,
                tool_call_id="flow_2",
                arguments={"config": config},
            )
            assert r2.success is True
            preview = json.loads(r2.output)
            assert len(preview["files"]) > 5

            # Step 3a: 请求确认
            defn3 = self._make_definition("crud_generate_files")
            r3a = await executor.execute(
                defn3,
                tool_call_id="flow_3a",
                arguments={"config": config, "confirmed": False},
            )
            assert r3a.success is True
            confirm_data = json.loads(r3a.output)
            assert confirm_data["requires_confirmation"] is True

            # Step 3b: 确认后写入
            r3b = await executor.execute(
                defn3,
                tool_call_id="flow_3b",
                arguments={"config": config, "confirmed": True},
            )
            assert r3b.success is True
            result = json.loads(r3b.output)
            assert result["success"] is True
            assert result["total_written"] > 0
            assert result["total_errors"] == 0

            # 验证 AI 只调用了 1 次 (只有 generate_config)
            assert gw._call_count == 1
        finally:
            executor_mod._PROJECT_ROOT = original_root

    # ----- Slot generation -----

    @pytest.mark.asyncio
    async def test_slot_generation(self):
        """crud_generate_slot 通过 AI 生成 Vue template"""
        slot_template = '<template>\n  <a-tag :color="statusColor">{{ text }}</a-tag>\n</template>'
        executor, gw = self._make_executor({
            "vue template": slot_template,
        })
        defn = self._make_definition("crud_generate_slot")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_slot",
            arguments={
                "field_name": "status",
                "description": "用彩色标签显示状态，请生成 Vue template 代码",
            },
        )

        assert result.success is True
        assert gw._call_count == 1

    # ----- Style recommendation -----

    @pytest.mark.asyncio
    async def test_style_recommendation(self):
        """crud_recommend_style 通过 AI 推荐布局"""
        style_resp = json.dumps({
            "layout": "standard",
            "search_form_cols": 3,
            "form_cols": 2,
        })
        executor, gw = self._make_executor({
            "推荐": style_resp,
        })
        defn = self._make_definition("crud_recommend_style")
        result = await executor.execute(
            defn,
            tool_call_id="e2e_style",
            arguments={
                "module_name": "notice",
                "field_count": 8,
                "has_status": True,
            },
        )

        assert result.success is True
        assert gw._call_count == 1

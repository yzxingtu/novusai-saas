"""
CRUD Generator 工具执行器

处理 13 个 CRUD Generator Tool 的执行逻辑：

直接执行（无需 AI）：
  - crud_preview_code:           Generator + Writer.preview()
  - crud_generate_files:         Generator + Writer.write()，支持 requires_confirmation
  - crud_batch_preview:          Generator.generate_batch() + Writer.preview_batch()
  - crud_batch_generate_files:   Generator.generate_batch() + Writer.write()，requires_confirmation
  - crud_batch_validate:         校验 BatchCrudProject（依赖/关联/字段）
  - crud_batch_merge_patch:      增量补丁合并（touchedPaths 保护）

AI 辅助（需要 AIGateway）：
  - crud_generate_config:        Prompt + gateway.chat() → CrudConfig JSON
  - crud_translate_i18n:         Prompt + gateway.chat() → 翻译后的 JSON
  - crud_suggest_fields:         Prompt + gateway.chat() → 推荐字段列表
  - crud_generate_slot:          Prompt + gateway.chat() → Vue template
  - crud_recommend_style:        Prompt + gateway.chat() → 布局/样式配置
  - crud_analyze_intent:         Prompt + gateway.chat() → 多实体分析
  - crud_batch_generate_config:  Prompt + gateway.chat() → BatchCrudProject JSON
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.crud_generator")

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)


def _json_output(data: Any) -> str:
    """统一 JSON 序列化"""
    return json.dumps(data, ensure_ascii=False, default=str)


def _parse_config(raw: dict | str) -> dict:
    """将 LLM 传入的 config 参数解析为 dict"""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


class CrudGeneratorExecutor(BaseToolExecutor):
    """
    CRUD Generator 专用执行器

    分发 13 个 Tool 的调用到对应的处理方法。
    直接执行类 Tool 使用 Phase 1 的 Generator/Writer；
    AI 辅助类 Tool 通过 AIGateway 调用 LLM。
    """

    _DISPATCH: dict[str, str] = {
        "crud_generate_config": "_generate_config",
        "crud_preview_code": "_preview_code",
        "crud_generate_files": "_generate_files",
        "crud_translate_i18n": "_translate_i18n",
        "crud_suggest_fields": "_suggest_fields",
        "crud_generate_slot": "_generate_slot",
        "crud_recommend_style": "_recommend_style",
        "crud_analyze_intent": "_analyze_intent",
        "crud_batch_generate_config": "_batch_generate_config",
        "crud_batch_preview": "_batch_preview",
        "crud_batch_generate_files": "_batch_generate_files",
        "crud_batch_validate": "_batch_validate",
        "crud_batch_merge_patch": "_batch_merge_patch",
    }

    def __init__(
        self,
        gateway: AIGateway | None = None,
    ) -> None:
        self._gateway = gateway

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        tool_name = definition.name

        method_name = self._DISPATCH.get(tool_name)
        if not method_name:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=f"Unknown CRUD Generator tool: {tool_name}",
            )

        handler = getattr(self, method_name)

        try:
            output = await handler(arguments, context)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "CrudGenerator tool error: %s: %s",
                tool_name, str(exc), exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        if definition.name not in self._DISPATCH:
            return False
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False
        return True

    # ========================================
    # AI 调用辅助
    # ========================================

    async def _call_ai(
        self,
        system_prompt: str,
        user_message: str,
        context: ExecutionContext | None = None,
    ) -> str:
        """调用 AIGateway 获取 LLM 响应文本

        自动注入项目知识图谱摘要到 system_prompt，使 AI 感知已有模型。
        如果 gateway 不可用，返回提示信息。
        """
        if not self._gateway:
            return _json_output({
                "error": "AI Gateway not available",
                "hint": "Please configure an AI model to use AI-assisted features.",
            })

        # 注入项目知识图谱
        enriched_prompt = system_prompt
        try:
            from app.codegen.knowledge_graph import get_graph_summary
            graph_summary = get_graph_summary()
            if graph_summary:
                enriched_prompt = (
                    f"{system_prompt}\n\n"
                    f"---\n{graph_summary}\n---\n\n"
                    "请基于以上已有模型信息，避免生成重复表名，正确引用已有表的外键关联。"
                )
        except Exception:
            pass  # 图谱不可用时静默降级

        from app.ai.types import ChatMessage

        messages = [
            ChatMessage(role="system", content=enriched_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        # 获取默认 chat 模型
        model_info = await self._gateway.model_repo.get_default_chat_model()
        if not model_info:
            return _json_output({
                "error": "No active chat model configured",
                "hint": "Please add an AI model in the admin panel.",
            })

        provider = await self._gateway.provider_repo.get_by_id(model_info.provider_id)
        if not provider:
            return _json_output({"error": "AI Provider not found"})

        response = await self._gateway.chat(
            provider_code=provider.code,
            messages=messages,
            model=model_info.model_id,
            temperature=0.3,
            max_tokens=4096,
        )

        return response.message.content

    # ========================================
    # Tool 1: crud_generate_config
    # ========================================

    async def _generate_config(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """自然语言 → CrudConfig JSON"""
        from app.codegen.ai_prompts import CRUD_CONFIG_GEN_PROMPT

        description = arguments.get("description", "")
        extra_context = arguments.get("context", "")

        user_msg = f"请根据以下需求生成 CrudConfig JSON：\n\n{description}"
        if extra_context:
            user_msg += f"\n\n额外上下文：\n{extra_context}"

        return await self._call_ai(CRUD_CONFIG_GEN_PROMPT, user_msg, context)

    # ========================================
    # Tool 2: crud_preview_code
    # ========================================

    async def _preview_code(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """预览将要生成的代码文件列表"""
        from app.codegen.generator import CrudGenerator
        from app.codegen.schemas import CrudConfig
        from app.codegen.writer import CrudWriter

        config_raw = _parse_config(arguments.get("config", {}))
        include_content = arguments.get("include_content", False)

        config = CrudConfig(**config_raw)
        gen = CrudGenerator()
        files = gen.generate(config)

        writer = CrudWriter(_PROJECT_ROOT)
        preview = writer.preview(files, include_content=include_content)

        return _json_output(preview)

    # ========================================
    # Tool 3: crud_generate_files
    # ========================================

    async def _generate_files(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """写入文件（支持 requires_confirmation 流程）"""
        from app.codegen.generator import CrudGenerator
        from app.codegen.schemas import CrudConfig
        from app.codegen.writer import ConflictAction, CrudWriter

        config_raw = _parse_config(arguments.get("config", {}))
        confirmed = arguments.get("confirmed", False)
        conflict_action_str = arguments.get("conflict_action", "skip")

        config = CrudConfig(**config_raw)
        gen = CrudGenerator()
        files = gen.generate(config)
        writer = CrudWriter(_PROJECT_ROOT)

        if not confirmed:
            # 未确认 → 返回预览 + requires_confirmation
            preview = writer.preview(files, include_content=False)
            preview["requires_confirmation"] = True
            preview["message"] = (
                f"Will generate {len(preview['files'])} files. "
                f"{preview['total_new']} new, {preview['total_conflict']} conflicts. "
                "Please confirm to proceed."
            )
            return _json_output(preview)

        # 已确认 → 执行写入
        conflict_action = ConflictAction(conflict_action_str)
        result = writer.write(files, conflict_action=conflict_action)

        return _json_output({
            "success": True,
            "written": result.written,
            "skipped": result.skipped,
            "merged": result.merged,
            "errors": result.errors,
            "total_written": len(result.written),
            "total_skipped": len(result.skipped),
            "total_merged": len(result.merged),
            "total_errors": len(result.errors),
        })

    # ========================================
    # Tool 4: crud_translate_i18n
    # ========================================

    async def _translate_i18n(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """翻译 i18n JSON"""
        from app.codegen.ai_prompts import I18N_TRANSLATE_PROMPT

        source_json = arguments.get("source_json", {})
        target_language = arguments.get("target_language", "en")

        user_msg = (
            f"请将以下中文 i18n JSON 翻译为 {target_language}：\n\n"
            f"{json.dumps(source_json, ensure_ascii=False, indent=2)}"
        )

        return await self._call_ai(I18N_TRANSLATE_PROMPT, user_msg, context)

    # ========================================
    # Tool 5: crud_suggest_fields
    # ========================================

    async def _suggest_fields(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """推荐字段"""
        from app.codegen.ai_prompts import FIELD_SUGGEST_PROMPT

        module_name = arguments.get("module_name", "")
        existing_fields = arguments.get("existing_fields", [])

        user_msg = f"模块名称：{module_name}\n"
        if existing_fields:
            user_msg += f"已有字段：{', '.join(str(f) for f in existing_fields)}\n"
        user_msg += "\n请推荐应该追加的字段、枚举和关联关系。"

        return await self._call_ai(FIELD_SUGGEST_PROMPT, user_msg, context)

    # ========================================
    # Tool 6: crud_generate_slot
    # ========================================

    async def _generate_slot(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """生成自定义列渲染 Vue template"""
        from app.codegen.ai_prompts import SLOT_CODE_GEN_PROMPT

        field_name = arguments.get("field_name", "")
        description = arguments.get("description", "")

        user_msg = (
            f"字段名：{field_name}\n"
            f"渲染效果描述：{description}\n\n"
            "请生成自定义列渲染的 Vue template 代码。"
        )

        return await self._call_ai(SLOT_CODE_GEN_PROMPT, user_msg, context)

    # ========================================
    # Tool 7: crud_recommend_style
    # ========================================

    async def _recommend_style(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """推荐布局和样式"""
        from app.codegen.ai_prompts import STYLE_RECOMMEND_PROMPT

        module_name = arguments.get("module_name", "")
        field_count = arguments.get("field_count", 0)
        has_status = arguments.get("has_status", False)
        has_hierarchy = arguments.get("has_hierarchy", False)

        user_msg = (
            f"模块名称：{module_name}\n"
            f"字段数量：{field_count}\n"
            f"有状态流转：{'是' if has_status else '否'}\n"
            f"有层级关系：{'是' if has_hierarchy else '否'}\n\n"
            "请推荐最佳的页面布局和样式配置。"
        )

        return await self._call_ai(STYLE_RECOMMEND_PROMPT, user_msg, context)

    # ========================================
    # Tool 8: crud_analyze_intent
    # ========================================

    async def _analyze_intent(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """业务意图分析"""
        from app.codegen.ai_prompts import INTENT_ANALYZE_PROMPT

        description = arguments.get("description", "")
        detail_level = arguments.get("detail_level", "basic")

        user_msg = (
            f"业务需求描述：{description}\n"
            f"分析详细程度：{detail_level}\n\n"
            "请分析业务意图，识别领域实体和关联关系。"
        )

        return await self._call_ai(INTENT_ANALYZE_PROMPT, user_msg, context)

    # ========================================
    # Tool 9: crud_batch_generate_config
    # ========================================

    async def _batch_generate_config(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """多表批量配置生成（AI 辅助）"""
        from app.codegen.ai_prompts import BATCH_CONFIG_GEN_PROMPT

        description = arguments.get("description", "")
        entities = arguments.get("entities")
        scope = arguments.get("scope", "tenant")
        parent_menu = arguments.get("parent_menu", "")

        user_msg = f"请根据以下需求为多个实体批量生成 BatchCrudProject JSON：\n\n{description}"
        if entities:
            user_msg += f"\n\n已识别的实体列表：\n{json.dumps(entities, ensure_ascii=False, indent=2)}"
        if scope:
            user_msg += f"\n\n生成范围：{scope}"
        if parent_menu:
            user_msg += f"\n父级菜单：{parent_menu}"

        return await self._call_ai(BATCH_CONFIG_GEN_PROMPT, user_msg, context)

    # ========================================
    # Tool 10: crud_batch_preview
    # ========================================

    async def _batch_preview(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """批量预览多表文件（直接执行）"""
        from app.codegen.generator import CrudGenerator
        from app.codegen.schemas import BatchCrudProject
        from app.codegen.writer import CrudWriter

        project_raw = _parse_config(arguments.get("project", {}))
        include_content = arguments.get("include_content", False)

        project = BatchCrudProject(**project_raw)
        gen = CrudGenerator()
        files = gen.generate_batch(project)

        writer = CrudWriter(_PROJECT_ROOT)
        preview = writer.preview_batch(files, include_content=include_content)

        return _json_output(preview)

    # ========================================
    # Tool 11: crud_batch_generate_files
    # ========================================

    async def _batch_generate_files(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """批量写入多表文件（支持 requires_confirmation 流程）"""
        from app.codegen.generator import CrudGenerator
        from app.codegen.schemas import BatchCrudProject
        from app.codegen.writer import ConflictAction, CrudWriter

        project_raw = _parse_config(arguments.get("project", {}))
        confirmed = arguments.get("confirmed", False)
        conflict_action_str = arguments.get("conflict_action", "skip")

        project = BatchCrudProject(**project_raw)
        gen = CrudGenerator()
        files = gen.generate_batch(project)
        writer = CrudWriter(_PROJECT_ROOT)

        if not confirmed:
            # 未确认 → 返回批量预览 + requires_confirmation
            preview = writer.preview_batch(files, include_content=False)
            preview["requires_confirmation"] = True
            entity_names = [e["entity_name"] for e in preview.get("entities", [])]
            preview["message"] = (
                f"Will generate {preview['total_files']} files "
                f"for {len(entity_names)} entities ({', '.join(entity_names)}). "
                f"{preview['total_new']} new, {preview['total_conflict']} conflicts. "
                "Please confirm to proceed."
            )
            return _json_output(preview)

        # 已确认 → 执行写入
        conflict_action = ConflictAction(conflict_action_str)
        result = writer.write(files, conflict_action=conflict_action)

        return _json_output({
            "success": True,
            "written": result.written,
            "skipped": result.skipped,
            "merged": result.merged,
            "errors": result.errors,
            "total_written": len(result.written),
            "total_skipped": len(result.skipped),
            "total_merged": len(result.merged),
            "total_errors": len(result.errors),
        })


    # ========================================
    # Tool 12: crud_batch_validate
    # ========================================

    async def _batch_validate(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """校验 BatchCrudProject（直接执行）"""
        from app.codegen.project_graph import build_project_graph
        from app.codegen.schema_guard import guard_batch_project
        from app.codegen.schemas import BatchCrudProject

        project_raw = _parse_config(arguments.get("project", {}))

        # Schema Guard: 严格校验输入
        guard = guard_batch_project(project_raw)
        if not guard.valid:
            return _json_output(guard.to_tool_output())

        project = BatchCrudProject(**project_raw)

        # 构建 ProjectGraph（含依赖排序 + 校验 + shared_enums 检查）
        graph = build_project_graph(project)

        # 构建 normalized_project（含最终 generation_order）
        normalized = project_raw.copy()
        if graph.valid:
            normalized["generation_order"] = graph.generation_order

        output = {
            "success": graph.valid,
            "normalized_project": normalized,
            "generation_order": graph.generation_order,
            "issues": [i.model_dump(mode="json") for i in graph.issues],
            "warnings": [w.model_dump(mode="json") for w in graph.warnings],
            "entity_count": graph.entity_count,
            "graph": graph.to_dict(),
        }

        return _json_output(output)

    # ========================================
    # Tool 13: crud_batch_merge_patch
    # ========================================

    async def _batch_merge_patch(
        self,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> str:
        """增量补丁合并（直接执行）"""
        from app.codegen.batch_merge import BatchMergePatch, merge_batch_project
        from app.codegen.schema_guard import guard_batch_project, guard_merge_patch
        from app.codegen.schemas import BatchCrudProject

        base_raw = _parse_config(arguments.get("base_project", {}))
        patch_raw = _parse_config(arguments.get("patch", {}))
        touched_paths_raw = arguments.get("touched_paths", [])

        # Schema Guard: 校验 base_project
        guard_base = guard_batch_project(base_raw)
        if not guard_base.valid:
            return _json_output(guard_base.to_tool_output())

        # Schema Guard: 校验 patch
        guard_p = guard_merge_patch(patch_raw)
        if not guard_p.valid:
            return _json_output(guard_p.to_tool_output())

        base_project = BatchCrudProject(**base_raw)
        patch = BatchMergePatch(**patch_raw)

        # touched_paths: list[str] → dict[str, set[str]]
        # 简化处理：将所有路径放入 "__project__" key
        tp: dict[str, set[str]] | None = None
        if touched_paths_raw:
            tp = {"__project__": set(touched_paths_raw)}

        result = merge_batch_project(base_project, patch, touched_paths=tp)

        output = {
            "success": True,
            "merged_project": result.project.model_dump(mode="json"),
            "merge_summary": result.summary.model_dump(mode="json"),
        }

        return _json_output(output)


__all__ = ["CrudGeneratorExecutor"]

"""
Integration Example: How to integrate CapabilityDescriptionBuilder into ConversationContextEngine
集成示例：如何将 CapabilityDescriptionBuilder 集成到 ConversationContextEngine

This file shows the changes needed in backend/app/ai/context/engine.py
本文件展示 backend/app/ai/context/engine.py 需要的修改
"""

# ========================================
# Step 1: Import the new module
# 步骤 1：导入新模块
# ========================================

# Add this import at the top of backend/app/ai/context/engine.py
from app.ai.capabilities.description_builder import (
    CapabilityDescriptionBuilder,
    CapabilityDescription,
)

# ========================================
# Step 2: Modify ConversationContextEngine.assemble()
# 步骤 2：修改 ConversationContextEngine.assemble() 方法
# ========================================

async def assemble(
    self,
    agent: Agent,
    request: ExecutionRequest,
    skill_result: "SkillResolveResult | None" = None,
) -> ContextAssembly:
    """
    Assemble conversation context with dynamic capability awareness.
    组装对话上下文，包含动态能力感知。
    """
    # ... existing code before capability assembly ...
    # ... 能力组装之前的现有代码 ...

    # ========================================
    # NEW: Build capability descriptions
    # 新增：构建能力描述
    # ========================================

    # Get configuration
    from app.configs.tenant import get_tenant_ai_config
    ai_config = await get_tenant_ai_config(self.db, request.tenant_id)

    # Check if dynamic capability awareness is enabled
    if ai_config.enable_dynamic_capability_awareness:
        capability_builder = CapabilityDescriptionBuilder(
            style=ai_config.capability_description_style,
            max_items_per_category=ai_config.max_capability_items_per_category,
        )

        capability_descriptions: list[CapabilityDescription] = []

        # 1. Build skill descriptions
        if skill_result:
            skill_descs = capability_builder.build_skill_descriptions(skill_result)
            capability_descriptions.extend(skill_descs)

        # 2. Build knowledge base descriptions
        if merged_kb_ids:
            from app.services.ai.agent_kb_binding_service import AgentKBBindingService

            kb_service = AgentKBBindingService(self.db, request.tenant_id)
            kb_bindings = await kb_service.get_agent_kb_bindings_with_metadata(
                agent.id,
                merge_platform_bindings=True,
            )
            kb_desc = capability_builder.build_knowledge_base_descriptions(kb_bindings)
            if kb_desc:
                capability_descriptions.append(kb_desc)

        # 3. Build page context description
        page_context = (
            request.input_variables.get("page_context")
            if request.input_variables
            else None
        )
        page_desc = capability_builder.build_page_context_description(page_context)
        if page_desc:
            capability_descriptions.append(page_desc)

        # 4. Build memory capability description
        memory_desc = capability_builder.build_memory_description(
            memory_enabled=request.memory_enabled,
            long_term_memory_enabled=long_term_memory_enabled,
        )
        if memory_desc:
            capability_descriptions.append(memory_desc)

        # 5. Format and inject into system prompt
        if capability_descriptions:
            capability_block = capability_builder.format_as_system_prompt_block(
                capability_descriptions
            )
            system_prompt_additions.append(capability_block)

    # ... existing code continues ...
    # ... 现有代码继续 ...

    return ContextAssembly(
        # ... existing fields ...
    )


# ========================================
# Step 3: Add helper method to AgentKBBindingService
# 步骤 3：在 AgentKBBindingService 中添加辅助方法
# ========================================

# Add this method to backend/app/services/ai/agent_kb_binding_service.py

async def get_agent_kb_bindings_with_metadata(
    self,
    agent_id: int,
    merge_platform_bindings: bool = False,
) -> list[dict[str, Any]]:
    """
    Get agent knowledge base bindings with metadata for capability description.
    获取智能体知识库绑定及元数据，用于能力描述。

    Returns:
        List of dicts with:
        - kb_id: Knowledge base ID
        - kb_name: Knowledge base name
        - kb_description: Knowledge base description
        - kb_document_count: Number of documents
    """
    from app.models.ai.knowledge_base import KnowledgeBase
    from sqlalchemy import select, func
    from app.models.ai.knowledge_base_document import KnowledgeBaseDocument

    # Get bindings
    bindings = await self.get_agent_kb_bindings(
        agent_id,
        merge_platform_bindings=merge_platform_bindings,
    )

    if not bindings:
        return []

    kb_ids = [binding.knowledge_base_id for binding in bindings]

    # Load knowledge base metadata
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.description,
            func.count(KnowledgeBaseDocument.id).label("document_count"),
        )
        .outerjoin(
            KnowledgeBaseDocument,
            KnowledgeBaseDocument.knowledge_base_id == KnowledgeBase.id,
        )
        .where(KnowledgeBase.id.in_(kb_ids))
        .group_by(KnowledgeBase.id)
    )

    result = await self.db.execute(stmt)
    rows = result.all()

    return [
        {
            "kb_id": row.id,
            "kb_name": row.name,
            "kb_description": row.description,
            "kb_document_count": row.document_count,
        }
        for row in rows
    ]


# ========================================
# Step 4: Add configuration to tenant AI config
# 步骤 4：在租户 AI 配置中添加配置项
# ========================================

# Add these fields to backend/app/configs/definitions/tenant/ai.py

class AIConfig(BaseModel):
    """AI configuration / AI 配置"""

    # ... existing fields ...

    # NEW: Dynamic capability awareness settings
    # 新增：动态能力感知设置
    enable_dynamic_capability_awareness: bool = Field(
        default=True,
        description="Enable dynamic capability awareness (inject skill and knowledge base descriptions into system prompt)",
    )

    capability_description_style: str = Field(
        default="detailed",
        description="Capability description style: 'detailed' or 'concise'",
    )

    max_capability_items_per_category: int = Field(
        default=20,
        description="Maximum capability items per category (prevents prompt bloat)",
    )


# ========================================
# Step 5: Modify BaseEngine._inject_tool_awareness()
# 步骤 5：修改 BaseEngine._inject_tool_awareness() 方法
# ========================================

# Modify backend/app/ai/engine/base.py

@staticmethod
def _inject_tool_awareness(
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    continuation_context: ResearchContinuationContext | None = None,
    selected_skill_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    ordered_requested_families: list[str] | None = None,
    skip_capability_summary: bool = False,  # NEW parameter
) -> None:
    """
    Inject tool awareness hints into system message.
    注入工具感知提示到 system 消息。

    Args:
        skip_capability_summary: If True, skip capability summary
            (because it's already injected by ContextEngine)
    """
    if (
        not messages
        or messages[0].role != "system"
        or (
            not tools
            and not (selected_skill_names or [])
            and not (context_sources or [])
        )
    ):
        return

    tool_names = [t.name for t in tools]

    if skip_capability_summary:
        # Only inject tool usage rules, not capability list
        # 只注入工具使用规则，不重复注入能力列表
        hint = (
            "\n\n---\n"
            "[TOOL USAGE RULES]\n"
            "When the user's request can be fulfilled by calling a tool, "
            "you MUST call the appropriate tool instead of generating text-only responses.\n"
            "Do NOT say you cannot access the database or perform actions — use your tools.\n"
            "When a newer user turn conflicts with an older temporary execution constraint "
            '(for example: "read-only", "do not write", "do not submit"), follow the latest user turn '
            "unless the user explicitly says the earlier constraint still applies.\n"
            "If the user asks for multiple operations or gives an ordered checklist, execute the requested operations "
            "in that order and only summarize after you have attempted each requested step.\n"
            "Do NOT show HTML, JSON, tool parameters or raw API output to the user. "
            "Tools are for internal execution; return natural language results only."
        )
    else:
        # Keep original logic (backward compatible)
        # 保持原有逻辑（向后兼容）
        hint = (
            "\n\n---\n"
            "[TOOL AWARENESS]\n"
            f"You have {len(tool_names)} tool(s) available: {', '.join(tool_names)}.\n"
            "When the user's request can be fulfilled by calling a tool, "
            "you MUST call the appropriate tool instead of generating text-only responses.\n"
            # ... rest of original content ...
        )

    # ... rest of the method remains the same ...


# ========================================
# Step 6: Update BaseEngine._prepare_execution() call site
# 步骤 6：更新 BaseEngine._prepare_execution() 调用点
# ========================================

# In backend/app/ai/engine/base.py, when calling _inject_tool_awareness:

# Check if dynamic capability awareness is enabled
from app.configs.tenant import get_tenant_ai_config
ai_config = await get_tenant_ai_config(self.db, request.tenant_id)

self._inject_tool_awareness(
    messages=messages,
    tools=tools,
    input_variables=request.input_variables,
    continuation_context=continuation_context,
    selected_skill_names=selected_skill_names,
    context_sources=context_sources,
    ordered_requested_families=ordered_requested_families,
    skip_capability_summary=ai_config.enable_dynamic_capability_awareness,  # NEW
)

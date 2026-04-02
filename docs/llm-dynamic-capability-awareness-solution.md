# LLM 动态能力感知方案

## 问题诊断

### 当前问题
1. **LLM 不知道自己能调用什么技能**：技能信息没有动态注入到 system prompt
2. **LLM 不知道自己能访问什么知识库**：知识库绑定信息对 LLM 不可见
3. **提示词固定死**：能力描述硬编码在 system prompt 中，无法根据实际绑定动态调整

### 根本原因分析

通过代码审计发现：

1. **技能解析流程**（`backend/app/ai/skills/resolver.py`）：
   - `SkillResolver.resolve()` 将 Skill 转换为 ToolDefinition
   - 生成了 `capability_descriptors` 列表，包含技能元信息
   - **但这些信息只用于工具调用，没有注入到 LLM 的上下文中**

2. **知识库绑定流程**（`backend/app/services/ai/agent_kb_binding_service.py`）：
   - `AgentKBBindingService` 管理 Agent 与 KnowledgeBase 的绑定关系
   - RAG 检索会使用这些绑定（`backend/app/ai/rag_injector.py`）
   - **但 LLM 不知道自己绑定了哪些知识库，只能被动接收检索结果**

3. **上下文组装流程**（`backend/app/ai/context/engine.py`）：
   - `ConversationContextEngine.assemble()` 负责组装对话上下文
   - 已经有 `ContextAssembler` 收集能力信息（`backend/app/ai/runtime/context_assembler.py`）
   - **但收集的能力信息没有转换为 LLM 可理解的自然语言描述**

4. **工具感知注入**（`backend/app/ai/engine/base.py:225-300`）：
   - `_inject_tool_awareness()` 方法会注入工具列表
   - **但只注入了工具名称，没有注入技能和知识库的语义信息**

## 解决方案设计

### 核心思路

**让 LLM 在每次对话开始时，通过 system prompt 动态了解自己当前拥有的能力**

### 方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                     对话请求                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  1. 技能解析 (SkillResolver)                                 │
│     - 解析 Agent 绑定的所有 Skill                            │
│     - 生成 ToolDefinition + CapabilityDescriptor             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 知识库加载 (AgentKBBindingService)                       │
│     - 加载 Agent 绑定的所有 KnowledgeBase                    │
│     - 获取知识库元信息（名称、描述、文档数量）                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  3. 能力描述生成 (NEW: CapabilityDescriptionBuilder)         │
│     - 将技能信息转换为自然语言描述                            │
│     - 将知识库信息转换为自然语言描述                          │
│     - 生成结构化的能力清单                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  4. 上下文注入 (ConversationContextEngine)                   │
│     - 将能力描述注入到 system prompt                         │
│     - 保持原有 system_prompt 不变                            │
│     - 动态追加 [CAPABILITIES] 区块                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  5. LLM 调用                                                 │
│     - LLM 看到完整的能力描述                                 │
│     - 根据能力主动调用工具/查询知识库                         │
└─────────────────────────────────────────────────────────────┘
```

### 详细设计

#### 1. 新增能力描述构建器

**文件位置**：`backend/app/ai/capabilities/description_builder.py`

```python
"""
Capability Description Builder / 能力描述构建器

将技能、知识库等能力信息转换为 LLM 可理解的自然语言描述
"""

from dataclasses import dataclass
from typing import Any

@dataclass
class CapabilityDescription:
    """能力描述"""
    category: str  # skills / knowledge_bases / page_context / memory
    title: str
    items: list[str]
    metadata: dict[str, Any] | None = None

class CapabilityDescriptionBuilder:
    """能力描述构建器"""
    
    def build_skill_descriptions(
        self,
        skill_result: Any,
    ) -> list[CapabilityDescription]:
        """
        从 SkillResolveResult 构建技能描述
        
        输入：SkillResolveResult（包含 tools, capability_descriptors）
        输出：结构化的技能描述列表
        
        示例输出：
        [
            CapabilityDescription(
                category="skills",
                title="Data Intelligence Skills",
                items=[
                    "data_query: Query database using natural language. Available tables: users(用户), agents(智能体), conversations(对话)",
                    "data_create: Create new records in allowed tables: users(用户)",
                    "data_update: Update existing records in allowed tables: users(用户)",
                ]
            ),
            CapabilityDescription(
                category="skills",
                title="Web Research Skills",
                items=[
                    "web_search: Search the web for current information",
                    "fetch_url: Fetch and read content from a specific URL",
                ]
            ),
        ]
        """
        pass
    
    def build_knowledge_base_descriptions(
        self,
        kb_bindings: list[dict[str, Any]],
    ) -> CapabilityDescription | None:
        """
        从知识库绑定构建知识库描述
        
        输入：知识库绑定列表（包含 kb_name, kb_description, kb_document_count）
        输出：知识库能力描述
        
        示例输出：
        CapabilityDescription(
            category="knowledge_bases",
            title="Knowledge Bases",
            items=[
                "产品文档库: 包含产品使用手册和API文档，共120个文档",
                "客户案例库: 客户成功案例和最佳实践，共45个文档",
            ],
            metadata={"total_documents": 165}
        )
        """
        pass
    
    def build_page_context_description(
        self,
        page_context: dict[str, Any] | None,
    ) -> CapabilityDescription | None:
        """
        从页面上下文构建描述
        
        示例输出：
        CapabilityDescription(
            category="page_context",
            title="Current Page Context",
            items=[
                "Page: 用户管理页面",
                "Available operations: create_user, update_user, delete_user",
            ]
        )
        """
        pass
    
    def build_memory_description(
        self,
        memory_enabled: bool,
        long_term_memory_enabled: bool,
    ) -> CapabilityDescription | None:
        """
        从记忆配置构建描述
        
        示例输出：
        CapabilityDescription(
            category="memory",
            title="Memory Capabilities",
            items=[
                "Session memory: Enabled (maintains conversation context)",
                "Long-term memory: Enabled (recalls user preferences and history)",
            ]
        )
        """
        pass
    
    def format_as_system_prompt_block(
        self,
        descriptions: list[CapabilityDescription],
    ) -> str:
        """
        将能力描述格式化为 system prompt 区块
        
        输出格式：
        ```
        [CAPABILITIES]
        You have access to the following capabilities:

        ## Skills
        - data_query: Query database using natural language. Available tables: users(用户), agents(智能体)
        - web_search: Search the web for current information
        - fetch_url: Fetch and read content from a specific URL

        ## Knowledge Bases
        You have access to 2 knowledge bases:
        - 产品文档库: 包含产品使用手册和API文档，共120个文档
        - 客户案例库: 客户成功案例和最佳实践，共45个文档

        When the user asks questions, you should:
        1. Check if any of your skills can help answer the question
        2. Search relevant knowledge bases for information
        3. Use tools proactively instead of saying "I cannot do that"
        ```
        """
        pass
```

#### 2. 修改上下文引擎

**文件位置**：`backend/app/ai/context/engine.py`

在 `ConversationContextEngine.assemble()` 方法中添加能力描述注入：

```python
async def assemble(
    self,
    agent: Agent,
    request: ExecutionRequest,
    skill_result: "SkillResolveResult | None" = None,
) -> ContextAssembly:
    # ... 现有代码 ...
    
    # 新增：构建能力描述
    from app.ai.capabilities.description_builder import CapabilityDescriptionBuilder
    
    capability_builder = CapabilityDescriptionBuilder()
    capability_descriptions: list[CapabilityDescription] = []
    
    # 1. 技能描述
    if skill_result:
        skill_descs = capability_builder.build_skill_descriptions(skill_result)
        capability_descriptions.extend(skill_descs)
    
    # 2. 知识库描述
    if merged_kb_ids:
        from app.services.ai.agent_kb_binding_service import AgentKBBindingService
        kb_service = AgentKBBindingService(self.db, request.tenant_id)
        kb_bindings = await kb_service.get_agent_kb_bindings(
            agent.id,
            merge_platform_bindings=True,
        )
        kb_desc = capability_builder.build_knowledge_base_descriptions(kb_bindings)
        if kb_desc:
            capability_descriptions.append(kb_desc)
    
    # 3. 页面上下文描述
    page_context = request.input_variables.get("page_context") if request.input_variables else None
    page_desc = capability_builder.build_page_context_description(page_context)
    if page_desc:
        capability_descriptions.append(page_desc)
    
    # 4. 记忆能力描述
    memory_desc = capability_builder.build_memory_description(
        memory_enabled=request.memory_enabled,
        long_term_memory_enabled=long_term_memory_enabled,
    )
    if memory_desc:
        capability_descriptions.append(memory_desc)
    
    # 5. 格式化并注入到 system prompt
    if capability_descriptions:
        capability_block = capability_builder.format_as_system_prompt_block(
            capability_descriptions
        )
        system_prompt_additions.append(capability_block)
    
    # ... 现有代码继续 ...
```

#### 3. 优化工具感知注入

**文件位置**：`backend/app/ai/engine/base.py`

修改 `_inject_tool_awareness()` 方法，避免重复注入：

```python
@staticmethod
def _inject_tool_awareness(
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    continuation_context: ResearchContinuationContext | None = None,
    selected_skill_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    ordered_requested_families: list[str] | None = None,
    skip_capability_summary: bool = False,  # 新增参数
) -> None:
    """
    注入工具感知提示
    
    如果 skip_capability_summary=True，则跳过能力总结部分
    （因为已经在 ContextEngine 中注入了更详细的能力描述）
    """
    if skip_capability_summary:
        # 只注入工具使用规则，不重复注入能力列表
        hint = (
            "\n\n---\n"
            "[TOOL USAGE RULES]\n"
            "When the user's request can be fulfilled by calling a tool, "
            "you MUST call the appropriate tool instead of generating text-only responses.\n"
            "Do NOT say you cannot access the database or perform actions — use your tools.\n"
            # ... 其他规则 ...
        )
    else:
        # 保持原有逻辑（向后兼容）
        hint = (
            "\n\n---\n"
            "[TOOL AWARENESS]\n"
            f"You have {len(tool_names)} tool(s) available: {', '.join(tool_names)}.\n"
            # ... 原有内容 ...
        )
    
    # ... 其余代码不变 ...
```

### 实现步骤

#### 阶段一：核心能力描述构建器（优先级：高）

1. **创建 `CapabilityDescriptionBuilder` 类**
   - 文件：`backend/app/ai/capabilities/__init__.py`
   - 文件：`backend/app/ai/capabilities/description_builder.py`
   - 实现技能描述构建
   - 实现知识库描述构建
   - 实现格式化输出

2. **单元测试**
   - 文件：`backend/tests/unit/ai/capabilities/test_description_builder.py`
   - 测试各种技能类型的描述生成
   - 测试知识库描述生成
   - 测试格式化输出

#### 阶段二：上下文引擎集成（优先级：高）

1. **修改 `ConversationContextEngine`**
   - 在 `assemble()` 方法中集成能力描述构建
   - 将能力描述注入到 `system_prompt_additions`
   - 确保不影响现有 RAG、记忆等功能

2. **集成测试**
   - 文件：`backend/tests/integration/ai/test_context_engine_capabilities.py`
   - 测试技能描述是否正确注入
   - 测试知识库描述是否正确注入
   - 测试多种能力组合场景

#### 阶段三：工具感知优化（优先级：中）

1. **修改 `_inject_tool_awareness()`**
   - 添加 `skip_capability_summary` 参数
   - 避免与能力描述重复

2. **调整调用点**
   - 在 `BaseEngine._prepare_execution()` 中传入 `skip_capability_summary=True`

#### 阶段四：前端展示优化（优先级：低）

1. **在对话界面显示当前能力**
   - 前端可以调用 API 获取 Agent 的能力清单
   - 在 UI 上展示"当前可用技能"和"当前可用知识库"

2. **能力变更提示**
   - 当管理员修改技能或知识库绑定时，提示用户刷新对话

### 配置选项

为了灵活控制，添加配置开关：

**文件位置**：`backend/app/configs/definitions/tenant/ai.py`

```python
class AIConfig(BaseModel):
    """AI 配置"""
    
    # 新增配置项
    enable_dynamic_capability_awareness: bool = Field(
        default=True,
        description="是否启用动态能力感知（在 system prompt 中注入技能和知识库描述）"
    )
    
    capability_description_style: str = Field(
        default="detailed",
        description="能力描述风格：detailed（详细）/ concise（简洁）"
    )
    
    max_capability_items_per_category: int = Field(
        default=20,
        description="每个类别最多显示的能力项数量（防止 prompt 过长）"
    )
```

### 示例效果

#### 修改前

**System Prompt**:
```
你是一个智能助手，可以帮助用户解答问题。
```

**用户提问**:
```
帮我查询一下有多少个用户
```

**LLM 回复**:
```
抱歉，我无法直接访问数据库。您需要联系管理员或使用数据库管理工具查询。
```

#### 修改后

**System Prompt**:
```
你是一个智能助手，可以帮助用户解答问题。

[CAPABILITIES]
You have access to the following capabilities:

## Skills
- data_query: Query database using natural language. Available tables: users(用户), agents(智能体), conversations(对话), messages(消息)
- data_create: Create new records in allowed tables: users(用户)
- data_update: Update existing records in allowed tables: users(用户)
- web_search: Search the web for current information
- fetch_url: Fetch and read content from a specific URL

## Knowledge Bases
You have access to 2 knowledge bases:
- 产品文档库: 包含产品使用手册和API文档，共120个文档
- 客户案例库: 客户成功案例和最佳实践，共45个文档

When the user asks questions, you should:
1. Check if any of your skills can help answer the question
2. Search relevant knowledge bases for information
3. Use tools proactively instead of saying "I cannot do that"
```

**用户提问**:
```
帮我查询一下有多少个用户
```

**LLM 回复**:
```
[调用 data_query 工具]
参数: {"question": "统计用户总数"}

根据查询结果，当前系统中共有 1,234 个用户。
```

### 性能考虑

1. **Token 消耗**
   - 能力描述会增加 system prompt 长度
   - 预估增加：200-500 tokens（取决于技能和知识库数量）
   - 优化：限制每个类别的最大项数（配置项：`max_capability_items_per_category`）

2. **缓存策略**
   - 能力描述可以在 Agent 级别缓存
   - 当技能或知识库绑定变更时，清除缓存
   - 实现：使用 Redis 缓存，key 格式：`capability_desc:agent:{agent_id}:v{version}`

3. **延迟加载**
   - 知识库元信息可以异步加载
   - 首次对话时可能稍慢，后续对话使用缓存

### 监控指标

添加以下监控指标，评估方案效果：

1. **工具调用率**
   - 修改前后的工具调用次数对比
   - 预期：工具调用率提升 30-50%

2. **"无法执行"回复率**
   - 统计 LLM 回复中包含"无法"、"不能"等否定词的比例
   - 预期：否定回复率下降 40-60%

3. **知识库命中率**
   - 统计 RAG 检索被实际使用的比例
   - 预期：知识库命中率提升 20-30%

4. **用户满意度**
   - 通过对话评分统计
   - 预期：满意度提升 15-25%

### 回滚方案

如果方案出现问题，可以通过配置快速回滚：

```python
# 在 tenant AI 配置中设置
enable_dynamic_capability_awareness = False
```

回滚后，系统恢复到原有行为，不会影响现有功能。

### 后续优化方向

1. **智能能力推荐**
   - 根据用户问题，动态推荐最相关的技能和知识库
   - 减少不相关能力的描述，降低 token 消耗

2. **能力使用统计**
   - 统计每个技能和知识库的实际使用频率
   - 优先展示高频使用的能力

3. **多语言支持**
   - 根据用户语言偏好，生成对应语言的能力描述
   - 支持中英文切换

4. **能力分组**
   - 将相关技能分组（如"数据操作"、"网络搜索"、"文档处理"）
   - 提供更清晰的能力结构

## 总结

本方案通过以下核心改进，解决 LLM 不知道自己能力的问题：

1. **动态能力描述生成**：将技能和知识库信息转换为 LLM 可理解的自然语言
2. **自动注入到上下文**：在每次对话时，动态将能力描述追加到 system prompt
3. **禁止固定提示词**：所有能力描述都是运行时生成，根据实际绑定动态调整
4. **向后兼容**：不影响现有功能，可通过配置开关控制

**预期效果**：
- LLM 主动调用工具的频率提升 30-50%
- "无法执行"类回复减少 40-60%
- 知识库利用率提升 20-30%
- 用户满意度提升 15-25%

**实施风险**：低
- 不修改核心逻辑，只是增强上下文
- 可通过配置快速回滚
- 增量实施，逐步验证效果

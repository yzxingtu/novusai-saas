# AI 实施提示词 - LLM 动态能力感知方案

请按照以下计划实施 LLM 动态能力感知功能。

## 项目背景

当前 LLM 不知道自己能调用什么技能、能访问什么知识库，导致用户体验不佳。需要实现动态能力感知机制，让 LLM 在每次对话时都能了解自己的能力。

完整方案文档：`docs/llm-dynamic-capability-awareness-solution.md`

## 实施要求

### 代码规范
1. **遵循项目现有代码风格**
   - 使用类型注解
   - 添加中英文双语注释
   - 遵循 PEP 8 规范

2. **测试驱动开发**
   - 先写测试，再写实现
   - 确保测试覆盖率 > 90%
   - 每个功能完成后立即运行测试

3. **增量提交**
   - 每完成一个小功能就提交
   - Commit message 格式：`feat: 简短描述` 或 `test: 简短描述`
   - 不要一次性提交大量代码

4. **向后兼容**
   - 不破坏现有功能
   - 添加配置开关，默认启用
   - 保留原有逻辑作为 fallback

## 实施任务

### 阶段一：核心能力描述构建器（优先级：高）

#### 任务 1.1：创建模块结构
**目标**：创建 `backend/app/ai/capabilities` 模块

**步骤**：
1. 创建 `backend/app/ai/capabilities/__init__.py`
2. 创建 `backend/app/ai/capabilities/description_builder.py`
3. 验证模块可以正常导入

**验收标准**：
- [ ] 文件已创建
- [ ] 可以成功 `from app.ai.capabilities import CapabilityDescriptionBuilder`

**参考代码**：已提供完整实现在 `backend/app/ai/capabilities/description_builder.py`

---

#### 任务 1.2：实现 CapabilityDescriptionBuilder 核心功能
**目标**：实现能力描述构建器的所有方法

**步骤**：
1. 实现 `CapabilityDescription` 数据类
2. 实现 `CapabilityDescriptionBuilder.__init__()`
3. 实现 `build_skill_descriptions()` - 从技能构建描述
4. 实现 `build_knowledge_base_descriptions()` - 从知识库构建描述
5. 实现 `build_page_context_description()` - 从页面上下文构建描述
6. 实现 `build_memory_description()` - 从记忆配置构建描述
7. 实现 `format_as_system_prompt_block()` - 格式化为 system prompt
8. 实现辅助方法

**验收标准**：
- [ ] 所有方法都有完整实现
- [ ] 所有方法都有类型注解
- [ ] 所有方法都有中英文注释
- [ ] 代码通过 `ruff check` 检查

**参考代码**：`backend/app/ai/capabilities/description_builder.py`（已完整实现）

---

#### 任务 1.3：编写单元测试
**目标**：为 CapabilityDescriptionBuilder 编写完整的单元测试

**步骤**：
1. 创建测试文件 `backend/tests/unit/ai/capabilities/test_description_builder.py`
2. 测试技能描述生成（空、单个、多个、不同家族）
3. 测试知识库描述生成（空、单个、多个、详细/简洁模式）
4. 测试页面上下文描述生成
5. 测试记忆描述生成
6. 测试格式化输出
7. 测试边界条件（最大项数限制）

**验收标准**：
- [ ] 测试文件已创建
- [ ] 运行 `pytest backend/tests/unit/ai/capabilities/test_description_builder.py -v` 全部通过
- [ ] 测试覆盖率 > 90%（运行 `pytest --cov=app.ai.capabilities`）

**参考代码**：`backend/tests/unit/ai/capabilities/test_description_builder.py`（已完整实现）

---

### 阶段二：上下文引擎集成（优先级：高）

#### 任务 2.1：添加配置项
**目标**：在租户 AI 配置中添加动态能力感知的配置项

**步骤**：
1. 打开 `backend/app/configs/definitions/tenant/ai.py`
2. 在 `AIConfig` 类中添加三个配置字段：
   - `enable_dynamic_capability_awareness: bool = True`
   - `capability_description_style: str = "detailed"`
   - `max_capability_items_per_category: int = 20`
3. 添加字段说明（中英文）

**验收标准**：
- [ ] 配置字段已添加
- [ ] 有完整的类型注解和描述
- [ ] 可以正常读取配置

**参考代码**：
```python
class AIConfig(BaseModel):
    # ... 现有字段 ...
    
    enable_dynamic_capability_awareness: bool = Field(
        default=True,
        description="Enable dynamic capability awareness / 启用动态能力感知",
    )
    
    capability_description_style: str = Field(
        default="detailed",
        description="Capability description style: detailed/concise / 能力描述风格：详细/简洁",
    )
    
    max_capability_items_per_category: int = Field(
        default=20,
        description="Max capability items per category / 每个类别最多显示的能力项数量",
    )
```

---

#### 任务 2.2：扩展 AgentKBBindingService
**目标**：添加获取知识库元数据的方法

**步骤**：
1. 打开 `backend/app/services/ai/agent_kb_binding_service.py`
2. 添加 `get_agent_kb_bindings_with_metadata()` 方法
3. 查询知识库的名称、描述、文档数量
4. 返回结构化数据

**验收标准**：
- [ ] 方法已添加
- [ ] 可以正确查询知识库元数据
- [ ] 返回格式符合 `CapabilityDescriptionBuilder` 的要求

**参考代码**：`docs/capability-awareness-integration-example.py` 中的 Step 3

---

#### 任务 2.3：修改 ConversationContextEngine
**目标**：在上下文组装时注入能力描述

**步骤**：
1. 打开 `backend/app/ai/context/engine.py`
2. 在 `assemble()` 方法中导入 `CapabilityDescriptionBuilder`
3. 读取租户 AI 配置
4. 检查 `enable_dynamic_capability_awareness` 是否启用
5. 如果启用，构建能力描述：
   - 技能描述（从 `skill_result`）
   - 知识库描述（从 `AgentKBBindingService`）
   - 页面上下文描述（从 `request.input_variables`）
   - 记忆描述（从 `request.memory_enabled`）
6. 格式化并追加到 `system_prompt_additions`

**验收标准**：
- [ ] 代码已修改
- [ ] 不影响现有功能
- [ ] 能力描述正确注入到 system prompt
- [ ] 配置关闭时不注入

**参考代码**：`docs/capability-awareness-integration-example.py` 中的 Step 2

---

#### 任务 2.4：编写集成测试
**目标**：测试能力描述是否正确注入到上下文

**步骤**：
1. 创建 `backend/tests/integration/ai/test_context_engine_capabilities.py`
2. 测试场景：
   - 只有技能
   - 只有知识库
   - 技能 + 知识库
   - 技能 + 知识库 + 页面上下文
   - 配置关闭时不注入
3. 验证 system prompt 中包含正确的能力描述

**验收标准**：
- [ ] 测试文件已创建
- [ ] 所有测试场景通过
- [ ] 运行 `pytest backend/tests/integration/ai/test_context_engine_capabilities.py -v` 全部通过

---

#### 任务 2.5：端到端测试
**目标**：在真实环境中验证功能

**步骤**：
1. 启动开发环境
2. 创建测试 Agent，绑定技能和知识库
3. 发起对话
4. 检查日志，确认 system prompt 包含能力描述
5. 验证 LLM 是否能正确理解并使用能力

**验收标准**：
- [ ] LLM 能看到技能列表
- [ ] LLM 能看到知识库列表
- [ ] LLM 能主动调用工具
- [ ] LLM 能主动查询知识库

---

### 阶段三：工具感知优化（优先级：中）

#### 任务 3.1：修改 BaseEngine._inject_tool_awareness()
**目标**：避免重复注入能力列表

**步骤**：
1. 打开 `backend/app/ai/engine/base.py`
2. 在 `_inject_tool_awareness()` 方法中添加 `skip_capability_summary: bool = False` 参数
3. 实现条件逻辑：
   - 如果 `skip_capability_summary=True`，只注入工具使用规则
   - 如果 `skip_capability_summary=False`，保持原有逻辑
4. 确保向后兼容

**验收标准**：
- [ ] 参数已添加
- [ ] 条件逻辑正确实现
- [ ] 不破坏现有功能

**参考代码**：`docs/capability-awareness-integration-example.py` 中的 Step 5

---

#### 任务 3.2：调整调用点
**目标**：在调用 `_inject_tool_awareness()` 时传入正确的参数

**步骤**：
1. 找到所有调用 `_inject_tool_awareness()` 的地方
2. 读取租户 AI 配置
3. 传入 `skip_capability_summary=ai_config.enable_dynamic_capability_awareness`

**验收标准**：
- [ ] 所有调用点已更新
- [ ] 配置启用时不重复注入
- [ ] 配置关闭时保持原有行为

**参考代码**：`docs/capability-awareness-integration-example.py` 中的 Step 6

---

### 阶段四：验证与优化（优先级：中）

#### 任务 4.1：性能测试
**目标**：确保性能没有明显下降

**步骤**：
1. 测试 Token 消耗增加量
2. 测试响应延迟增加量
3. 如果性能下降 > 10%，考虑优化

**验收标准**：
- [ ] Token 消耗增加 < 10%
- [ ] 响应延迟增加 < 5%

---

#### 任务 4.2：效果验证
**目标**：验证功能是否达到预期效果

**步骤**：
1. 准备测试用例（用户问题 + 预期行为）
2. 对比修改前后的 LLM 回复
3. 统计工具调用率、否定回复率

**验收标准**：
- [ ] 工具调用率有明显提升
- [ ] "无法执行"类回复明显减少
- [ ] 知识库被更主动地使用

---

## 执行指南

### 开始前
1. 阅读完整方案：`docs/llm-dynamic-capability-awareness-solution.md`
2. 查看参考代码：`backend/app/ai/capabilities/description_builder.py`
3. 理解集成方式：`docs/capability-awareness-integration-example.py`

### 执行顺序
**严格按照任务顺序执行**：
1. 阶段一 → 阶段二 → 阶段三 → 阶段四
2. 每个任务完成后，运行测试确认无误
3. 每个任务完成后，提交代码

### 提交规范
```bash
# 功能实现
git commit -m "feat(ai): add CapabilityDescriptionBuilder"

# 测试
git commit -m "test(ai): add tests for CapabilityDescriptionBuilder"

# 集成
git commit -m "feat(ai): integrate capability awareness into context engine"

# 优化
git commit -m "refactor(ai): optimize tool awareness injection"
```

### 遇到问题时
1. 先查看参考代码和文档
2. 检查是否遵循了项目规范
3. 运行测试确认问题范围
4. 如果无法解决，记录问题并寻求帮助

### 完成标准
- [ ] 所有任务的验收标准都已满足
- [ ] 所有测试通过
- [ ] 代码审查通过
- [ ] 端到端测试通过
- [ ] 性能符合要求

## 注意事项

1. **不要跳过测试**：每个功能都必须有测试
2. **不要一次性实现所有功能**：按任务顺序，逐步实现
3. **不要破坏现有功能**：确保向后兼容
4. **不要忽略性能**：注意 Token 消耗和响应延迟
5. **不要硬编码**：使用配置项控制行为

## 参考资料

- 完整方案设计：`docs/llm-dynamic-capability-awareness-solution.md`
- 集成示例代码：`docs/capability-awareness-integration-example.py`
- 实施检查清单：`docs/capability-awareness-implementation-checklist.md`
- 快速概览：`docs/capability-awareness-quick-overview.md`

---

**开始实施前，请确认你已经理解了整个方案和执行流程。**

**如有疑问，请先查阅文档，或询问项目负责人。**

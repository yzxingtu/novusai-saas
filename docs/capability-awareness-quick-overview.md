# LLM 动态能力感知方案 - 快速概览

## 问题

当前 LLM 不知道自己能调用什么技能、能访问什么知识库，导致：
- 用户问"帮我查询数据库"，LLM 回复"我无法访问数据库"
- 明明绑定了知识库，LLM 却不主动查询
- 能力描述硬编码在 system prompt 中，无法动态调整

## 解决方案

**核心思路**：在每次对话时，动态将 Agent 的技能和知识库信息注入到 system prompt，让 LLM 知道自己有什么能力。

### 架构

```
对话请求
  ↓
技能解析 (SkillResolver)
  ↓
知识库加载 (AgentKBBindingService)
  ↓
能力描述生成 (NEW: CapabilityDescriptionBuilder) ← 核心新增
  ↓
上下文注入 (ConversationContextEngine)
  ↓
LLM 调用
```

### 示例效果

**修改前**：
```
System Prompt: 你是一个智能助手。

用户: 帮我查询有多少个用户
LLM: 抱歉，我无法直接访问数据库。
```

**修改后**：
```
System Prompt: 你是一个智能助手。

[CAPABILITIES]
## Skills
- data_query: Query database. Available tables: users(用户), agents(智能体)
- web_search: Search the web

## Knowledge Bases
- 产品文档库: 120 documents
- 客户案例库: 45 documents

用户: 帮我查询有多少个用户
LLM: [调用 data_query 工具] 当前系统中共有 1,234 个用户。
```

## 实施步骤

### 阶段一：核心构建器（2 天）
1. 创建 `CapabilityDescriptionBuilder` 类
2. 实现技能、知识库、页面上下文、记忆的描述生成
3. 编写单元测试

### 阶段二：上下文集成（3 天）
1. 在 `ConversationContextEngine` 中集成构建器
2. 添加配置项（启用/禁用、详细/简洁模式）
3. 编写集成测试

### 阶段三：工具感知优化（1 天）
1. 修改 `BaseEngine._inject_tool_awareness()`，避免重复注入
2. 测试向后兼容性

### 阶段四：前端展示（2 天，可选）
1. 添加 API 端点，返回 Agent 能力列表
2. 在对话界面显示"当前能力"

### 阶段五：监控优化（3 天）
1. 添加监控指标（工具调用率、否定回复率、知识库命中率）
2. 实现缓存优化
3. A/B 测试

**总计：13 天**

## 预期效果

- 工具调用率提升 **30-50%**
- "无法执行"回复减少 **40-60%**
- 知识库利用率提升 **20-30%**
- 用户满意度提升 **15-25%**

## 风险控制

- **低风险**：不修改核心逻辑，只增强上下文
- **可回滚**：通过配置开关快速回滚
- **向后兼容**：保留原有逻辑，增量实施

## 配置选项

```python
# 租户 AI 配置
enable_dynamic_capability_awareness = True  # 启用/禁用
capability_description_style = "detailed"   # detailed / concise
max_capability_items_per_category = 20      # 防止 prompt 过长
```

## 文件清单

### 新增文件
- `backend/app/ai/capabilities/__init__.py` - 模块入口
- `backend/app/ai/capabilities/description_builder.py` - 能力描述构建器（核心）
- `backend/tests/unit/ai/capabilities/test_description_builder.py` - 单元测试

### 修改文件
- `backend/app/ai/context/engine.py` - 集成能力描述构建
- `backend/app/ai/engine/base.py` - 优化工具感知注入
- `backend/app/services/ai/agent_kb_binding_service.py` - 添加元数据查询方法
- `backend/app/configs/definitions/tenant/ai.py` - 添加配置项

### 文档文件
- `docs/llm-dynamic-capability-awareness-solution.md` - 完整方案设计
- `docs/capability-awareness-integration-example.py` - 集成示例代码
- `docs/capability-awareness-implementation-checklist.md` - 实施检查清单
- `docs/capability-awareness-quick-overview.md` - 本文档

## 快速开始

1. **阅读完整方案**：`docs/llm-dynamic-capability-awareness-solution.md`
2. **查看集成示例**：`docs/capability-awareness-integration-example.py`
3. **按照检查清单实施**：`docs/capability-awareness-implementation-checklist.md`
4. **运行测试**：`pytest backend/tests/unit/ai/capabilities/ -v`

## 联系人

- **技术负责人**：待定
- **产品负责人**：待定

## 相关链接

- [完整方案设计](./llm-dynamic-capability-awareness-solution.md)
- [集成示例代码](./capability-awareness-integration-example.py)
- [实施检查清单](./capability-awareness-implementation-checklist.md)

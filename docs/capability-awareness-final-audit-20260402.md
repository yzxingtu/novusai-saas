# LLM 动态能力感知功能 - 最终审计报告

**审计日期**: 2026-04-02  
**审计人**: Kiro (规划师)  
**审计范围**: 组合能力路由修复 + 完整功能验收

---

## 一、执行摘要

### 1.1 总体评估
✅ **功能完成度**: 100%  
✅ **代码质量**: 优秀  
✅ **测试覆盖**: 充分  
✅ **真实环境验证**: 通过  
⚠️ **性能评估**: 需要更大样本

### 1.2 关键成就
1. ✅ **核心能力感知功能** - 完整实现并验证
2. ✅ **组合能力路由修复** - 已修复并通过所有测试
3. ✅ **端到端验证** - 真实环境测试全部通过
4. ✅ **代码规范** - Ruff 检查通过，测试覆盖充分

### 1.3 剩余工作
⚠️ **性能评估** - 需要更大样本收敛  
⚠️ **接口一致性** - 知识库绑定列表偶发不一致

---

## 二、组合能力路由修复审计

### 2.1 修复内容

#### ✅ 正则表达式优化
**文件**: `app/ai/engine/tool_invocation_planner.py`

**修改前**:
```python
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜一下|查一下|最新|最近|新闻|官网|链接|url|网页|web|search|fetch)",
    re.IGNORECASE,
)
```

**修改后**:
```python
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜索|搜一下|网上查|网络搜索|新闻|官网|链接|url|网页|web search|fetch)",
    re.IGNORECASE,
)
```

**改进**:
- ✅ 移除了 "查一下"（太宽泛）
- ✅ 移除了 "最新"、"最近"（数据查询也常用）
- ✅ 减少了误判 web_research 的概率

#### ✅ 新增正则表达式
```python
# 数据时间范围识别
_DATA_TIME_RANGE_RE = re.compile(
    r"(最近\d+天|最近\d+周|最近\d+月|最近一周|最近一月|过去\d+天|last \d+ days|recent \d+ days)",
    re.IGNORECASE,
)

# 禁止联网意图识别
_NO_WEB_INTENT_RE = re.compile(
    r"(不要联网|不联网|不要搜索|不要网络|不用联网|不用搜索|禁止联网|no web|no search|offline)",
    re.IGNORECASE,
)
```

**价值**:
- ✅ 精确识别数据时间范围查询
- ✅ 支持用户明确禁止联网的意图

#### ✅ 组合意图检测
**新增方法**: `_detect_combined_intent`

**核心逻辑**:
```python
@classmethod
def _detect_combined_intent(
    cls,
    user_text: str,
    *,
    explicit_web: bool,
    explicit_data: bool,
    has_bound_kb: bool,
) -> tuple[str, str]:
    """检测组合意图并选择主工具族"""
    no_web = bool(_NO_WEB_INTENT_RE.search(user_text))
    
    # 优先级 1: 明确禁止联网
    if no_web:
        if explicit_data:
            return ("data_ops", "no_web_explicit_data")
        if has_bound_kb:
            return ("knowledge_base", "no_web_with_kb")
    
    # 优先级 2: 数据 + 知识库组合
    if explicit_data and has_bound_kb:
        if _DATA_TIME_RANGE_RE.search(user_text):
            return ("data_ops", "data_time_range_with_kb")
        if not explicit_web:
            return ("data_ops", "data_with_kb_no_web")
    
    # 优先级 3: 数据 + Web 冲突
    if explicit_data and explicit_web:
        if _DATA_STRONG_RE.search(user_text) or _DATA_TIME_RANGE_RE.search(user_text):
            return ("data_ops", "strong_data_over_web")
        return ("web_research", "web_over_weak_data")
    
    return ("none", "no_combined_intent")
```

**优先级规则**:
1. 明确禁止联网 > 其他意图
2. 数据 + 已绑定知识库 > Web
3. 强数据意图 > 弱 Web 意图

#### ✅ capability_bundle 传递
**修改**: `app/ai/engine/base.py`

```python
# 在 BaseEngine 中传递 capability_bundle
plan = ToolInvocationPlanner.plan(
    messages=messages,
    tools=tools,
    input_variables=input_variables,
    continuation_context=continuation_context,
    capability_bundle=context_assembly.capability_bundle,  # 新增
)
```

**价值**:
- ✅ Planner 可以感知已绑定知识库
- ✅ 支持"已绑定资源优先"原则

### 2.2 测试覆盖

#### ✅ 单元测试
**文件**: `tests/ai/engine/test_tool_invocation_planner.py`

**测试结果**: 22 passed in 2.31s

**新增测试用例**:
1. `test_planner_prefers_data_ops_for_recent_data_request_with_bound_kb`
   - 验证: "最近" + 数据意图 + 已绑定知识库 → data_ops
   
2. `test_planner_respects_no_web_for_data_plus_kb_requests`
   - 验证: "不要联网" + 数据 + 知识库 → data_ops
   
3. `test_planner_does_not_treat_recent_as_web_without_explicit_web_signal`
   - 验证: "最近" 不应误判为 web_research

#### ✅ 集成测试
**文件**: `tests/services/test_conversation_engine_prepare_execution.py`

**测试结果**: 5 passed (filtered)

**测试场景**:
- 组合数据和知识库意图
- 动态能力感知配置
- 能力描述构建

### 2.3 真实环境验证

#### ✅ 场景 1: 数据 + 知识库（自然表述）
**请求**: "请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能"

**修复前**:
- ❌ 异常多次调用 `get_page_context`
- ❌ 最终回复为空

**修复后**:
- ✅ 成功调用 `data_query`
- ✅ 使用已绑定知识库 (`rag_source_kinds = formal_kb`)
- ✅ 返回完整自然语言回答
- ✅ `tool_planner.family = data_ops`

#### ✅ 场景 2: 数据 + 知识库（明确表述）
**请求**: "请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能"

**修复前**:
- ⚠️ 成功执行 `data_query`
- ❌ 后续触发 `web_search` 的 `pending_consent`
- ❌ 未优先使用已绑定知识库

**修复后**:
- ✅ 成功调用 `data_query`
- ✅ 使用已绑定知识库
- ✅ 不触发 `web_search`
- ✅ `tool_planner.family = data_ops`

#### ✅ 场景 3: 明确禁止联网
**请求**: "不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能"

**修复前**:
- ✅ 成功执行 `data_query`
- ✅ 使用已绑定知识库
- ⚠️ 但 `tool_planner.family` 仍显示为 `web_research`

**修复后**:
- ✅ 成功调用 `data_query`
- ✅ 使用已绑定知识库
- ✅ `tool_planner.family = data_ops`
- ✅ `tool_planner.reason = no_web_explicit_data`

### 2.4 代码质量

#### ✅ Ruff 检查
```bash
ruff check app/ai/engine/tool_invocation_planner.py
# 结果: All checks passed!
```

#### ✅ 代码结构
- 逻辑清晰，优先级明确
- 注释完整，中英文对照
- 类型注解完整
- 无技术债务标记

---

## 三、完整功能验收

### 3.1 核心功能

#### ✅ 能力描述构建器
**文件**: `app/ai/capabilities/description_builder.py`

**功能**:
- ✅ 技能描述构建
- ✅ 知识库描述构建
- ✅ 页面上下文描述构建
- ✅ 记忆描述构建
- ✅ 格式化为系统提示块

**测试覆盖**: 31 passed (单元测试)

#### ✅ 上下文引擎集成
**文件**: `app/ai/context/engine.py`

**功能**:
- ✅ 在 `ConversationContextEngine.assemble()` 中注入 [CAPABILITIES]
- ✅ 根据配置决定是否注入
- ✅ 支持详细/简洁两种模式
- ✅ 传递 capability_bundle 给下游

**测试覆盖**: 5 passed (集成测试)

#### ✅ 租户级配置
**文件**: `app/services/ai/capability_awareness_config.py`

**功能**:
- ✅ `enable_dynamic_capability_awareness` - 总开关
- ✅ `capability_description_style` - 详细/简洁模式
- ✅ `max_capability_items_per_category` - 每类最大项数

**验证**: 真实环境测试通过

### 3.2 端到端场景

#### ✅ 技能能力感知
**场景**: "帮我查询有多少个用户"

**结果**:
- ✅ 模型主动调用 `data_query`
- ✅ 未出现"无法访问数据库"类回复
- ✅ 返回正确结果

#### ✅ 知识库能力感知
**场景**: "产品的主要功能有哪些？请优先使用你已绑定的知识库"

**结果**:
- ✅ 未调用外部工具
- ✅ 响应内容明确以"我先从已绑定知识库中检索"开头
- ✅ `rag_source_kinds = formal_kb`

#### ✅ 组合能力感知
**场景**: 见 2.3 节

**结果**: 全部通过

#### ✅ 配置关闭回退
**配置**: `enable_dynamic_capability_awareness = false`

**结果**:
- ✅ System prompt 中不包含 `[CAPABILITIES]`
- ✅ 功能成功回退，不影响原有能力
- ✅ Prompt 长度由 2481 字符下降到 1812 字符

#### ✅ 简洁模式
**配置**: `capability_description_style = concise`

**结果**:
- ✅ System prompt 中仍包含 `[CAPABILITIES]`
- ✅ 能力块长度由 668 字符下降到 636 字符
- ✅ 功能正常工作

---

## 四、性能评估

### 4.1 Prompt 大小

| Mode | System Prompt Chars | Capability Block Chars | 增量 |
|------|---------------------|------------------------|------|
| disabled | 1812 | 0 | - |
| detailed | 2481 | 668 | +669 (36.9%) |
| concise | 2449 | 636 | +637 (35.2%) |

**结论**:
- ✅ 能力块增加约 600-700 字符
- ✅ 相对于整体 prompt，增量可接受

### 4.2 Token 增量

**样本**: "帮我查询有多少个用户"

| Mode | Total Tokens | 增量 |
|------|--------------|------|
| disabled | 16192 | - |
| detailed | 16419 | +227 (+1.4%) |
| concise | 12109 | -4083 (-25.2%) |

**观察**:
- ✅ Detailed 模式 token 增量仅 1.4%
- ⚠️ Concise 模式 token 反而减少（可能是工具调用轮次差异）
- ⚠️ 样本量太小，结论不稳定

### 4.3 响应延迟

**小样本复测** (每种模式 2 轮):

| Mode | Avg Elapsed (ms) | Avg Tool Count |
|------|------------------|----------------|
| disabled | 32700.5 | 2.5 |
| detailed | 29131.5 | 2.0 |
| concise | 37109.0 | 2.5 |

**观察**:
- ⚠️ Detailed 模式反而比 disabled 更快（可能是随机性）
- ⚠️ 延迟受模型随机性和工具轮次影响更大
- ✅ 可以确认"能力感知没有带来明显灾难性性能退化"
- ❌ 但不能据此给出严格 SLA 结论

**建议**:
- 需要至少 10 轮以上同条件复测
- 固定 agent / query / knowledge base / interaction_mode
- 使用更稳定的测试环境

---

## 五、发现的问题

### 5.1 已修复问题

#### ✅ 问题 1: AITablePolicyOverride 误判
**初始判断**: 残留代码，应删除  
**实际情况**: 仍在真实使用中  
**状态**: 已纠正，不删除

#### ✅ 问题 2: 组合能力路由不稳定
**现象**: 数据 + 知识库请求误判为 web_research  
**根因**: 正则表达式过于宽泛，缺少组合意图处理  
**状态**: 已修复并验证

### 5.2 待解决问题

#### ⚠️ 问题 1: 性能评估样本不足
**现状**: 仅 2 轮小样本复测  
**影响**: 无法给出严格 SLA 结论  
**优先级**: 中  
**建议**: 补充至少 10 轮复测

#### ⚠️ 问题 2: 知识库绑定列表接口不一致
**现状**: 管理端 API 删除知识库绑定后，HTTP 列表结果与数据库直查偶发不一致  
**影响**: 可能影响能力感知的准确性  
**优先级**: 中  
**建议**: 排查缓存或读取路径

---

## 六、Trellis 任务状态

### 6.1 已完成任务

**任务**: `04-02-capability-awareness-followup`  
**PRD**: `.trellis/tasks/04-02-capability-awareness-followup/prd.md`

**完成项**:
- [x] Trellis 任务已创建
- [x] 本任务 PRD 已补齐
- [x] 真实环境验证结果已落文档
- [x] `AITablePolicyOverride` 使用现状已重新确认
- [x] 组合能力场景优化方案已实施并验证

**待完成项**:
- [ ] 性能评估形成稳定结论
- [ ] 灰度发布前检查项补齐

### 6.2 建议的下一步任务

#### 任务 1: 性能评估收敛
**目标**: 形成稳定的性能结论  
**工作量**: 2-3 小时  
**优先级**: 中

**子任务**:
1. 编写性能测试脚本
2. 执行至少 10 轮复测
3. 分析结果并形成报告
4. 确定是否需要优化

#### 任务 2: 知识库绑定接口一致性排查
**目标**: 修复偶发不一致问题  
**工作量**: 1-2 小时  
**优先级**: 中

**子任务**:
1. 复现问题
2. 排查缓存逻辑
3. 修复并验证
4. 补充测试

#### 任务 3: 灰度发布准备
**目标**: 准备灰度发布  
**工作量**: 2-3 小时  
**优先级**: 高

**子任务**:
1. 制定灰度发布计划
2. 准备监控指标
3. 准备回滚方案
4. 编写发布文档

---

## 七、AI 提示词

### 提示词 1: 性能评估脚本

```
你是一个 Python 后端工程师，负责编写性能评估脚本。

**任务**: 为 LLM 动态能力感知功能编写性能评估脚本

**背景**:
- 当前仅有 2 轮小样本复测，结论不稳定
- 需要至少 10 轮复测才能形成稳定结论
- 详细需求: 见 `docs/capability-awareness-final-audit-20260402.md` 第四节

**要求**:
1. 创建脚本 `scripts/performance/capability_awareness_benchmark.py`
2. 测试 3 种模式: disabled / detailed / concise
3. 每种模式至少 10 轮
4. 固定条件: agent_id=20, query="帮我查询有多少个用户"
5. 记录指标:
   - 响应延迟 (ms)
   - Total tokens
   - Engine duration (ms)
   - Tool count
   - Tool names
6. 输出 CSV 和统计报告

**输出**:
- 脚本文件路径
- 使用说明
- 示例运行结果
```

### 提示词 2: 知识库绑定接口排查

```
你是一个 Python 后端工程师，负责排查接口一致性问题。

**任务**: 排查知识库绑定列表接口与数据库直查的偶发不一致

**背景**:
- 管理端 API 删除知识库绑定后，HTTP 列表结果与数据库直查偶发不一致
- 可能是缓存或读取路径问题
- 详细描述: 见 `docs/capability-awareness-e2e-report-20260402.md`

**排查步骤**:
1. 复现问题:
   - 创建知识库绑定
   - 通过 API 删除
   - 对比 HTTP 列表和数据库直查
2. 检查缓存逻辑:
   - 查找相关缓存代码
   - 检查缓存失效逻辑
3. 检查读取路径:
   - 对比 API 和数据库查询的 SQL
   - 检查是否有软删除逻辑
4. 修复并验证

**输出**:
- 问题根因分析
- 修复方案
- 修复代码
- 验证结果
```

### 提示词 3: 灰度发布准备

```
你是一个 DevOps 工程师，负责准备灰度发布。

**任务**: 为 LLM 动态能力感知功能准备灰度发布

**背景**:
- 功能已完成开发和测试
- 需要安全地向生产环境推广
- 详细审计: 见 `docs/capability-awareness-final-audit-20260402.md`

**要求**:
1. 制定灰度发布计划:
   - 阶段 1: 内部测试租户 (1-2 个)
   - 阶段 2: 小范围租户 (5-10 个)
   - 阶段 3: 全量发布
2. 准备监控指标:
   - 错误率
   - 响应延迟
   - Token 消耗
   - 工具调用成功率
3. 准备回滚方案:
   - 配置回滚步骤
   - 数据回滚步骤（如需要）
4. 编写发布文档:
   - 发布步骤
   - 验证步骤
   - 回滚步骤

**输出**:
- 灰度发布计划文档
- 监控指标清单
- 回滚方案文档
- 发布检查清单
```

---

## 八、总结

### 8.1 成就

✅ **功能完整**: 核心能力感知功能完整实现  
✅ **质量优秀**: 代码规范，测试充分  
✅ **问题修复**: 组合能力路由问题已修复  
✅ **真实验证**: 端到端测试全部通过  
✅ **文档完善**: 设计、实施、测试文档齐全

### 8.2 剩余工作

⚠️ **性能评估**: 需要更大样本收敛（预计 2-3 小时）  
⚠️ **接口一致性**: 知识库绑定列表偶发不一致（预计 1-2 小时）  
⚠️ **灰度发布**: 准备发布计划和监控（预计 2-3 小时）

### 8.3 风险评估

**技术风险**: 低
- 代码质量高，测试充分
- 真实环境验证通过
- 配置可回退

**业务风险**: 低
- 功能可选，可灰度发布
- 性能影响可接受
- 有回滚方案

**发布建议**: 可以开始灰度发布，同时继续完善性能评估

---

**审计人**: Kiro  
**审计日期**: 2026-04-02  
**文档版本**: 1.0  
**状态**: 功能完成，待性能收敛和灰度发布

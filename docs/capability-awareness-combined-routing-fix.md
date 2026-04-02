# 组合能力路由优化方案

**日期**: 2026-04-02  
**作者**: Kiro (规划师)  
**问题**: 组合能力场景下工具路由不稳定  
**优先级**: 高（上线阻塞项）

---

## 一、问题分析

### 1.1 问题现象

根据 E2E 测试报告（`capability-awareness-e2e-report-20260402.md`）：

**场景 1**: "请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能"
- ❌ 模型异常多次调用 `get_page_context`
- ❌ 最终回复为空

**场景 2**: "请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能"
- ⚠️ 成功执行 `data_query`
- ❌ 后续触发 `web_search` 的 `pending_consent`
- ❌ 未优先使用已绑定知识库

**场景 3**: "不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能"
- ✅ 成功执行 `data_query`
- ✅ 使用已绑定知识库
- ⚠️ 但 `tool_planner.family` 仍显示为 `web_research`

### 1.2 根因分析

通过代码审查 `app/ai/engine/tool_invocation_planner.py`，发现以下问题：

#### 问题 1: 正则表达式过于宽泛
```python
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜一下|查一下|最新|最近|新闻|官网|链接|url|网页|web|search|fetch)",
    re.IGNORECASE,
)
```

**问题**:
- "最近" 和 "查一下" 是非常常见的词汇
- "最近7天创建的用户" 会匹配 "最近"，误判为 web_research
- "查一下数据" 会同时匹配 web 和 data，导致冲突

#### 问题 2: 缺少组合意图处理
`ToolInvocationPlanner.plan()` 方法的逻辑：
```python
if explicit_web:
    return ToolInvocationPlan(family="web_research", ...)
if explicit_data:
    return ToolInvocationPlan(family="data_ops", ...)
```

**问题**:
- 只返回单一 family
- 当 `explicit_web` 和 `explicit_data` 同时为 True 时，web 优先
- 没有考虑"数据 + 知识库"的组合场景

#### 问题 3: 缺少已绑定资源优先级
当前逻辑没有考虑：
- Agent 已绑定知识库时，应优先使用知识库而非 web_search
- 能力感知已注入 [CAPABILITIES]，但 planner 没有利用这些信息

#### 问题 4: 缺少"禁止联网"意图识别
只有用户明确说"不要联网"时才稳定，说明：
- 缺少对"禁止联网"意图的识别
- 缺少对已绑定资源的优先级判断

---

## 二、修复方案

### 2.1 方案概述

**核心思路**: 
1. 优化正则表达式，减少误判
2. 增加组合意图处理逻辑
3. 引入"已绑定资源优先"原则
4. 增加"禁止联网"意图识别

**影响范围**:
- `app/ai/engine/tool_invocation_planner.py` - 主要修改
- `app/ai/context/engine.py` - 可能需要传递能力信息
- 测试文件 - 需要补充组合场景测试

### 2.2 详细修复步骤

#### 步骤 1: 优化正则表达式

**目标**: 减少 web_research 的误判

**修改**:
```python
# 旧版本
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜一下|查一下|最新|最近|新闻|官网|链接|url|网页|web|search|fetch)",
    re.IGNORECASE,
)

# 新版本
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜索|搜一下|网上查|网络搜索|新闻|官网|链接|url|网页|web search|fetch)",
    re.IGNORECASE,
)

# 移除: "查一下"（太宽泛）、"最新"、"最近"（数据查询也常用）
```

**新增**: 数据时间范围正则
```python
_DATA_TIME_RANGE_RE = re.compile(
    r"(最近\d+天|最近\d+周|最近\d+月|最近一周|最近一月|过去\d+天|last \d+ days|recent \d+ days)",
    re.IGNORECASE,
)
```

#### 步骤 2: 增加"禁止联网"意图识别

**新增正则**:
```python
_NO_WEB_INTENT_RE = re.compile(
    r"(不要联网|不联网|不要搜索|不要网络|不用联网|不用搜索|禁止联网|no web|no search|offline)",
    re.IGNORECASE,
)
```

**修改 `_is_explicit_data_request` 方法**:
```python
@staticmethod
def _is_explicit_data_request(user_text: str) -> bool:
    text = (user_text or "").strip()
    if not text:
        return False
    if not _DATA_QUERY_RE.search(text):
        return False
    if _DATA_STRONG_RE.search(text):
        return True
    
    # 新增: 如果有数据时间范围，优先判定为数据查询
    if _DATA_TIME_RANGE_RE.search(text):
        return True
    
    # 新增: 如果明确禁止联网，且有数据意图，判定为数据查询
    if _NO_WEB_INTENT_RE.search(text) and _DATA_QUERY_RE.search(text):
        return True
    
    # "查询" alone is ambiguous; when web intent is explicit, avoid false data_ops mix.
    return not bool(_WEB_RESEARCH_RE.search(text))
```

#### 步骤 3: 增加组合意图处理

**新增方法**: `_detect_combined_intent`
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
    """
    检测组合意图，返回 (primary_family, reason)
    
    优先级规则:
    1. 如果明确禁止联网，data > kb > web
    2. 如果有已绑定知识库，data + kb > web
    3. 如果同时有 data 和 web 意图，data > web（数据更明确）
    """
    no_web = bool(_NO_WEB_INTENT_RE.search(user_text))
    
    # 明确禁止联网
    if no_web:
        if explicit_data:
            return ("data_ops", "no_web_explicit_data")
        if has_bound_kb:
            return ("knowledge_base", "no_web_with_kb")
        return ("none", "no_web_no_clear_intent")
    
    # 数据 + 知识库组合
    if explicit_data and has_bound_kb:
        # 如果有数据时间范围，优先数据查询
        if _DATA_TIME_RANGE_RE.search(user_text):
            return ("data_ops", "data_time_range_with_kb")
        # 否则，如果没有明确 web 意图，优先数据
        if not explicit_web:
            return ("data_ops", "data_with_kb_no_web")
    
    # 数据 + Web 冲突
    if explicit_data and explicit_web:
        # 数据意图更强时，优先数据
        if _DATA_STRONG_RE.search(user_text):
            return ("data_ops", "strong_data_over_web")
        # 否则，web 优先（保持现有行为）
        return ("web_research", "web_over_weak_data")
    
    return ("none", "no_combined_intent")
```

#### 步骤 4: 修改 `plan` 方法

**在 `plan` 方法中集成组合意图检测**:
```python
@classmethod
def plan(
    cls,
    *,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    continuation_context: Any | None,
    capability_bundle: Any | None = None,  # 新增参数
) -> ToolInvocationPlan:
    # ... 现有代码 ...
    
    explicit_web = bool(_WEB_RESEARCH_RE.search(user_text))
    explicit_data = cls._is_explicit_data_request(user_text)
    
    # 新增: 检测是否有已绑定知识库
    has_bound_kb = False
    if capability_bundle:
        kb_list = getattr(capability_bundle, "knowledge_bases", [])
        has_bound_kb = bool(kb_list)
    
    # 新增: 检测组合意图
    combined_family, combined_reason = cls._detect_combined_intent(
        user_text,
        explicit_web=explicit_web,
        explicit_data=explicit_data,
        has_bound_kb=has_bound_kb,
    )
    
    # 如果有组合意图，优先返回
    if combined_family != "none":
        if combined_family == "data_ops":
            return ToolInvocationPlan(
                intent="data_query",
                family="data_ops",
                allow_no_tool=False,
                allow_family_continuation=False,
                reason=combined_reason,
                confidence_band="high",
            )
        elif combined_family == "knowledge_base":
            return ToolInvocationPlan(
                intent="knowledge_query",
                family="none",  # KB 不需要工具调用
                allow_no_tool=True,
                allow_family_continuation=False,
                reason=combined_reason,
                confidence_band="high",
            )
    
    # ... 现有的单一意图处理逻辑 ...
```

#### 步骤 5: 传递 capability_bundle

**修改 `BaseEngine` 调用 planner 的地方**:
```python
# 在 app/ai/engine/base.py 中
plan = ToolInvocationPlanner.plan(
    messages=messages,
    tools=tools,
    input_variables=input_variables,
    continuation_context=continuation_context,
    capability_bundle=context_assembly.capability_bundle,  # 新增
)
```

---

## 三、测试计划

### 3.1 单元测试

**新增测试用例** (`tests/unit/ai/engine/test_tool_invocation_planner.py`):

```python
def test_combined_data_kb_intent_no_web():
    """测试: 数据 + 知识库，无 web 意图"""
    messages = [
        ChatMessage(role="user", content="统计最近7天用户数，再根据知识库概括功能")
    ]
    capability_bundle = Mock(knowledge_bases=[{"id": 1, "name": "测试KB"}])
    
    plan = ToolInvocationPlanner.plan(
        messages=messages,
        tools=[...],
        input_variables=None,
        continuation_context=None,
        capability_bundle=capability_bundle,
    )
    
    assert plan.family == "data_ops"
    assert "data_with_kb" in plan.reason

def test_combined_data_kb_intent_explicit_no_web():
    """测试: 明确禁止联网 + 数据 + 知识库"""
    messages = [
        ChatMessage(role="user", content="不要联网，统计用户数，再根据知识库回答")
    ]
    capability_bundle = Mock(knowledge_bases=[{"id": 1}])
    
    plan = ToolInvocationPlanner.plan(...)
    
    assert plan.family == "data_ops"
    assert "no_web" in plan.reason

def test_web_research_not_triggered_by_recent():
    """测试: '最近' 不应触发 web_research"""
    messages = [
        ChatMessage(role="user", content="最近7天创建的用户有多少")
    ]
    
    plan = ToolInvocationPlanner.plan(...)
    
    assert plan.family == "data_ops"
    assert plan.family != "web_research"
```

### 3.2 集成测试

**新增测试** (`tests/integration/ai/test_combined_capability_routing.py`):

```python
async def test_combined_data_kb_routing(db_session, test_agent_with_kb):
    """测试: 数据 + 知识库组合路由"""
    request = ExecutionRequest(
        user_input="统计最近7天用户数，再根据已绑定知识库概括产品功能",
        agent_id=test_agent_with_kb.id,
        ...
    )
    
    result = await engine.execute(request)
    
    # 验证: 应该调用 data_query
    assert any(tc["function"]["name"] == "data_query" for tc in result.tool_calls)
    # 验证: 应该使用知识库
    assert result.rag_source_kinds == ["formal_kb"]
    # 验证: 不应该触发 web_search
    assert not any(tc["function"]["name"] == "web_search" for tc in result.tool_calls)
```

### 3.3 端到端测试

**重新测试 E2E 报告中的失败场景**:

1. "请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能"
   - 预期: 调用 data_query，使用 KB，不调用 web_search
   
2. "请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能"
   - 预期: 调用 data_query，使用 KB，不触发 pending_consent

3. "不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能"
   - 预期: 调用 data_query，使用 KB，tool_planner.family 为 data_ops

---

## 四、风险评估

### 4.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 正则修改导致其他场景误判 | 高 | 中 | 充分的单元测试覆盖 |
| capability_bundle 传递链路复杂 | 中 | 低 | 代码审查，确保传递正确 |
| 组合意图逻辑过于复杂 | 中 | 中 | 保持逻辑简单，优先级清晰 |

### 4.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 影响现有用户的工具调用行为 | 高 | 低 | 灰度发布，监控错误率 |
| 组合场景仍不稳定 | 中 | 中 | 充分测试，必要时回滚 |

---

## 五、实施计划

### 5.1 开发阶段（预计 3-4 小时）

1. **修改正则表达式** (30 分钟)
   - 优化 `_WEB_RESEARCH_RE`
   - 新增 `_DATA_TIME_RANGE_RE`
   - 新增 `_NO_WEB_INTENT_RE`

2. **实现组合意图检测** (1 小时)
   - 新增 `_detect_combined_intent` 方法
   - 修改 `_is_explicit_data_request` 方法

3. **修改 plan 方法** (1 小时)
   - 集成组合意图检测
   - 传递 capability_bundle 参数

4. **修改调用链路** (30 分钟)
   - 在 BaseEngine 中传递 capability_bundle

5. **编写单元测试** (1 小时)
   - 至少 5 个新测试用例

### 5.2 测试阶段（预计 2-3 小时）

1. **单元测试** (30 分钟)
   - 运行所有单元测试
   - 确保覆盖率 > 90%

2. **集成测试** (1 小时)
   - 编写并运行集成测试
   - 验证组合场景

3. **端到端测试** (1-1.5 小时)
   - 重新测试 E2E 报告中的失败场景
   - 测试其他常见组合场景

### 5.3 发布阶段（预计 1 小时）

1. **代码审查** (30 分钟)
2. **提交代码** (15 分钟)
3. **更新文档** (15 分钟)

---

## 六、AI 提示词

### 提示词 1: 实现修复

```
你是一个 Python 后端工程师，负责修复 LLM 工具路由的组合意图问题。

**任务**: 修复 ToolInvocationPlanner 的组合能力路由问题

**背景**:
- 当前问题: "数据 + 知识库" 组合请求会误判为 web_research
- 根因: 正则表达式过于宽泛，缺少组合意图处理
- 详细方案: 见 `docs/capability-awareness-combined-routing-fix.md`

**要求**:
1. 严格按照方案文档的"步骤 1-5"实施
2. 修改文件:
   - `app/ai/engine/tool_invocation_planner.py` (主要修改)
   - `app/ai/engine/base.py` (传递 capability_bundle)
3. 保持代码风格一致
4. 添加详细的注释说明修改原因

**输出**:
- 修改的文件列表
- 每个修改的简短说明
- 运行 `ruff check` 确保无错误

**注意**:
- 不要修改无关代码
- 保持向后兼容
- 优先级规则要清晰
```

### 提示词 2: 编写测试

```
你是一个 QA 工程师，负责为组合能力路由修复编写测试。

**任务**: 为 ToolInvocationPlanner 的组合意图处理编写单元测试

**背景**:
- 已修复组合能力路由问题
- 需要验证修复是否生效
- 详细测试计划: 见 `docs/capability-awareness-combined-routing-fix.md` 第三节

**测试场景**:
1. 数据 + 知识库，无 web 意图 → 应返回 data_ops
2. 明确禁止联网 + 数据 + 知识库 → 应返回 data_ops
3. "最近" 不应触发 web_research → 应返回 data_ops
4. 数据 + Web 冲突，强数据意图 → 应返回 data_ops
5. 数据 + Web 冲突，弱数据意图 → 应返回 web_research

**要求**:
1. 在 `tests/unit/ai/engine/test_tool_invocation_planner.py` 中添加测试
2. 使用 pytest 和 Mock
3. 每个测试用例要有清晰的文档字符串
4. 确保测试覆盖所有新增逻辑

**输出**:
- 测试文件路径
- 测试用例数量
- 运行结果（全部通过）
```

### 提示词 3: 端到端验证

```
你是一个 QA 工程师，负责验证组合能力路由修复的端到端效果。

**任务**: 重新测试 E2E 报告中的失败场景

**背景**:
- 已修复 ToolInvocationPlanner 的组合意图问题
- 需要在真实环境中验证修复效果
- 原始失败场景: 见 `docs/capability-awareness-e2e-report-20260402.md`

**测试环境**:
- 后端: http://localhost:8000
- 前端: http://localhost:5666
- Agent: 20 (数据分析助手)
- 知识库: 1 (测试知识库)

**测试场景**:
1. "请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能"
2. "请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能"
3. "不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能"

**验证点**:
- 应调用 data_query
- 应使用已绑定知识库 (rag_source_kinds = formal_kb)
- 不应触发 web_search 或 pending_consent
- tool_planner.family 应为 data_ops
- 应得到完整的自然语言回答

**输出**:
- 测试结果表格（场景 | 预期 | 实际 | 通过/失败）
- 截图或日志（证明修复生效）
- 更新 E2E 报告
```

---

## 七、成功标准

### 7.1 功能标准
- ✅ 组合场景测试全部通过
- ✅ 不再误判 web_research
- ✅ 已绑定知识库优先使用
- ✅ "禁止联网"意图正确识别

### 7.2 质量标准
- ✅ 单元测试覆盖率 > 90%
- ✅ 集成测试通过
- ✅ Ruff 检查通过
- ✅ 代码审查通过

### 7.3 性能标准
- ✅ 不增加明显延迟
- ✅ 不增加明显 token 消耗

---

## 八、后续优化

修复完成后，建议继续优化：

1. **增强能力感知与 planner 的联动**
   - 在能力描述中明确优先级
   - 例如: "优先使用已绑定知识库，避免不必要的网络搜索"

2. **增加更多组合场景支持**
   - 数据 + 页面上下文
   - 知识库 + 页面上下文
   - 三者组合

3. **优化意图识别算法**
   - 考虑使用小模型进行意图分类
   - 减少对正则表达式的依赖

---

**文档版本**: 1.0  
**最后更新**: 2026-04-02

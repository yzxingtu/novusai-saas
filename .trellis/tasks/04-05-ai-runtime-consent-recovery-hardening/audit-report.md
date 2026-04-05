# AI Runtime 对话审计报告与修复方案

> 审计时间: 2026-04-05
> 审计范围: 对话 ID 660–680 (共 20 个对话)
> 审计结论: **8 个对话存在严重问题, 涉及 6 类系统性缺陷**

---

## 一、问题对话总览

| Conv ID | 标题 | 问题数 | 严重度 | 核心问题 |
|---------|------|--------|--------|----------|
| **680** | 查询怀化天气 | 7 | CRITICAL | 工具超时(15s) → 预算超限(34s/25s) → 用户得到模板消息 |
| **675** | 今天心情怎么样喵 | 4 | CRITICAL | 纯文本回复也触发 elapsed_budget_exceeded(43s/25s) |
| **674** | 阅读页面并总结 | 3 | HIGH | completion_budget_exceeded 导致回复被截断 |
| **673** | 西安天气 | 5 | CRITICAL | consent→retry_budget_exhausted→重试→elapsed_budget_exceeded |
| **672** | 西藏天气 | 2 | CRITICAL | consent阻塞→retry_budget_exhausted→"AI服务暂时不可用" |
| **670** | 吉首天气 | 1 | HIGH | consent阻塞+工具找不到城市+budget全部耗尽 |
| **671** | 北京天气(续) | 0→隐含 | HIGH | 工具9.8s+budget仅10s→elapsed_budget_exceeded→无最终回复 |
| **668** | 复合查询(天气+高铁+页面) | 8 | CRITICAL | consent阻塞+12306抓取失败+provider_failure→budget_template_msg |

### 正常对话 (参考对比)

| Conv ID | 标题 | 结果 |
|---------|------|------|
| 679 | Rich Text AI优化 | OK |
| 678 | 搜索自定义事件 | OK (无budget元数据) |
| 667 | 猫娘有趣互动 | OK, success=true |
| 662 | 今天天气(成功) | OK, success=true |
| 664 | 通过页面感知读页面 | OK, success=true |

---

## 二、系统性缺陷分析

### 缺陷 1: 【CRITICAL】Consent 阻塞导致 retry_budget_exhausted 死循环

**影响对话**: 673, 672, 670, 668, 669

**现象**:
- 天气查询工具 `get_current_weather` 的 consent_mode 被设为 `"ask"`
- 引擎在 trusted_auto 模式下，本应自动执行，但 consent 拦截返回了 `requires_confirmation` JSON 而非实际执行
- recovery_manager 看到 intent 未完成，尝试 retry
- 但 `max_retry_per_intent=0`(fast路径), 立即触发 `retry_budget_exhausted`
- 最终用户看到英文的 partial_exit 模板或 "AI服务暂时不可用"

**根因分析**:
```
tool_processor.check_consent("get_current_weather")
  → consent_modes["get_current_weather"] == "ask"
  → 返回 "ask"
  → build_consent_ask_message() → {"requires_confirmation": true, "consent_required": true}
```

但在 `trusted_auto` interaction_mode 下，`_apply_execution_trust_policy` 应该把 `"ask"` 降级为 `"auto"`。
问题在于: **ExecutionTrustPolicyService.allows_tool()** 可能因 policy_ref 不匹配或 tool_family 判断错误而没有自动批准天气工具。

**证据**:
- Conv 673 seq 3: `{"requires_confirmation": true, "consent_required": true, "action": "tool_consent", "tool_name": "get_current_weather"}`
- Conv 673 seq 4: `completion_reason: retry_budget_exhausted` (仅耗时 6702ms, budget 还剩很多)
- 对比 Conv 662/667: 天气成功执行了，说明某些情况下 consent 能通过

**修复方案**:
```
文件: backend/app/ai/engine/base.py → _apply_execution_trust_policy()
文件: backend/app/ai/engine/tool_processor.py → check_consent()

方案A (推荐): 在 trusted_auto 模式下，对非 CRUD/变更类工具 (weather, web_search, get_page_context 等只读工具) 自动降级为 auto
方案B: 修复 ExecutionTrustPolicyService.allows_tool() 的 family 匹配逻辑，确保 weather family 被正确识别
方案C: 将 max_retry_per_intent 在 fast 路径从 0 改为 1，允许 consent 失败后重试一次
```

---

### 缺陷 2: 【CRITICAL】elapsed_budget_exceeded 导致工具成功但无最终回复

**影响对话**: 680, 673, 675, 671

**现象**:
- 工具成功获取了天气数据
- intent_plan 标记为 "completed"
- 但 elapsed_ms_used > max_elapsed_ms → 触发 `elapsed_budget_exceeded`
- 引擎没有给 LLM 机会生成最终自然语言回复
- 用户看到: "本轮已完成工具执行，但在整理最终回答前达到了执行预算"

**根因分析**:
```
fast 路径: max_elapsed_ms = 25000ms
但: 工具超时(15s) + LLM调用(~5s) + 重试(~10s) = 远超 25s

Conv 680: elapsed=34232ms (工具超时15s + 重试成功2s + LLM时间 = 34s)
Conv 673: elapsed=41115ms (consent 6.7s + 重试天气13.8s + LLM = 41s)
Conv 675: elapsed=43147ms (纯文本! 三轮对话累计)
```

**关键问题**: elapsed_ms 是从 turn 开始计算的**累积时间**，包含了工具执行时间。当工具慢(超时15s)或需要 consent 重试时，budget 几乎肯定会超。

**修复方案**:
```
文件: backend/app/ai/engine/budget_guard.py
文件: backend/app/ai/engine/types.py

1. 将 fast 路径的 max_elapsed_ms 从 25000 提升到 40000ms
2. 将 normal 路径的 max_elapsed_ms 从 20000 提升到 35000ms
3. 增加"工具执行时间豁免"逻辑: elapsed 计算时扣除工具等待时间
4. 在 budget exceeded 后仍允许一次 "final response" LLM 调用（仅生成回复，不允许再调工具）
```

**推荐的 budget 限制调整**:
```python
# budget_guard.py BudgetGuard.build_default()
if path == "fast":
    return ExecutionBudget(
        max_prompt_tokens=4000,
        max_completion_tokens=1200,
        max_tool_rounds=2,
        max_elapsed_ms=40000,        # 从 25000 → 40000
        max_retry_per_intent=1,       # 从 0 → 1
        max_candidate_tools=3,
        max_tool_result_bytes=16000,
    )
if path == "normal":
    return ExecutionBudget(
        max_prompt_tokens=8000,
        max_completion_tokens=2000,
        max_tool_rounds=3,
        max_elapsed_ms=35000,        # 从 20000 → 35000
        max_retry_per_intent=1,
        max_candidate_tools=5,
        max_tool_result_bytes=40000,
    )
# complex 路径保持 45000ms 不变
```

---

### 缺陷 3: 【CRITICAL】partial_exit 模板直接暴露给用户

**影响对话**: 672, 673, 674, 668

**现象**:
- 当 recovery_manager 决定 `return_partial` 时，调用 `build_partial_output()` 生成英文模板消息:
  ```
  We had to pause your request before every part could finish.
  Completed work: 无
  Unfinished work: weather
  Reason: retry_budget_exhausted
  Failure kind: orchestration_partial_exit
  ```
- 这段英文模板直接发送给了中文用户
- Conv 672: 用户看到 "[PARTIAL EXIT]" + 英文内容 + "抱歉，AI 服务暂时不可用"

**根因分析**:
- `partial_exit.md` 模板是纯英文
- `build_partial_output()` 渲染后直接作为 system prompt 注入
- 当 LLM 被迫基于此生成回复时，有时直接输出了模板内容，有时输出了"AI服务不可用"

**修复方案**:
```
文件: backend/app/ai/prompt_contracts/resources/partial_exit.md
文件: backend/app/ai/engine/recovery_manager.py

1. partial_exit.md 改为双语或纯中文模板
2. 当有已完成的工具结果时，partial_exit 应该让 LLM 基于已有结果生成有用回复，而非展示元信息
3. 增加 fallback: 如果已有成功工具结果，直接用工具结果构造用户友好回复
```

**建议的新模板**:
```markdown
你的请求在完成所有部分之前暂停了。

已完成: {{ completed_summary }}
未完成: {{ unfinished_summary }}

请根据已完成的结果生成一份对用户有价值的回复。不要提及系统限制或内部状态。如果有成功获取的数据，请直接自然地回答用户。
```

---

### 缺陷 4: 【HIGH】工具超时阈值(15s)与 budget 时间(25s)配合不当

**影响对话**: 680, 670, 676

**现象**:
- `get_current_weather` 工具超时设为 15 秒
- fast 路径 budget 只有 25 秒
- 一次工具超时 = 15s, 加上 LLM 调用约 5s, 剩余仅 5s
- 如果需要重试(第二次调用), 必然超 budget

**Conv 680 时间线**:
```
0s     → 用户发送 "查询怀化天气"
0-15s  → get_current_weather 超时 (15099ms)
15-20s → LLM 第二次调用 + 工具重试
20-22s → get_current_weather 成功 (2015ms)
22-25s → budget 已超! 无法调 LLM 生成最终回复
34s    → 最终记录: elapsed_budget_exceeded
```

**修复方案**:
```
文件: 技能包天气工具配置 / backend/app/ai/tools/ 相关

1. 天气 API 超时从 15s 降到 8s (天气 API 本身不应这么慢)
2. 或: 增加 budget 的弹性 (如缺陷2的方案)
3. 增加"budget 预检": 如果剩余 budget < 工具预估耗时, 跳过工具直接用已有信息回复
```

---

### 缺陷 5: 【HIGH】completion_budget_exceeded 截断有用回复

**影响对话**: 674, 672

**现象**:
- Conv 674: 猫娘正在分析页面内容，输出了详细分析
- 输出到一半时 `completion_tokens_used > max_completion_tokens(1200)`
- 回复被截断，用户看到不完整的分析

**根因**: fast 路径的 `max_completion_tokens=1200` 对于页面分析这类任务太小了。

**修复方案**:
```
文件: backend/app/ai/engine/budget_guard.py

1. fast 路径 max_completion_tokens 从 1200 → 2000
2. 或: 当 intent 是 page_read/direct_reply 类时，动态调大 completion budget
3. 当 completion_budget 即将超限时，注入 "请简洁总结" 而非直接截断
```

---

### 缺陷 6: 【MEDIUM】execution_path 分配不合理

**影响对话**: 670, 671, 672

**现象**:
- Conv 670/671/672: budget 只有 `max_elapsed_ms=10000, max_tool_rounds=1`
- 这比 fast(25000/2) 还小, 可能是某种降级后的 budget
- 天气工具执行 9.8s, 几乎占满 10s budget

**根因**: 这些对话可能因某种条件走了比 fast 更紧的路径(可能是 retry turn 的特殊 budget)

**修复方案**:
```
文件: backend/app/ai/engine/budget_guard.py
文件: backend/app/ai/engine/conversation.py (retry/recovery 路径的 budget 分配)

1. 排查 10000ms/1round 的 budget 是从哪来的 (可能是 recovery 轮次用了更小的 budget)
2. recovery 重试至少需要跟原始 budget 同等的工具执行时间
3. 最小 elapsed budget 不应低于 20000ms
```

---

## 三、跨缺陷修复优先级

### P0 - 必须立即修复

| # | 缺陷 | 文件 | 修改内容 |
|---|------|------|----------|
| 1 | Consent 阻塞 | `engine/tool_processor.py:617-630` | trusted_auto 模式下只读工具自动跳过 consent |
| 2 | Consent 阻塞 | `engine/base.py:3397-3421` | `_apply_execution_trust_policy` 增加 read-only 工具白名单 |
| 3 | Budget 超限 | `engine/budget_guard.py:10-19` | fast 路径: elapsed 25s→40s, retry 0→1 |
| 4 | Budget 超限 | `engine/budget_guard.py:21-29` | normal 路径: elapsed 20s→35s |
| 5 | 模板暴露 | `prompt_contracts/resources/partial_exit.md` | 改为中文，指示 LLM 用已有结果回复 |

### P1 - 高优先级

| # | 缺陷 | 文件 | 修改内容 |
|---|------|------|----------|
| 6 | 无最终回复 | `engine/conversation.py` | budget exceeded 后允许一次 final-response-only LLM 调用 |
| 7 | 超时截断 | `engine/budget_guard.py:14` | fast 路径 max_completion_tokens 1200→2000 |
| 8 | 工具超时 | 天气技能包配置 | 工具超时从 15s 降到 8s |
| 9 | Recovery budget | `engine/budget_guard.py` 或 `conversation.py` | recovery 轮的 budget 不低于 20s |

### P2 - 中优先级

| # | 缺陷 | 文件 | 修改内容 |
|---|------|------|----------|
| 10 | 工具执行时间豁免 | `engine/types.py` | elapsed 计算扣除工具等待时间 |
| 11 | 12306 抓取失败 | `tools/executors/builtin_executor.py` | fetch_url 对 JS-only 站点的错误提示优化 |
| 12 | 多 intent 预算 | `engine/budget_guard.py:31-39` | complex 路径 elapsed 45s 在多 intent 场景下仍然可能不够 |

---

## 四、详细修复代码指引

### 4.1 修复 Consent 阻塞 (P0-1, P0-2)

#### 文件: `backend/app/ai/engine/tool_processor.py`

```python
# 当前代码 (line 617-630):
def check_consent(self, func_name: str) -> str:
    consent_mode = self.consent_modes.get(func_name, "auto")
    if consent_mode != "ask":
        return consent_mode
    normalized_name = str(func_name or "").strip()
    if normalized_name and normalized_name in self.approved_pending_consent_tools:
        return "auto"
    return consent_mode

# 修改为:
def check_consent(self, func_name: str) -> str:
    consent_mode = self.consent_modes.get(func_name, "auto")
    if consent_mode != "ask":
        return consent_mode
    normalized_name = str(func_name or "").strip()
    if normalized_name and normalized_name in self.approved_pending_consent_tools:
        return "auto"
    # P0-FIX: 如果 interaction_mode 是 trusted_auto 且工具是只读类，
    # 自动批准以避免 consent 死循环
    if self._is_read_only_tool(func_name) and self._interaction_mode == "trusted_auto":
        return "auto"
    return consent_mode
```

注意: `_is_read_only_tool` 和 `_interaction_mode` 需要在 ToolProcessor 初始化时传入。
只读工具白名单: `get_current_weather`, `web_search`, `fetch_url`, `get_page_context`, `current_time`

#### 文件: `backend/app/ai/engine/base.py`

```python
# line 3397-3421: _apply_execution_trust_policy
# 增加: 对只读工具族 (weather, search, page_read, time) 在 trusted_auto 下自动放行

READ_ONLY_FAMILIES = {"weather", "search", "page_context", "time", "fetch"}

@classmethod
def _apply_execution_trust_policy(cls, *, tools, input_variables, tool_consent_modes, trust_policy_ref):
    if not tools or not isinstance(trust_policy_ref, dict):
        return tool_consent_modes
    updated = dict(tool_consent_modes)
    for tool in tools:
        current_mode = updated.get(tool.name, "auto")
        if current_mode != "ask":
            continue
        tool_family = cls._tool_semantic_family(tool, input_variables)
        # 原有逻辑
        if ExecutionTrustPolicyService.allows_tool(
            tool_name=tool.name,
            tool_family=tool_family,
            policy_ref=trust_policy_ref,
        ):
            updated[tool.name] = "auto"
            continue
        # P0-FIX: 只读工具族自动放行
        if tool_family in READ_ONLY_FAMILIES:
            updated[tool.name] = "auto"
    return updated
```

### 4.2 修复 Budget 限制 (P0-3, P0-4, P1-7)

#### 文件: `backend/app/ai/engine/budget_guard.py`

```python
# line 10-39 完整替换:
@staticmethod
def build_default(path: ExecutionPath, *, intent_count: int) -> ExecutionBudget:
    if path == "fast":
        return ExecutionBudget(
            max_prompt_tokens=4000,
            max_completion_tokens=2000,     # 1200 → 2000
            max_tool_rounds=2,
            max_elapsed_ms=40000,            # 25000 → 40000
            max_retry_per_intent=1,          # 0 → 1
            max_candidate_tools=3,
            max_tool_result_bytes=16000,
        )
    if path == "normal":
        return ExecutionBudget(
            max_prompt_tokens=8000,
            max_completion_tokens=2000,
            max_tool_rounds=3,
            max_elapsed_ms=35000,            # 20000 → 35000
            max_retry_per_intent=1,
            max_candidate_tools=5,
            max_tool_result_bytes=40000,
        )
    return ExecutionBudget(
        max_prompt_tokens=12000,
        max_completion_tokens=3000,
        max_tool_rounds=min(6, max(2, intent_count * 2)),
        max_elapsed_ms=60000,                # 45000 → 60000
        max_retry_per_intent=1,
        max_candidate_tools=6,
        max_tool_result_bytes=60000,
    )
```

### 4.3 修复 partial_exit 模板 (P0-5)

#### 文件: `backend/app/ai/prompt_contracts/resources/partial_exit.md`

```markdown
---
[PARTIAL EXIT]
Completed work:
{{ completed_summary }}

Unfinished work:
{{ unfinished_summary }}

Reason:
{{ exit_reason }}

Failure kind:
{{ failure_kind }}

Return the completed results now.
Do not imply the unfinished portions are done.
If you have tool results that answer part of the user's question, present them naturally.
Do not show this metadata to the user.
Reply in the user's language.
```

### 4.4 增加 Final Response 机会 (P1-6)

#### 文件: `backend/app/ai/engine/conversation.py`

在主执行循环中, 当 `elapsed_budget_exceeded` 触发时:
```python
# 伪代码 - 找到 budget 检查后的分支:
if budget_exit_reason == "elapsed_budget_exceeded":
    # P1-FIX: 如果已有成功的工具结果, 允许一次 final response
    if self._has_successful_tool_results(messages):
        # 设置一个宽松的 mini-budget 仅用于生成回复
        final_budget = ExecutionBudget(
            max_prompt_tokens=budget.max_prompt_tokens,
            max_completion_tokens=budget.max_completion_tokens,
            max_tool_rounds=0,  # 不允许再调工具
            max_elapsed_ms=budget.elapsed_ms_used + 15000,  # 额外15s
            max_retry_per_intent=0,
            max_candidate_tools=0,
            max_tool_result_bytes=0,
        )
        # 执行一次 final LLM 调用
        await self._generate_final_response(messages, final_budget)
        return
```

### 4.5 修复 Recovery Budget (P1-9)

排查 `max_elapsed_ms=10000, max_tool_rounds=1` 的来源。
在 recovery/retry 路径中, 确保重试 budget 不低于:
```python
recovery_budget = ExecutionBudget(
    max_elapsed_ms=max(20000, original_budget.max_elapsed_ms // 2),
    max_tool_rounds=max(1, original_budget.max_tool_rounds),
    # ... 其他字段
)
```

---

## 五、验证测试用例

修复后需验证以下场景:

| # | 测试场景 | 预期结果 |
|---|----------|----------|
| 1 | 天气查询 (trusted_auto) | 工具直接执行, 不触发 consent, 返回自然语言天气回复 |
| 2 | 天气查询 (工具超时一次) | 重试成功后, LLM 生成最终回复, 不展示预算模板 |
| 3 | 页面阅读+总结 | completion 不被截断, 完整分析回复 |
| 4 | 复合查询 (天气+搜索+页面) | 所有 intent 有足够时间完成, 或已完成部分有自然回复 |
| 5 | 天气查询 (consent_mode=ask, 非 trusted_auto) | 正常触发 consent, 用户确认后执行 |
| 6 | Budget 超限 + 已有工具结果 | 用户看到基于结果的自然语言回复, 不看到英文模板 |
| 7 | 纯文本长对话第三轮 | elapsed 不因多轮累积而超限 |

---

## 六、文件变更清单 (供 Codex 参考)

```
backend/app/ai/engine/budget_guard.py        — 调整 budget 限制
backend/app/ai/engine/tool_processor.py       — consent 检查增加只读工具放行
backend/app/ai/engine/base.py                 — trust policy 增加只读工具族白名单
backend/app/ai/engine/recovery_manager.py     — recovery budget 下限保障
backend/app/ai/engine/conversation.py         — budget exceeded 后增加 final response
backend/app/ai/engine/types.py                — elapsed 计算优化 (P2)
backend/app/ai/prompt_contracts/resources/partial_exit.md — 模板改为中文+指令
```

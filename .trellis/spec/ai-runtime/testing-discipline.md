# AI Dialogue Testing Discipline (Canonical)

> 本规范为 NovusAI AI 对话系统的**测试欺诈防范 canonical spec**。所有改动 AI 对话 live path 的任务，
> 以及 Codex 多代理施工，都必须遵守本文件。
>
> 建立动机：2026-04-23 用户观察到"Codex 写了大量测试文件，跑起来全绿，但实际 AI 对话一用就不对"。
> 这是典型的 **test theater（测试剧场）**：测试存在且通过，但并不 actually verify the behavior the
> user cares about. 本规范用一组硬性规则终止这类现象。

## 1. 核心原则（非交易性）

1. **绿灯不等于功能对**。单元测试通过、类型检查通过、lint 通过，都只是**必要条件**，不是"功能已实现"的
   充分条件。任何 milestone 的 exit criteria 都必须同时包含 behavioral smoke 验证。
2. **测试必须证明行为，不能只证明存在**。
   `assert response is not None` / `assert mock.called` 不是合格 assertion。
3. **Mock 不得让测试变成自 fulfilling 的循环**。如果测试的"预期结果"就是 mock 的返回值，这个测试
   什么都没证明。
4. **每个功能修复前，先写一个能 RED 的测试**。只有"先红后绿"的测试才能证明那条代码真的在起作用。
5. **真对话烟雾测试（real-dialogue smoke）是 milestone 的强制门禁**。不是 unit + integration
   全绿就能发布，必须跑真模型、真 runtime 的一组对话并得到人或脚本的 pass 判定。

## 2. 测试三级分类（必须显式标注）

每个测试文件的 docstring 或函数 decorator/comment 必须显式标注其类别：

| 类别 | 目的 | Mock 策略 | 判定 |
|---|---|---|---|
| `structural` | 验证 import、函数签名、数据流 schema、serialization | 可自由 mock | 只需"不抛异常" + schema match |
| `behavioral` | 验证业务逻辑在**不 mock 关键决策层**时的真实行为 | 严格限制（见 §3） | 必须断言可观察结果 |
| `smoke` | 验证端到端对话（真模型或 canned model replay）能生成符合用户期望的输出 | 不允许 mock LLM 的返回值 | 必须有人工或 scripted judge 做 pass/fail |

标注方式（Python / TS 通用约定）：

```python
# backend/tests/ai/engine/test_turn_executor.py
"""
Test type: behavioral
Scope: TurnExecutor.run single-intent tool-bearing turn
Real dependencies: InMemoryConversationRepo, fake ChatMessageAdapter
Mocked dependencies: LLM call (recorded fixture replay, not stubbed success)
"""
```

```ts
// frontend/apps/web-antd/src/.../__tests__/use-ai-chat-turn-flow.test.ts
// Test type: behavioral
// Verifies: canonical turnFlow projection given a recorded SSE sequence
// Mock strategy: Only network transport is mocked via MSW; turnFlow logic runs real.
```

**PR 审核必须拒绝未显式分类的测试文件**。

## 3. Mock 使用边界

### 3.1 允许 mock（任何测试类别）

- 网络传输层（HTTP client、WebSocket、Socket.IO transport）的 **传输本身**
- 数据库 session（用 in-memory SQLite 或 test-factory）
- 时间（`freezegun` / `vi.setSystemTime`）
- 随机性（seed 或 mock `random`）
- 外部服务鉴权 / quota 计数器
- 静态配置读取

### 3.2 `behavioral` / `smoke` 测试禁止 mock 的对象

以下对象如果被 mock 到"直接返回期望值"，测试无效：

- **LLM response body**（message text, tool calls, reasoning content）在 `behavioral` 中只允许用
  **recorded fixture replay**（真模型曾经产出过的真实响应 JSON），不允许在测试里手写 `"ideal answer"`
  作为 mock return。
- **Tool executor result**：在 `behavioral` 验证 memory / KB / skill-pack
  逻辑或 retired online-search removal guard 时，工具执行必须走真实 executor 或经过验证的
  recorded fixture，不允许 mock executor 直接返回 "success"。
- **Intent planner output** 在测试 intent routing 时不得被 mock 成"预期 intent"。若要测 downstream，
  应用真实 intent planner + 固定 user_text + 固定 capability bundle。
- **Memory policy / thread_memory_state** 在测试 memory 行为时不得被 mock 为"已有记忆"，必须通过
  真实写入 + 读取流程。
- **TurnFlow projection** 在前端测试里不得被 mock。SSE ingestion 测试必须用真实的
  `chat-message-turn-flow.ts` projection + 录制的 SSE event 序列。

### 3.3 Anti-mock 反模式（立即 revert）

```python
# 反模式 1: 自 fulfilling 测试
def test_ai_answers_correctly():
    mock_llm.return_value = "Paris"
    response = ask("What is the capital of France?")
    assert response == "Paris"  # 这什么都没证明
```

```python
# 反模式 2: 只断言 "被调用"
def test_skill_is_resolved():
    run_turn(...)
    assert mock_resolver.resolve_for_agent.called  # 不证明 resolution 是否正确
```

```python
# 反模式 3: 隐式接受 None / 空列表
def test_tool_routing():
    result = route_tools(...)
    assert result is not None  # 空列表也会通过，但用户永远拿不到工具
```

```ts
// 反模式 4: 前端 mock 掉 turnFlow 后验证 UI
it('renders tool call', () => {
    wrapper = mount(ChatMessageItem, { props: { message: { turnFlow: { stages: [{...fake}] } } } });
    expect(wrapper.find('.tool-call').exists()).toBe(true); // 没验证 SSE → turnFlow 的真实路径
});
```

## 4. 强制 Assertion 强度

每个 `behavioral` / `smoke` 测试必须满足：

1. **Arrange / Act / Assert 三段明确**。测试正文中可看到"输入是什么 → 触发了什么 → 验证了什么具体输出值"。
2. **Assertion 验证可观察输出**（至少一条）：
   - 返回值的内容（不只是类型或非空）
   - 状态变更的具体字段值
   - 事件序列的内容和顺序
   - 持久化数据的具体内容
3. **禁止的弱 assertion**（listed exhaustively，PR 审核自动拒绝）：
   - `assert X is not None` 作为唯一断言
   - `assert isinstance(X, dict)` 作为唯一断言
   - `assert len(X) > 0` 作为唯一断言（除非紧跟具体内容断言）
   - `assert mock.called` 作为唯一断言
   - `assert X == X`（同义反复）
   - 空 `assert True` / 没有 assert 的测试体

## 5. 真对话烟雾测试（Real-Dialogue Smoke）

### 5.1 Smoke set 来源

`.trellis/tasks/04-23-codex-llm-first-dialogue-replan/smoke-scenarios.md`
维护当前必须通过的对话场景清单（见本文件末尾 §12 的 living document
约定；04-29 successor adoption 完成前仍以该 living ledger 为准）。每个场景至少包含：

- `scenario_id`（稳定 ID，例：`SKILL-001-basic-invocation`）
- `user_input`（具体 prompt）
- `required_capabilities`（已安装 skills / KB 绑定 / permissioned tool access 等前置）
- `expected_observable_outcome`（具体要出现的 tool call 序列、消息内容特征、不能出现的错误）
- `historical_failure`（可选：过去这个场景失败过的具体症状）

### 5.2 Smoke 执行要求

- **必须打真实的 LLM provider**（或经审批的 deterministic replay fixture，但 replay fixture 必须
  由 QA 人工验证过其原始真对话结果）。
- **必须跑 real `TurnExecutor` + real tool executors**。Page awareness/page-operation
  smoke 只允许作为 retirement guard，证明相关字段或工具不可用；不得作为正向能力验收。
- **判定方式**：
  - 自动化：通过 `scripted judge`（规则断言：tool call kind、消息特征词、完成状态）
  - 或人工：QA 在 smoke report 里为每个 scenario 打 pass/fail
- Smoke run **每个 milestone 必须跑一次完整 set**（不是抽样）。

### 5.3 Smoke 失败即 milestone fail

- Smoke 集失败 > 10% → milestone 整个回滚
- Smoke 集失败任意一个属于 `must-pass` 等级的场景 → milestone 立即 fail，不允许人工豁免
- 新增 smoke 场景必须先以 RED 状态入库，等实现跑绿后才能 merge

## 6. Known-Bug-First 测试纪律

### 6.1 当前已知"AI 对话不对"的所有症状

由 `.trellis/tasks/04-23-codex-llm-first-dialogue-replan/known-bug-scenarios.md` 维护
（living document）。每一条：

- `bug_id`（稳定 ID，例：`BUG-2026-04-23-001`）
- `reporter` + `report_date`
- `reproduction_prompt`（可复现的对话输入）
- `current_wrong_behavior`（现在实际出错的表现）
- `expected_behavior`（正确应表现）
- `status`：`unreproduced_locally` / `red_test_written` / `fix_in_progress` / `fixed_with_green_test` / `regressed`

### 6.2 测试先行规则

**任何声称"修复了 bug X"的 PR，必须：**

1. 先提交一个 RED 测试，明确展示 bug X 的失败断言（`status: red_test_written`）
2. 修复代码进来后，同一测试变绿（`status: fixed_with_green_test`）
3. 测试必须放在 `tests/regressions/` 下并带 bug_id 注释：

```python
# backend/tests/regressions/test_bug_2026_04_23_001.py
"""
Test type: behavioral
Regression for: BUG-2026-04-23-001
Original symptom: 用户要求联网搜索，但 runtime 编造带来源的当前信息，而不是走 unsupported/no-tool 路径。
Scope: Intent routing + retired online-search guard
"""
```

### 6.3 禁止 bug 关闭的 claim 模式

**禁止以下 claim 模式"关闭" bug**：

- "I ran the tests and they all passed" — 不够，必须指向一个对应的 RED→GREEN 测试
- "The existing tests still pass after my change" — 不够，现有测试通过不证明你的 fix 真的生效
- "I manually tested it" — 作为补充可以，但必须同时有自动化 RED→GREEN 证据

### 6.4 用户真实会话复核标准

当用户或 QA 提供真实 `conversation_id`、trace、截图，或粘贴实际失败阶段时，修复任务必须先复核这条
**具体会话**，不能只跑相邻 bug 或同类 prompt 的既有测试。

每个此类修复至少满足：

1. **CLI 证据锚定**：先运行 `novusai ai conversation show <conversation_id> --json`
   或等价仓库 CLI，记录真实 `prompt`、`completion_reason`、`failure_kind`、
   `evidence_status`、`answer_source`、`provider/search/fetch diagnostics`。
2. **同 ID 回归锚点**：新增或更新的 regression 测试名称、docstring 或断言必须引用该
   `conversation_id` / `bug_id`。相邻会话（例如 2295、2305）通过不能证明 2299 修复。
3. **失败原因同构**：RED 测试必须复现同一失败类别，例如 `blocked_url`、`no_results`、
   `no_answer_quality_evidence`、`low_query_relevance` 不能混用为同一个绿灯。
4. **真实路径边界**：retired online-search 类 bug 的 behavioral 测试必须覆盖
   `intent planning -> capability/tool resolution -> provider payload guard -> turn acceptance`
   中导致用户失败的最短真实路径；只测前端 residual suppression 或只测一个旧 search wrapper
   是否过滤不够。
5. **复测口径**：修复后汇报必须同时列出：
   - 原始会话 ID 和原始 failure kind
   - 新增/更新的 bug-specific regression
   - structural 命令
   - behavioral 命令
   - smoke/replay 是否已跑；若未跑，必须写明 `smoke blocked`，不得声称完整 green

如果当前环境无法重放真实 provider，对话修复只能声明
`structural + behavioral verified candidate`，不能声明 milestone 或 regressions fully green。

## 7. 测试 PR 审核清单（Codex 必须在 PR 描述里自答）

每个涉及测试的 PR（包括新增和修订）必须在 PR body 包含以下自问答，缺任意一项拒绝：

```markdown
## Testing discipline self-check

- [ ] Test type(s) of files in this PR: structural / behavioral / smoke
- [ ] If behavioral or smoke: is LLM response mocked? If yes, is it recorded fixture
      replay or hand-written stub? (Hand-written stub is forbidden per §3.2)
- [ ] If this PR claims to fix a bug: which bug_id in known-bug-scenarios.md does
      it reference? Is there a corresponding red_test_written → fixed_with_green_test
      transition?
- [ ] If a user/QA conversation_id exists: did this PR inspect that exact
      conversation through CLI and add a same-ID/same-failure regression?
- [ ] For each new test: write one sentence answering "If the feature this test
      covers silently regresses, will this test fail?" If answer is "maybe not",
      the test is not strong enough.
- [ ] Does any assertion in this PR fall into §4.3 forbidden-weak-assertion list?
      If yes, rewrite.
- [ ] For smoke scenarios touched: did you run them against a real provider /
      recorded fixture? Attach run log or fixture hash.
```

Reviewer（或 Codex parent agent）必须在 merge 前逐条核对。

## 8. Milestone Exit Criteria（对所有任务强制）

任何 milestone / phase 的 exit criteria 必须同时包含：

1. **Structural gate**（必要）：
   - Lint / typecheck / 单元测试全绿
2. **Behavioral gate**（必要）：
   - 该 milestone 涉及的所有业务路径，behavioral 测试覆盖 ≥ 80% 决策分支
   - 本 milestone 声称 fix 的所有 bug_id，在 known-bug-scenarios.md 状态 = `fixed_with_green_test`
3. **Smoke gate**（必要）：
   - Real-dialogue smoke set 通过率 100%（`must-pass` 等级场景）/ ≥ 90%（总体）
   - Smoke run artifact（log 或 video）已归档到 `.trellis/tasks/<task-id>/smoke-runs/<milestone>/`
4. **Regression gate**（必要）：
   - 上一个 milestone 的 smoke set 仍然全绿（防止 fix 引入回归）

**没有四 gate 同时绿，milestone 不得声称 completed**。

## 8.1 Selection AI Local Dialogue Gate

任何涉及富文本或普通 `input`/`textarea` 本地选区 AI 的 PR，必须在测试说明或 PR self-check 中明确回答：

1. **Structural**：共享 controller/浮层、operation stream、富文本 adapter、普通输入框 adapter、字段策略、管理端/企业端/个人偏好入口是否存在且分层正确。
2. **Behavioral**：是否证明选区 session 在菜单打开时冻结，预览前不写回，应用时只替换冻结范围，selection drift/value drift/目标元素漂移会失败关闭。
3. **Local dialogue**：写作问答是否停留在本地浮层，是否没有默认调用 `AIChatSlidePanel`、`useAIPanelStore.openWithContext` 或其它全局侧边栏入口。
4. **Policy**：普通输入框 AI 是否同时受账号 AI、平台/企业策略、个人偏好和字段级 opt-out/action allowlist 控制；富文本 AI 是否不受普通输入框偏好影响。
5. **Smoke**：是否用真实 provider 或项目认可的 replay smoke 验证普通输入框选区应用、富文本格式写回和偏好开关组合。未执行时只能声明 `smoke blocked/not run`，不得宣称端到端完成。

这些测试仍必须显式标注 `structural` / `behavioral` / `smoke`，且不得用“mock 被调用”代替具体 value/正文/浮层状态断言。

## 9. 作业产物归档

每次 milestone 完成必须在 task 目录下归档：

- `smoke-runs/<milestone>/<timestamp>-report.md`（每个 scenario 的 pass/fail + log 片段）
- `smoke-runs/<milestone>/fixtures/`（本次使用的 LLM replay fixture，若有）
- 更新 `known-bug-scenarios.md` 中所有被 touch 的 bug_id status

这些 artifact 是 milestone 验收的**强制性证据**。

## 10. Codex 施工的额外硬规则

在 Codex 多代理施工时（见 `04-23-codex-llm-first-dialogue-replan/codex-execution-brief.md`），
本规范追加以下硬规则：

1. **Codex 不得宣布 milestone 通过，除非**：
   - 已在本 PR body 中填写 §7 自问答
   - 已生成 §9 归档 artifact
   - Parent agent / 人类 owner 已核对 smoke run 证据
2. **Codex 写的每一个 behavioral / smoke 测试**，若使用了 mock，必须在 docstring 里列出 mock 清单，
   并说明"为什么这个 mock 不会让测试自 fulfill"。
3. **Codex 不得使用"其他测试通过了" / "原有测试绿灯" / "没有回归"等理由来证明自己的变更有效**。
   必须指向一个为这个变更新写的 RED→GREEN 测试，或一个其 PASS 是由这个变更驱动的现有测试。
4. **Codex 子代理在 A1–A6 完成任务时，必须各自附一份对应 owner 范围的 smoke report**。
   子代理不得仅靠单元测试绿灯就声称完成。

## 11. 本规范的反模式速查表

| 反模式 | 描述 | 如何发现 | 如何拒绝 |
|---|---|---|---|
| 自 fulfilling mock | mock 返回 = 断言期望值 | PR diff 中 `mock.return_value = X` + `assert ... == X` | revert |
| 弱 assertion | 只断言 is not None / called / len > 0 | PR diff 中单 assertion 行模式匹配 | revert |
| 结构测试冒充行为测试 | 只验证 import / schema 但声称测试业务逻辑 | 文件未标注 test type；或 test body 无实际行为断言 | 要求补标注或补断言 |
| Green without red first | 新 bug fix 直接写绿测试 | git log 中无对应 RED commit | 要求补 RED commit |
| Smoke 跳过真模型 | smoke 测试里也 mock 了 LLM | smoke 目录下存在非 recorded-fixture 的 stub | revert |
| Milestone declared on unit only | exit criteria 只跑 unit / typecheck | milestone 报告中无 smoke 归档 | 拒绝 milestone |

## 12. Living Documents（必须持续维护）

本规范引用两份 living document，它们不在 canonical spec 中，但由相关任务目录维护：

- `.trellis/tasks/04-23-codex-llm-first-dialogue-replan/known-bug-scenarios.md`
- `.trellis/tasks/04-23-codex-llm-first-dialogue-replan/smoke-scenarios.md`

每次 smoke run 后必须更新这两份文档。其它涉及 AI 对话的任务若要修改其中条目，应走"追加 + 引用"
模式，不得擅自删除或降级 bug_id / scenario_id 状态。

## 13. 与既有 spec 的关系

- 本 spec 补充但不替代 `.trellis/spec/backend/quality-guidelines.md` 的通用测试规则
- 对 AI 对话 live path 有交叉的任何 spec 冲突，以本 spec 为准
- `AGENTS.md` / `workflow.md` 中若未来要强调测试，应引用本文件

## 14. 修订记录

- 2026-04-23: 初版。动机：用户发现 Codex 写的测试全绿但 AI 对话实际不对（test theater），
  需要建立硬性防范规范，同步到 04-23 umbrella。

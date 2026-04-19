# 设计信息

## 现状诊断

当前仓库已经不缺“页面 AI 基础设施”，缺的是统一 owner 和闭环状态机。

### 已有基础件

1. 前端已有 shared AI runtime，能够产出 `surface_stack`、`active_form_summary`、`suggested_tools`、`ui_epoch` 等摘要事实。
2. 后端已有 page intent、tool router、page-flow recovery、canonical turn diagnostics、thin `page_context` 治理规则。
3. 前端 page-AI 入口已经收敛到单一路径，旧 page-local registry 并非当前主路径。

### 当前结构性失衡

1. 导航语义隐式依赖并未稳定注入的菜单目录，跨页意图容易退化成对当前 DOM 的局部猜测。
2. `suggested_tools` 被用于能力描述或工具暴露，导致 runtime 决策被当前页面 DOM 形态牵引。
3. `Intent -> Tool` 仍以静态优先级配方为主，没有显式建模 `surface/form` 状态迁移。
4. 表单身份仍通过 `page_key / session_id / legacy surface fallback` 猜测，而不是强制绑定真实 `surface_id`。
5. page recovery 主要通过 prompt hint 驱动，没有把 `ui_epoch / active_surface / diff` 当作一等事实消费。
6. page stop-loss 仍以文本收尾为中心，而不是以页面流程里程碑为中心。
7. live 路径里 canonical runtime 与 legacy compat 同时产生活跃事实，导致执行真相源不唯一。
8. 技能运行时仍把 `Skill.skill_md`、`prompt_skill`、capability descriptor 与 tool definition 混在一起，已安装 skill pack 没有自然成为统一 capability surface。
9. 记忆仍主要通过显式 `memory_recall` intent 或额外提醒进入 turn，缺少 thread-level policy、external-context pollution guard 和后台 capture/recall owner 的分离。

结论：当前实现的症状不是“某页面没适配”，而是 runtime 还没有成为页面操作的唯一 owner，所以团队会自然滑向逐页补丁。

## Codex 参考对照

`codex-main` 给出的关键不是“Playwright 工具更多”，而是更严格的运行时所有权设计：

1. turn 主循环统一消费 `ResponseEvent / ResponseItem`，只按通用输出项类型分发，不按页面类型分支。
2. 工具路由先把模型输出翻译为通用 `ToolPayload`，再进入 router/orchestrator，不把页面行为写死在会话逻辑中。
3. 浏览器能力通过 MCP/connector 暴露，聊天核心只认 `server + tool + arguments`，页面快照和元素 schema 归浏览器工具端所有。
4. 审批、沙箱、网络、重试都归统一 orchestrator 处理，不跟某类页面工具绑死。
5. 当工具变多时，Codex 通过动态暴露、threshold、tool search 控制模型可见性，而不是为页面堆 prompt。
6. 停止条件定义在 turn/runtime 层，通过 `needs_follow_up`、pending input、token budget、stream completion、retry/backoff 等通用信号驱动。
7. 对复杂环境交互，Codex 还提供了 `js_repl + codex.tool(...)` 这类统一可编程执行环境，进一步避免在会话层散落页面脚本逻辑。
8. 技能通过 turn 级别的显式 mention、依赖补全和 injection 进入统一 loop，skill pack 是 capability pack，不是“写给 prompt 看”的额外说明文本。
9. 记忆通过 startup pipeline、thread memory mode、external-context pollution guard 进行治理，而不是把 recall 逻辑分散到页面语义和提示词补丁里。

可迁移结论：

1. NovusAI 的聊天核心不应继续持有“当前页面如何理解”的逻辑，只应持有事件协议、工具协议、上下文治理和停止条件。
2. 浏览器/page-runtime 应成为独立 owner，统一维护快照、交互元素、surface graph、form sessions 和结构化 diff。
3. 页面导航、surface 打开、表单处理和完成判定必须进入统一状态机，而不是继续叠加静态工具配方和 prompt 恢复提示。
4. 技能包必须收敛为 capability pack，安装即进入统一 capability inventory，再由 turn/runtime 做动态暴露，不再把 `skill_md` / `prompt_skill` 当主真相源。
5. memory 必须收敛为 thread/runtime 资源，显式区分 capture、recall、policy、pollution guard，不再靠用户提醒或页面适配兜底。

## 目标架构

### 保留的 seams

1. shared UI runtime 与 `runtime-bridge`
2. thin `page_context`
3. `IntentPlan -> ToolRoutingDecision` 总线
4. `FormSessionManager` 作为统一表单状态仓库
5. canonical `turn_flow / diagnostics / selected_tool_names`
6. 现有 context-budget 与 diagnostics 约束
7. 技能包的 packaging/import 能力，但仅作为 capability pack catalog 起点
8. session memory / long-term memory 的独立存储与服务层 capture 能力

### 必须删除的 seams

1. 导航判定对未稳定注入 `page_data.available_menus` 的隐式依赖
2. `suggested_tools` 反向驱动 runtime 工具选择或能力注入
3. 以静态工具序列承载页面工作流的主路径
4. `page_key -> session_id` 及 legacy surface fallback 作为表单主身份链
5. 以 prompt hint 为主的 page recovery
6. 以文本合成为中心的 page stop-loss
7. live 路径里 legacy compat 与 canonical fact source 同时活跃
8. 以 `Skill.skill_md` / `prompt_skill` / capability descriptor 作为 live capability truth
9. 把显式 `memory_recall` intent 当作长期记忆可用性的唯一 owner

### 新 owner 划分

1. navigation catalog owner
   提供稳定导航目录、导航句柄或导航搜索入口，与当前页面 DOM 解耦。
2. page runtime owner
   维护 snapshot、interactables、surface graph、`ui_epoch`、`active_surface`、structured diff、form sessions。
3. capability pack owner
   负责 skill pack / MCP / generic tool family 的安装目录、依赖、动态暴露与 discoverability，不允许 package 文档或 page hints 成为 live routing 主真相源。
4. tool exposure owner
   根据 connector/config/runtime policy 暴露页面能力，不允许页面局部 hints 反向控制 live tool routing。
5. page workflow state owner
   将页面任务建模为 `discover -> navigate/open -> read -> write -> submit -> verify` 的显式状态机。
6. recovery/stop-loss owner
   直接消费 page-progress 事实，做 intent 内续跑、consent pause、page-progress partial，而不是退回文本式收尾。
7. memory policy owner
   负责 thread/session memory mode、capture vs recall 边界、external-context pollution guard 和 durable memory eligibility。
8. live truth owner
   保障 live turn 只存在单一 canonical execution fact source。

### 页面工作流状态机

目标状态机应至少具备以下阶段：

1. `discover_target`
   明确目标页面、目标入口或目标 surface，而不是直接对当前 DOM 发起盲点操作。
2. `navigate_or_open`
   调用导航目录、页面跳转或 `ui_open_surface / ui_click` 等动作，产生 `ui_epoch / surface diff`。
3. `read_context`
   在确认页面或 surface 已变化后，读取 `ui_get_snapshot / ui_read_surface / ui_get_form_state` 等结构化信息。
4. `perform_write`
   基于已确认的 form session 执行 `ui_fill_form / ui_set_field / ui_submit_form`。
5. `verify_progress`
   用 `ui_epoch`、`active_surface`、成功提示、表单清空或列表变化验证动作推进。
6. `pause_or_finish`
   若命中 consent gate，则以 `confirmation_required` / `pause_for_consent` 收尾；若还有未完成阶段，则回到下一状态，而不是直接结束整个 turn。

## 迁移计划

### Phase 0: Baseline and Scope Freeze

1. 冻结本任务起点：shared UI runtime、thin `page_context`、tool router、page-flow recovery 已存在，不再在文档中写成待建。
2. 明确本任务只做架构收敛、seam 清理和 phased migration，不推倒重建 UI runtime。
3. 把 `1302 / 1303 / 1240 / 1272 / 1274` 这类案例归档为“owner 失衡”证据，而非页面个案。

### Phase 1: Intent and Tool Convergence

1. 收敛 page intent taxonomy，使导航、surface 打开、表单写入、验证续跑有清晰边界。
2. 让 tool routing 从“静态工具配方”向“基于 workflow state 的工具暴露”迁移。
3. 停止让 `suggested_tools` 反向参与 runtime 决策，仅保留展示用途或本地 UX 辅助。
4. 开始切断 `prompt_skill` / capability description / `skill_md` 对 live tool exposure 的反向控制，只保留 catalog 或 diagnostics 语义。

### Phase 2: Navigation and Surface Ownership

1. 引入稳定 navigation catalog seam，去掉导航判定对当前页 DOM 和未稳定注入菜单字段的依赖。
2. 强制 `surface_id -> form_session_id` 成为主身份链，废弃 `page_key -> session_id` 主路径。
3. 将 surface 打开、表单激活、surface 切换统一落入 page runtime owner。

### Phase 3: Recovery and Page-Progress Stop-Loss

1. 让 recovery 直接消费 `ui_epoch / active_surface / structured diff / form_session_not_found` 等事实。
2. 把“打开成功但还未读取”“导航成功但尚未验证”等 page-progress 状态纳入 stop-loss 和 partial-exit 语义。
3. consent gate 继续作为 first-class pause，不得再被吞成 retry exhaustion 或 generic failure。

### Phase 4: Capability Pack and Memory Governance

1. 将 skill pack 明确定义为 capability pack：安装进入 inventory，turn 内按 mention/policy/runtime 决定是否暴露，不再要求逐页适配。
2. 限制 `Skill.skill_md`、package `SKILL.md`、`prompt_skill` 仅承担 packaging、catalog、UX 或 diagnostics 角色。
3. 给 memory 增加 thread/session policy 与 external-context pollution guard 设计，停止把“是否 recall”仅仅视作一个 intent 分支。
4. 把记忆 capture/recall 与页面语义、page recovery、prompt hint 完全解耦。

当前实现推进（2026-04-19）：

1. `backend/app/ai/context/orchestrator.py` 已不再把长期记忆召回完全锁死在显式 `memory_recall` intent 上；普通 turn 只要 `long_term_memory_enabled=true` 且具备用户作用域，就可以进入 bounded vector recall，而 profile snapshot 仍保持显式 recall 语义。
2. `backend/app/ai/runtime/types.py`、`backend/app/ai/skills/resolver.py`、`backend/app/ai/runtime/context_assembler.py` 已将 `selected_skill_names` 收敛为 execution-backed capability truth；带有 `has_execution_tools=false` 的 descriptor-only skill 不再被当作 live skill surface。
3. `backend/app/ai/capabilities/description_builder.py` 已停止把 `suggested_tools` 回写进 page capability description，避免 capability awareness 再次被前端 UX hint 反向污染。
4. `backend/app/ai/engine/prepare_execution_runtime_helpers.py`、`backend/app/ai/engine/system_prompt_capability_decisions.py`、`backend/app/ai/runtime/context_capability_bridge.py` 已改为以 `memory_context_enabled` 作为运行时记忆参与的统一 owner；`has_memory_intent` 仅保留显式 `memory_save` / `memory_recall` 语义。
5. live 技能描述符已经统一向 `CapabilityDescriptor(kind="capability_pack")` 收敛；`prompt_skill` 仅保留为读路径兼容输入，不再是 live capability truth。
6. `backend/app/ai/engine/tool_router.py` 已开始把页面 workflow state 作为一等事实：运行时会解析 `active_surface_id`、surface kind、overlay presence、surface stack depth，并把 `page_navigation`、`page_row_detail`、`page_form_read`、`page_form_write`、`page_editor_write` 收敛到显式 `workflow_stage`。
7. `backend/app/ai/engine/prepare_execution_tool_helpers.py` 已把 `page_workflow_stage` / `page_workflow_state` 写回 `IntentPlan.metadata`，使 router、completion、contract breach、recovery 使用同一份 live workflow truth，而不是各自再猜页面处于哪个阶段。
8. `backend/app/ai/engine/system_prompt_intent_helpers.py`、`backend/app/ai/engine/recovery_status_update.py`、`backend/app/ai/engine/tool_policy_intent_helpers.py` 已把 page intent 完成判定改为 stage-aware contract：`page_navigation` 在 discover 阶段需要“动作 + 验证”组合才算完成；`page_row_detail` 在 open 阶段不会因 `ui_click` / `ui_open_surface` 单独完成；`page_form_write` / `page_editor_write` 在 ready-to-submit 阶段只接受 `ui_submit_form` 作为完成信号。
9. `backend/app/ai/engine/page_flow_recovery_helpers.py` 已开始消费 canonical workflow metadata：row-detail 已打开 detail surface 时 recovery 只推荐读工具；导航与表单场景的 no-progress diagnostics 也会携带完整 workflow state，减少 prompt-hint 式恢复猜测。
10. `frontend/apps/web-antd/src/components/business/ai-runtime/runtime-bridge-snapshot.ts` 已开始把 compact `page_data.navigation_catalog` / `page_data.navigation_context` 注入 thin `page_context`，让 cross-page routing 可以消费统一导航目录，而不是继续依赖逐页注入或 prompt 猜测。
11. `frontend/apps/web-antd/src/utils/page-navigation.ts` 已与 runtime-bridge 对齐：导航工具结果会复用同一套 compact navigation page-data seam，并在 fallback 场景保持 summary-first，不再制造第二份 live 导航真相源。
12. `backend/app/ai/navigation_semantics.py` 与 `backend/app/ai/tools/page_runtime/navigation.py` 已收口到 `navigation_catalog` 单一路径；`available_menus` 不再属于 live runtime contract，页面导航意图检测与候选解析不再各维护一套菜单打分逻辑。
13. `frontend/apps/web-antd/src/composables/use-form-state-tracker.ts` 已把 runtime-facing 表单接口明确收敛到 session/surface-first（如 `getFormApiBySessionId`、`getSessionBySurfaceId`、`closeBySurfaceId`）；page-key 仅保留兼容映射，不再作为新 runtime 主身份链。
14. `backend/app/schemas/ai/agent_chat.py` 已把 compact `page_context.page_data` 正式建模进请求边界，只允许 summary-first 的 `navigation_catalog` / `navigation_context` / locale-ish 元数据通过，避免前端 canonical seam 在请求归一化时被静默丢弃。
15. `backend/tests/test_admin_agent_chat_routes_contract.py` 已补上 `/ai/agent-chat` 传输层哨兵测试：未知 `page_data` key 会在 schema 边界直接返回 `422`，而夹带坏条目的 `navigation_catalog` 会在进入 route/chat 逻辑前被过滤，防止任意一个坏菜单条目拖垮整轮请求。
16. `frontend/apps/web-antd/src/utils/ai-page-capabilities.ts`、`frontend/apps/web-antd/src/components/business/ai-chat-panel/tool-call-utils.ts` 已停止把 `navigate_menu`、`open_page`、`read_visible_rows`、`fill_form`、`submit_form` 等 legacy 名字视为 live page-runtime truth；当前 capability filtering、pending-op 展示与 navigation-only allowlist 仅识别 canonical `ui_*` 工具名。
17. `frontend/apps/web-antd/src/composables/use-ai-page-policy.ts` 已将 route-security 默认写入动作收敛到 canonical `ui_set_field` / `ui_fill_form` / `ui_submit_form`；`use-page-ai-operation-helpers-*` 中原先会静默产出 `create_record` / `open_page` / `read_row_detail` 等 legacy 默认名的 helper 现已要求显式 `name`，避免新代码继续无意识复活旧 seam。

### Phase 5: Context-Budget Alignment

1. 维持 thin `page_context`，不回退到重内容 prompt 注入。
2. 将 page/runtime/context 的新增事实统一纳入现有 budget 和 diagnostics。
3. 对 `suggested_tools`、surface 摘要、page-progress diagnostics、skill-pack descriptors、memory summaries 的用途做严格边界约束。

### Phase 6: Frontend Shell and Live Truth Freeze

1. 冻结唯一 page-AI 链路，禁止新增 page-local policy/runtime 旁路。
2. 清理 live 路径中 legacy compat 对 canonical turn/runtime fact 的二次镜像与拼接。
3. 确保前端展示层和后端诊断层都只消费单一 canonical truth source。

### Phase 7: Legacy Surface Removal and Verification Sync

1. 清理仍残留在 runtime 语义面中的旧 page tool 认知和双轨兼容。
2. 以 tool router、page recovery、page-runtime guards/policy、thin `page_context` payload、skill-pack activation、memory policy、frontend 唯一链路为验证锚点。
3. 每完成一阶段实现，都要同步更新 canonical spec 或当前任务文档，避免再次出现“代码已变、文档还停在旧阶段”的漂移。

## 风险与回滚

### 风险

1. 若直接大面积删除 legacy compat，可能影响现有前端 turn-flow 展示和旧对话回放。
2. 若把页面状态机拆得过细，可能造成 intent/router/diagnostics 之间新一轮 owner 交叉。
3. 若 navigation catalog 设计成重内容注入，容易破坏 thin `page_context` 和 budget 纪律。
4. 若 recovery 仍然保留 prompt-hint 主路径，后续实现会继续滑回页面适配。
5. 若 skill pack 继续同时承担 prompt 资产和 runtime capability，两套真相源会继续互相污染。
6. 若 memory 仍缺 thread-level policy 与污染治理，外部 context 与 durable memory 会持续互相串味。

### 回滚与缓释

1. 所有 live seam 迁移先以 canonical truth source 为目标，legacy 仅保持只读回放兼容，不再参与运行时判定。
2. 新状态机先覆盖 page navigation/surface/form 核心路径，再逐步吸纳其他 page intents，避免一次性重写全部行为。
3. 所有新增 runtime 事实都先挂到现有 diagnostics/budget 面，未记账即视为设计不合格。
4. 每一阶段先完成一组明确的测试锚点和任务文档更新，再推进下一阶段。
5. skill pack 和 memory 的 owner 清理优先先做“禁止新增旧 seam”，再做 runtime 主路径替换，避免一次性重写整个 catalog 和记忆系统。

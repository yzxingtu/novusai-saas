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
7. `backend/app/ai/engine/prepare_execution_tool_helpers.py` 已把 `page_workflow_stage` / `page_workflow_phase` / `page_workflow_goal` / `page_workflow_state` / `page_workflow_completion` 写回 `IntentPlan.metadata`，使 router、completion、contract breach、recovery 使用同一份 live workflow truth，而不是各自再猜页面处于哪个阶段。
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
18. `backend/app/services/ai/conversation_interaction_service.py`、`frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat-interactions.ts` 与消息合并层已把 `pending_confirmation` 的 live match key 收敛到 `tool_name`：前后端都不再要求依赖 `action/table` 才能完成确认回传，旧字段仅保留为证据与历史兼容信息。
19. `backend/app/ai/tools/semantic_defaults.py` 已把 `page_context_available_ui_tools()` 收敛为 runtime-state-only 推断：helper 不再读取 `suggested_tools`，也不再把整套 `ui_*` 工具无差别回灌给 backend 消费方；`backend/tests/services/test_agent_chat_page_context.py` 与 `backend/tests/ai/test_tool_argument_recovery.py` 已补上回归测试，防止 `suggested_tools -> backend runtime semantics` 这条 seam 再次复活。
20. `backend/app/ai/runtime/types.py`、`backend/app/ai/engine/prepare_execution_tool_helpers.py` 已新增 live capability projection：一旦 tool planning 选出本轮工具子集，capability bundle、runtime manifest、runtime capability summary 与 `selected_skill_names` 诊断都会投影到该子集，避免“agent 级已授权 skill”继续直接冒充本轮 live skill surface。
21. 该投影规则保留了 capability-reporting turn 的 inventory 语义：当用户只是在问“这轮有哪些能力”且本轮没有 live tool 子集时，runtime summary 仍可报告 broader inventory；但一旦进入真实 tool-bearing turn，live diagnostics 只能反映被选中的 capability packs。
22. `backend/app/ai/memory_policy.py`、`backend/app/ai/context/orchestrator.py`、`backend/app/ai/runtime/context_assembler.py`、`backend/app/ai/runtime/manifest.py` 与 `backend/app/services/ai/agent_chat_memory_support.py` 已围绕统一 `memory_runtime_policy` 收敛：context gating、runtime manifest、session-memory load 与 long-term capture 不再各自直接看 raw request flag；当 turn 被 `web_search` / `fetch_url` 等外部 research 路径污染时，durable long-term capture 会被显式抑制并记录污染原因。
23. `backend/app/ai/skills/turn_activation.py`、`backend/app/ai/skills/resolver.py`、`backend/app/ai/runtime/context_assembler.py` 与 `backend/app/ai/capabilities/description_builder.py` 已新增 turn-level skill activation seam：resolved inventory 与 live activation 被显式分离，显式 skill mention、page/web runtime policy 与 capability-reporting query 会共同决定本轮 skill preview，而 capability summary / selected_skill_names / skills description 则改为消费 activated subset，而不是继续把 agent 级已安装 inventory 直接冒充 live capability truth。
24. `backend/app/services/ai/agent_chat_command_service.py`、`backend/app/services/ai/agent_chat_stream_persistence_orchestrator.py`、`backend/app/services/ai/conversation_message_persistence_support.py`、`backend/app/services/ai/conversation_message_persistence_service.py` 与 `backend/app/services/ai/conversation_runtime_projection_service.py` 已把 `memory_runtime_policy` 接入持久 owner：assistant 元数据会写入 normalized policy，`conversation.metadata_.thread_memory_state` 会保存 thread-level snapshot，而 conversation detail 的 diagnostics / last_run_summary 在缺少 assistant-level policy 时也可回退读取 thread state，并继续投影 normalized `memory_runtime_policy` 与 compact `memory_mode`，不再只暴露污染布尔位。
25. `backend/app/services/ai/agent_chat_stream_persistence_orchestrator.py` 已把 stream `on_complete` 的 fallback result 重建收敛为 dataclass-field-only copy；新增的私有运行时属性（如 `_memory_runtime_policy`）不会再把错误分支本身炸成二次异常，stream persistence failure 可以继续走 error-message / marker 持久化路径。
26. `backend/app/ai/engine/page_workflow_state_machine.py`、`backend/app/ai/engine/tool_router.py`、`backend/app/ai/engine/system_prompt_intent_helpers.py` 与 `backend/app/ai/engine/page_flow_recovery_helpers.py` 已把页面工作流 owner 从路由分支内联字符串进一步收口为独立状态机：页面 intent 会统一投影 `discover / navigate_or_open / read / write / submit / verify` 这些 canonical phase，并把 machine-readable `page_workflow_completion` contract 一起写入 `IntentPlan.metadata`，使 completion / recovery / contract-breach 不再各自维护第二份 stage 规则。
27. `backend/app/ai/tools/executors/ui_action_executor.py` 的兼容执行路径也已删除 `page_key -> get_active_session_id()` 的 live session 猜测回退；页面动作现在只接受 live `page_session_id`（来自 execution context 或 thin `page_context`），不再让 page key 重新充当 session 主身份链。
28. `backend/app/ai/context/assembly_initial_support.py`、`backend/app/ai/runtime/context_assembler.py`、`backend/app/ai/runtime/context_capability_bridge.py` 与 `backend/app/ai/skills/resolver.py` 已把 skill startup owner 再前移一刀：turn activation 现在会刷新 provisional capability bundle / initial intent planning，不再只在 prepared-execution 末端才裁掉 broader inventory；同时 auto-injected baseline builtins 不再被误判成 skill-owned，因此启动阶段仍可保持 baseline 工具可用，而 skill-owned tool/descriptors 会收敛到 activated subset。
29. `backend/app/services/ai/agent_chat_memory_support.py`、`backend/app/services/ai/agent_chat_runtime_support.py` 与 `backend/app/services/ai/agent_chat_command_service.py` 已把 memory startup owner 从 chat/stream 内联逻辑中抽出：`thread_memory_state` 会先经过统一 normalization，再由共享 startup helper 对 request 执行 priming；chat 与 stream 现在复用同一条 startup seam，不再各自直接解析 `conversation.metadata_.thread_memory_state`。
30. `backend/app/ai/skills/resolver.py`、`backend/app/ai/skills/turn_activation.py`、`backend/app/ai/engine/dispatcher.py`、`backend/app/services/ai/agent_chat_stream_bootstrap_service.py` 与 `backend/app/ai/engine/prepare_execution_pipeline.py` 已把一部分 skill inventory owner 再前移到 resolver 输入边界：当 turn 已带有显式 skill mention、显式工具名或 capability-reporting query 时，startup resolver 会先基于 grant-level preview 做预过滤，再进入完整 skill resolve；chat/stream/dispatcher/prepare-execution 现在都会把 live request 传进这条 startup seam，而不是一律先把 agent 全量 grant eager resolve 出来。
31. `backend/app/ai/skills/resolver.py`、`backend/app/ai/skills/turn_activation.py` 与 `backend/app/ai/engine/system_prompt_intent_helpers.py` 已继续把 startup owner 往前收口：resolver startup 现在会先从 live request 推导 page/web runtime-policy family，再结合 preview semantic families 对 plugin/connector grant 做 bounded 预过滤；因此 page/web turn 不必等到 full resolve 之后才开始裁掉无关 skill inventory，而 prepared-execution 的 intent-flag helper 也会保留 `has_web_research_intent`，不再在统一 turn flag 面上丢信号。
32. `backend/app/ai/memory_policy.py` 与 `backend/app/services/ai/conversation_runtime_projection_service.py` 已把 memory read-model projection 进一步收口为共享 helper：assistant metadata 与 thread fallback 现在都会先经过同一套 normalization，再导出 compact `memory_mode`（`disabled` / `session_only` / `long_term_only` / `session_and_long_term`），避免 conversation detail/error-only fallback 各自拼接第二份 memory 真相源。
33. `backend/app/plugins/manifest.py`、`backend/app/ai/skills/resolver_parts/loaders.py` 与 `backend/app/ai/skills/resolver.py` 已把 plugin skill 的 startup preview 再往前收一刀：插件 manifest 现在可以为 `extensions.skills[*]` 声明 bounded `preview_tool_names` / `preview_semantic_families`，resolver 启动阶段会从 DB 中的 `plugin.manifest` snapshot 读取这份 catalog-only preview 来做预过滤，因此名字中性的 plugin skill 也能在 page/web/tool-explicit turn 上更早收敛，而不必 fallback 到全量 eager resolve 或 prompt 猜测。
34. `backend/app/services/ai/runtime_inventory_service.py`、`backend/app/services/ai/runtime_inventory_service_support.py` 与 `backend/app/ai/skills/resolver.py` 已把 capability-pack inventory/read-model owner 继续向统一 resolver 收口：runtime inventory 不再维护第二套 agent-skill grant 解析路径，而是直接复用 `resolve_for_agent(...)`；同时 resolved capability descriptor 与 extension 摘要会继续保留 `startup_preview_tool_names` / `startup_preview_semantic_families` 这类 catalog-only discoverability 元数据，使安装态 plugin capability 能在 runtime manifest / diagnostics 中被看见，而不需要重新跑 live plugin resolver 才“看起来存在”。
35. `backend/app/ai/memory_policy.py` 与 `backend/app/services/ai/conversation_runtime_projection_service.py` 已把 memory read-model owner 再前移一刀：conversation detail / error-only fallback 现在会通过共享 helper 统一解析 assistant metadata 与 `thread_memory_state`，并显式投影 `memory_runtime_policy_source`（`assistant_metadata` / `thread_memory_state`）和 `thread_memory_state_updated_at`，让 thread-level memory snapshot 的来源与新鲜度在 read-model 上可见，不再像第二条隐式 memory 真相源。
36. `backend/app/ai/runtime/context_assembler.py`、`backend/app/ai/runtime/manifest.py`、`backend/app/services/ai/agent_chat_turn_projection.py` 与 `backend/app/services/ai/conversation_runtime_projection_service.py` 已把 turn-level skill activation observability 接回 canonical owner 链：skill context source metadata 现在会同时投影 live selected subset、broader resolved inventory 与 activation reason，runtime diagnostics / compact runtime summary / conversation detail read-model 统一复用这份 metadata，不再需要从 prompt hint、page-local state 或第二套 routing 解释路径去猜“这轮为什么只激活了这些 capability packs”。
37. `backend/app/tasks/agent_batch.py` 与 `backend/app/services/ai/runtime_inventory_service_support.py` 已把 capability-pack startup/read-model owner 再收一刀：batch warmup 不再在 item execution 前 eager resolve 一次全量 agent inventory，避免非 live 启动路径重新冒充 routing owner；同时 runtime inventory / empty manifest payload 会显式标注 `selection_semantics=inventory_snapshot` 与 `selection_live=false`，把 catalog/read-model 语义和真实 live turn truth 继续锁死在不同 owner 面上。

### 2026-04-21 审计补充：仍未收敛到 codex-main owner 的差距

以下结论来自对当前工作树与 `C:\Users\Administrator\Downloads\codex-main` 的再次逐文件对照。它们代表仍活跃的 runtime seam，不应被 Trellis 目标规范误判为“已经完成”。

1. `suggested_tools` 作为 backend runtime 语义输入的 seam 已完成清理，但它仍保留在 frontend affordance / compact snapshot / read-model 边界中，因此后续实现仍需继续守住“只读 UX hint，不回流 live routing”的边界，避免旧 seam 以展示层 helper 的名义复活。
2. 技能包的 inventory owner 已不再是“无条件 agent 级 eager resolve”，但仍未完全收敛到 codex-main 的 turn-level mention/policy/connector 激活模型。
   当前 `backend/app/ai/skills/resolver.py` 已能在 startup 阶段对显式 skill mention、显式工具名、capability-reporting query 与 request-derived page/web runtime policy 做 grant-level 预过滤，并为 plugin/connector grant 附加 bounded semantic-family preview；但这仍是安全启发式，未知 preview 的 connector 依赖、安装态 discoverability 与更强的 startup activation owner 仍是后续 debt。
3. 记忆治理已不再是纯 raw request flag 直连，也不再停留在“command service 内联抄 thread state”的阶段，但仍未完全落到 codex-main 那种 stateful thread memory mode。
   当前 `backend/app/ai/memory_policy.py` 已把 context gating、manifest、session-memory load 和 long-term capture 收敛到统一 `memory_runtime_policy`，`backend/app/services/ai/agent_chat_memory_support.py` 也已提供共享 startup helper，对 chat/stream 启动统一解析并归一化 `thread_memory_state`；但这仍是轻量 thread snapshot，还没有 codex-main 那种 startup memory jobs、后台 consolidation 与更强的 state-db-backed thread owner，因此跨 turn 的长期治理和后台记忆整编仍是后续 debt。
4. `backend/app/sio/page_session.py` 仍保留 `(scope, user_id, page_key) -> page_session_id` 的活跃会话追踪与保守 fallback，这说明 backend connector transport 还没有完全摆脱 `page_key -> session_id` 身份链残留。
   这不是“必须兼容旧前端”的理由；对当前新 SaaS 来说，它应直接并入 `WS4 browser-connector-externalization`，作为 page-session transport owner 的待删 seam。
5. `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat-turn-flow.ts`、`chat-message-turn-flow.ts` 与 `use-ai-chat-page-operations.ts` 仍保留较重的 legacy turn-flow/backfill/page-op gating 逻辑：当前 live UI 在 canonical `turn_flow` 缺失时会重建 `legacy-*` timeline，并在 page-operation channel readiness 上继续参考 `suggested_tools` 与 route/page-key fallback。
   对当前新 SaaS 来说，这些默认兼容层不应继续被视为合理存量；它们应直接并入 `WS6 frontend-live-truth-freeze`，作为需要删除而不是保留的 frontend live seam。

这些差距说明：

1. 当前代码虽然已经明显脱离“逐页补适配”的最差状态，但还没有完全达到 codex-main 那种“统一 turn loop + 通用 tool payload + 外部 connector/MCP owner + thread-level memory owner”的收敛程度。
2. 后续 Phase 1 / Phase 2 / Phase 4 的实现顺序仍然正确，不应回头补更多页面特例；应该继续优先清理上述两条 live seam，并持续守住已收掉的 `suggested_tools -> runtime semantics` 边界。
3. canonical spec 里的目标规则继续保持不变；这里记录的是当前实现债务，而不是要把规范降回兼容旧 seam 的状态。

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

## 剩余任务拆分（2026-04-21）

从本轮开始，后续实现不再按“每次对话临时挑一刀”推进，而是统一按下面 6 个 Trellis child tasks 前移。对应 ownership、依赖与 merge order 以 [ownership-matrix.md](./ownership-matrix.md) 为准。

1. `04-21-codex-capability-pack-startup-owner`
   目标：收掉 capability pack 的最后一批 startup/live owner seam，让 resolver、runtime inventory、manifest、diagnostics、batch/warmup 明确区分 catalog inventory 与 live turn truth。
2. `04-21-codex-thread-memory-owner`
   目标：把当前的 normalized `thread_memory_state` 继续收口为更强的 thread owner，补齐 startup priming、pollution guard、capture/review background seam。
3. `04-21-codex-browser-connector-externalization`
   目标：把 page/browser 执行继续外推成 connector/MCP-like 边界，聊天核心只吃 canonical `ui_*` payload 和 connector 结果。
4. `04-21-codex-page-workflow-state-owner`
   目标：补齐页面工作流状态机的 stop-loss / recovery / completion 闭环，彻底停止 prompt-hint 与文本式早收尾主导 page progress。
5. `04-21-codex-turn-loop-orchestrator-convergence`
   目标：在前面 owner 稳定后，再收聊天核心与 turn loop，让核心只剩统一事件协议、工具协议、预算治理和停止条件。
6. `04-21-codex-frontend-live-truth-freeze`
   目标：冻结 frontend 唯一 live truth 链路，确保 slide panel / chat panel / page capability UI 只消费 canonical runtime diagnostics，不复活旧 page-op / `suggested_tools` seam。

执行约束：

1. 子任务可以并行研究，但写代码时必须遵守 ownership matrix，避免再回到“多个对话同时踩同一组文件”的状态。
2. `.trellis/spec/**` 与 umbrella task 文档继续由当前 umbrella owner 维护；child tasks 不提前宣告未落地 contract 已完成。
3. 后续每次实现优先引用对应 child task 的 `prd.md` / `implement.jsonl` / `check.jsonl`，而不是只依赖聊天上下文回忆剩余工作。

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

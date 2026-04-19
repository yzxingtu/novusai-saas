# Codex 通用页面操作架构重规划

## 背景

当前 AI 对话已经具备 shared UI runtime、thin `page_context`、page intent、tool router、page-flow recovery、turn-flow diagnostics 等基础件，但真实交互体验仍然表现为“某个页面能不能用，要看这页是不是又补了一层适配”。对话 `1302` 和 `1303` 暴露的不是单个页面漏配，而是页面导航、surface 打开、表单读取、恢复续跑、完成判定之间没有形成单一 owner 的状态驱动闭环。

同一类问题也已经蔓延到技能调用和记忆治理：当前技能更像“要靠 prompt 和 capability descriptor 提醒模型的配置项”，记忆更像“只有明确说 recall 才勉强想起的附加 contributor”，而不是统一运行时内可安装、可治理、可追踪的能力资源。对于通用 SaaS，这会自然把系统推回“每来一个页面、每来一类 skill、每来一段记忆都要再适配一层”的路线。

用户要求对照 `C:\Users\Administrator\Downloads\codex-main` 的通用工具调用模式，重新规划当前 SaaS AI 对话架构，避免继续走“每个页面补一点规则、补一点提示、补一点兼容”的路线。

## 问题陈述

当前系统“看起来很蠢”的根因不是 page runtime 不存在，而是以下结构性问题同时存在：

1. 页面导航语义仍隐式依赖前端未稳定提供的菜单目录，跨页动作容易退化成对当前 DOM 的局部猜测。
2. `suggested_tools` 等页面局部状态被反向用于工具暴露和能力描述，runtime 会被当前页面形态牵着走。
3. `Intent -> Tool` 仍以静态优先级配方为主，没有把 `surface/form` 状态迁移建模成一等公民。
4. 表单身份仍混用 `page_key / session_id / legacy surface fallback`，而不是强制绑定到真实 `surface_id`。
5. 前端已经生成 `ui_epoch / surface_stack / diff` 等结构化事实，但恢复逻辑主要还是通过 prompt hint 驱动，而不是直接消费这些事实。
6. 页面任务的 stop-loss 仍偏向“现在能不能收成一段文本”，而不是“当前页面流程推进到了哪个 UI 里程碑”。
7. canonical runtime 与 legacy compat 在 live 路径中同时产生活跃事实，导致 page-runtime 的真相源不唯一。
8. 技能运行时仍混用 `Skill.skill_md`、`prompt_skill`、capability description 和 tool definitions，安装 skill pack 之后不会自然收敛为统一 capability surface。
9. memory 仍主要依赖显式 `memory_recall` intent 或额外提醒进入 turn，缺少 thread-level policy、external-context pollution guard 和稳定的 capture/recall owner。

这些问题的共同后果是：每当新页面的 surface 机制、表单生命周期或导航入口略有不同，团队就会倾向于继续补页面规则和 prompt 例外，而不是修正运行时所有权边界。

## 目标

本任务目标是形成一份可执行的重规划，明确 NovusAI AI 对话应如何向 Codex 风格的通用页面执行架构收敛：

1. 主循环只围绕统一事件和工具协议运行，不把页面类型、页面名称或局部 DOM 形态写进 turn orchestration。
2. 页面能力通过稳定 runtime seam 暴露，页面快照、交互元素和浏览器细节由 page/browser tool owner 持有，不在聊天核心内部分叉。
3. 页面操作工作流从“按页面适配的静态工具梯子”升级为“由 navigation/surface/form/page-progress 状态驱动的状态机”。
4. 既有 shared UI runtime、thin `page_context`、tool router、page recovery、budget diagnostics 继续沿用，不推倒重建。
5. 通过 phased migration 明确哪些 seams 保留、哪些 seams 需要删除、哪些 owner 需要重划，后续实现工作按阶段展开。
6. 技能包和记忆能力回归统一运行时治理：已安装 capability pack 无需逐页适配即可进入统一 tool exposure，memory 不再依赖 prompt 提醒或页面语义才能表现得像“记得住”。

## 非目标

本任务不是：

1. 重新从零搭建 UI runtime、`runtime-bridge`、`UIGraphBuilder` 或 `FormSessionManager`。
2. 继续为具体页面补更多 intent 关键词、locator 例外或 prompt 兜底。
3. 在本次规划内直接完成所有代码重构；本任务先产出架构决策、迁移顺序和验收基线。
4. 把厚页面内容重新塞回 `page_context` 或 prompt baseline。

## 需求

### 1. 对照 Codex 提炼可迁移的架构原则

规划必须明确吸收以下来自 `codex-main` 的通用模式：

1. turn 主循环以统一 `ResponseEvent / ResponseItem` 协议驱动，只按消息、工具调用、工具结果、推理片段等通用输出项分派。
2. 工具调用通过统一 `ToolPayload` 和 router/orchestrator 分发，不在会话逻辑里写死某类页面行为。
3. 浏览器能力视为 MCP/connector 暴露的外部能力，聊天核心只认 `server + tool + arguments` 边界。
4. 审批、沙箱、网络、重试和停止条件由统一 orchestrator/turn runtime 处理，而不是由页面动作私有处理。
5. 当工具集变大时，工具暴露应支持动态发现、延迟暴露或 search/threshold 机制，避免海量页面动作直接淹没模型。

### 2. 现有能力必须作为起点，而不是被文档错误描述成“待建”

新规划必须把以下现状冻结为基线：

1. shared UI runtime 和 `runtime-bridge` 已存在，且已生成 `surface_stack`、`active_form_summary`、`suggested_tools`、`ui_epoch` 等摘要事实。
2. page intent、tool router、page-flow recovery、turn-flow diagnostics 已经部分落地，但当前 owner/seam 仍未收敛。
3. thin `page_context`、summary-first、详细信息走 `ui_get_snapshot / ui_read_* / ui_get_form_state` 的原则继续有效。
4. 前端 page-AI 继续只允许一条链路：`route.meta.ai -> useCurrentPageAIPolicy -> layout shell -> AIChatSlidePanel -> usePageAICapability -> runtime-bridge`。

### 3. 新架构必须显式重划 owner 和 seam

规划必须定义以下核心 owner：

1. navigation catalog owner：提供稳定的跨页导航目录或导航句柄，不再依赖当前页 DOM 猜测目标入口。
2. page runtime owner：负责快照、interactables、surface graph、form sessions、`ui_epoch`、structured diff 等事实维护。
3. tool exposure owner：负责动态暴露页面相关工具，不允许 `suggested_tools` 反向驱动 runtime 决策。
4. page workflow state owner：把 `discover -> open surface -> read surface/form -> fill -> submit -> verify` 建模为显式状态迁移。
5. recovery/stop-loss owner：直接消费 page-progress 事实，而不是只回写 prompt hint 或文本式 partial output。
6. live truth owner：live 路径只保留 canonical turn/runtime fact source，legacy compat 仅允许存在于离线读取或迁移边界。

### 4. 页面工作流必须从静态工具配方升级为状态驱动

规划必须要求：

1. `page_navigation` 不再隐式依赖 `page_data.available_menus` 这种未稳定注入的字段。
2. `page_form_write` 不能只靠静态工具排序表达“先打开，再读表单，再填，再提交”。
3. `surface_id -> form_session_id` 成为主身份链，禁止以 `page_key -> session_id` 或 legacy fallback 作为主路径。
4. recovery 直接消费 `ui_epoch / active_surface / structured diff`，能从“打开成功”自动转入下一阶段，而不是继续 broad page read loop。
5. stop-loss 新增 page-progress 语义，例如“surface 已打开但表单尚未读取”“导航已推进但目标页尚未验证”，避免动作成功后被文本合成逻辑过早终止。

### 5. 技能包和记忆必须回归运行时 owner

规划必须要求：

1. 已安装 skill pack 应作为 capability pack 被 runtime 解析、筛选和动态暴露，而不是继续依赖页面适配、prompt block 或 capability descriptor 提醒才可用。
2. `Skill.skill_md`、package `SKILL.md`、`CapabilityDescriptor(kind="prompt_skill")` 只能保留为 packaging、catalog 或 UX 元数据，不得再成为 live tool exposure 主真相源。
3. memory 必须被明确定义为 thread/runtime 资源，显式区分 capture、recall、thread policy 和 external-context pollution guard，而不是继续混在 page intent 或 prompt hint 中。
4. 外部 context（web/MCP/connector 等）进入 turn 时，memory 必须具备污染或降级策略，避免无条件把外部事实写回 durable memory，或无条件把旧记忆混回当前 turn。

### 6. 预算和上下文治理不能倒退

新规划必须保证：

1. `page_context` 继续保持 thin payload，只保留 `page_key / page_title / page_session_id / ui_epoch / active_form_summary / surface_stack` 等摘要字段。
2. 页面大内容、DOM 细节、表格正文、表单原始值只能通过页面工具按需拉取，不能重新回灌到 baseline prompt。
3. page/runtime/context 注入继续纳入现有 budget 和 diagnostics 约束，不能再新增第二套未记账的上下文路径。

## 验收标准

当本任务完成时，至少满足以下条件：

1. `.trellis/tasks/04-19-codex-universal-page-ops-replan/prd.md` 明确写清现状基线、结构性问题、目标 owner、非目标和验收标准，不再把已存在能力写成待建。
2. `.trellis/tasks/04-19-codex-universal-page-ops-replan/info.md` 明确给出 phased migration，覆盖 baseline freeze、intent/tool convergence、page recovery/consent closure、context-budget alignment、frontend seam freeze、legacy surface removal、verification sync。
3. 文档显式对照 `codex-main` 的统一 turn loop、tool router/orchestrator、MCP tool exposure、skill-pack turn injection、memory pipeline/thread policy、外部 browser connector 边界和统一停止条件，并提炼出可迁移原则。
4. 文档显式列出当前系统必须删除的 seams，包括但不限于：`suggested_tools` 反向驱动 runtime、`page_key -> session_id` 主身份链、prompt-hint 主导的恢复、`Skill.skill_md` / `prompt_skill` 作为 live capability truth、live 路径里的 legacy compat 真相源。
5. 文档显式列出必须保留的 seams，包括但不限于：shared UI runtime、thin `page_context`、`IntentPlan -> ToolRoutingDecision` 总线、`FormSessionManager` 作为统一仓库、canonical `turn_flow / diagnostics`、技能包作为独立 capability pack、memory capture/recall 的独立 owner。
6. 文档明确未来实现验收锚点，至少覆盖 tool router、page recovery、page-runtime policy/guards、thin `page_context` payload、skill-pack activation / tool exposure、memory policy / pollution guard、frontend 唯一 page-AI 链路。

## 验证

本任务当前轮的验证方式为文档与代码路径对照验证：

1. 对照 `codex-main` 的核心文件，确认其主循环、工具路由、MCP 暴露、orchestrator 和停止条件均不按页面类型分叉。
2. 对照 `codex-main` 的 `skills.rs`、`stream_events_utils.rs` 与 `memories/README.md`，确认 skill-pack turn injection、external-context memory pollution guard、startup memory pipeline 与统一 turn runtime 的 owner 分界。
3. 对照本仓库 AI runtime 相关规范、任务文档和活跃代码路径，确认 shared UI runtime、page router、recovery、skill catalog、memory orchestrator、budget、frontend shell 等现状边界。
4. 将上述证据沉淀到 Trellis 任务文档与 canonical spec，作为后续实现任务的唯一规划输入。

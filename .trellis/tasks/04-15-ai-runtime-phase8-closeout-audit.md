# 2026-04-15 AI Runtime Phase 8 收尾审计

## 范围

- `.trellis/spec/ai-runtime/*.md`
- `backend/app/ai/**`
- `backend/app/services/ai/**`
- `frontend/apps/web-antd/src/components/business/{ai-chat-panel,ai-slide-panel,ai-runtime}/**`
- `frontend/apps/web-antd/src/views/{admin/ai,tenant/ai,user/ai-chat}/**`
- `frontend/apps/web-antd/src/composables/use-page-ai-operation-helpers.ts`

## 本次核验命令

1. AI 热点与主干文件行数核验
   - `python` 扫描 `backend/app/ai/**`、`backend/app/services/ai/**`、AI 前端相关目录
2. AI 生产文件阈值核验
   - 后端 AI `.py > 600`
   - `backend/app/ai/adapters/openai_compatible/**.py > 400`
   - 前端 AI `.vue > 450`
   - 前端 AI `.ts > 500`
   - AI 生产文件统一 `> 1000`
3. 关键结构存在性核验
   - `backend/app/ai/runtime/protocol_planner.py`
   - `backend/app/ai/runtime/protocol_runner.py`
   - `backend/app/ai/adapters/openai_compatible/**`
   - `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanelShell.vue`
4. 前端回归核验
   - `node frontend/node_modules/vue-tsc/bin/vue-tsc.js -p frontend/apps/web-antd/tsconfig.json --noEmit --skipLibCheck`
   - `pnpm exec vitest run --dom src/components/business/ai-chat-panel/__tests__/use-ai-chat.test.ts src/components/business/ai-chat-panel/__tests__/ChatMessageItem.test.ts src/components/business/ai-chat-panel/__tests__/ChatMessageItem.turn-diagnostics.test.ts src/components/business/ai-slide-panel/__tests__/AIChatSlidePanel.test.ts`
   - `pnpm exec vitest run --dom src/components/business/ai-runtime/__tests__/runtime-bridge.test.ts src/components/business/ai-runtime/__tests__/form-session-manager.test.ts src/components/business/ai-runtime/__tests__/locator-resolver.test.ts src/components/business/ai-runtime/__tests__/ui-action-executor.test.ts`

## 已完成

1. AI 生产代码 `>1000` 行文件已清零。
   - 本次扫描结果为 `NONE`。
2. 后端 AI 主链热点文件已压回治理阈值内。
   - `backend/app/ai/engine/base.py` 81 行
   - `backend/app/services/ai/conversation_service.py` 489 行
   - `backend/app/ai/adapters/openai_adapter.py` 206 行
   - `backend/app/services/ai/agent_chat_service.py` 462 行
   - `backend/app/ai/gateway.py` 456 行
3. `openai_adapter.py -> openai_compatible/**` 的 facade + package 化边界已经稳定。
   - `backend/app/ai/adapters/openai_adapter.py`
   - `backend/app/ai/adapters/openai_compatible/**`
4. 运行时协议主干已经稳定存在。
   - `backend/app/ai/runtime/contracts.py`
   - `backend/app/ai/runtime/protocol_planner.py`
   - `backend/app/ai/runtime/protocol_runner.py`
5. 前端 AI 公共入口已经完成 wrapper / shell 化。
   - `frontend/apps/web-antd/src/components/business/ai-chat-panel/ChatMessageItem.vue`
   - `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue`
   - `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`
   - `frontend/apps/web-antd/src/views/tenant/ai/agents/detail.vue`
   - `frontend/apps/web-antd/src/views/user/ai-chat/index.vue`
6. 本轮已确认的前端回归点已恢复。
   - `vue-tsc` 通过
   - AI chat / slide-panel 定向单测 86 条通过
   - AI runtime 定向单测 56 条通过
7. 前端 AI runtime / page helper 最后 5 个超阈值尾项已经完成 companion module 拆分。
   - `frontend/apps/web-antd/src/components/business/ai-runtime/runtime-bridge.ts` 21 行
   - `frontend/apps/web-antd/src/components/business/ai-runtime/form-session-manager.ts` 277 行
   - `frontend/apps/web-antd/src/components/business/ai-runtime/locator-resolver.ts` 240 行
   - `frontend/apps/web-antd/src/components/business/ai-runtime/ui-action-executor.ts` 278 行
   - `frontend/apps/web-antd/src/composables/use-page-ai-operation-helpers.ts` 22 行
8. 当前审计范围内的生产文件阈值已经全部通过。
   - 后端 AI `.py > 600`: `NONE`
   - `openai_compatible/**.py > 400`: `NONE`
   - 前端 AI `.vue > 450`: `NONE`
   - 前端 AI `.ts > 500`: `NONE`
   - AI 生产文件 `> 1000`: `NONE`

## 未完成

1. 原蓝图中的部分“最终命名即最终文件”尚未逐字落地。
   - 未形成 `backend/app/ai/intent/`
   - 未形成 `backend/app/ai/context_pipeline/`
   - 未形成 `backend/app/ai/engine/streaming/`
   - 未形成 `backend/app/services/ai/chat_command_service.py`
   - 未形成 `backend/app/services/ai/conversation_query_service.py`
2. `module-map.md` 仍未逐包普遍化，当前以 `.trellis/spec/ai-runtime/*.md` 作为等价治理文档承载。

## 可接受偏离

1. 后端服务层采用了“稳定 facade + mixins / read-model / support”而不是蓝图字面文件名。
   - 证据：
     - `backend/app/services/ai/conversation_service.py`
     - `backend/app/services/ai/conversation_facade_mixins.py`
     - `backend/app/services/ai/conversation_read_model_service.py`
   - 判断：责任边界已经稳定，命名未逐字对齐不构成主链阻塞。
2. `IntentSet`、`ContextContribution`、`ConversationReadModel` 没有全部以蓝图字面类名落地。
   - 证据：
     - intent / context / read-model 能力分别落在 `engine/context/services` 现有合同中
   - 判断：能力已存在，但公共 contract 命名未完全统一，属于可接受偏离。
3. 没有逐包落地 `module-map.md` 文件，但已有等价 canonical 文档覆盖主要边界。
   - 证据：
     - `.trellis/spec/ai-runtime/module-boundaries.md`
     - `.trellis/spec/ai-runtime/provider-contracts.md`
     - `.trellis/spec/ai-runtime/service-layer.md`
     - `.trellis/spec/ai-runtime/frontend-ai-shell.md`
     - `.trellis/spec/ai-runtime/tool-skill-governance.md`
   - 判断：治理文档已存在，当前更缺的是 runtime frontend 尾项拆分，而不是再复制一层 package README。

## 本次提升为规范的稳定事实

1. AI runtime/page 工具前端共享层已经形成稳定包边界：
   - `components/business/ai-runtime/**` 负责 page context、locator、form session、UI action 执行
   - 稳定公共入口文件可以保持 facade，不再重新吸收内部实现；新增逻辑应继续下沉到 sibling `*-core.ts` / `*-support.ts` / `*-contracts.ts`
   - 页面与通用 composable 不应再复制这些域逻辑
2. AI 模块现在适合采用明确阈值治理：
   - 后端 AI 生产模块目标不超过 600 行
   - provider 协议实现目标不超过 400 行
   - AI 前端 SFC 目标不超过 450 行
   - AI 前端 TS/composable/runtime helper 目标不超过 500 行
   - 任一 AI 生产文件超过 1000 行时视为阻塞治理债

## 收尾结论

- Phase 8 收尾治理已完成，原先 5 个 frontend AI runtime/page helper 超阈值尾项已经全部关闭。
- 主链重构、巨型热点拆分、协议/runtime/provider facade、前端公共壳层、前端 runtime 共享层与关键回归修复均已完成。
- 当前剩余的是“蓝图字面命名与治理文档形态未完全逐字对齐”的可接受偏离，不再属于阻塞 Phase 8 关闭的工程尾项。

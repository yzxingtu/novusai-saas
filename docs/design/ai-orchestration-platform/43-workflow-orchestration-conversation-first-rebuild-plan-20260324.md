# Workflow Orchestration 对话式重构方案（2026-03-24）

## 1. 结论

当前 `workflow-orchestration` 的核心问题不是“页面不够多”，而是**产品入口仍然是资源视角，不是任务视角**。

用户真实心智是：

1. 我想描述一个业务流程
2. 系统帮我梳理成可执行工作流
3. 我确认后发布
4. 我运行并看结果

当前实现却更接近：

1. 先进入模板/发布/运行/产物等资源页
2. 再猜测哪个入口对应“开始使用”
3. 新建后常常直接落到骨架页或契约不完整页面
4. AI 能力存在于宿主，但插件没有把它作为主入口

因此重构方向必须是：

- 保留插件隔离与宿主通用桥接边界
- 把首页和新建流改成**对话式 workbench**
- 把 AI 从“旁边有个面板”改成“第一入口”
- 把模板/工作流/运行/产物降级为支撑资源，而不是第一认知负担

## 2. 本轮已落地（Phase 1）

### 2.1 宿主通用 AI bridge

这轮没有把 workflow 业务逻辑塞回宿主，只补了宿主通用桥接：

- `frontend/apps/web-antd/src/store/shared/ai-panel.ts`
  - 新增面向外部入口的 `pendingMessage` / `pendingConversationId`
  - 新增 `queueMessage()` / `queueConversationRestore()` / `openWithContext()` 等桥接能力
- `frontend/apps/web-antd/src/layouts/basic.vue`
  - 将 `pendingMessage` / `pendingConversationId` 切到 `ai-panel` store 托管
  - 保持 CommandBar 与全局 AI 面板消费路径一致
- `frontend/apps/web-antd/src/utils/plugin-shared.ts`
  - 新增通用 `openAIPanel({ message, agentId, conversationId })`
  - 新增 `getActiveAIConversation()` / `subscribeAIConversation()`
  - 当前对话快照会携带 `pageContextKey` / `routePath`
  - 将该能力暴露给插件 `window.NovusPluginShared`
- `backend/plugins/workflow-orchestration/frontend/src/shared/ai.ts`
  - 新增按 `conversationScope` 的 `sessionStorage` 对话续接
  - Admin 与 Tenant planner 已分别固定到共享 scope：
    - `admin.workflow_orchestration.planner`
    - `tenant.workflow_orchestration.planner`
  - 续接写入现在会校验当前 `pageContextKey` 是否仍属于 `workflow_orchestration` 命名空间，避免无关页面把 planner 对话 scope 污染掉

这一步解决的是：插件页面不只是终于可以“主动打开全局 AI 面板并预填一句提示词”，还可以在同一条 planner 对话里从首页继续到详情页、列表页和结果页，而不会轻易被无关页面串话。

### 2.2 插件页面 AI 元数据收口

`backend/plugins/workflow-orchestration/plugin.yaml`

已为 admin / tenant 关键页面补 `ai` 元数据，包括：

- admin home / templates / template detail / template editor / releases / runtime
- tenant home / workflows / workflow create / workflow detail / workflow editor / runs / artifacts

目的：

- 宿主 `route.meta.ai` 可以明确识别这些插件页
- 页面上下文 key 不再完全依赖 path 归一化猜测
- 后续页面 context / operations 可以稳定挂载

### 2.3 Admin 首页重做为对话式 workbench

`backend/plugins/workflow-orchestration/frontend/src/views/admin/home/index.vue`

已重做为：

- 第一屏先给 AI 需求输入框
- 明确主动作：
  - 让 AI 帮我规划
  - 新建模板
  - 刷新
- 提供 3 个 starter prompts
- 明确 3 步 onboarding：
  - 新建模板
  - 做发布检查
  - 看运行治理
- 原有统计数据降级为次级概览

同时补了页面 AI context / operations：

- 打开模板新建入口
- 打开 AI 规划
- 打开运行治理
- 刷新首页

### 2.4 Admin 模板页从“资源页”继续收口到 planner hub

`backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/index.vue`

已不仅支持通过路由 query 自动打开新建模板弹窗，也继续接回 admin planner 对话链：

- 顶部新增 AI 入口，可直接基于当前筛选词继续模板规划
- 列表首屏新增明确的“Ask AI / 新建模板”双入口
- 空态补齐“Ask AI / 新建模板”双 CTA
- 接入页面 AI context / operations：
  - 打开模板新建入口
  - 打开模板 AI 规划
  - 打开发布中心
  - 刷新模板列表

这解决的是：

- 首页 CTA 不再只是“带你去模板列表”
- 可以直接进入新建动作，不要求用户再自己找一次按钮
- 模板列表不再是纯资源页，而是 admin planner 的第二站

### 2.5 Tenant 首页改成“先说需求，再创建”

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/home/index.vue`

已改为：

- 第一屏先放 AI 输入框
- 主动作：
  - 让 AI 帮我起步
  - 开始新建工作流
  - 打开工作流中心 / 运行中心
- starter prompts
- 三步式 onboarding：
  - 新建工作流
  - 发布版本
  - 运行并看结果

同时保留原有：

- 今日待办
- 重点工作流
- 运行与结果流
- 风险告警
- 平台边界说明

也就是说，**运营视角没有丢，但第一屏的认知负担已经从“看板”切成“起步动作”**。

### 2.6 Tenant 独立新建引导页

新增：

- `backend/plugins/workflow-orchestration/frontend/src/views/tenant/workflows/create.vue`
- `backend/plugins/workflow-orchestration/frontend/src/index.ts`
- `backend/plugins/workflow-orchestration/plugin.yaml`

现在 tenant 不再只能从 `workflows/new/editor` 这种骨架式路径直接掉入编辑器，而是先进入：

- 对话式起步卡片
- 快速空白创建表单
- 三步说明卡片

并且这个页面已经接上 page-aware AI：

- `create_blank_workflow`
- `open_workflow_ai_planner`
- `open_workflow_center`

### 2.7 Tenant 工作流列表收口到“新建引导 + AI”

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/workflows/index.vue`

已改为：

- 主按钮不再直接跳骨架编辑器，而是跳 `workflows/new`
- 新增“让 AI 帮我规划”动作
- 空态也给出 AI 与新建引导
- 对不可运行的 workflow 增加“先发布再运行”的显式提示
- 接入页面 AI context / operations：
  - 打开新建引导
  - 打开 AI 规划
  - 刷新工作流列表

### 2.8 多语言同步

本轮同步更新了：

- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/zh-CN.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/en-US.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/zh-CN.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/en-US.ts`

重点新增的是：

- 首页 conversation-first 文案
- 新建引导页文案
- starter prompt 文案
- AI operation label/description

### 2.9 Admin 发布/运行页接回同一条 planner 对话链路

`backend/plugins/workflow-orchestration/frontend/src/views/admin/releases/index.vue`

已继续从“纯发布列表”收口到 planner flow：

- 顶部新增 AI 入口，可直接让 AI 判断当前应该补模板、做发布检查还是回运行治理
- 列表页接入页面 AI context / operations：
  - 打开模板中心
  - 打开发布 AI 规划
  - 刷新发布中心

`backend/plugins/workflow-orchestration/frontend/src/views/admin/runtime/index.vue`

已继续从“纯运行表格”收口到 runtime-governance assistant：

- 顶部新增 AI 入口，可直接让 AI判断当前应重放、恢复、终止还是回模板侧修订
- 列表页接入页面 AI context / operations：
  - 打开模板中心
  - 打开运行治理 AI
  - 刷新运行治理

这一步的目的，是把 admin 侧主链路收成一条真实顺序：

1. 首页开始规划
2. 到模板列表继续细化并创建
3. 到发布中心做发布检查
4. 到运行治理处理上线后的真实运行问题

### 2.10 Tenant 运行/结果中心接回同一条对话链路

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/runs/index.vue`

已继续收口为“下一步判断中心”，不再只是动作按钮列表：

- 顶部新增 AI 入口，可直接让 AI 判断当前应该回工作流、继续观察运行，还是进入结果中心
- 空态补上“回工作流中心 + 打开 AI”双 CTA，不再只有被动空页
- 接入页面 AI context / operations：
  - 打开工作流中心
  - 打开结果中心
  - 打开运行 AI 助手
  - 刷新运行中心

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/artifacts/index.vue`

已继续收口为“结果解读与后续处理中心”：

- 顶部新增 AI 入口，可直接让 AI 解读当前结果后该回运行、回工作流，还是直接处理结果
- 空态补上“回工作流中心 + 回运行中心 + 打开 AI”三向 CTA
- 接入页面 AI context / operations：
  - 打开运行中心
  - 打开工作流中心
  - 打开结果 AI 助手
  - 刷新结果中心

这一步的目的不是增加更多页面，而是把 tenant 侧的后半程也并回同一条 conversation-first 节奏：

1. 先说需求
2. 再创建/复制工作流
3. 然后发布与运行
4. 最后在运行/结果页继续沿着同一条 AI 对话判断下一步

### 2.11 Tenant run detail / artifact detail 继续接回 planner 对话

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/runs/detail.vue`

已继续接回同一条 `TENANT_WORKFLOW_AI_CONVERSATION_SCOPE`：

- 顶部新增 `Ask AI` 动作，不再让 run detail 只剩信息浏览和手动按钮
- 页面 AI context 已包含 run id / workflow id / status / current node / artifact count
- 页面 operations 已补：
  - 打开工作流详情
  - 打开相关结果
  - 打开运行 AI 助手
  - 刷新运行详情

`backend/plugins/workflow-orchestration/frontend/src/views/tenant/artifacts/detail.vue`

也已接回同一条 planner 对话：

- 顶部新增 `Ask AI` 动作
- 页面 AI context 已包含 artifact id / workflow id / run id / status / type / downloadability / feedbackability
- 页面 operations 已补：
  - 打开工作流详情
  - 打开运行详情
  - 打开结果 AI 助手
  - 刷新结果详情

这一步的意义是：

- tenant 侧不再只有列表页能续 AI，对话可以继续深入到具体运行和具体结果
- 用户从“列表 -> 详情”后不需要重新开一条新对话解释上下文
- detail 页开始承担“继续判断下一步”的角色，而不是纯只读终点

## 3. 本轮验证

已完成：

- `backend/plugins/workflow-orchestration/frontend` 下 `npm run build`
  - 通过
- admin / tenant locale key 对齐检查
  - admin `zh-CN = 350`，`en-US = 350`
  - tenant `zh-CN = 473`，`en-US = 473`
  - 双向缺失均为空
- `frontend/apps/web-antd` 下定向 vitest
  - `src/store/shared/__tests__/ai-panel.test.ts`
  - `src/composables/__tests__/use-plugin-frontend-init.test.ts`
  - 通过

额外说明：

- 宿主全量 `vue-tsc --noEmit` 仍被现有测试文件阻断：
  - `frontend/apps/web-antd/src/composables/__tests__/use-plugin-frontend-init.test.ts`
  - `frontend/apps/web-antd/src/components/business/ai-slide-panel/__tests__/AIChatSlidePanel.test.ts`
  - `frontend/apps/web-antd/src/components/business/org-node-dialog/OrgNodeDialog.vue`
- 这不是本轮 workflow-orchestration 新逻辑引入的业务错误，而是当前宿主测试文件本身已有类型问题

本轮未完成：

- 浏览器级长链路手工验收
- 从“新建 -> 发布 -> 运行 -> 结果反馈”的完整 UI 回归

原因：

- 当前工具链浏览器调用超时，无法稳定完成远程页面交互

## 4. 仍然没解决的真实问题（Phase 2 重点）

### 4.1 Tenant 已有模板目录 API，但还要继续收口成稳定闭环

当前真实状态已经不是“缺 API”，而是“API 与起步体验还需要继续收口”。

现在 tenant 侧已经具备：

- `GET templates`
- `POST workflows/copy-from-template`
- 新建页里的模板卡片 / 搜索 / 复制入口

这意味着：

- tenant 第一跳已经不再只有“空白创建 + AI”
- 但模板目录仍只是新建页中的一个区域，不是完整的任务起步闭环
- 列表看到的已发布版本、复制时锁定的版本、复制成功后的默认落点，都需要继续保持一致

本轮新增收口：

- 模板卡片返回 `current_published_version_id`
- `copy-from-template` 按当前已发布版本锁定复制，不再允许直接 POST 绕过“已发布可复制”约束
- 创建成功后默认进入 detail hub，而不是直接掉进骨架 editor
- 新建成功与模板复制成功文案已改成“进入详情页/detail hub”，不再误导成“直接进入 editor”

下一步要补：

- tenant 模板目录的来源说明 / 版本说明 / 适用范围说明
- copy-only 角色的页面级显式 gating 与空态引导
- detail hub 到 publish / run / artifact 的下一步提示

### 4.2 发布动作仍不够显式

当前发布能力存在，但还缺：

- 可视化 checklist
- 禁用原因解释
- “为什么我现在不能发布”的页面内说明

下一步要补：

- 编辑器/详情页的发布准备度卡片
- 缺失版本 / 缺失快照 / 状态不允许发布 的原因回显

### 4.3 运行入口仍应继续简化

当前已经加了“先发布再运行”提示，但还不够：

- 运行列表空态仍可更直接
- 运行详情与结果中心之间可再缩短一步

下一步要补：

- 运行列表空态 CTA 再收口
- 从 workflow detail 到 run / artifact 的联动强化

### 4.4 编辑器仍然是骨架，不是可完成任务的 builder

这是整个产品仍然最重的技术债：

- Admin template editor 仍主要是骨架
- Tenant editor 仍然偏“基础信息 + 画布预览”
- 还不是一个真正 conversation-first builder

Phase 2/3 需要判断：

1. 是继续补足可视化 builder
2. 还是直接转向“AI 主导编排，画布只做检查与修正”

从当前用户反馈看，建议偏向第 2 条。

## 5. 推荐的下一阶段重构顺序

### Phase 2

1. 做 tenant 模板目录与“从模板创建”
2. 做发布 checklist 与禁用原因解释
3. 做 run / artifact 空态 CTA 收口
4. 做首页与新建页的浏览器级回归

### Phase 3

1. 定义 conversation-first builder 交互模型
2. AI 输出 workflow draft
3. 页面只承担：
   - 约束确认
   - 版本检查
   - 运行前校验
   - 结果回看
4. 把“画布编辑”降为专家模式，而不是默认入口

## 6. 产品验收标准

重构后的合格标准不是“页面更多”，而是以下问题都能回答“是”：

### Admin

- 首页第一屏是否能直接开始规划模板
- 是否能直接进入模板新建，而不是先看资源页
- 是否能明确知道“新建 -> 发布 -> 运行治理”的顺序

### Tenant

- 用户是否能在 10 秒内找到“怎么新建”
- 是否能先与 AI 讨论，再决定创建
- 是否能在创建后明确下一步是发布还是运行
- 是否能从运行与结果页面回到同一条运营节奏

### AI 集成

- 插件页面是否能主动打开全局 AI 面板
- AI 是否能拿到稳定的 page key / context
- AI 是否能执行页面级导航或刷新，而不是只会聊天

## 7. 边界原则

这轮以及后续都继续遵守：

- workflow 业务逻辑留在 `backend/plugins/workflow-orchestration/**`
- 宿主只补通用能力，不写 workflow 私有逻辑
- 所有页面用户可见文案必须进 locale
- page-aware AI 接入优先复用宿主现成机制，不另起一套私有对话系统

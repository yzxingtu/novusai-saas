# AI 页面能力统一交接记录

审计时间：2026-03-22

## 一、背景

本轮工作承接 [ai-page-capability-unification.plan.md](/E:/git_clone/novusai-saas-yudi/docs/design/ai-page-capability-unification.plan.md)，目标是把页面 AI 能力统一到同一套运行时协议，并在收尾阶段清理前端接入噪音、补齐缺失说明、核对 `rules / skill` 口径是否一致。

此前用户口头提到的交接文档路径为 `docs/design/ai-page-capability-unification-handoff-20260322.md`，仓库中实际缺失。本文件即为补齐后的正式交接记录。

## 二、本轮已完成事项

### 1. 富文本页能力统一接入已补齐

已新增并接回以下共享 helper / 页面接入文件：

- [use-page-ai-operation-helpers.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-page-ai-operation-helpers.ts)
- [command-operation-helpers.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/command-operation-helpers.ts)
- [content-operation-helpers.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/content-operation-helpers.ts)
- [document-page-ai.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/document-page-ai.ts)

目的：

- 把富文本命令型操作和内容型操作抽到共享层
- 让富文本页能力不再散落在单页实现中
- 与 `useDetailPageAi()` / `useCrudList` / `useCrudPage` 的统一 page AI 协议保持同方向演进

### 2. 编译报错与页面接入回归已修复

已修复：

- [DomainsModal.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/tenant/list/modules/DomainsModal.vue) 的 `@click` 事件签名问题
- [use-detail-page-ai.test.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/__tests__/use-detail-page-ai.test.ts) 的预期同步更新
- 缺失文件导致的 `import-analysis` 报错链已经收口

### 3. Vite 构建链噪音已收口

构建侧本轮做了两类整理：

- Vite 插件从前端 `src` 目录移到 Node 侧构建目录：
  - [vite-plugin-novus-plugins.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts)
  - [vite.config.mts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/vite.config.mts)
  - [tsconfig.node.json](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/tsconfig.node.json)
  - [tsconfig.json](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/tsconfig.json)
- 生产构建误吃到 workspace stub dist 的问题已规避：
  - [vite.config.mts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/vite.config.mts)

关键结论：

- `jiti/createRequire` 报错并不是来自业务页面 AI 代码
- 实际根因是 `@vben-core/shared` 的 `dist/*.mjs` 为 `unbuild --stub` 产物，内部通过 `jiti` 跳回 `src`
- `vite build` 在生产模式下错误解析到了这些 stub 文件，导致浏览器构建链带入 Node-only 的 `jiti`
- 现已在 Vite 中将 `@vben-core/shared/*` 子路径定向到 `src`，同时将 `pinia-plugin-persistedstate` 锁到浏览器可用入口，构建恢复通过

### 4. 规则与 Skill 口径已统一

已核对并统一：

- [ai-architecture.md](/E:/git_clone/novusai-saas-yudi/.cursor/rules/ai-architecture.md)
- [novusai-saas.md](/E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md)
- [SKILL.md](C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md)

统一后的口径：

- `ResourceScopeEnum` 只认五类：`global_shared` / `admin_only` / `all_tenants` / `admin_and_selected_tenants` / `selected_tenants`
- Skill 无独立 `scope`
- SkillPackage / Skill 的“是否企业自有 / 是否可编辑”只看 `tenant_id` / `owner_tenant_id`
- 禁止继续用旧的 `all_tenants + tenant_id 是否为空` 双重语义判断企业归属

## 三、已验证门禁

以下命令已在 2026-03-22 本地复验通过：

```powershell
cd frontend/apps/web-antd
pnpm exec vue-tsc --noEmit --skipLibCheck
```

```powershell
cd frontend
pnpm run test:unit -- --run `
  apps/web-antd/src/components/business/rich-text-editor/__tests__/useEditorPageOps.test.ts `
  apps/web-antd/src/components/business/ai-slide-panel/__tests__/pageContextEditorOps.test.ts `
  apps/web-antd/src/composables/__tests__/use-detail-page-ai.test.ts `
  apps/web-antd/src/composables/__tests__/use-page-operation-channel.test.ts
```

结果：4 个测试文件，19 个用例，全部通过。

```powershell
cd frontend/apps/web-antd
pnpm exec vite build
```

结果：构建通过，插件静态资源正常复制。

## 四、当前剩余事项

以下问题目前仍存在，但已确认为非阻塞项：

### 1. 构建告警仍有噪音

`vite build` 目前仍会输出两类 warning：

- `ant-design-vue` 某些组件既被动态导入又被静态导入，导致“dynamic import will not move module into another chunk”
- 个别 chunk 体积较大，`bootstrap-*.js` 超过默认 chunk warning 阈值

这两类属于性能/分包优化问题，不再阻塞功能正确性、类型检查或生产构建。

### 2. Vitest 配置有低优先级弃用提示

当前 `frontend/vitest.config.ts` 仍会提示 workspace file 方案后续将弃用，建议未来迁移到 `test.projects`。

### 3. 后端 Alembic / 数据库启动报错未纳入本轮处理

用户已明确说明此前多次出现的数据库迁移/启动异常“不是本轮修改引入，不需要处理”。因此本轮没有修改任何后端迁移恢复逻辑，也没有对相关报错做收敛。

## 五、如果下一轮继续推进

建议按以下顺序继续：

1. 清理 [component/index.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/core/adapter/component/index.ts) 与 `ant-design-vue` 的动态/静态混用告警
2. 评估 `bootstrap` 大 chunk 的拆分策略，必要时补 `manualChunks`
3. 将 `frontend/vitest.config.ts` 迁移到 `test.projects`
4. 继续把剩余手写 page AI 页面收敛到统一 helper 与自动接入协议

## 六、当前结论

截至 2026-03-22，本轮“AI 页面能力统一”收尾工作里，前端真实阻塞项已清理完成：

- 缺失 helper / 缺失导入已补齐
- 类型检查通过
- 相关单测通过
- 生产构建通过
- `rules / skill` 口径已统一
- 正式 handoff 文档已补齐

可以在此基础上继续做下一轮 page AI 能力统一或纯性能噪音治理，不需要再回头处理本轮已收口的问题。

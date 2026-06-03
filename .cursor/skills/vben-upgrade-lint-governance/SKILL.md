---
name: vben-upgrade-lint-governance
description: NovusAI 前端 vben 升级与 lint 治理技能。用于执行 vue-vben-admin 上游升级、维护 baseline/ownership/vendor 产物、区分升级相关与历史 lint 债，并按目录分片做安全回归与并行清理。
---

# Vben 升级与 Lint 治理技能

## 何时使用

- 升级 `frontend/` 的 vben 上游版本
- 维护 `frontend/docs/upgrade/**`、`frontend/scripts/vben/**`
- 处理“大批量前端 lint 债”
- 需要把升级相关问题与历史遗留问题拆开治理
- 需要并行拆分前端子目录给子代理清理

## 先看这些文件

- `frontend/docs/upgrade/vben-baseline.json`
- `frontend/docs/upgrade/vben-ownership.yaml`
- `frontend/docs/upgrade/reports/*.md`
- `frontend/scripts/vben/sync-upstream.mjs`
- `frontend/scripts/vben/diff-upstream.mjs`
- `frontend/scripts/vben/verify-upgrade.mjs`

## 升级总原则

- 默认在真实仓库 `E:\git_clone\novusai-saas-yudi` 落改动；不要把最终结果留在临时 worktree。
- 升级策略固定为“强跟踪，不做 upstream 历史 merge”。
- 不把根 `package.json.version` 当升级完成标准。
- 主仓长期只保留 `web-antd`；官方其他 app 只做参考快照。
- 升级时优先保护 Novus 插件桥接：
  - `frontend/apps/web-antd/vite.config.mts`
  - `frontend/apps/web-antd/build/**`
  - `frontend/apps/web-antd/src/utils/plugin-*.ts`
  - `frontend/apps/web-antd/src/composables/use-plugin-frontend-init.ts`

## 升级执行顺序

1. 先更新上游事实与基线文件，不要先改业务页。
2. 先同步 `upstream_owned`：workspace、catalog、toolchain、`packages/**`、`internal/**`、`playground/**`。
3. 再恢复 `novus_bridge_owned`：插件资源路径、代理、运行时桥接、动态路由初始化。
4. 最后才处理 `product_owned`：仅合并真正有上游改动冲突的业务面。
5. 完成后更新 baseline、ownership、diff 报告。

## Lint 治理顺序

- 先拆成两类：
  - 升级相关 lint：本次升级引入的错误，必须先清零
  - 历史 lint 债：升级完成后再逐片处理
- 历史 lint 债一律按目录分片，不要全仓混修。
- 每处理完一个片区都要回跑该片区 `eslint` / `stylelint` / `prettier --check`。
- 片区通过后再回全量 `pnpm -C frontend run lint`，重新取最新热点，不追旧清单。

## 推荐分片

- `frontend/apps/web-antd/src/components/business/**`
- `frontend/apps/web-antd/src/views/user/**`
- `frontend/apps/web-antd/src/views/admin/**`
- `frontend/apps/web-antd/src/views/tenant/**`
- `frontend/apps/web-antd/src/composables/**`
- `frontend/apps/web-antd/src/core/**`
- `frontend/apps/web-antd/src/views/_core/**`
- `frontend/apps/web-antd/src/views/_shared/**`
- `frontend/apps/web-antd/src/{api,constants,layouts,locales,router,store,types,utils}/**`
- `frontend/{packages,internal,playground,scripts}/**`

## 子代理规则

- 只有目录所有权完全不重叠时才并行。
- 每个子代理都要明确写清 owned paths。
- 子代理只允许修改自己负责的目录，不得顺手改别处。
- 主代理负责：
  - 分配目录
  - 审计回报
  - 复核主工作区结果
  - 回全量 lint / build / test

## 常用命令

```powershell
corepack pnpm -C frontend run lint
corepack pnpm -C frontend run check:type
corepack pnpm -C frontend run build:antd
corepack pnpm -C frontend run test:unit

corepack pnpm -C frontend exec eslint "<glob>"
corepack pnpm -C frontend exec eslint --fix "<glob>"
corepack pnpm -C frontend exec stylelint "<glob>"
corepack pnpm -C frontend exec stylelint --fix "<glob>"
corepack pnpm -C frontend exec prettier --write "<glob>"
corepack pnpm -C frontend exec prettier --check "<glob>"
```

## 可接受的最小策略

- 格式问题优先用 `prettier --write`
- 样式顺序/alpha 规则优先用 `stylelint --fix`
- import 顺序、简单 `eqeqeq`、`toSorted()`、`replaceAll()` 等优先用 `eslint --fix`
- 只有自动修不动时才手改
- 手改要尽量保持行为不变

## 生成物与例外

- 生成物优先通过 `.prettierignore` 或窄范围 eslint/stylelint 例外处理，不要反复手格式化。
- 对 `v-html`、测试 harness 多组件文件、JSDoc 等 warning，只有在安全语义明确时才压制。
- DOMPurify 包裹的 `v-html` 若确需保留，必须写明是窄范围例外。

## 最终验收

至少确认：

- `corepack pnpm -C frontend run lint` 通过
- `corepack pnpm -C frontend run check:type` 通过；若失败，明确是项目既有基线还是本次引入
- `corepack pnpm -C frontend run build:antd` 通过
- `corepack pnpm -C frontend run test:unit` 通过；若失败，先修 mock/契约漂移
- 插件资源与 admin/tenant 关键页面冒烟不回退

## 输出要求

- 回报时区分：
  - 已清零的片区
  - 剩余 error 数
  - 剩余 warning 数
  - 是否已回全量 lint / type / build / unit test
- 如果只清了片区，不要声称“全仓完成”。

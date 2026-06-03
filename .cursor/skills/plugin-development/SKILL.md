---
name: plugin-development
description: NovusAI 插件开发技能。用于修改 plugin.yaml、前端 runtime 契约、权限桥接、菜单标题、多语言、release manifest 与浏览器回归闭环。只保留可执行规则与检查项。
---

# 插件开发技能

这是一个薄路由技能。插件 runtime 的 canonical 规则已经收口到
`.trellis/spec/guides/plugin-runtime-playbook.md`。

## 何时使用

- 新建或重构 `backend/plugins/{plugin-name}/`
- 修改 `plugin.yaml`、`extensions.frontend.pages[*]`、`pages[*].menu`
- 排查插件页面首屏 403、菜单可见但页面不可进、切语言后标题不更新、生产态白屏、public asset 错端加载
- 审核 loader cache、release manifest、permission bridge、浏览器回归闭环

## Canonical Sources

先读这些：

1. `.trellis/spec/guides/plugin-runtime-playbook.md`
2. `.trellis/spec/backend/index.md`
3. `.trellis/spec/frontend/index.md`

`.cursor/rules/plugin-system.md` 只在需要宿主实现细节时补充阅读。

## 默认流程

1. 读目标插件的 `plugin.yaml`
2. 读宿主消费链路：
   - `/permissions/menus`
   - `/plugins/slots`
   - `ensurePluginRoutes()`
   - `loadPluginComponents()` / `getPluginComponent()`
3. 落最小改动
4. 跑：
   - `novusai plugin validate backend/plugins/{name}`
   - `novusai plugin build backend/plugins/{name}`
   - `novusai plugin pack backend/plugins/{name} --release`
5. 做真实浏览器回归

## 禁止

- 不要再依赖旧的兼容 playbook
- 不要在这里复制长篇插件规范正文
- 不要跳过 validate/build/pack/browser regression

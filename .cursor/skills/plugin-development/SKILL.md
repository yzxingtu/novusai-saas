---
name: plugin-development
description: NovusAI 插件开发技能。适用于新建插件、迁移旧插件、修复 plugin.yaml、处理授权/启动恢复/前端契约、或执行 plugin CLI 的场景。
---

# 插件开发技能

## 何时使用

- 新增 `backend/plugins/{name}/` 插件
- 将旧插件迁移到 `pages + dev.entry + release.manifest`
- 修复授权、启用、过期、恢复、启动恢复链路
- 调整插件菜单挂载、页面声明、前端 slots
- 执行 `novusai plugin build / validate / pack`

## 必守模型

- 插件必须零侵入，代码只能留在插件目录内。
- `plugin.yaml` 是声明层单一事实来源。
- License 语义只允许：
  - `trial`
  - `fixed_term`
  - `perpetual`
- 页面与菜单只允许：
  - `extensions.frontend.pages[*]`
  - `pages[*].menu`
- 前端契约只允许：
  - 开发态：`extensions.frontend.dev.entry`
  - 生产态：`extensions.frontend.release.manifest`
- 当前不支持 `user` 端插件；只写 `admin` / `tenant`。

## 前端开发规则

- dev 模式走 `/__plugin_dev__/{plugin}/entry`，用于源码调试与 HMR。
- production 模式只能消费 `frontend/dist/plugin.manifest.json` 和其声明的发布产物。
- 插件元数据图标只允许插件根目录 `icon.png`；未提供时宿主管理端统一回退 `lucide:plug`。
- 插件页面/菜单图标默认使用 `lucide:*`，禁止依赖在线 Iconify。
- 不允许继续写：
  - `frontend.menus`
  - `frontend.standalone_pages`
  - `frontend.admin.entry`
  - `frontend.tenant.entry`
  - `frontend.npm_dependencies`
- release 产物缺失时，安装/启用必须 fail-close。

## 菜单与权限

- 页面路径、组件名、标题只在 `pages[*]` 声明一次。
- `pages[*].menu` 只负责菜单入口元数据，不重复声明页面路由。
- 菜单位置调整只重建导航域，不重跑整套扩展注册。
- 权限同步唯一入口是 `sync_plugin_permissions(plugin.name)`。

## 启动边界

- `discover` 只做发现和漂移标记。
- `sync-manifest` 只同步同版本 manifest 漂移，不覆盖 `granted_capabilities`。
- `upgrade` 才能处理版本变化。
- 启动恢复不处理前端 npm 依赖。

## 依赖模型

- Python 依赖运行在共享宿主环境。
- `install / upgrade / repair / dependencies/install` 可以处理 Python 依赖；
  `enable` 会在共享环境预检通过后按需补装缺失依赖。
- `startup restore` 只校验 Python/插件依赖，不再自动 `pip install`。
- 插件间依赖只允许 `dependencies.plugins`：
  - 推荐对象写法：`{ plugin, version }`
  - 无版本约束时可简写为字符串
- 新 manifest 禁止：
  - `compatibility.requires`
  - `dependencies.system`
- 运行时仅对历史数据库中的旧 `manifest` 投影保留兼容读取，不能继续在源码和脚手架里生成旧字段。

## 常用命令

```bash
novusai plugin create my-plugin --template=minimal
novusai plugin create my-plugin --template=full-module
novusai plugin build backend/plugins/my-plugin
novusai plugin validate backend/plugins/my-plugin
novusai plugin pack backend/plugins/my-plugin --release
novusai plugin pack backend/plugins/my-plugin --source
```

## 开发检查清单

1. 先确认插件顶层 `scope` 与企业分配模型是否一致。
2. 再确认 `capabilities` 是否与真实行为匹配。
3. 再确认 `dependencies.python` / `dependencies.plugins` 是否与真实运行模型一致。
4. 如有前端页面，必须同时检查：
   - `pages[*].path`
   - `pages[*].scope`
   - `pages[*].component`
   - `pages[*].menu`
   - `pages[*].icon`
   - `extensions.frontend.dev.entry`
   - `extensions.frontend.release.manifest`
5. 如有图标，必须同时检查：
   - 顶层 `icon` 是否为 `icon.png` 或空字符串
   - 插件根目录是否真的提供了 `icon.png`
   - 是否没有引入在线 Iconify 依赖
6. 如是付费插件，确认统一 runtime gate 已覆盖执行入口。
7. 最后跑 `validate`、相关 pytest/vitest、以及需要的 `pack` 验证。

## 参考

- `../novusai-saas/references/plugin-spec.md`
- `../novusai-saas/references/icon-spec.md`
- `../novusai-saas/references/plugin-menu-registration.md`
- `../../../docs/audit/plugin-system-comprehensive-audit-20260322.md`

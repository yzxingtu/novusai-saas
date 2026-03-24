---
name: plugin-development
description: NovusAI 插件开发技能。用于修改 plugin.yaml、前端 runtime 契约、权限桥接、菜单标题、多语言、release manifest 与浏览器回归闭环。只保留可执行规则与检查项。
---

# 插件开发技能

## 先读最小手册

开始任何插件开发、修复、审计之前，先读：

- `.cursor/ai-plugin-minimum-playbook.md`

这份最小手册优先解决 AI 最容易复发的错误：

- 菜单不显示
- 菜单未翻译
- 页面能看到但进不去
- 切语言后标题不更新
- public asset 错端加载
- release 打包后白屏

如果最小手册与本技能正文冲突，以最小手册和 `.cursor/rules/plugin-system.md` 为准。

## 何时使用

- 新建或重构 `backend/plugins/{plugin-name}/`
- 修改 `plugin.yaml`、`extensions.frontend.pages[*]`、`pages[*].menu`
- 排查插件页面首屏 403、菜单可见但页面不可进、切语言后标题不更新、生产态白屏、public asset 错端加载
- 审核 loader cache、release manifest、permission bridge、浏览器回归闭环

## 开始前先做什么

1. 读目标插件的 `plugin.yaml`。
2. 判定插件前端入口属于哪类：
   - 普通 admin 页面
   - 普通 tenant 页面
   - public 资源入口，例如登录前 captcha provider
   - 只有 slot/widget，没有 page
3. 读宿主 3 条消费链路：
   - 菜单：`/permissions/menus`
   - 页面：`/plugins/slots` + `ensurePluginRoutes()`
   - 资产：`loadPluginComponents()` / `getPluginComponent()` / `buildPluginAssetUrl()`
4. 再开始改代码；不要先猜权限、猜 side、猜 manifest。

## 必守规则

### 1. 声明层

- `plugin.yaml` 是插件页面、菜单、权限、前端入口的单一事实源。
- 页面只在 `extensions.frontend.pages[*]` 声明。
- 菜单只在 `pages[*].menu` 声明。
- 页面标题只来自 `pages[*].title`。
- 菜单标题只来自 `pages[*].menu.title`。
- 插件内部按钮、表单、提示文案才允许走 `registerLocale(locale, 'plugin.{manifest-name}', messages)`。
- 不要把插件菜单标题写进宿主 `backend/app/locales/*/menu.json`。

### 2. runtime signature

- 调用 loader 时 scope 必须显式传入，而且只能二选一：
  - `endpoint`
  - `publicEndpoint`
- 禁止省略 scope 参数。
- 禁止同时传 `endpoint` 与 `publicEndpoint`。
- loader cache key 必须同时包含：
  - scope signature：`pluginName::auth:{endpoint}` 或 `pluginName::public:{publicEndpoint}`
  - runtime signature：`dev={dev_entry}|manifest={release_manifest}`
- 同插件、同 scope 下，只要 `dev_entry` 或 `release_manifest` 改变，就必须重新加载。
- `setup()` 成功后才能写入 loaded cache。
- `setup()` 失败后必须清理中间状态，允许下次重试。
- `unloadPlugin()` 只能清理目标 scope，不能误删同插件其他 scope。

### 3. public asset 隔离

- 普通 admin/tenant 页面、page slot、dashboard widget、settings tab、notification UI 一律走：
  - `loadPluginComponents(plugin, runtime, { endpoint })`
  - `/plugin-assets/{plugin}/{file}`
- 只有 public 资源入口才允许走：
  - `loadPluginComponents(plugin, runtime, { publicEndpoint })`
  - `/plugin-public-assets/{publicEndpoint}/{plugin}/{file}`
- `publicEndpoint` 不是通用 side 选择器。
- public asset 请求不得带 `Authorization` 头。
- public asset 侧必须清理历史 `novus_plugin_asset_token` cookie。
- 只要 public asset 请求仍携带历史 cookie，或响应没有主动清 cookie，都按未收口处理。
- 如果调用方传入预前缀路径，路径必须与当前 `pluginName`、当前 scope 对齐；不对齐时必须 fail-close。

### 4. release manifest

- 开发态入口只认 `extensions.frontend.dev.entry`。
- 生产态入口只认 `extensions.frontend.release.manifest`。
- release 契约文件固定为 `frontend/dist/plugin.manifest.json`。
- `/plugins/slots` 返回的前端 slot 必须携带 `frontend_runtime`。
- manifest 中声明的组件名，必须由插件前端入口真实导出。
- install / enable / sync-manifest 运行时同样要校验：
  - `pages[*].title` / `pages[*].menu.title` locale 完整
  - 若 `frontend.dev.entry` 存在，则必须含 canonical locale prefix
  - 若 `frontend.dev.entry` 存在，则必须导出 manifest 声明组件
- 声明了 `release.manifest` 却没有产出 `frontend/dist/plugin.manifest.json`，按失败处理，不得降级启用。
- `pack --source` 不是 release 验收，必须跑 `validate -> build -> pack --release`。

### 5. permission bridge

- 宿主菜单码与插件页面码必须闭环。
- `pages[*].menu` 存在时，页面访问码必须桥接菜单码。
- 当前菜单桥接格式固定为：
  - `menu:{scope}.plugin_{safe_plugin_name}_{page_name}`
- 前端权限池必须把菜单 `code` 放进 `accessStore.accessCodes`。
- 插件前端权限判断必须优先使用桥接：
  - `window.NovusPluginShared.getAccessCodes()`
  - `window.NovusPluginShared.hasAccessByCodes(codes)`
- 插件页面首屏请求前先判权限，不要先发请求再吃 403。
- CTA 必须按“目标权限 + 当前状态”一起 gating；不要只看状态，不要只看菜单可见。

### 6. menu / i18n / title

- manifest 标题是真相，不是一次性快照。
- 宿主消费插件标题时必须保留可重算来源，例如 `titleLocaleMap`。
- `registerLocale()` 只影响插件内部文案，不负责菜单标题系统。
- 插件前端至少注册一个 canonical prefix：
  - `plugin.{manifest-name}`
- legacy alias 只允许兼容，不能只有 alias 没有 canonical。
- 只有当前代码仍在消费 legacy key 时，才允许保留 alias；一旦源码已迁到 canonical prefix，就必须删除 alias 注册，避免兼容层长期滞留。
- 切语言后必须同步验证：
  - sidebar
  - breadcrumb
  - `document.title`
  - 页面 heading
  - 已打开 tab 标题

## 开发/审计步骤

1. 读 `plugin.yaml`
   - 检查 `scope`
   - 检查 `extensions.frontend.pages[*]`
   - 检查 `pages[*].menu`
   - 检查 `permissions[*]`
   - 检查 `extensions.frontend.dev.entry`
   - 检查 `extensions.frontend.release.manifest`
2. 读插件前端入口
   - 是否导出所有声明组件
   - 是否注册 `plugin.{manifest-name}` locale prefix
   - 是否在首屏请求前做权限 gating
   - 是否基于 `window.NovusPluginShared` 做 CTA gating
3. 读宿主消费点
   - `/permissions/menus`
   - `/plugins/slots`
   - `ensurePluginRoutes()`
   - `loadPluginComponents()` / `getPluginComponent()`
4. 跑 CLI
   - `novusai plugin validate backend/plugins/{name}`
   - `novusai plugin build backend/plugins/{name}`
   - `novusai plugin pack backend/plugins/{name} --release`
5. 做浏览器回归

## 审计清单

### loader / asset

- 是否仍有只按 `pluginName` 缓存的地方
- 是否仍有省略 scope 参数的 loader 调用
- 是否存在把普通页面错误打到 `/plugin-public-assets/...`
- 是否允许 public/auth 预前缀路径旁路 scope 校验
- 是否在 runtime contract 变化后仍复用旧 bundle

### permission bridge

- 菜单 `code` 是否进入 `accessStore.accessCodes`
- `/plugins/slots` 的 `accessCodes` 是否同时含显式页面码与菜单桥接码
- 插件前端是否通过 `window.NovusPluginShared.getAccessCodes/hasAccessByCodes` 判权限
- 首屏请求前是否已完成权限 gating
- CTA 是否按目标权限 + 当前状态一起控制

### title / i18n

- `pages[*].title` 是否补齐 `zh-CN` / `en`
- `pages[*].menu.title` 是否补齐 `zh-CN` / `en`
- 是否保留 `titleLocaleMap`
- 切语言后 breadcrumb / tab / document title 是否同步更新

### release

- `frontend/dist/plugin.manifest.json` 是否存在
- manifest `entry` / `css` / `assets` 是否真实存在
- 生产态是否只消费 `release.manifest`
- 是否把 `.backups/**` 误当成 release 正例

## 回归清单

### CLI

- `novusai plugin validate backend/plugins/{name}`
- `novusai plugin build backend/plugins/{name}`
- `novusai plugin pack backend/plugins/{name} --release`

### 浏览器

- 按矩阵跑，不要只跑一条 happy path：
  - scope：`admin` / `tenant` / `public`
  - 进入方式：菜单进入 / direct URL / 硬刷新
  - 权限状态：正常 / 撤权 / 插件禁用或 runtime gate fail-close
  - 资产模式：`/plugin-assets/...` / `/plugin-public-assets/...`
- 切换语言后检查 sidebar / breadcrumb / tab / `document.title`
- 验证普通插件页资源只命中 `/plugin-assets/...`
- 验证 public captcha 只命中 `/plugin-public-assets/...` 且不带 `Authorization`
- 验证 public 资源响应会主动清理历史 cookie

## 明确禁止

- 禁止把 `.backups/**` 当正式模板
- 禁止把普通插件页面打到 `/plugin-public-assets/...`
- 禁止省略 loader scope 参数
- 禁止只按插件名做 loader cache
- 禁止把 `registerLocale()` 当菜单标题系统
- 禁止把 route meta title 提前压平成不可重算字符串
- 禁止菜单可见、页面可进、runtime gate 三套逻辑漂移
- 禁止继续写旧字段：
  - `frontend.menus`
  - `frontend.standalone_pages`
  - `frontend.admin.entry`
  - `frontend.tenant.entry`
  - `frontend.npm_dependencies`

## 参考

- `.cursor/rules/plugin-system.md`
- `docs/design/plugin-system-comprehensive-audit-20260324.md`

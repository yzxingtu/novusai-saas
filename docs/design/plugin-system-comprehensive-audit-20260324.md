# 插件系统综合审计收口（2026-03-24）

本文件只保留 3 类内容：

1. 必须成立的系统约束
2. 审计时逐项勾选的检查清单
3. 改动后必须执行的回归清单

不再记录背景介绍、历史演进和泛泛最佳实践。

## 一、必须成立的系统约束

### A. runtime signature

- 插件 loader scope 只能二选一：
  - `endpoint`
  - `publicEndpoint`
- loader cache key 必须同时包含：
  - scope signature：`pluginName::auth:{endpoint}` 或 `pluginName::public:{publicEndpoint}`
  - runtime signature：`dev={dev_entry}|manifest={release_manifest}`
- 同插件、同 scope 下，只要 `dev_entry` 或 `release_manifest` 变化，就必须重新加载。
- `setup()` 成功前不得写入 loaded cache。
- `setup()` 失败后必须清理中间状态，允许下次重试。
- `unloadPlugin()` 只能清理目标 scope，不得误删同插件其他 scope。

### B. public asset 隔离

- 普通 admin/tenant 页面、slot、widget、settings tab、notification UI 只能走：
  - `/plugin-assets/{plugin}/{file}`
  - `loadPluginComponents(plugin, runtime, { endpoint })`
- public 资源入口，例如登录前 captcha provider，只能走：
  - `/plugin-public-assets/{publicEndpoint}/{plugin}/{file}`
  - `loadPluginComponents(plugin, runtime, { publicEndpoint })`
- `publicEndpoint` 不是普通页面 side 参数。
- public asset 请求不得带 `Authorization`。
- public asset 必须清理历史 `novus_plugin_asset_token` cookie。
- 预前缀路径必须校验 pluginName 与 scope 一致性；不一致时必须 fail-close。

### C. permission bridge

- 菜单可见、页面可进、运行可执行是三层不同判断。
- `pages[*].menu` 存在时，页面访问码必须桥接菜单码。
- 当前菜单桥接格式固定为：
  - `menu:{scope}.plugin_{safe_plugin_name}_{page_name}`
- 菜单 `code` 必须进入 `accessStore.accessCodes`。
- `/plugins/slots` 返回的 `accessCodes` 必须包含显式页面码和桥接菜单码。
- route guard 在 access 判断前，必须先完成插件路由 bootstrap。
- 插件前端必须优先用共享桥接判断权限：
  - `window.NovusPluginShared.getAccessCodes()`
  - `window.NovusPluginShared.hasAccessByCodes(codes)`
- 首屏请求前先判权限；CTA 按目标权限 + 当前状态一起 gating。

### D. menu / i18n / title

- 页面标题真相只来自 `pages[*].title`。
- 菜单标题真相只来自 `pages[*].menu.title`。
- 插件内部按钮、表单、提示文案才来自 `registerLocale()`。
- 宿主消费插件标题时必须保留 locale map，例如 `titleLocaleMap`，不能过早压平成字符串。
- 插件前端至少注册一个 canonical prefix：
  - `plugin.{manifest-name}`
- 切语言后必须同步刷新：
  - sidebar
  - breadcrumb
  - `document.title`
  - 页面 heading
  - tab 标题

### E. release manifest

- 开发态入口只认 `extensions.frontend.dev.entry`。
- 生产态入口只认 `extensions.frontend.release.manifest`。
- release 契约文件固定为 `frontend/dist/plugin.manifest.json`。
- `/plugins/slots` 返回的前端 slot 必须携带 `frontend_runtime`。
- manifest 中声明的组件名必须由插件入口真实导出。
- manifest 中声明的 JS / CSS / assets 必须真实存在。
- 声明了 `release.manifest` 却没有产出 release 文件时，必须 fail-close。

## 二、审计清单

### 1. 声明层审计

- 读 `plugin.yaml`
- 检查 `extensions.frontend.pages[*]`
- 检查 `pages[*].menu`
- 检查 `permissions[*]`
- 检查 `extensions.frontend.dev.entry`
- 检查 `extensions.frontend.release.manifest`
- 检查 `pages[*].title` 是否补齐 `zh-CN` / `en`
- 检查 `pages[*].menu.title` 是否补齐 `zh-CN` / `en`

### 2. loader / asset 审计

- 是否仍有省略 scope 参数的 `loadPluginComponents()` / `getPluginComponent()` 调用
- 是否仍有只按 `pluginName` 缓存的分支
- 是否仍有只按 `pluginName + endpoint` 缓存的分支
- runtime contract 变化后是否仍复用旧 bundle
- 是否仍可能把普通页面资源打到 `/plugin-public-assets/...`
- 是否仍允许预前缀 public/auth 路径绕过 scope 校验
- public asset 是否确实不带 `Authorization`
- public asset 是否确实清理历史 cookie

### 3. permission bridge 审计

- `/permissions/menus` 是否返回插件菜单
- 菜单 `code` 是否进入 `accessStore.accessCodes`
- `/plugins/slots` 是否返回 page slot
- `/plugins/slots` 的 `accessCodes` 是否含页面码 + 菜单桥接码
- `ensurePluginRoutes()` 是否注册出真实路由
- `route.meta.accessCodes` 是否与前两者闭环一致
- 插件前端是否用 `window.NovusPluginShared.getAccessCodes/hasAccessByCodes`
- 首屏请求前是否做权限 gating
- CTA 是否按目标权限 + 状态一起 gating

### 4. menu / i18n / title 审计

- 宿主 route meta 是否保留 `titleLocaleMap`
- breadcrumb 是否走可重算标题
- tab 标题是否走可重算标题
- `document.title` 是否走可重算标题
- 页面主标题是否走同一套 locale 来源
- `registerLocale()` 是否只承担插件内部文案，不再承担菜单标题

### 5. release 审计

- `frontend/dist/plugin.manifest.json` 是否存在
- manifest `entry` / `css` / `assets` 是否真实存在
- `/plugins/slots` 是否返回 `frontend_runtime`
- 插件入口是否导出 manifest 声明组件
- 是否错误引用 `.backups/**` 中的历史产物
- 是否执行了 `validate -> build -> pack --release`

## 三、问题判定标准

出现以下任一情况，按未收口处理：

- loader 调用省略 scope 参数
- loader cache 未包含 runtime signature
- 普通插件页请求打到 `/plugin-public-assets/...`
- public captcha 请求携带 `Authorization`
- 菜单出现但直接 URL 进入插件页仍 403 / 回首页
- 插件前端首屏先发请求后判权限
- CTA 仅按状态显示，未校验目标权限
- 切语言后 sidebar 与 breadcrumb / tab / `document.title` 不一致
- 声明了 `release.manifest` 但缺少 `frontend/dist/plugin.manifest.json`

## 四、最小回归清单

### CLI

- `novusai plugin validate backend/plugins/{name}`
- `novusai plugin build backend/plugins/{name}`
- `novusai plugin pack backend/plugins/{name} --release`

### 浏览器功能回归

- 从菜单进入插件页
- 直接输入插件 URL 进入插件页
- 插件页硬刷新
- 从 admin 端验证一次
- 从 tenant 端验证一次
- 若有 public 入口，再验证 public 流程

### 浏览器权限回归

- 菜单可见时，页面必须真的可进
- 移除权限后，菜单、页面、CTA 必须一起消失或禁用
- 首屏请求前先判权限，不允许先打 403
- CTA 必须对“目标权限 + 当前状态”同时生效

### 浏览器标题回归

- 切语言前后分别检查：
  - sidebar
  - breadcrumb
  - 当前 tab
  - `document.title`
  - 页面 heading

### 浏览器网络回归

- 普通插件页网络请求只能命中 `/plugin-assets/...`
- public captcha 网络请求只能命中 `/plugin-public-assets/...`
- public captcha 请求头不含 `Authorization`
- 切换 runtime contract 后，网络面板能看到重新拉取对应 manifest / bundle，而不是静默复用旧产物

## 五、建议记录格式

每次插件系统审计结论建议按以下结构记录：

1. 审计范围
2. 未收口问题
3. 证据位点
4. 修复动作
5. 回归结果
6. 剩余风险

## 六、禁止事项

- 禁止把 `.backups/**` 当正式模板
- 禁止把普通插件页打到 `/plugin-public-assets/...`
- 禁止省略 loader scope 参数
- 禁止只按 `pluginName` 做缓存
- 禁止把 `registerLocale()` 当菜单标题系统
- 禁止把 route meta title 变成不可重算快照
- 禁止遗漏菜单码进入前端权限池
- 禁止继续生成旧字段：
  - `frontend.menus`
  - `frontend.standalone_pages`
  - `frontend.admin.entry`
  - `frontend.tenant.entry`
  - `frontend.npm_dependencies`

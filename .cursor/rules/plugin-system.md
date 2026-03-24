# 插件系统规则

本规则文件只定义可执行约束。出现例外时，按 fail-close 处理，不做“先放过再补”。

## Rule 1: `plugin.yaml` 是唯一声明源

- 页面只允许在 `extensions.frontend.pages[*]` 声明。
- 菜单只允许在 `pages[*].menu` 声明。
- 页面标题只来自 `pages[*].title`。
- 菜单标题只来自 `pages[*].menu.title`。
- 插件内部文案才允许走 `registerLocale(locale, 'plugin.{manifest-name}', messages)`。
- 禁止把插件菜单标题写进宿主 `backend/app/locales/*/menu.json`。

## Rule 2: loader scope 必须显式、互斥

- 调用 `loadPluginComponents()` / `getPluginComponent()` 时，必须显式传入：
  - `endpoint`
  - 或 `publicEndpoint`
- 禁止省略 scope 参数。
- 禁止同时传 `endpoint` 与 `publicEndpoint`。
- 普通 admin/tenant 页面、page slot、widget、settings tab、notification UI 只能传 `endpoint`。
- public captcha / 登录前资源才允许传 `publicEndpoint`。

## Rule 3: loader cache 必须按 runtime signature 隔离

- loader cache key 必须同时包含：
  - scope signature：`pluginName::auth:{endpoint}` 或 `pluginName::public:{publicEndpoint}`
  - runtime signature：`dev={dev_entry}|manifest={release_manifest}`
- 禁止只按 `pluginName` 缓存。
- 禁止只按 `pluginName + endpoint` 缓存。
- 同插件同 scope 下，只要 `dev_entry` 或 `release_manifest` 变化，就必须重新加载。
- 只有 `setup()` 成功后才能写入 loaded cache。
- `setup()` 失败后必须清理中间状态，允许后续重试。
- `unloadPlugin()` 必须按 scope 卸载，不能误删同插件其他 scope 的 cache、script、css、global。

## Rule 4: public asset 与 private asset 必须硬隔离

- 普通插件页面资源只能命中 `/plugin-assets/{plugin}/{file}`。
- public 资源只能命中 `/plugin-public-assets/{publicEndpoint}/{plugin}/{file}`。
- `publicEndpoint` 不是普通 side 选择器。
- public asset 请求不得带 `Authorization` 头。
- public asset 响应必须清理历史 `novus_plugin_asset_token` cookie。
- 对预前缀路径必须做一致性校验：
  - 路径中的 `pluginName` 必须等于当前插件
  - public 路径必须要求匹配的 `publicEndpoint`
  - authenticated 路径不得在 `publicEndpoint` 模式下加载

## Rule 5: release manifest 是生产态唯一前端契约

- 开发态入口只认 `extensions.frontend.dev.entry`。
- 生产态入口只认 `extensions.frontend.release.manifest`。
- release 契约文件固定为 `frontend/dist/plugin.manifest.json`。
- `/plugins/slots` 返回的每个前端 slot 都必须携带 `frontend_runtime`。
- manifest 中声明的 JS / CSS / assets 必须真实存在。
- manifest 中声明的组件名必须由插件前端入口真实导出。
- 声明了 `release.manifest` 却没有产出 release 文件，必须 fail-close。

## Rule 6: menu / page / runtime gate 是三层闭环

- 菜单可见、页面可进、运行可执行不是一回事。
- 菜单来自 `/permissions/menus`。
- 页面来自 `/plugins/slots` + `ensurePluginRoutes()`。
- 运行可执行来自 runtime gate。
- route guard 在判断 `to.meta.accessCodes` 前，必须先完成插件路由 bootstrap。
- 禁止把“菜单出现”当成“页面一定可进”。

## Rule 7: permission bridge 必须完整闭环

- `pages[*].menu` 存在时，页面访问码必须桥接菜单码。
- 当前菜单桥接格式固定为：
  - `menu:{scope}.plugin_{safe_plugin_name}_{page_name}`
- 菜单 `code` 必须进入 `accessStore.accessCodes`。
- `/plugins/slots` 返回的 `accessCodes` 必须包含：
  - 显式页面权限码
  - 桥接后的菜单权限码
- 插件前端权限判断必须优先走共享桥接：
  - `window.NovusPluginShared.getAccessCodes()`
  - `window.NovusPluginShared.hasAccessByCodes(codes)`
- 首屏请求前必须先判权限，不允许先请求再等 403。
- CTA 必须按目标权限 + 当前状态一起 gating。

## Rule 8: menu / i18n / title 必须保留重算来源

- manifest 标题是多语言真相，不能只保留某次 locale 的字符串快照。
- 宿主 route meta 必须保留 locale map，例如 `titleLocaleMap`。
- `registerLocale()` 只影响插件内部文案，不负责菜单标题系统。
- 插件前端至少注册一个 canonical prefix：
  - `plugin.{manifest-name}`
- 切语言后必须同步刷新：
  - sidebar
  - breadcrumb
  - `document.title`
  - 页面 heading
  - tab 标题

## Rule 9: fail-close 必须同步权限与入口

- `sync_plugin_permissions(plugin.name)` 是权限同步唯一入口。
- disable、repair、startup restore 失败、license/runtime gate fail-close 时，必须同步禁用：
  - 菜单权限
  - 页面入口
  - 运行时注册
- 不允许留下幽灵菜单、幽灵页面、幽灵 CTA。

## Rule 10: 审计清单

每次改插件系统，至少逐项确认：

- 是否仍有省略 scope 参数的 loader 调用
- 是否仍有只按插件名缓存的 loader 分支
- 是否仍可能把普通页面资源打到 `/plugin-public-assets/...`
- 是否仍允许预前缀路径旁路 scope 校验
- 是否在 runtime contract 变化后复用旧 bundle
- 是否把菜单权限码写入前端权限池
- 是否在插件前端使用 `window.NovusPluginShared` 做首屏权限 gating
- 是否按目标权限 + 当前状态 gating CTA
- 是否保留 `titleLocaleMap`
- 是否保证切语言后 breadcrumb / tab / `document.title` 同步更新
- 是否真实产出 `frontend/dist/plugin.manifest.json`

## Rule 11: 浏览器回归清单

每次涉及插件菜单、页面、权限、标题、loader、asset 的改动，至少跑：

- 从菜单进入插件页
- 直接输入插件 URL
- 插件页硬刷新
- 切换语言后检查 sidebar / breadcrumb / tab / `document.title`
- 分别验证 admin 与 tenant
- 检查普通插件页网络请求只命中 `/plugin-assets/...`
- 检查 public captcha 网络请求只命中 `/plugin-public-assets/...`
- 确认 public 请求不带 `Authorization`
- 禁用插件或撤销权限后，确认菜单、页面、CTA 一起消失或禁用

## Rule 12: 禁止事项

- 禁止把 `.backups/**` 当正式模板
- 禁止把普通插件页面打到 `/plugin-public-assets/...`
- 禁止省略 loader scope 参数
- 禁止只按 `pluginName` 做 cache
- 禁止把 `registerLocale()` 当菜单标题系统
- 禁止把 route meta title 当不可变快照
- 禁止菜单、页面、runtime gate 三套逻辑继续漂移
- 禁止继续使用旧字段：
  - `frontend.menus`
  - `frontend.standalone_pages`
  - `frontend.admin.entry`
  - `frontend.tenant.entry`
  - `frontend.npm_dependencies`

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
- install / enable / sync-manifest 运行时必须与 CLI validate 共享同一套前端契约校验：
  - `pages[*].title`
  - `pages[*].menu.title`
  - `frontend.dev.entry` 的 canonical locale prefix
  - `frontend.dev.entry` 对 manifest 声明组件的真实导出
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
- 是否仍存在只消费 legacy alias、未迁到 canonical prefix 的插件

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
- install / enable / sync-manifest 与 CLI validate 仍不是同一套 fail-close 校验
- public 资源请求或响应未能证明历史 `novus_plugin_asset_token` cookie 被主动清理

## 四、最小回归清单

### CLI

- `novusai plugin validate backend/plugins/{name}`
- `novusai plugin build backend/plugins/{name}`
- `novusai plugin pack backend/plugins/{name} --release`

### 浏览器功能回归

- 按矩阵跑：
  - scope：`admin` / `tenant` / `public`
  - 进入方式：菜单进入 / 直接 URL / 硬刷新
  - 权限状态：正常 / 撤权 / 插件禁用或 runtime gate fail-close
  - 资产模式：`/plugin-assets/...` / `/plugin-public-assets/...`
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

- 开发态宿主若启用 Vite plugin dev loader，插件源码入口会先命中 `/__plugin_dev__/{plugin}/entry`
- `/plugin-public-assets/...` 与 `/plugin-assets/...` 的路径隔离验收，必须在 release runtime / preview 宿主下执行
- 普通插件页网络请求只能命中 `/plugin-assets/...`
- public captcha 网络请求只能命中 `/plugin-public-assets/...`
- public captcha 请求头不含 `Authorization`
- public captcha 响应必须能看到历史 `novus_plugin_asset_token` cookie 被主动清理
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

## 七、2026-04-04 再审计硬化结果

本轮实际收口了以下高风险问题：

- `startup discovery / restore / enable` 现在统一走 fail-close 安全扫描；存在扫描告警的插件不再在启动期继续注册、恢复或执行生命周期钩子。
- marketplace preview 与 confirm-install 现在都会校验“registry detail -> 解压 manifest”身份一致性，防止 slug 选项与最终安装包漂移。
- marketplace 下载在重试耗尽后不再生成 DEBUG stub 包，而是统一 fail-close。
- `VersionManager.rollback()` 不再在 Alembic downgrade 失败后继续偷偷恢复文件；现在会阻断回滚，并尽量恢复当前启用版本的 runtime。
- rollback 过程中会同步更新 `PluginVersion` 活跃记录，避免 DB 版本历史与磁盘版本漂移。
- `SkillPackage / Skill / AgentSkillGrant` 运行时门禁统一到 package active/not deleted 语义；插件停用或包停用后不会再从 resolver / router 暴露能力。
- `novusdoc` 样例插件补齐了共享权限桥接：首屏请求前 gating、CTA gating、只读编辑器、无权限页、AI page operations 同步收口。
- CLI `full-module` 模板不再伪造 `frontend/dist/plugin.manifest.json`；fresh create -> validate 与 build 后 release 校验语义已对齐。
- `slider-captcha` 在 release preview 宿主上的 tenant login 真实页级 E2E 已补齐：tenant 侧只命中 `/plugin-public-assets/tenant/slider-captcha/*`、请求不带 `Authorization`、响应会主动清理历史 `novus_plugin_asset_token` cookie，tenant 资源返回 503 时会回退到内置图片验证码。

## 八、注入能力矩阵（2026-04-04）

| 注入面 | Schema | Runtime | Disable/Uninstall 收口 | Permission / Scope / Security | 测试 / 样例 | 结论 |
|---|---|---|---|---|---|---|
| 顶层 capability 注入 | PASS | `PluginContext` / runtime gate 消费 | PASS | capability 明确校验 | lifecycle tests；`weather-widget` | 正常 |
| Skill 注入 | PASS | `extensions.skills[*]` -> Skill 投影 | PASS | resolver 走 grant + package gate | skill resolver tests；`weather-widget` | 正常 |
| SkillPackage 投影同步 | PASS | enable/upgrade 同步 | PASS | 只做目录投影，不自动授权 | skill service tests | 正常 |
| Agent 绑定链路 | PASS | `AgentSkillGrant -> Skill -> Resolver` | PASS | package inactive / deleted fail-close | grant/router tests | 正常 |
| admin API route 注入 | PASS | API dispatcher 注册 | PASS | permission/action + db proxy gate | dispatcher tests；`novusdoc` | 正常 |
| tenant API route 注入 | PASS | API dispatcher 注册 | PASS | tenant scope + permission gate | dispatcher tests；`novusdoc` | 正常 |
| public API route 注入 | PASS | dispatcher 注册 | PASS | public route 显式声明，鉴权单独控制 | webhook/public tests；`slider-captcha` | 正常 |
| Webhook endpoint 注入 | PASS | webhook dispatcher 注册 | PASS | auth type / secret / runtime gate | webhook tests | 正常 |
| EventBus 事件订阅 | PASS | event bus 注册 | PASS | payload/timeout 隔离 | event bus lifecycle + registrar bridge tests | 正常 |
| 系统 Hook 点注入 | PASS | hook registry 注册 | PASS | hook point 白名单 | hook runtime + registrar bridge tests | 正常 |
| Celery task 注入 | PASS | task registry / beat sync | PASS | task definition sync + fail-close | task sync tests；`storage-billing` | 正常 |
| queue consumer 注入 | PASS | schema 有入口，runtime 较薄 | PARTIAL | manifest -> registrar -> Celery bootstrap / task execution / unregister 边界已测，但热卸载仍受 Celery worker 生命周期限制 | registrar bridge tests；Celery bootstrap tests；sample contract tests；unregister contract tests | 边界已明确 |
| Socket.IO namespace 注入 | PASS | namespace 注册 | PASS | namespace auth/gate + wrapper early-fail 已测 | namespace lifecycle + wrapper + registrar bridge tests | 正常 |
| middleware 注入 | PASS | runtime 支持 | PASS | enable/disable 会重排 `user_middleware` 并重建 `middleware_stack` | registrar bridge tests + started-app runtime rebuild tests | 正常 |
| storage driver 注入 | PASS | storage registry 注册 | PASS | driver capability + config gate | storage plugin tests；host helper/facade tests；host selector tests；`amazon-s3`/`aliyun-oss` | 正常 |
| adapter 注入 | PASS | adapter registry 注册 | PASS | typed adapter contract | adapter runtime bridge tests | 正常 |
| notification template 注入 | PASS | enable 时同步 DB | PASS | send path / sync / cleanup 生命周期已测 | notification runtime lifecycle tests | 正常 |
| permission/action 注入 | PASS | RBAC sync 注册 | PASS | action code / menu bridge | permission sync tests；`novusdoc` | 正常 |
| menu/page 注入 | PASS | pages -> menus/routes | PASS | accessCodes + menu bridge | frontend runtime tests；`weather-widget` | 正常 |
| frontend route 注入 | PASS | `ensurePluginRoutes()` | PASS | route meta accessCodes | loader/route tests | 正常 |
| dashboard widget 注入 | PASS | slot registry | PASS | `/plugins/slots` + runtime gate | `weather-widget` | 正常 |
| header widget 注入 | PASS | slot registry | PASS | access/scope filter | slot filter tests | 正常 |
| settings tab 注入 | PASS | slot registry + host settings page 消费 | PASS | slot refresh / unload 闭环沿用统一 plugin slot runtime | `plugin-slots` store + `PluginSettingsTabs` tests | 正常 |
| floating panel 注入 | PASS | slot registry + layout 浮层消费 | PASS | slot refresh / unload 闭环沿用统一 plugin slot runtime | `plugin-slots` store + `PluginFloatingPanels` tests | 正常 |
| notification UI 注入 | PASS | slot registry + notification panel/toast 消费 | PASS | event 匹配 + slot refresh 闭环已补 | `plugin-slots` store + `PluginNotificationUI` tests | 正常 |
| public asset / captcha provider 注入 | PASS | public asset runtime | PASS | 无 `Authorization` + 清 cookie | public asset tests；`slider-captcha` | 正常 |
| custom typed extension 注入 | PARTIAL | `custom.type` 仅少量宿主消费 | PARTIAL | typed whitelist 有限 | captcha provider 有样例 | 应新增更多 typed point |
| tenant menu policy / entitlement policy 注入 | PASS | tenant entitlement service + slot filter | PASS | plan/license/assignment gate | entitlement tests | 正常 |
| plugin managed agent / source_plugin 注入 | PASS | managed agent sync / source_plugin 绑定 | PASS | plugin source scope 明确 | managed agent sync tests | 正常 |
## 九、当前残余缺口

注：

- `AI 页面感知 / 页面操作 / KB / RAG` 不再计入狭义“插件原生注入矩阵”。它更准确地属于“插件 -> 宿主 AI runtime 集成面”：插件页面通过宿主共享 bridge 注册 page awareness / operations，KB / RAG 也通过宿主 Agent / resolver / injector 体系联动，而不是通过 `plugin.yaml` 声明一个独立原生注入点。

- `consumer` 仍属于“schema / registrar bridge 已打通，但 worker 热卸载语义受 Celery 限制”的扩展面；当前已经覆盖 manifest -> registrar -> Celery bootstrap、消息处理、任务执行以及 `unregister_all` 只清 tracking 的合同。它之所以仍保留 `PARTIAL`，是因为 Celery worker 进程内 hot-unregister 本身不是宿主可承诺语义，而不是因为 bootstrap 证据缺失。
- storage 方向已经补到宿主 helper/facade + 前端选择器级证据，但页级/API/browser 回归仍偏薄。下一步最好再在 `backend/tests` 或 `frontend` 页面上跑一个真实的 storage plugin 用例（例如 admin/tenant 存储配置页、上传/下载入口或 API 消费）来证明 host 这边的 UI/API 不只是展示驱动标签，而是真正配置并使用了 `storage manager` 注册的驱动。
- browser 级多语言联动仍建议在长期运行的完整宿主环境再做一轮人工复核；public captcha 的 tenant login 网络面板与 failover 已在 release preview 宿主完成实测。

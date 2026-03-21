# 插件系统规则

## 当前统一模型

- 插件代码只能位于 `backend/plugins/{name}/` 或历史归档目录 `backend/plugins/.backups/**/files/`。
- `plugin.yaml` 是插件声明层单一事实来源；数据库中的 `manifest` 是运行时投影，不是开发时主来源。
- 前端插件采用双契约：
  - 开发态：`extensions.frontend.dev.entry`
  - 生产态：`extensions.frontend.release.manifest` 指向 `frontend/dist/plugin.manifest.json`
- 页面与菜单采用单一模型：`extensions.frontend.pages[*]` 声明页面；`pages[*].menu` 声明该页面是否派生为菜单入口。
- 当前不支持 `user` 端插件。manifest、registry、文档和脚手架都只允许 `admin` / `tenant`。

## License 与运行时闸门

- License 只允许三种语义：
  - `trial`
  - `fixed_term`
  - `perpetual`
- 禁止再出现 `perpetual + expires_at` 混合语义。
- 插件授权的含义是“宿主平台是否允许插件能力运行”，不是“源码绝对不可见”。
- 所有会执行插件能力的入口都必须经过统一 runtime gate：
  - 插件启用
  - 启动恢复
  - API 分发
  - webhook 分发
  - `/plugin-assets`
  - 前端 slots / 页面加载

## 启动与版本边界

- `discover` 只负责发现新插件与标记漂移，不得热升级、热同步 manifest。
- `sync-manifest` 只允许显式同步同版本 manifest 漂移，不得覆盖 `granted_capabilities`。
- 版本变化必须走正式 `upgrade`，不得由启动扫描静默完成。
- 启动恢复只做运行时恢复，不处理前端 npm 依赖。

## 依赖模型

- Python 依赖采用“共享宿主环境 + 安装期预检 + 启动期只校验”：
  - `install / upgrade / repair / dependencies/install` 可以处理 Python 依赖
  - `enable` 只在通过预检后按需补装 Python 依赖
  - `startup restore` 只校验，不再 `pip install`
- 插件间依赖只允许 `dependencies.plugins` 一套声明：
  - 推荐对象写法：`{ plugin: base-plugin, version: \">=1.2.0\" }`
  - 空依赖也应显式写成 `plugins: []`
- 不允许再使用：
  - `compatibility.requires`
  - `dependencies.system`
- 新版 manifest/schema 会直接拒绝 `compatibility.requires` 与 `dependencies.system`；
  运行时仅对历史数据库 `manifest` 投影保留只读兼容读取，不得在 `plugin.yaml`、脚手架或正式发布包中继续使用。
- 管理端与 API 的依赖状态只反映真实运行模型：
  - `python`
  - `plugins`
  - 不再保留运行期 `npm` 安装/卸载语义

## 前端契约

- 开发态必须走 `/__plugin_dev__/{plugin}/entry`，禁止继续伪装成 `/plugin-assets/{plugin}/index.js`。
- 生产态必须先读取 `frontend/dist/plugin.manifest.json`，再按 manifest 加载 JS/CSS。
- `plugin.manifest.json` 是正式发布契约，`dist/index.js` 不是唯一契约。
- 生产环境前端插件缺失 release manifest 或缺少 manifest 指向的产物时，安装/启用必须 fail-close。
- `/plugin-assets` 只用于运行时 release 资产分发；`plugin.manifest.json`、JS、CSS、运行时图片等都必须受 token + enabled + scope + tenant assignment + license 约束。
- 管理态展示图标必须走独立的 `/plugin-icons/{plugin}/{file}` 元数据通道：
  - 只允许管理端鉴权访问
  - 不得再被 `enabled` / license gate 一起封死
  - 不得复用完整 access token query string
- 插件元数据图标规则固定为：
  - `plugin.yaml` 顶层 `icon` 只允许 `icon.png` 或空字符串
  - 插件根目录存在 `icon.png` 时可由加载器自动补齐
  - 未提供 `icon.png` 时，管理端统一回退到 `lucide:plug`
  - 禁止把插件元数据图标写成任意 `mdi:*` / `simple-icons:*` / URL / 在线 Iconify 前缀
- 插件页面与菜单图标可以继续使用 `lucide:*`，但必须是平台本地已注册图标，禁止依赖在线 Iconify
- 受控插件资产默认通过 `Authorization` 或同源鉴权 Cookie 访问，响应缓存必须是 `private`，禁止返回 `public` 缓存语义。

## 菜单与页面

- 不允许再使用 `frontend.menus`、`frontend.standalone_pages`、`frontend.admin.entry`、`frontend.tenant.entry`、`frontend.npm_dependencies`。
- 菜单调整只允许重建导航域，不得重跑整套扩展注册。
- `sync_plugin_permissions(plugin.name)` 仍是权限同步唯一入口；禁止在插件事务里跑全量 `sync_permissions()`。

## CLI 与打包

- 使用：
  - `novusai plugin build`
  - `novusai plugin validate`
  - `novusai plugin pack --release`
  - `novusai plugin pack --source`
- `pack --release` 默认排除：
  - `frontend/src`
  - 前端测试文件
  - `frontend/package.json` / `vite.config.*` / lockfile
  - `backend/tests`
- `pack --source` 用于源码链路，允许保留 `frontend/src`。

## 历史对象处置

- 正式插件必须全部迁到新模型。
- 历史/备份插件至少要迁到当前 schema，可作为 validate 基线。
- `novusdoc-pro` 当前仓库无正式源码，按“已归档样例”处理，不再作为核心插件模型依据。

## 禁止事项

- 禁止在主系统前端源码中落插件业务页面或插件 locale。
- 禁止新增与旧模型兼容的双源字段。
- 禁止在运行期依赖 manifest 中的 npm 安装声明。
- 禁止绕过 `PluginDbProxy` 操作非 `px_{name}_*` 表，除非 manifest 明确声明 `db_table_prefixes`。
- 禁止未声明 capability 就调用对应上下文能力。

## 参考

- `../skills/plugin-development/SKILL.md`
- `../skills/novusai-saas/references/plugin-spec.md`
- `../skills/novusai-saas/references/plugin-menu-registration.md`
- `../../docs/audit/plugin-system-comprehensive-audit-20260322.md`

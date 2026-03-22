# 插件系统全面审计报告（2026-03-22）

> 2026-03-22 当日已按本报告启动并落地统一整改。以下审计问题与方案保留为审计依据；当前实现状态以第 14 章“实施回写”补充说明为准。

## 1. 审计范围

本次审计基于以下范围进行静态代码审计与规则对照：

- 项目插件系统实现：`backend/app/plugins/*`
- 插件管理 API：`backend/app/api/admin/plugins.py`、`backend/app/api/tenant/plugins.py`
- 插件服务与生命周期：`backend/app/services/system/plugin_service.py`、`backend/app/plugins/lifecycle.py`、`backend/app/plugins/startup.py`
- 插件授权与试用：`backend/app/plugins/license.py`、`backend/app/models/system/plugin_license.py`、`backend/app/enums/plugin.py`、`backend/app/cli.py`
- 前端插件加载与构建：`frontend/apps/web-antd/src/utils/plugin-loader.ts`、`frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts`（当前路径；审计时实现已迁移出 `src/utils/`）
- 插件静态资源与打包：`backend/app/main.py`、`backend/app/plugins/asset_resolver.py`、`backend/scripts/plugin_cli.py`
- 历史/备份插件源码：`backend/plugins/.backups/*`
- 历史基线与上线材料：
  - `docs/reports/m590/baseline/plugin_status_api.json`
  - `docs/reports/m590/m590_detailed_milestone_v2.md`
  - `docs/guides/plugin-smoke-validation.md`
  - `docs/guides/plugin-go-live-runbook.md`
- `.cursor` 规范与技能：
  - `.cursorrules`
  - `.cursor/rules/plugin-system.md`
  - `.cursor/skills/plugin-development/SKILL.md`

本报告重点回答五个问题：

1. 当前插件系统整体是否合理。
2. “试用”和“带期限授权”到底在代码里是什么意思。
3. 付费插件、尤其前端部分，当前是否适合商业交付。
4. 当前系统是否真正支持“编译产物模式”和“源码模式”两种运行方式。
5. 当前插件依赖模型是否合理，是否已经形成完整闭环。

## 2. 总体结论

结论可以概括为六句话：

1. 当前插件系统的总体方向是对的，尤其是“零侵入插件目录 + manifest 声明 + 生命周期 + UMD 前端动态加载 + 权限同步”这一套架构方向没有问题。
2. 当前实现最严重的问题不在“有没有授权”，而在“授权没有形成真正的运行时闭环”。也就是状态可以显示授权，但系统没有稳定、统一地在启用、恢复、分发入口处执行授权闸门。
3. 当前付费插件交付链路不适合商业化发布，尤其前端部分。原因不是“前端必须编译”，而是即使编译了，官方打包链路仍然会把 `frontend/src` 一起打出去，导致源码照样交付。
4. 当前系统不是“统一支持编译版和非编译版”的对称模型，而是“生产环境走编译产物，开发环境走源码转译”的双轨模型。这个模型本身可以成立，但目前没有被完整建模和强制校验，导致行为不一致、语义不清晰。
5. 当前依赖治理只把“Python 依赖能不能装上”做到了局部闭环，但“跨插件冲突、插件间版本依赖、system 前置条件、启动恢复边界”都没有完整建模。
6. 当前正式插件、历史插件、脚手架模板三套模型并存。也就是说，就算正式插件后续整改到位，如果 `plugin_cli`、`.cursor`、历史插件不一起迁移，后续新插件还会继续生成旧契约。

换句话说，当前系统最不合适的地方不是某一个函数写错，而是以下四个层面的定位混乱：

- 授权系统的产品定位混乱：看起来像 DRM，实际上只能做平台运行门禁。
- 前端发布模型混乱：运行时只认 `dist/index.js`，但打包时又把 `src/` 一起发出去。
- 依赖治理模型混乱：共享环境、插件依赖、system 前置条件、管理端 API 没有统一语义。
- manifest 单一事实来源原则落实不彻底：规则上强调 manifest 驱动，实际关键配置仍被硬编码或闲置。

## 3. 与 `.cursor` 规则的对照结论

### 3.1 符合规则的部分

以下部分整体符合 `.cursor/rules/plugin-system.md` 的设计方向：

- 插件代码目录保持在 `backend/plugins/{name}/`，没有把插件业务逻辑写入主系统目录。
- 插件前端采用 UMD 动态加载，不编进宿主前端主 bundle。
- 生命周期有明确入口：`on_install`、`on_enable`、`on_disable`、`on_uninstall`、`on_upgrade`。
- 菜单/权限同步整体遵循 `sync_plugin_permissions(plugin.name)`，没有在关键路径里直接乱跑全量权限同步。
- 插件前端插槽通过 registry 统一注册与分组，整体结构是清晰的。

### 3.2 偏离规则的部分

以下部分和 `.cursor` 规则存在明显偏差：

1. manifest 不是完全意义上的单一事实来源。
   - `pricing.trial.enabled`、`pricing.trial.days` 明明在 manifest 中存在，但试用逻辑实际由管理端 API 写死为 14 天。
   - `frontend.admin.entry` / `frontend.tenant.entry` 在 manifest 里有定义，但运行时根本没有消费它。

2. “沙箱”表述强于实现。
   - `.cursor` 和代码注释都倾向于把 `PluginContext` 说成插件与系统交互的唯一入口。
   - 实际插件模块是直接在宿主进程内动态导入执行，能力校验主要约束的是“通过 ctx 访问的接口”，而不是插件代码本身的全部行为。

3. 付费与试用逻辑没有被 manifest 驱动闭环。
   - 规则强调 manifest 声明式设计。
   - 当前授权系统仍然大量依赖散落在 API、CLI、状态查询里的分支判断，缺乏统一状态机。

## 4. 关键问题清单（按严重级别排序）

---

### P0-1. 付费插件没有真正的运行时 License 闸门

#### 现状

- 插件 API 分发只检查插件是否存在且 `status == enabled`。
- 插件 Webhook 分发只检查插件是否存在且 `status == enabled`。
- 插件前端 slots 返回链路只基于“已启用插件”组织前端插槽，不检查 License 状态。
- 插件静态资源 `/plugin-assets/{plugin}/...` 也只检查插件是否已启用，不检查 License 状态。
- 启用流程 `enable()` 不检查授权是否有效。
- 服务启动时 `restore_enabled_plugins()` 也不检查授权是否有效。

对应代码：

- `backend/app/plugins/api_dispatcher.py:54-80`
- `backend/app/plugins/webhook_dispatcher.py:36-70`
- `backend/app/api/admin/plugins.py:180-235`
- `backend/app/api/tenant/plugins.py:105-169`
- `backend/app/main.py:733-808`
- `backend/app/plugins/lifecycle.py:554-640`
- `backend/app/plugins/startup.py:250-416`

#### 为什么不合适

这会导致授权系统退化成“状态展示系统”，而不是“执行控制系统”。

对于付费插件，真正有意义的授权控制只能是：

- 未授权时不允许启用；
- 已过期时不允许恢复；
- 已过期时不允许分发 API/Webhook；
- 已过期时不应该继续返回插件页面插槽和静态资源；
- 菜单、页面、能力点一起收口。

如果系统只是显示“expired”，但运行时仍然继续执行，那么：

- 对产品来说，授权模型是假的；
- 对用户来说，界面会产生误导；
- 对后续维护来说，问题会蔓延到菜单、企业分配、市场安装、自动恢复等所有链路。

#### 为什么必须改

因为这是授权系统是否成立的最基本前提。

在“插件代码已交付”的前提下，License 的唯一现实意义就是“平台层是否允许它正常运行”。如果连这个都不严格执行，那么 License 就只剩下展示价值，没有业务价值。

#### 建议

增加统一的运行时授权断言，例如 `assert_plugin_license_active(plugin_id or plugin_name)`，并统一接入：

- `lifecycle.enable()`
- `startup.restore_enabled_plugins()`
- `api_dispatcher._dispatch_plugin_api()`
- `webhook_dispatcher.webhook_dispatcher()`

---

### P0-2. “带期限授权”的数据模型语义错误

#### 现状

- CLI 支持 `novusai license generate --days N` 生成带期限的 License Key。
- payload 中确实会写入 `expires_at`。
- 但是数据库模型的 `license_type` 只有 `trial` 和 `perpetual`。
- 激活时，不管是否存在 `expires_at`，都统一写成 `license_type='perpetual'`。

对应代码：

- `backend/app/cli.py:467-514`
- `backend/app/plugins/license.py:54-100`
- `backend/app/plugins/license.py:225-281`
- `backend/app/enums/plugin.py:43-47`
- `backend/app/models/system/plugin_license.py:33-50`

#### 为什么不合适

因为它把三个不同语义的概念混在了一起：

- 试用授权
- 永久付费授权
- 带期限的付费授权

而当前实现只有两个显式类型：

- `trial`
- `perpetual`

于是“带期限的付费授权”被硬塞成“`perpetual` + `expires_at`”。

这会带来三个问题：

1. 产品语义不清。
   - 用户看到的是“带期限授权”。
   - 数据库里看到的是“永久授权但有过期时间”。

2. 状态机不好写。
   - 调度任务、启用校验、状态接口都需要额外用 `expires_at` 推断语义。

3. 后续扩展会持续混乱。
   - 一旦以后要支持续费、订阅、宽限期、自动续期，这个模型会立刻变成负资产。

#### 为什么必须改

因为这是整个授权系统混乱的根源之一。当前你“没搞懂是什么意思”，不是理解问题，而是模型本身就表达错了。

#### 建议

两种方案选一种，不要继续维持当前混合语义：

1. 引入明确类型：
   - `trial`
   - `perpetual`
   - `time_limited` 或 `subscription`

2. 或者统一简化为：
   - `trial`
   - `paid`

然后通过 `expires_at is null / not null` 区分永久和期限授权。

---

### P1-1. 历史上调度任务只处理试用过期，不处理带期限付费授权过期

#### 现状

- 历史实现中的定时任务 `check_trial_expirations()` 只筛选 `license_type == trial`。
- 它会对试用过期做两件事：
  - 标记 `is_valid = false`
  - 尝试禁用插件
- 但对付费且设置了 `expires_at` 的授权，没有对应的统一过期任务。

补充说明：

- 该问题在后续整改中已统一收口为 `check_plugin_license_expirations()`。
- 本节保留的是 2026-03-22 审计时的原始问题描述，用于说明为什么需要这次整改。

对应代码：

- `backend/app/plugins/license.py:522-585`
- `backend/app/tasks/scheduled.py:160-225`

#### 为什么不合适

这会造成同一个“过期”概念，在试用和付费场景下行为不一致：

- 试用过期：可能禁用插件
- 付费过期：状态接口显示 expired，但系统未必真正停用

这既不利于用户理解，也不利于运维排查。

#### 为什么必须改

因为一旦系统支持“期限授权”，就必须把“到期后如何处理”建成统一策略，而不是只处理 trial。

#### 建议

新增统一过期任务，例如：

- `check_plugin_license_expirations()`

同时处理：

- 试用过期
- 期限付费授权过期

并统一触发：

- 状态失效
- 插件禁用
- 管理端提醒
- 审计日志

---

### P1-2. 试用逻辑脱离 manifest 配置，违背 manifest 驱动原则

#### 现状

- manifest 中有 `pricing.trial.enabled` 与 `pricing.trial.days`。
- 但管理端激活试用接口直接写死 `trial_days=14`。
- 前端文案也写死“开始 14 天免费试用”。
- 后端没有检查插件是否真的允许试用。

对应代码：

- `backend/app/plugins/manifest.py:821-834`
- `backend/app/api/admin/plugins.py:1210-1224`
- `frontend/apps/web-antd/src/views/admin/plugins/modules/PluginConfigDrawer.vue:918-927`
- `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/plugin.json:231-233`

#### 为什么不合适

这和插件系统自己的设计哲学冲突：

- 规则说 manifest 是单一事实来源；
- 实际试用关键参数却被硬编码在 API 和 UI 层。

这会造成：

- 改 manifest 不生效；
- 不同插件不能定义不同 trial 天数；
- 插件可以声明“不允许试用”，但后台仍可强行开试用。

#### 为什么必须改

因为“是否允许试用、试用多少天”本来就属于插件商业策略的一部分，理应由插件自身 manifest 声明，而不是由平台硬编码决定。

#### 建议

试用激活接口改为：

- 先读取插件 manifest
- 检查 `pricing.type == paid`
- 检查 `pricing.trial.enabled == true`
- 天数使用 `pricing.trial.days`

前端按钮展示也应基于后端返回的 trial 配置，而不是本地写死。

---

### P1-3. 试用可重复发放，且会污染正式授权状态

#### 现状

- `create_trial_license()` 只是简单插入一条新 trial 记录。
- 没有阻止重复试用。
- 没有阻止已购买后再次试用。
- 没有阻止免费插件试用。
- 没有失效旧试用。
- 状态查询按 `created_at desc` 只取最新一条。

对应代码：

- `backend/app/plugins/license.py:397-421`
- `backend/app/plugins/license.py:285-381`
- `backend/app/plugins/license.py:424-500`
- `backend/app/plugins/context.py:387-455`

#### 为什么不合适

这会带来两个层面的混乱：

1. 商业策略失效。
   - 一个插件理论上可以无限重新试用。

2. 状态判断失真。
   - 新插入的试用记录可能覆盖掉已有正式授权在状态接口中的表现。

#### 为什么必须改

因为试用不是普通数据记录，而是商业策略的一部分。它必须被视为有限状态机，而不是“多插一条记录”。

#### 建议

建立明确规则，例如：

- 每个插件每个安装实例只允许一次试用
- 已存在有效付费授权时禁止试用
- 免费插件禁止试用
- manifest 明确禁用试用时禁止试用

状态查询也应从“最新记录优先”改为“当前最优有效记录优先”。

---

### P1-4. 付费插件前端发布链路不适合商业交付

#### 现状

- 运行时设计上，生产环境只认 `frontend/dist/index.js` 这一类编译产物。
- 但官方打包命令 `novusai plugin pack` 会把整个插件目录打包进 ZIP。
- 因此 `frontend/src`、`vite.config.ts`、`package.json` 等前端源码和构建文件会一起发出去。

对应代码：

- `frontend/apps/web-antd/src/utils/plugin-loader.ts:115-179`
- `backend/app/main.py:733-808`
- `backend/app/plugins/asset_resolver.py:14-52`
- `backend/scripts/plugin_cli.py:698-742`

#### 为什么不合适

这会直接击穿“付费插件前端应该交付编译产物”的商业前提。

也就是说，当前系统对付费插件前端的真实交付状态是：

- 运行时要求编译产物
- 发布时却把源码也一起交付

这是最不合适的一种状态，因为：

- 既承担了构建成本；
- 又没有获得源码保护的任何收益；
- 还会让授权看起来像“收费但代码全给”。

#### 为什么必须改

如果未来要做市场插件、商业插件、私有交付插件，这条链路必须先改。否则“付费插件前端已编译”在商业上没有意义，因为源码仍在包里。

#### 建议

把 `plugin pack` 分成至少两种模式：

1. `dev pack`
   - 保留源码，供内部开发或联调

2. `release pack`
   - 排除 `frontend/src`
   - 排除测试、lockfile、构建配置（按需）
   - 只保留 `frontend/dist` 和运行必要文件

---

### P1-5. 安装/启用链路没有对前端编译产物做 fail-close 校验

#### 现状

- CLI 的 `plugin validate` 会把 `frontend/dist/index.js` 缺失视为错误。
- 但后台上传安装接口 `/plugins/upload` 没有复用这层校验。
- 生命周期的前端依赖处理只负责安装 npm 依赖，不会自动构建 `dist`。
- 结果是：一个前端插件即使没有 dist，也可能被成功安装，直到前端运行时再 404。

对应代码：

- `backend/scripts/plugin_cli.py:611-619`
- `backend/app/api/admin/plugins.py:643-698`
- `backend/app/plugins/lifecycle.py:1954-2057`

#### 为什么不合适

因为这把错误从“安装期可见错误”推迟成了“运行期隐性错误”。

安装期应当尽量 fail-close，尤其是前端插件这种资源完整性要求非常明确的场景。

#### 为什么必须改

因为当前系统对生产环境的实际要求已经很明确：前端插件必须有 `dist/index.js`。既然这是硬前提，就不应该在安装时装作它是可选项。

#### 建议

在非 `DEBUG` 环境下，凡是声明了前端扩展的插件：

- 安装时必须校验 `frontend/dist/index.js`
- 启用时再次校验
- 缺失则直接拒绝安装/启用

---

### P1-6. 当前系统不是对称支持“编译版 / 非编译版”，而是双轨模型且未被明确建模

#### 现状

当前真实支持矩阵如下：

| 运行场景 | 形态 | 当前状态 |
|---|---|---|
| 生产环境 | 已编译 UMD (`frontend/dist/index.js`) | 支持 |
| 生产环境 | 仅源码 (`frontend/src/index.ts`) | 不支持 |
| 开发环境 | 源码模式（Vite 直接转译 `src/index.ts`） | 支持 |
| 开发环境 | 仅编译产物、无源码 | 不是正式支持路径，存在兼容风险 |

依据代码：

- 生产环境前端 loader 走 `<script src="/plugin-assets/{plugin}/index.js">`，再读取 `window.NovusPlugin_xxx`
- 开发环境 loader 走 `import('/plugin-assets/{plugin}/index.js')`
- dev Vite 插件在存在 `src/index.ts` 时接管该路径并返回 ESM
- 后端静态资源仅从 `frontend/dist` 提供非图标资源

对应代码：

- `frontend/apps/web-antd/src/utils/plugin-loader.ts:136-199`
- `frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts`
- `backend/app/plugins/asset_resolver.py:24-52`

#### 为什么不合适

双轨模型本身不是问题，问题在于系统没有把它说清楚，也没有把边界强制建模：

- manifest 没有声明当前插件属于哪种前端交付模式；
- 安装链路没有明确校验；
- 打包链路没有区分 dev/release；
- 开发环境下 compiled-only 插件不是稳定支持路径。

这会让维护者误以为系统“同时支持编译和非编译”，实际上支持条件高度不对称。

#### 为什么必须改

因为前端运行模式直接关系到：

- 插件发布流程
- 商业交付方式
- CI 校验规则
- 市场插件格式

这不能靠约定俗成，必须显式化。

#### 建议

明确建模前端交付模式，例如：

- `frontend.delivery = "prebuilt_umd"` 或 `"dev_source_only"`

但更现实的做法是：

- 对外发布一律要求 `prebuilt_umd`
- 本地开发允许源码模式作为开发特性
- 不把源码模式当成正式发布模式

---

### P1-7. 菜单位置调整错误地触发了整套扩展重注册

#### 现状

- `PUT /admin/plugins/{plugin_id}/menu-config` 的语义只是“调整菜单挂载位置”。
- 但当前实现会：
  - `registry.unregister_all(plugin.name)`
  - 再次调用 `register_all_extensions(...)`
  - 然后再 `sync_plugin_permissions(plugin.name)`
- 这意味着一个纯菜单配置动作，会把该插件的：
  - API
  - skills
  - tasks
  - notifications
  - frontend slots
  - middleware
  - webhook
  - consumers
  一起重注册。

对应代码：

- `backend/app/api/admin/plugins.py`
- `backend/app/plugins/_extension_registrar.py`

#### 为什么不合适

因为“菜单挂载调整”本质上只是权限树和导航元数据调整，不应该触碰整套运行期扩展。

当前设计会带来四个问题：

1. 菜单位置更新和运行期功能耦合过深。
2. 只改菜单，却可能因为某个无关扩展加载失败而整体失败。
3. 在线系统做菜单调整时，会引入不必要的注册抖动。
4. 这也让管理员误以为“菜单配置”是个轻量动作，但实际上它在碰整套插件运行模型。

#### 为什么必须改

因为这既影响可用性，也影响运维稳定性。

菜单改动应该是元数据更新，不应该演变成一次“迷你 enable/repair”。

#### 建议

把“菜单位置调整”从全量扩展重注册中拆出来，至少做到：

1. 单独更新菜单相关 PermissionMeta / permissions 表。
2. 单独刷新前端路由和菜单树。
3. 不再因为调整菜单而重触 API、skills、tasks、webhook 的注册流程。

---

### P1-8. 同一个插件页面需要在 `menus` 和 `standalone_pages` 双重声明，漂移风险高

#### 现状

当前前端页面类插件通常需要两份声明：

1. `extensions.frontend.menus`
   - 负责侧边栏菜单与 RBAC 菜单权限

2. `extensions.frontend.standalone_pages`
   - 负责动态路由注册

这意味着同一个页面的关键字段会重复出现：

- path
- title
- component 名称语义
- admin / tenant 端别关系

代码中也明确体现了这种分裂：

- 菜单权限树依赖 `register_menu()`
- 路由注册依赖 `standalone_pages`
- 插件菜单经常没有静态 `component`，而是依赖隐藏的 standalone route

对应代码：

- `backend/app/plugins/registry.py`
- `backend/app/plugins/_extension_registrar.py`
- `frontend/apps/web-antd/src/composables/use-plugin-frontend-init.ts`
- `frontend/apps/web-antd/src/api/shared/menu-transformer.ts`
- `backend/app/rbac/services/permission_service.py`

#### 为什么不合适

因为一个“用户可点击的插件页面入口”被拆成了两份声明，维护者很容易改一份漏一份。

典型后果包括：

- 菜单 path 改了，但 standalone route 没改
- route 已注册，但菜单没挂出来
- 菜单存在，但点击后路由找不到
- admin / tenant 双端页面的路径和组件语义漂移

这不是使用者理解问题，而是模型本身存在双源声明。

#### 为什么必须改

因为这是“菜单注册不好用”和“页面功能注册不好用”的共同根源。

只要单页插件还要同时维护 `menus` 和 `standalone_pages` 两个来源，漂移就无法根治。

#### 建议

把“可导航页面”收敛成单一事实来源，例如：

1. 让 `menus` 直接引用页面声明。
2. 或者引入 `pages` 概念，再由页面声明派生：
   - 菜单
   - 路由
   - 可见性
   - AI page metadata

核心目标是：

- 一个插件页面只维护一次路径和组件绑定
- 菜单只是页面的可见入口，而不是另一套并行声明

---

### P1-9. manifest/registry 宣称支持 `user` 端插件，但运行时链路没有打通

#### 现状

- manifest 校验层允许前端扩展和权限扩展使用 `user` 端别。
- `registry.register_menu()` 也支持 `scope='user'`，并会生成 `menu:user.plugin_*` 权限码。
- 但 `sync_plugin_permissions()` 只同步 `menu:admin.plugin_*` 与 `menu:tenant.plugin_*` 前缀，不处理 `menu:user.plugin_*`。
- 前端插件初始化的 `EndpointSide` 只有 `admin | tenant`，没有 `user`。
- 菜单父级选择 API 只返回 `admin` 和 `tenant` 两棵树，没有 `user`。

对应代码：

- `backend/app/plugins/manifest.py`
- `backend/app/plugins/registry.py`
- `backend/app/rbac/sync.py`
- `frontend/apps/web-antd/src/composables/use-plugin-frontend-init.ts`
- `backend/app/api/admin/plugins.py`

#### 为什么不合适

这不是“功能暂时没做”，而是“schema 和运行时承诺不一致”。

对插件开发者来说，这会造成明显误导：

- manifest 写得过
- registry 注册得进
- 但权限同步、菜单配置、前端初始化都跑不通

结果就是系统表面上支持 `user` 端插件，实际上没有完整可用的交付链路。

#### 为什么必须改

因为这种“半支持”状态会直接污染后续插件设计。

如果不处理，未来任何人只要看到 schema 支持 `user`，就会自然认为：

- 可以声明 `user` 菜单
- 可以声明 `user` 页面
- 可以做 `user` 端插件

但当前代码并不能兑现这个承诺。

#### 建议

必须二选一，不要继续维持“写得进 manifest 但跑不通”的状态：

1. 真正补齐 `user` 端插件链路
   - `sync_plugin_permissions()` 增加 `user` 前缀同步
   - 菜单父级选择 API 增加 `user` 树
   - 前端插件初始化增加 `user` 端入口
   - `/plugins/slots` 与动态路由注册补齐 `user` 端

2. 或者明确取消当前版本的 `user` 端插件支持
   - 从 manifest 校验、registry、文档、`.cursor` 规则里移除 `user`

---

### P1-10. 插件脚手架与 CLI 校验/打包仍在产出旧模型，未来插件会继续偏离整改方案

#### 现状

- `plugin_cli.py` 的 full-module 模板仍固定生成 `frontend/dist/index.js` 的 UMD 输出。
- `_manifest_has_frontend_extensions()` 仍把 `frontend.admin.entry` / `frontend.tenant.entry` 当成前端存在性的判断条件。
- `validate` 与 `pack` 仍以 `frontend/dist/index.js` 作为核心契约，没有 release manifest、没有 source/release 区分。
- 当前脚手架不会生成“开发态源码契约 + 生产态发布契约 + release/source 分包”模型。

对应代码：

- `backend/scripts/plugin_cli.py`

#### 为什么不合适

因为这会让未来的新插件继续沿着旧模型生成。

也就是说，即使你把：

- 运行时
- 安装链路
- 打包链路
- `.cursor` 规则

都改好了，只要脚手架还停在旧模型，后续插件开发者还是会继续：

- 写 `frontend.admin.entry`
- 默认依赖固定 `dist/index.js`
- 沿用旧的菜单/页面组织方式

这样整改成果会被新的脚手架反向冲淡。

#### 为什么必须改

因为脚手架是“未来增量插件的入口”。

不改脚手架，就等于系统还在官方支持旧模型。

#### 建议

把 `plugin create / build / validate / pack` 一起升级，不要只改其中一段：

1. `create`
   - 生成新前端契约与 release/source 分轨目录

2. `build`
   - 生成 `frontend/dist/plugin.manifest.json`

3. `validate`
   - 区分开发模式和发布模式校验

4. `pack`
   - 支持 `--release` 与 `--source`
   - 默认发布模式不再交付 `frontend/src`

---

### P1-11. 启动时 manifest 热同步会自动覆盖 `granted_capabilities`，破坏“声明能力/授权能力”边界

#### 现状

- `Plugin.granted_capabilities` 在模型里明确写的是“管理员授权的能力列表”。
- 管理端也提供了单独的能力授权接口 `PUT /admin/plugins/{id}/capabilities`。
- 但 `discover_and_register()` 在“磁盘 manifest 与 DB manifest 不一致”时，会直接执行：
  - `existing_plugin.granted_capabilities = manifest.capabilities or existing_plugin.granted_capabilities`
- 插件运行时 `PluginContext` / `api_dispatcher` 又正是依赖 `plugin.granted_capabilities` 做能力闸门。

对应代码：

- `backend/app/models/system/plugin.py`
- `backend/app/api/admin/plugins.py`
- `backend/app/plugins/startup.py`
- `backend/app/plugins/api_dispatcher.py`
- `backend/app/plugins/context.py`

#### 为什么不合适

这会把两个本来应该严格分开的概念混在一起：

- 插件声明它“想要什么能力”
- 平台管理员“实际授予什么能力”

现在的行为实际上是：

- 插件作者改了 `plugin.yaml`
- 服务重启或启动发现同步后
- 平台就可能自动把新声明的能力授给插件

这会让管理员的授权动作失去独立意义。

#### 为什么必须改

因为如果能力授权边界不成立，那么：

- capability 管控就只是表面配置
- 审计和审批记录没有真实价值
- 后续插件升级会产生“声明变更即自动扩权”的风险

对于一个本来就不是硬沙箱的系统来说，这条边界反而更应该严。

#### 建议

至少要做三件事：

1. manifest 里保留 `capabilities` 作为“声明能力 / requested capabilities”
2. DB 里的 `granted_capabilities` 只允许管理员显式修改
3. 启动同步与 manifest 热同步禁止自动覆盖 `granted_capabilities`

如果磁盘 manifest 新增了能力声明，应改为：

- 标记插件 `review_required`
- 或阻止自动恢复
- 或要求管理员重新审批后再启用

---

### P1-12. `/plugin-assets` 静态资源分发没有按 scope / tenant assignment / license 收口

#### 现状

- `/plugin-assets/{plugin_name}/{file_path}` 是公开 GET/HEAD 路由。
- 非 icon 资源只检查“插件是否 enabled”。
- 不检查：
  - 资源 scope
  - 企业分配
  - 当前请求身份
  - License 状态
- 这意味着只要知道插件名和资源路径，任何人都能请求已启用插件的 `frontend/dist/*`。

对应代码：

- `backend/app/main.py`
- `backend/app/plugins/asset_resolver.py`

#### 为什么不合适

这会造成几个边界问题：

1. `admin_only` 插件的前端产物对匿名访问者同样可下载。
2. `selected_tenants` / `admin_and_selected_tenants` 插件即使没有分配给某企业，前端 bundle 仍可直接请求。
3. 付费插件即使前台入口被隐藏，编译产物仍然没有按授权收口。

这和“菜单不可见”“slots 不返回”不是一回事，因为这些只是在导航层做隐藏，不是资源分发层的授权。

#### 为什么必须改

因为前端交付边界不仅取决于“是否打了源码”，也取决于“编译产物是否对未授权方可见”。

如果编译产物下载口始终公开，那么：

- `admin_only` / 指定企业插件的可见性边界不完整
- 商业插件的发布边界也不完整

#### 建议

要把插件资源分发改成受控模型，至少选一种：

1. 由 slots API 下发带时效的签名资源 URL
2. 前端通过 authenticated fetch 拉取 JS/CSS，再转 object URL 加载
3. 在资源分发端做与 slots/API 相同的：
   - scope 校验
   - tenant assignment 校验
   - license 校验

不应该继续维持“运行入口受控、静态产物公开裸露”的状态。

---

### P1-13. 启动热同步绕过正式升级流程，版本管理和 manifest 投影会漂移

#### 现状

- `discover_and_register()` 对“磁盘有、DB 也有”的插件会直接同步 manifest。
- 这个同步会直接更新：
  - `plugin.manifest`
  - `plugin.version`
  - `plugin.scope`
  - `display_name / description / icon / tags`
  - `installed_packages`
  - `ai_requirements`
- 但它不会：
  - 创建新的 `PluginVersion` 记录
  - 调用 `VersionManager.upgrade()`
  - 调用 `on_upgrade()`
  - 走正式升级/回滚链路
- 同时，它又没有完整同步所有投影字段，例如：
  - `pricing_type`
  - `pricing_info`
  - `author`
  - `homepage`
  - `repository_url`
  - `license_text`

对应代码：

- `backend/app/plugins/startup.py`
- `backend/app/plugins/version_manager.py`
- `backend/app/models/system/plugin.py`

#### 为什么不合适

这会导致一种很别扭的“半升级”状态：

- 版本号已经变了
- manifest 快照已经变了
- 但版本历史没记
- 升级钩子没跑
- 正式升级流程也没走

这不仅让版本治理失真，还会让部分字段变成：

- manifest 里是新值
- DB 投影字段里还是旧值

最后就是同一个插件在不同接口上看到的元信息可能不一致。

#### 为什么必须改

因为只要系统已经存在：

- `VersionManager.upgrade()`
- `PluginVersion`
- `on_upgrade()`

就不应该再允许启动时的目录扫描偷偷承担“静默升级”的职责。

否则：

- 运维不知道插件实际上被升级了
- 回滚依据不完整
- 审计记录不完整
- 商业插件升级边界也会变得模糊

#### 建议

明确区分三件事：

1. `discover`
   - 只负责“发现新插件”和“发现缺失插件”

2. `sync`
   - 最多只同步非关键展示字段
   - 严禁自动变更 `version / scope / granted_capabilities / pricing`

3. `upgrade`
   - 版本变化必须强制走 `VersionManager.upgrade()`
   - 必须写 `PluginVersion`
   - 必须进入 `on_upgrade()` 和正式回滚链路

---

### P1-14. Python 依赖直接安装到宿主共享环境，但没有跨插件/宿主冲突治理

#### 现状

- `_install_python_deps()` 直接对当前项目 Python 解释器执行 `pip install`。
- 它只判断“当前已安装版本是否满足这个插件自己的 requirement”。
- 它不会在安装前统一检查：
  - 是否与其他已安装插件声明的 Python 依赖冲突
  - 是否会破坏宿主主项目自身依赖
  - 是否存在“两个插件要求同一包不同主版本”的无解情况
- `_uninstall_python_deps()` 也只是基于：
  - 其他插件的 `installed_packages`
  - 主项目 `pyproject.toml`
  - `pip show Required-by`
  做启发式保留/删除，并没有真正的依赖锁或求解结果可回放。

对应代码：

- `backend/app/plugins/lifecycle.py:1599-2203`
- `backend/app/plugins/startup.py:417-420`
- `backend/app/plugins/version_manager.py:158-170`

#### 为什么不合适

当前插件后端全部运行在同一个 Python 进程里，这意味着：

- 同名模块的多版本并存并不成立；
- 最后一次 `pip install` 很可能覆盖前一次插件所依赖的版本；
- 一个新插件的依赖升级，可能静默破坏：
  - 其他插件
  - 宿主后端
  - 已经通过测试的运行环境

也就是说，当前模型本质上是“共享宿主环境模式”，但系统没有把共享环境该有的冲突治理做完。

#### 为什么必须改

因为现在仓库里的正式插件虽然大多只依赖少量 Python 包，但这不代表模型本身合理。

一旦后面出现：

- 第三方插件
- 付费插件
- 更多存储/AI/集成类插件

共享环境下的依赖冲突就会从“隐患”变成“线上不稳定源”。

#### 建议

明确把后端插件依赖模型定为“共享宿主环境 + 安装期求解 + 启动期只校验”，并一次性补齐：

1. 安装/升级前做 Python 依赖冲突预检。
2. 把“宿主依赖 + 已安装插件依赖 + 新插件依赖”合并成统一求解图。
3. 无法同时满足时，直接拒绝安装或升级，不允许先装再看。
4. 生成可追踪的依赖快照或锁定结果，不能只靠 `installed_packages` 回忆历史。

---

### P1-15. 插件间依赖被拆成两套声明，生命周期与卸载保护不一致

#### 现状

- 当前代码同时存在两套“插件依赖”语义：
  - `dependencies.plugins`：名称级依赖
  - `compatibility.requires`：带版本约束的依赖
- 安装和启用时，这两套都会检查。
- 但停用/卸载保护、依赖查询、依赖方查询只看 `dependencies.plugins`。
- 也就是说，如果一个插件只通过 `compatibility.requires` 声明依赖：
  - 启用时会被要求目标插件存在且版本满足
  - 但目标插件被停用或卸载时，不一定会被这条依赖拦住
  - 管理端“依赖/被依赖”接口也不会完整反映这条关系

对应代码：

- `backend/app/plugins/manifest.py:771-781`
- `backend/app/plugins/manifest.py:835-838`
- `backend/app/plugins/lifecycle.py:327-380`
- `backend/app/plugins/lifecycle.py:639-683`
- `backend/app/plugins/lifecycle.py:895-898`
- `backend/app/plugins/lifecycle.py:1152-1156`
- `backend/app/plugins/lifecycle.py:1301-1368`

#### 为什么不合适

这不是“写法有点重复”这么简单，而是同一个依赖关系在不同生命周期阶段看到的是两套图：

- 安装/启用看的是 A 图
- 停用/卸载看的是 B 图
- 管理端展示又是 C 图

最后会出现一种非常危险的状态：

- 运行前置依赖检查通过
- 但后续对底座插件的禁用/卸载保护没有完全跟上

#### 为什么必须改

因为插件依赖必须是单一事实来源。

否则插件作者根本不知道：

- 应该写在哪个字段
- 哪个字段才会真的影响生命周期
- 哪个字段只是“装的时候看看，卸的时候不认”

#### 建议

不要继续保留这套双轨模型。应统一成一套规范化的插件依赖声明，并让以下链路全部复用同一份归一化结果：

1. install preview
2. install
3. enable
4. disable
5. uninstall
6. `get_dependencies`
7. `get_dependents`
8. 管理端依赖状态展示

更合适的方向是把插件间依赖收敛到 `dependencies.plugins`，并支持对象化声明版本约束，而不是继续把“依赖”拆一半放在 `compatibility.requires`。

---

### P1-16. 依赖状态、预览与管理 API 没有反映真实依赖模型

#### 现状

- `get_dependency_status()` 目前只真正计算 Python 依赖状态。
- 它完全忽略：
  - 插件间依赖
  - 版本约束依赖
  - `system` 依赖
- `npm` 在当前实现里已经不再由宿主运行时安装，但 API 和管理端交互仍然保留：
  - `python / npm / force` 请求体
  - `npm` 结果对象
  - 管理页仍然发送 `npm: true`
- `dependencies.system` 在 schema 中存在，但目前除了 install preview 原样透出外，没有实际校验、没有预检、没有执行策略。

对应代码：

- `backend/app/services/system/plugin_service.py:580-629`
- `backend/app/api/admin/plugins.py:83-170`
- `backend/app/plugins/lifecycle.py:1007-1088`
- `backend/app/plugins/preview.py:138-206`
- `frontend/apps/web-antd/src/api/admin/plugin.ts`
- `frontend/apps/web-antd/src/views/admin/plugins/index.vue`

#### 为什么不合适

这会导致管理端和接口对外表达出错误事实：

- 一个插件明明缺少上游插件或版本不匹配，依赖状态仍可能显示“installed”
- `system` 字段看起来像支持，实际上没人校验
- `npm` 看起来还能装/卸，实际上只是兼容外壳

这对新系统来说非常不合适，因为它会直接误导：

- 插件作者
- 运维人员
- 后续接手实现的人

#### 为什么必须改

依赖系统最怕“声明支持”和“实际支持”不一致。

如果系统还没有真的支持某类依赖，就不应该继续以正式 API 形态对外承诺。

#### 建议

1. `dependency_status` 改成真实模型：
   - `python`
   - `plugins`
   - `system`
2. `npm` 从运行期依赖 API 和管理页动作里彻底移除。
3. `dependencies.system` 二选一：
   - 要么补成真正可校验的 typed preflight 模型
   - 要么在当前版本先从正式 schema 与文档里移除
4. install preview 必须给出：
   - 缺失插件依赖
   - 版本不匹配
   - 缺失系统前置条件

---

### P1-17. 启动恢复仍会自动安装 Python 依赖，运行期与安装期边界没有完全切开

#### 现状

- 插件启用时会安装 Python 依赖。
- 插件升级时也会安装 Python 依赖。
- 但服务启动恢复 `restore_enabled_plugins()` 仍然会再次尝试 `_install_python_deps()`。

对应代码：

- `backend/app/plugins/lifecycle.py:716-726`
- `backend/app/plugins/startup.py:417-420`
- `backend/app/plugins/version_manager.py:158-159`

#### 为什么不合适

启动恢复本来应该是：

- 校验
- 恢复注册
- fail-close 标记错误

而不是在服务启动时继续修改宿主环境。

否则启动成功与否会额外依赖：

- 外部网络
- 编译工具链（例如 Rust/Cargo）
- pip 当前索引状态
- 启动瞬间的环境稳定性

这和前面已经收敛好的“前端 npm 依赖不属于启动恢复”是同一个问题，只是后端 Python 依赖这半边还没有彻底收口。

#### 为什么必须改

因为只要启动阶段还在 `pip install`，生产环境就仍然不是一个确定性可回放的发布环境。

#### 建议

把 Python 依赖补装权限收敛到三个入口：

1. install
2. upgrade
3. 显式 repair

而 `startup.restore_enabled_plugins()` 只做：

1. 快速校验依赖是否满足
2. 不满足则标记 `error / repair_required`
3. 不再在生产启动链路里直接安装

---

### P2-1. `frontend.admin.entry` / `frontend.tenant.entry` 当前是死字段

#### 现状

- manifest schema 定义了 `frontend.admin.entry` 和 `frontend.tenant.entry`
- 但实际运行时没有任何地方使用这个字段
- 前端 loader 直接把入口写死为 `/plugin-assets/{plugin}/index.js`
- 后端 slots API 也只返回 `styles`

对应代码：

- `backend/app/plugins/manifest.py:533-537`
- `backend/app/api/admin/plugins.py:213-235`
- `backend/app/api/tenant/plugins.py:148-168`
- `frontend/apps/web-antd/src/utils/plugin-loader.ts:142-179`

#### 为什么不合适

这会制造“manifest 可配置”的假象：

- 看起来支持多入口、按端侧区分入口
- 实际上完全不生效

这类死字段对长期维护非常不友好，因为它会误导新开发者。

#### 为什么必须改

因为 manifest 是插件作者和平台约定的核心接口。这里不能存在看似重要但实际上无效的字段。

#### 建议

要么：

- 真正接入 `entry`

要么：

- 删除该字段，统一约定入口就是 `index.js`

---

### P2-2. “沙箱”不是硬隔离沙箱，当前表述不准确

#### 现状

- `PluginContext` 限制了通过 ctx 访问 DB、HTTP、存储、AI 等能力。
- 但插件模块本身是在宿主进程内动态导入执行。
- 插件可直接 import 宿主已有依赖。
- 安全扫描是 AST 级静态检查，深度有限。
- 仓库中的插件已经直接导入 `httpx`、`os`。

对应代码：

- `backend/app/plugins/context.py:1-220`
- `backend/app/plugins/security_scan.py:24-165`
- `backend/app/plugins/module_loader.py:34-83`
- `backend/plugins/weather-widget/backend/open_meteo.py:12-18`
- `backend/plugins/qiniu-kodo/backend/driver.py:15-17`

#### 为什么不合适

当前最不合适的地方不在“实现弱”，而在“命名和心智预期强”。

如果把它叫真正的 sandbox，用户会自然以为：

- 插件无法直接访问宿主环境
- 只能通过 ctx 访问外部能力
- capability 声明能真正约束插件代码行为

但实际并不是这样。

#### 为什么必须改

因为安全边界的误判比安全边界本身更危险。错误的安全预期会导致错误的运营和商业决策。

#### 建议

短期内：

- 调整文档措辞，明确这是“能力约束层”而不是“进程级沙箱”

长期如果要提升安全性：

- 进程隔离
- 解释器隔离
- 更强的导入与网络限制

---

### P2-3. DEBUG 无公钥降级路径过松

#### 现状

- 当没有配置公钥且 `DEBUG=True` 时，`verify_license_key()` 直接解析 payload 而不验签。
- 正常路径里会检查 `payload.plugin == plugin_name`。
- DEBUG 降级路径中没有重新做插件名匹配。

对应代码：

- `backend/app/plugins/license.py:121-132`
- `backend/app/plugins/license.py:165-175`

#### 为什么不合适

虽然这是开发模式问题，但它会让：

- 开发环境的授权行为
- 生产环境的授权行为

出现不一致，增加调试误判概率。

#### 为什么必须改

因为 License 本来就已经是业务边界较脆弱的一层，开发路径不应再额外放大语义漂移。

#### 建议

即使在 DEBUG fallback，也应该补做：

- 插件名匹配检查
- 必要字段完整性检查

---

### P2-4. 菜单选择交互过弱，容易产生错误挂载和无效提交

#### 现状

当前 `PluginMenuConfigModal` 的体验问题比较集中：

1. 它本质上只是“每个菜单项对应一个 TreeSelect”。
2. 没有展示最终挂载结果预览。
3. 没有展示：
   - 结果路径
   - 所属端别
   - 最终 permission code
   - 将挂到哪一层目录之下
4. 当插件未给出默认 parent 时，会自动选第一个目录节点。
5. `TreeSelect` 允许 clear，但后端 `parent` 是必填模式，容易形成无效提交。
6. `scope == both` 时，前端仍然用一条菜单记录去承载 admin / tenant 两侧父级，抽象层次不清楚。

对应代码：

- `frontend/apps/web-antd/src/views/admin/plugins/modules/PluginMenuConfigModal.vue`
- `backend/app/api/admin/plugins.py`

#### 为什么不合适

这会让管理员在操作时只能“猜”：

- 选这个父级到底会出现在左侧哪个层级
- tenant 和 admin 两侧是否一致
- 清空是不是允许的
- 当前显示的是 manifest 默认值，还是已保存覆盖值

这类问题不会直接炸系统，但会持续制造“看起来能配、实际难以心中有数”的体验。

#### 为什么必须改

因为插件菜单挂载本来就是动态插件系统最容易让人迷糊的一层。

如果这里的交互不够明确，管理员就会把“菜单问题”误判成“插件问题”或“权限问题”。

#### 建议

菜单配置 UI 至少补齐：

1. 明确显示“manifest 默认挂载位置”和“当前覆盖值”。
2. 提供实时预览：
   - 管理端最终路径
   - 企业端最终路径
   - 最终挂载目录链路
3. 不允许产生空 parent 的无效提交。
4. 对 `both` 端别显示为两条清晰记录，而不是一个抽象行里塞两个父级字段。
5. 提供“恢复默认”而不是依赖手工清空。

---

### P2-5. 功能/扩展注册模型过于单体，诊断与运维体验差

#### 现状

当前 `register_all_extensions()` 把几乎所有插件能力都揉进了一个批处理函数：

- skills
- adapters
- storage
- hooks
- events
- webhooks
- tasks
- notifications
- permissions
- socketio
- menus
- frontend slots
- middleware
- custom
- consumers

失败时主要记录为：

- ext type
- entry point

然后由调用方自己决定是否 fail-close。

#### 为什么不合适

这会带来几个实际问题：

1. 注册粒度太粗。
2. 一眼看不出“哪类功能”真的注册成功了。
3. 不能针对菜单、路由、skills、tasks 做细粒度重建。
4. 也不利于未来在管理端做“扩展健康状态”可视化。

#### 为什么必须改

因为动态插件系统后面一定会走向：

- 局部重建
- 局部修复
- 局部开关
- 更细的错误诊断

现在这套“全量批注册 + 泛化失败列表”的模式，很快就会成为维护负担。

#### 建议

逐步把扩展注册拆成按域的注册器或至少按域的 orchestrator，例如：

1. runtime handlers
2. frontend navigation
3. background jobs
4. AI / skill bindings
5. notification / webhook / socketio

菜单配置、页面路由刷新、skill 修复、task 修复，后续都应能独立执行。

---

### P2-6. 企业分配接口缺少 scope 校验，分配模型也没有完整落到管理端

#### 现状

- 插件资源 scope 明确区分了：
  - 所有企业可见
  - 指定企业可见
  - 管理端可见
- 但 `PluginService.assign_tenants()` 并不校验当前插件 scope 是否真的需要企业分配。
- 管理端前端只有：
  - 分配
  - 取消分配
- 而后端模型与 service 其实还存在：
  - `is_active`
  - `toggle_tenant_assignment()`

对应代码：

- `backend/app/services/system/plugin_service.py`
- `backend/app/models/system/resource_tenant_assignment.py`
- `backend/app/api/admin/plugins.py`
- `frontend/apps/web-antd/src/views/admin/plugins/modules/PluginConfigDrawer.vue`

#### 为什么不合适

这会导致两个问题：

1. 对不需要分配的插件也可以写入分配数据
   - 例如 `global_shared` / `all_tenants` / `admin_only`
   - 这些数据写进表里没有明确业务意义

2. 分配模型在后端和前端不一致
   - 后端有 `is_active`
   - 前端只有 add/remove
   - service 里还有 toggle 方法，但管理端没有完整暴露

这会让“企业分配”看起来像是做完了，实际上还是半套模型。

#### 为什么必须改

因为插件本来就已经同时涉及：

- 资源 scope
- 企业可见性
- 菜单/slots/API 分发

如果分配模型本身不严，后续排查“为什么某企业能看到/看不到某插件”会越来越混乱。

#### 建议

1. `assign_tenants()` 先校验 scope 是否属于 assignment-required scopes
2. 非 assignment-required 的插件禁止写入 RTA 记录
3. 明确管理端到底采用哪种模型：
   - 仅 add/remove
   - 还是 add/disable/enable/remove 四态管理
4. 如果保留 `is_active`，前端必须补齐对应操作，不要只留后端死能力

---

### P2-7. API 端别语义过松：admin 侧会回退匹配 `tenant_routes`

#### 现状

- `_dispatch_plugin_api()` 里明确写了：
  - tenant 侧只匹配 `tenant_routes + public_routes`
  - admin 侧匹配 `admin_routes + tenant_routes + public_routes`
- 也就是说，admin 请求会把 `tenant_routes` 当成可回退匹配目标。

对应代码：

- `backend/app/plugins/api_dispatcher.py`

#### 为什么不合适

“admin 权限更高”不等于“tenant 端 handler 在 admin 上下文里也天然成立”。

很多 tenant route 的真实语义其实隐含依赖：

- `tenant_id`
- tenant side path
- tenant 侧页面上下文
- tenant assignment 的可见性逻辑

如果 admin 侧直接把它当回退路由，插件作者就很难准确理解：

- 什么路由算 admin-only
- 什么路由算 tenant-only
- 什么路由应该双端共用

#### 为什么必须改

因为插件系统已经在 manifest 中把 API 明确拆成：

- `admin_routes`
- `tenant_routes`
- `public_routes`

如果运行时又把端别边界重新揉回去，这个设计就失真了。

#### 建议

应改成更严格的显式模型：

1. admin 请求只匹配 `admin_routes`
2. tenant 请求只匹配 `tenant_routes`
3. 公开请求只匹配 `public_routes`
4. 如果确实要双端可用，就显式声明两份
   - 或新增真正的 `both_routes` 概念

不要再依赖“admin 是 superset，所以 tenant_routes 也顺便开放”的隐式规则。

---

### P3-1. 前端“付费插件”判定存在死代码与语义漂移

#### 现状

- 管理端前端把“是否付费插件”判断成：
  - `pricing_type === 'paid'`
  - 或 `tier === 'pro'`
- 但后端 `PluginTierEnum` 实际只有：
  - `official`
  - `verified`
  - `community`

对应代码：

- `frontend/apps/web-antd/src/views/admin/plugins/modules/PluginConfigDrawer.vue:472-474`
- `backend/app/enums/plugin.py:20-25`

#### 为什么不合适

这里把两个本来不同维度的概念混在了一起：

- `pricing_type` 是商业属性
- `tier` 是信任等级属性

而且 `pro` 在当前后端枚举里根本不存在，这说明前端已经出现了语义漂移和死代码。

#### 为什么必须改

这类问题虽然不属于高危 bug，但它会持续误导维护者：

- 新人会以为 tier 可以表达商业分层；
- 后续有人如果继续往 tier 塞商业语义，会让“信任等级”和“计费等级”彻底混淆。

#### 建议

- 删除 `tier === 'pro'` 判定
- 商业属性只由 `pricing_type` 或未来单独的商业字段表达
- 不要让 `tier` 再承载收费语义

## 5. “试用”和“带期限授权”在当前代码中的真实含义

### 5.1 试用

当前“试用”是代码里最明确的一种授权记录：

- `plugin_licenses.license_type = 'trial'`
- 到期时间放在 `trial_expires_at`
- 状态接口会返回 `status = trial`
- 调度任务只处理这一类

也就是说，“试用”在当前系统中是一个真正被显式建模出来的类型。

### 5.2 带期限授权

当前“带期限授权”不是一个独立类型，而是：

- 通过 CLI `--days` 生成 Key
- payload 中带 `expires_at`
- 激活写库时仍然写成 `license_type = 'perpetual'`
- 同时给这条记录挂上 `expires_at`

所以它的真实语义是：

> 一条被标记为 `perpetual` 的付费 License 记录，但实际又带有到期时间。

这就是当前最令人困惑的地方。

### 5.3 为什么你会觉得“没搞懂”

因为代码没有用清晰的数据模型表达这个业务概念。

不是你没理解，而是实现本身就把两个互相冲突的概念混用了：

- `perpetual`
- `expires_at`

## 6. 前端插件运行与交付模式审计

### 6.1 当前运行机制

当前前端插件的正式运行机制是：

1. 后端通过 slots API 返回前端插槽声明
2. 前端按插件名调用 `loadPluginComponents(pluginName)`
3. 生产环境通过 `/plugin-assets/{plugin}/index.js` 加载 UMD bundle
4. UMD bundle 暴露 `window.NovusPlugin_{plugin_name_underscored}`
5. 前端从该全局对象读取组件导出

这条链路是成立的，说明“前端插件运行时以编译产物为主”这个设计是对的。

### 6.2 当前开发机制

开发模式下，Vite 自定义插件会拦截同一个 `/plugin-assets/{plugin}/index.js` 路径：

- 如果存在 `frontend/src/index.ts`
- 则直接把源码通过 Vite 转译后返回

这条链路解决的是开发效率问题，本身也是合理的。

### 6.3 当前不合适的地方

问题不在“支持源码模式”，而在以下三点：

1. 运行模式没有被清楚建模。
2. 发布链路没有按照运行模式做严格区分。
3. 商业交付时前端源码仍被打包交付。

### 6.4 对付费插件意味着什么

如果插件前端源码和插件包一起交付，那么：

- 前端是否“先编译”并不能构成源码保护；
- License 也不可能成为真正的防复制机制；
- 商业控制只能依赖平台运行门禁，而不是代码保密。

因此，对付费插件来说，当前最不合适的不是“支持源码模式”，而是：

- 发布链路没有把“开发源码”和“商业交付产物”隔离开。

### 6.5 关于 “dev 和生产都用 dist 不合理” 的更准确结论

这件事需要拆开看。

更准确的结论不是“生产环境用 dist 不合理”，而是：

- 生产环境使用编译产物本身是合理的。
- 不合理的是 dev 和 prod 现在被伪装成同一个运行契约。

为什么这么说：

1. 生产环境本来就应该加载稳定、可部署、可缓存的发布产物。
   - 否则你会把 TypeScript、Vue SFC、Vite 转译能力、Node 工具链一起带进运行时。
   - 对正式环境来说，这不是简化，而是把构建期职责和运行期职责混在一起。

2. 当前真正不合理的点，是 dev 和 prod 都对外暴露成同一个 `/plugin-assets/{plugin}/index.js`。
   - dev 实际返回的是 `src/index.ts` 被 Vite 临时转译后的 ESM。
   - prod 实际返回的是 `frontend/dist/index.js`。
   - 路径相同，但语义完全不同，这会制造大量维护误判。

3. 当前前端运行契约过于“伪静态化”。
   - 它把发布物固定死成 `index.js`。
   - 这会让 `frontend.admin.entry` / `frontend.tenant.entry` 变成死字段。
   - 也不利于未来支持 hashed chunk、独立 CSS、code splitting、构建 manifest。

4. 当前生产恢复链路还在试图“补 npm 依赖”，这也说明构建期和运行期边界还没切干净。
   - 对前端插件来说，生产态应该依赖发布产物，而不是依赖现场再装 npm 包。

所以真正应该改造的方向是：

- dev 走明确的源码开发契约
- prod 走明确的发布产物契约
- 两者不要再共用同一个“看上去像 dist 文件”的 URL 语义
- `plugin pack` 也不要再把两条链路的文件混装到一个交付包里

## 7. 完整端到端流程回放（基于代码真实路径）

这一节只描述代码真实执行路径，不等同于下一节的“已执行验证”。

换句话说，这里回答的是：

- 用户从后台点击某个动作后，系统实际上会调用哪些代码。
- 这些代码链路里，授权、过期、前端产物分别在哪一层被处理。
- 哪些地方只是“看起来有能力”，但实际上没有接进主链路。

### 7.1 安装流程回放

安装链路的实际入口是管理端 `POST /admin/plugins/upload`。

真实流程如下：

1. 后端先调用 `_extract_plugin_from_zip()`，把 ZIP 解压到系统临时目录，而不是项目目录。
2. 解压前先走 `ensure_package_size_limit()`，解压时走 `extract_plugin_zip_safely()`，这里会做 ZIP 安全校验。
3. 管理端 API 会先查数据库，若同名插件已安装，则拒绝并要求走卸载或升级流程。
4. 然后进入 `PluginService.install_from_path()`，继续调用 `PluginLifecycle.install()`。
5. `install()` 内部会读取 manifest、加 Redis 安装锁、把插件目录复制到 `backend/plugins/{name}/`。
6. 接着做平台版本兼容性、插件依赖、版本约束检查。
7. 如果插件带 migrations，则执行 Alembic upgrade。
8. 如果声明了 AI features / i18n，则在安装阶段写入相关记录。
9. 调用插件 `on_install()`。
10. 最后写入 `plugins` 表与 `plugin_versions` 表，插件状态记为 `installed`，而不是 `enabled`。

这条链路有三个关键审计结论：

1. 安装本身不做 License 校验。
   - 也就是说，安装一个“付费插件”和安装一个“免费插件”在主链路上没有本质区别，差别只体现在 `pricing_info` 被写入数据库。

2. 安装本身不会自动发放试用。
   - `create_trial_license()` 的 docstring 写着“安装付费插件无 Key 时自动调用”，但实际代码唯一调用点是管理端显式接口 `POST /{plugin_id}/activate-trial`。
   - 这说明当前“试用自动开通”只是注释语义，不是真实行为。

3. 安装链路不对前端 `dist/index.js` 做后台 fail-close。
   - 当前严格检查主要发生在 CLI `plugin validate`。
   - 后台上传安装 API 并不会因为前端缺失 `frontend/dist/index.js` 而在安装阶段直接失败。

### 7.2 启用流程回放

启用链路入口是管理端 `POST /admin/plugins/{plugin_id}/enable`。

真实流程如下：

1. 管理端如果传了 `menu_overrides`，会先把菜单挂载配置写入插件 config。
2. 然后进入 `PluginService.enable_plugin()`，继续调用 `PluginLifecycle.enable()`。
3. `enable()` 会查插件记录、加载 manifest，并在 DEBUG 模式下把磁盘 manifest 的关键信息同步回数据库。
4. 接着检查：
   - 冲突插件是否已启用
   - 依赖插件是否已启用
   - 依赖插件版本是否满足要求
5. 如果插件带 migrations，则执行 Alembic upgrade。
6. 如果声明了 Python / npm 依赖，则尝试自动安装。
7. 调用 `register_all_extensions()` 注册 API、frontend slots、skills、tasks、notifications 等扩展点。
8. 如果关键扩展加载失败，会 fail-close 回滚注册，并把插件状态标为 `error`。
9. 若扩展注册成功，则继续：
   - 创建或激活 Skill 记录
   - 重建 AI feature 绑定
   - 同步通知模板
   - 同步周期任务
10. 然后调用插件 `on_enable()`。
11. 成功后把状态改为 `enabled`，再执行 `sync_plugin_permissions(plugin_name)`，并启用菜单权限。

这条链路的关键结论是：

1. 启用流程没有统一的 License gate。
   - 它会检查依赖、冲突、扩展加载、生命周期钩子，但不会检查“当前插件是否有有效授权”。

2. 启用流程也没有对前端 `dist/index.js` 做硬性 fail-close。
   - 也就是说，一个前端插件即使没有可用编译产物，也可能在启用阶段通过，直到前端实际加载 `/plugin-assets/{plugin}/index.js` 时才暴露问题。

3. 当前系统真正 fail-close 的是“扩展加载失败”，不是“商业授权失效”或“前端产物缺失”。

### 7.3 试用、激活、带期限授权流程回放

当前授权相关入口只有三类：

- `GET /admin/plugins/{plugin_id}/license`
- `POST /admin/plugins/{plugin_id}/activate-license`
- `POST /admin/plugins/{plugin_id}/activate-trial`

真实流程如下：

1. `GET /license`
   - 只是读取当前状态并返回给前端展示，不会改变任何运行状态。

2. `POST /activate-license`
   - 先验签并校验 License Key 的 plugin name。
   - 检查 Key 是否已被激活，防止重放。
   - 如果 payload 里有 `expires_at`，会转换成数据库时间字段。
   - 然后把该插件旧的有效 license 统一置为无效。
   - 再插入一条新的 `PluginLicense` 记录。

3. `POST /activate-trial`
   - 直接调用 `create_trial_license(plugin_id, trial_days=14, db=db)`。
   - 试用天数固定写死为 14。
   - 没有读取 manifest 的 `pricing.trial.enabled` / `pricing.trial.days`。

这条链路最需要别人理解的点有四个：

1. 试用不是安装时自动发生，而是后台显式点击后才发生。

2. 当前“试用”是一个显式类型。
   - `license_type = 'trial'`
   - 到期字段是 `trial_expires_at`

3. 当前“带期限授权”不是一个显式类型。
   - 激活付费 Key 时，无论 Key 是否带 `expires_at`，写库都统一写成 `license_type = 'perpetual'`
   - 只是额外挂一个 `expires_at`

4. 这正是“你会觉得没搞懂”的根源。
   - 因为系统把“永久付费授权”和“带期限的付费授权”混在同一个显式类型里表示。

### 7.4 过期处理流程回放

审计当时唯一的定时过期任务是 `check_trial_expirations()`；当前实现已统一为 `check_plugin_license_expirations()`。

真实流程如下：

1. 定时任务只查询：
   - `license_type == trial`
   - `is_valid == true`
   - `trial_expires_at is not null`
2. 如果试用已过期：
   - 若插件当前是 `enabled`，则尝试调用 `PluginLifecycle.disable()`
   - 然后把该 trial 记录置为 `is_valid = false`
3. 如果距离试用到期不足 3 天，则只生成提醒动作。

这里最关键的结论是：

1. 当前只处理“试用过期”，不处理“带期限付费授权过期”。
2. 付费授权的 `expires_at` 主要只在“状态查询”时被识别为 expired。
3. 只要插件数据库状态仍是 `enabled`，API、Webhook、slots、静态资源、启动恢复都可能继续工作。

也就是说，当前过期语义存在两套系统：

- trial：有调度任务，会尝试禁用插件
- paid with expires_at：主要只是状态展示，没有统一停用闭环

### 7.5 服务启动后的恢复流程回放

服务启动时会执行 `restore_enabled_plugins()`。

真实流程如下：

1. 启动阶段在恢复之前，还会先经过 `discover_and_register()`。
2. 然后查询数据库里所有 `status = enabled` 的插件。
3. 对每个插件重新加载 manifest。
4. 如果启用 heavy restore：
   - 执行 Alembic upgrade
   - 补装 Python 依赖
   - 补装 npm 依赖
5. 之后调用 `register_all_extensions()` 恢复所有扩展点注册。
6. 如果关键扩展恢复失败，则把插件状态改成 `error`。
7. 如果恢复成功，则保持 `enabled` 状态并清理错误计数。

这里的关键结论是：

1. 启动恢复只认数据库里的 `status = enabled`。
2. 它不会检查该插件对应的 License 是否过期、撤销或无效。
3. 启动前置的 `discover_and_register()` 还会把磁盘 manifest 的部分关键字段同步回 DB。
4. 因此，一个“已过期但仍保持 enabled 状态”的插件，在服务重启后仍会被继续恢复。
5. 同时，一个磁盘上 manifest/version 已变化的插件，也可能在启动时进入“未走正式升级链路的半升级状态”。

这说明当前授权系统没有接入“冷启动路径”的运行门禁。

### 7.6 前端 slots / plugin-assets / UMD 加载流程回放

这部分正好回答你前面问的另一个问题：系统到底能不能支持“编译的”和“未编译的”前端插件。

实际答案是：能支持，但不是对称的统一模型，而是双轨模型。

真实流程如下：

1. 后端 admin/tenant `slots` API 只基于“已启用插件”返回前端插槽数据。
2. 前端 `plugin-loader.ts` 统一按插件名加载 `/plugin-assets/{plugin}/index.js`。
3. 在开发模式：
   - Vite 插件 `vite-plugin-novus-plugins.ts` 拦截这个路径
   - 如果存在 `frontend/src/index.ts`，就把源码转译成 ESM 返回
4. 在生产模式：
   - 前端直接插入 `<script src="/plugin-assets/{plugin}/index.js">`
   - 期望插件 bundle 在 `window.NovusPlugin_{name}` 上暴露导出
5. 后端 `/plugin-assets/{plugin}/{file}` 真实允许读取的只有两类文件：
   - 插件根目录的图标文件
   - `frontend/dist` 下的静态资源

这说明：

1. 生产运行只认编译产物 `frontend/dist/index.js`。
2. 开发调试才认 `frontend/src/index.ts`。
3. 当前系统确实同时支持“编译产物模式”和“源码模式”，但前提是：
   - 源码模式只在开发态成立
   - 编译产物模式才是生产态正式契约
4. 当前 `/plugin-assets` 这条真实分发链路只检查 enabled，不检查 scope、tenant assignment、license。

因此，准确表述应该是：

- 当前系统支持“开发态源码转译 + 生产态编译产物加载”
- 但不等于“任意环境都可以对称运行 src 和 dist 两种插件”

还有一个补充结论也很重要：

- manifest 里的 `frontend.admin.entry` / `frontend.tenant.entry` 并没有参与这条真实加载链路。
- 当前真正的运行约定是固定路径 `/plugin-assets/{plugin}/index.js`，而不是 manifest entry。

### 7.7 打包发布流程回放

打包相关有两个主要命令：

- `plugin validate`
- `plugin pack`

真实行为如下：

1. `plugin validate`
   - 如果 manifest 声明了前端扩展，则要求存在 `frontend/dist/index.js`
   - 缺失时会直接报错
   - 也会扫描 `.vue`、i18n key、安全风险等

2. `plugin pack`
   - 如果前端插件缺少 `frontend/dist/index.js`，只打印 warning，不会阻止打包
   - 打包时会递归遍历整个插件目录
   - 只排除了少数目录和扩展名：
     - `node_modules`
     - `__pycache__`
     - `.git`
     - `.venv`
     - `.pyc/.pyo`

这意味着：

1. `plugin pack` 会把 `frontend/dist` 打进去。
2. `plugin pack` 也会把 `frontend/src` 打进去。
3. 它还会把测试文件、锁文件、Vite 配置等一起打进去。

所以当前系统不是“打包时二选一地支持 compiled 或 source”，而是：

- 运行时：开发态和生产态走不同轨道
- 打包时：把两条轨道的文件一起交付

对于内部免费插件，这可能只是包体不够干净。

但对于付费前端插件，这就是明显不合适的商业交付模型。

## 8. 已执行验证（实跑）

### 8.1 插件链路自动化回归

已执行插件相关自动化回归：

```text
backend/.venv/Scripts/python -m pytest tests/plugins/test_contract_lifecycle.py tests/plugins/test_plugin_menu_canonical_scope.py tests/plugins/test_marketplace_client.py tests/test_plugin_api_dispatcher_security.py tests/test_plugin_api_dispatcher_context_safety.py tests/test_plugin_webhook_dispatcher_security.py tests/test_plugin_loader.py tests/test_plugin_module_loader.py tests/test_plugin_manifest_validation.py tests/test_plugin_asset_resolver.py tests/test_plugin_package_security.py tests/test_plugin_license_query_stability.py tests/test_plugin_license_verification_policy.py tests/test_plugin_service_license_activation.py tests/test_plugin_startup_restore_modes.py tests/test_plugin_lifecycle_lock.py tests/test_plugin_lifecycle_cleanup_safety.py tests/test_plugin_transaction_semantics.py tests/test_plugin_version_manager_locking.py tests/test_storage_plugins.py tests/migrations/test_alembic_plugin_paths_consistency.py -q
```

结果：

- `132 passed in 2.16s`

这说明：

- 当前插件骨架、生命周期、打包安全、资产路径解析、恢复流程等基础能力没有明显回归失败。
- 但测试通过不等于商业授权闭环成立，因为授权门禁本身还没有统一接进主链路。

### 8.2 7 个正式插件的 CLI validate 实跑结果

已对以下正式插件执行 `plugin validate`：

- `aliyun-oss`
- `amazon-s3`
- `novusdoc`
- `qiniu-kodo`
- `storage-migration`
- `tencent-cos`
- `weather-widget`

结果如下：

1. `aliyun-oss`
   - 全通过
   - 无前端

2. `amazon-s3`
   - 全通过
   - 无前端

3. `qiniu-kodo`
   - 全通过
   - 无前端

4. `tencent-cos`
   - 全通过
   - 无前端

5. `storage-migration`
   - 全通过
   - `frontend/dist/index.js` 存在
   - 安全扫描 clean

6. `weather-widget`
   - 1 条 warning
   - `Security: backend/open_meteo.py:13: imports dangerous module 'os'`

7. `novusdoc`
   - 3 条 warning
   - `i18n key 'plugin' in en.json should start with 'plugin.novusdoc.'`
   - `i18n key 'plugin' in zh-CN.json should start with 'plugin.novusdoc.'`
   - `Security: backend/api/export.py:19: dangerous call 'compile()'`

这里要特别强调一个结论：

- 当前仓库里的 3 个正式前端插件 `novusdoc`、`storage-migration`、`weather-widget`，都已经具备 `frontend/dist/index.js`。
- 所以“当前这份代码仓库里的正式插件”在生产态是能加载编译产物的。
- 问题不是“当前现有插件跑不起来”，而是“系统契约没有把这件事建成强制规则”。

### 8.3 `plugin pack` 端到端回放结果

已实际执行：

- `plugin pack backend/plugins/novusdoc`
- `plugin pack backend/plugins/storage-migration`
- `plugin pack backend/plugins/weather-widget`

产物结果如下：

| 插件 | 打包输出 | ZIP 内关键内容 | 审计结论 |
|---|---|---|---|
| `novusdoc` | `36 files, 66.1 KB` | 同时包含 `frontend/dist/index.js` 与 `frontend/src/*`，并包含 `frontend/src/views/__tests__/DocumentEditorPageAwareness.test.ts` | 前端源码与测试文件一起交付，不适合付费前端插件发布 |
| `storage-migration` | `25 files, 52.2 KB` | 同时包含 `frontend/dist/index.js` 与 `frontend/src/*` | 编译产物和源码一起交付 |
| `weather-widget` | `31 files, 313.0 KB` | 同时包含 `frontend/dist/index.js` 与 `frontend/src/*`，并包含 `backend/tests/*` | 前端源码与后端测试文件一起交付，不适合商业发布包 |

这组实跑结果把前面的问题彻底坐实了：

1. 当前前端插件确实能以编译产物运行。
2. 当前开发态也确实能以源码转译运行。
3. 但官方打包链路并没有把这两种模式隔离成两类交付物，而是把两者一起塞进同一个 ZIP。

### 8.4 实跑后的直接结论

如果你问的是：

- “系统能不能跑编译好的插件？”
  - 能，当前 3 个正式前端插件都已经具备 `frontend/dist/index.js`，生产态就是这么跑的。

- “系统能不能跑未编译的插件？”
  - 能，但那是开发态通过 Vite 拦截 `/plugin-assets/{plugin}/index.js` 后把 `src/index.ts` 转译出来，不是正式发布模型。

- “当前官方打包是不是同时支持这两种交付？”
  - 从“把文件都打进 ZIP”这个角度看，是的。
  - 但这不是合理的商业交付支持，而是把开发源码和生产产物混装到同一个包里。

### 8.5 历史/备份插件补充实跑结果

为了回答“其他已经做完的插件是不是也要按新模型统一整改”，本次还额外对历史/备份插件做了补充校验。

已实际执行：

- `python backend/scripts/plugin_cli.py validate backend/plugins/.backups/netdisk/1.0.0_20260316_201902/files`
- `python backend/scripts/plugin_cli.py validate backend/plugins/.backups/novus-crud-code/1.0.0_20260314_083358/files`
- `python backend/scripts/plugin_cli.py validate backend/plugins/.backups/regression-probe/0.0.1_20260303_090249/files`
- `python backend/scripts/plugin_cli.py validate backend/plugins/.backups/example-weather/1.0.0_20260303_091616/files`

结果如下：

| 插件 | 证据来源 | 实跑结果 | 直接结论 |
|---|---|---|---|
| `netdisk` | 备份源码 | validate 失败：`scope: admin_and_assigned` 已不是当前 canonical scope；同时存在 `frontend/src` 与 `frontend/dist` | 说明该插件属于已做完但仍停留在旧 schema/旧作用域语义的历史插件，迁移前不能直接按当前正式插件标准恢复 |
| `novus-crud-code` | 备份源码 | validate 失败：`extensions.frontend.menus[].scope=admin_only` 不符合当前前端端别语义；另有 `<style scoped>` 违例 | 这是当前“旧前端模型”最典型的历史插件，必须随新前端契约一起迁移 |
| `regression-probe` | 备份源码 | validate clean | 更像回归/探针插件，可保留为系统测试夹具 |
| `example-weather` | 备份源码 | validate clean | 更像样例插件，可作为新模板迁移后的基准示例 |

另外还有一个重要事实：

- 当前正式源码目录 `backend/plugins/` 里并不存在 `novusdoc-pro` 插件根目录。
- 历史文档 `docs/reports/m590/baseline/plugin_status_api.json`、`docs/guides/plugin-smoke-validation.md`、`docs/guides/plugin-go-live-runbook.md` 曾把 `novusdoc-pro` 按较高优先级记录。
- 但按当前业务澄清，它只是一个富文本测试/文档菜单页样例插件，不应再被当成当前插件系统架构的核心目标插件。

这意味着：

- `novusdoc-pro` 当前只能按“历史运行基线 / 文档证据”审计，不能按“当前工作区正式源码”做同等级代码审计。
- 交付给实施同学时，必须把这一点写清楚，避免误以为仓库里已经保留了它的完整源码根目录。

### 8.6 现有自动化的覆盖缺口

本次补审后，还额外确认了一个事实：

- 现有自动化虽然覆盖了插件生命周期、manifest 校验、dispatcher 基础安全、asset resolver 安全、version manager 加锁等基础能力，
- 但没有对以下新增高风险问题建立明确回归断言：

1. `discover_and_register()` 不得自动覆盖 `granted_capabilities`
2. `/plugin-assets` 必须受 scope / tenant assignment / license 约束
3. manifest/version 变更不得在 discover 阶段形成 silent upgrade
4. `assign_tenants()` 必须校验 assignment-required scope
5. admin side 不得隐式回退匹配 `tenant_routes`

这意味着当前测试“全绿”并不能覆盖这轮新增发现。

因此在实施整改时，必须把上述五类问题同步补成自动化用例，否则很容易在后续重构时再次回归。

## 9. 现有正式插件与历史插件补充审计

### 9.1 总体画像

当前仓库内正式插件的总体情况如下：

1. 一共 7 个正式插件。
2. 其中 4 个是纯后端存储驱动插件：
   - `aliyun-oss`
   - `amazon-s3`
   - `qiniu-kodo`
   - `tencent-cos`
3. 其中 3 个带前端：
   - `novusdoc`
   - `storage-migration`
   - `weather-widget`
4. 这 7 个正式插件全部都是 `pricing.type: free`。
5. 也就是说，当前正式插件并没有任何一个真的在依赖“试用 / 付费 / 带期限授权”链路。
6. 当前前端插件都同时存在：
   - `frontend/src/index.ts`
   - `frontend/dist/index.js`
7. 当前正式插件里没有任何一个使用 `frontend.admin.entry` 或 `frontend.tenant.entry`。

这意味着：

- 授权系统目前更像“平台预留能力”，不是“现有正式插件已广泛接入的能力”。
- 正式前端插件当前的真实运行契约，就是“开发态走 src，生产态走 dist”。

### 9.2 汇总表

| 插件 | 范围 | 前端 | 主要扩展 | 当前风险/备注 | 商业交付判断 |
|---|---|---|---|---|---|
| `aliyun-oss` | `global_shared` | 无 | `storage_drivers×1` | 无前端；CLI validate clean | 前端源码泄露问题不涉及；若做商业插件仍只有平台门禁 |
| `amazon-s3` | `global_shared` | 无 | `storage_drivers×1` | 无前端；CLI validate clean | 前端源码泄露问题不涉及；若做商业插件仍只有平台门禁 |
| `novusdoc` | `admin_and_selected_tenants` | 有 | `api`、`frontend` | 前端 ZIP 含 `src`；i18n 前缀 warning；`compile()` warning | 不适合直接作为付费前端插件交付 |
| `qiniu-kodo` | `global_shared` | 无 | `storage_drivers×1` | 无前端；CLI validate clean | 前端源码泄露问题不涉及；若做商业插件仍只有平台门禁 |
| `storage-migration` | `admin_only` | 有 | `api`、`frontend` | 前端 ZIP 含 `src`；CLI validate clean | 不适合直接作为付费前端插件交付 |
| `tencent-cos` | `global_shared` | 无 | `storage_drivers×1` | 无前端；CLI validate clean | 前端源码泄露问题不涉及；若做商业插件仍只有平台门禁 |
| `weather-widget` | `admin_and_selected_tenants` | 有 | `skills×1`、`api`、`frontend` | 前端 ZIP 含 `src`；backend 测试文件也会打包；`os` 导入 warning | 不适合直接作为付费前端插件交付 |

### 9.3 逐个结论

#### 9.3.1 `aliyun-oss`

- 插件类型：全局共享存储驱动插件。
- 核心能力：`storage:read`、`storage:write`。
- 扩展点：`storage_drivers`，入口为 `driver.OssStorageDriver`。
- 审计结论：
  - 结构简单，零前端，当前 `validate` clean。
  - 这类插件不涉及“前端源码是否交付”的问题。
  - 但如果以后做商业插件，License 仍然只能作为平台启停门禁，而不是源码保护手段。

#### 9.3.2 `amazon-s3`

- 插件类型：全局共享存储驱动插件。
- 核心能力：`storage:read`、`storage:write`。
- 扩展点：`storage_drivers`，入口为 `driver.S3StorageDriver`。
- 审计结论：
  - 与 `aliyun-oss` 类似，当前没有明显结构问题。
  - 不涉及前端打包泄露，但依然受“授权只剩平台门禁意义”的总体约束。

#### 9.3.3 `qiniu-kodo`

- 插件类型：全局共享存储驱动插件。
- 核心能力：`storage:read`、`storage:write`。
- 扩展点：`storage_drivers`，入口为 `driver.KodoStorageDriver`。
- 审计结论：
  - 当前 `validate` clean。
  - 与其他纯后端驱动插件一样，结构上比较清晰。
  - 商业问题不在前端，而在“宿主平台是否严格执行授权闸门”。

#### 9.3.4 `tencent-cos`

- 插件类型：全局共享存储驱动插件。
- 核心能力：`storage:read`、`storage:write`。
- 扩展点：`storage_drivers`，入口为 `driver.CosStorageDriver`。
- 审计结论：
  - 当前 `validate` clean。
  - 同样不涉及前端交付问题，但仍受 License gate 缺失的总体问题影响。

#### 9.3.5 `novusdoc`

- 插件类型：带前端页面的完整业务模块插件。
- 范围：`admin_and_selected_tenants`。
- 核心能力：`db:own_tables`、`storage:read`、`storage:write`、`config:write`。
- 扩展点：
  - admin/tenant 双侧 API 路由
  - admin/tenant 双侧菜单与 standalone pages
- 审计结论：
  - 当前既有 `frontend/src`，也有 `frontend/dist`，说明它已经符合“开发态源码 + 生产态编译产物”的双轨模型。
  - 但 `plugin pack` 会把 `frontend/src` 与前端测试文件一起打包出去。
  - 当前又存在 i18n key 前缀 warning 和 `compile()` 安全扫描 warning。
  - 所以它作为免费内置插件可以继续使用，但不适合直接复制为付费前端插件发布模板。

#### 9.3.6 `storage-migration`

- 插件类型：带前端页面的管理端运维工具插件。
- 范围：`admin_only`。
- 核心能力：`db:own_tables`、`storage:read`、`storage:write`。
- 扩展点：
  - admin API
  - admin 菜单
  - standalone page
- 审计结论：
  - 当前 `validate` clean，`frontend/dist/index.js` 存在，生产态可运行。
  - 但 `plugin pack` 同样会把 `frontend/src` 一起带出。
  - 这类插件比较适合作为平台内置运维模块，不适合作为“靠前端闭源来收费”的插件样板。

#### 9.3.7 `weather-widget`

- 插件类型：前端组件 + API + AI skill 的混合型插件。
- 范围：`admin_and_selected_tenants`。
- 核心能力：`http:outbound`。
- 扩展点：
  - `skills`：`weather-realtime`
  - admin/tenant API
  - `header_widgets`
- 审计结论：
  - 这是当前正式插件里最能代表“插件系统全能力”的样例。
  - 它同时覆盖了前端组件、后端 API、外部 HTTP 调用、AI skill。
  - 当前 `validate` 有 1 条 warning：`backend/open_meteo.py` 导入了 `os`。
  - `plugin pack` 会把 `frontend/src` 和 `backend/tests/*` 一起打进 ZIP。
  - 因此它非常适合做开发演示样例，但不适合作为商业发布包模板直接外发。

### 9.4 历史/备份插件补充审计

这一节专门回答你后来追加的那个要求：

- “其他已经做完的插件，也要按照优化后的来。”

这里需要先把证据等级说清楚，否则容易误导实施方。

#### 9.4.1 证据等级分层

当前仓库里的插件资产实际上分成三层：

1. 正式源码层
   - 位于 `backend/plugins/*`
   - 当前只有 7 个正式插件

2. 备份源码层
   - 位于 `backend/plugins/.backups/*`
   - 可以做二级静态审计与 CLI validate

3. 历史运行基线 / 文档层
   - 位于 `docs/reports/m590/*`、`docs/guides/*`
   - 只能证明“曾经启用并经过验证”，不能替代当前源码审计

因此，这一节会明确区分：

- 哪些结论来自当前正式源码
- 哪些结论来自备份源码
- 哪些结论仅来自历史基线与发布文档

#### 9.4.2 历史插件汇总表

| 插件 | 当前仓库形态 | 前端形态 | 主要问题 | 整改建议 |
|---|---|---|---|---|
| `netdisk` | 仅备份源码 + 基线文档 | 同时存在 `frontend/src` 与 `frontend/dist` | 备份 manifest 仍使用旧 scope `admin_and_assigned`；与当前 canonical schema 不一致 | 先统一 scope 与 manifest 语义，再按新前端契约迁移 |
| `novus-crud-code` | 仅备份源码 + 基线文档 | 同时存在 `frontend/src` 与 `frontend/dist`，且使用 `frontend.admin.entry` | 典型旧前端模型；`menus.scope=admin_only` 已与当前 endpoint scope 语义冲突；Vue 样式写法也不符合现规范 | 必须整包迁移到新页面/菜单模型与新前端发布模型 |
| `novusdoc-pro` | 仅历史基线/文档证据，当前无正式源码根目录 | 基线显示同时声明 `frontend.admin.entry` 与 `frontend.tenant.entry` | 当前业务定位只是富文本测试/文档菜单页样例，不应主导核心架构判断；但其历史实现仍可作为旧前端/旧 license 设计的辅助样本 | 本轮必须明确处置：继续保留则本轮一并迁移；不再保留则本轮直接归档 |
| `regression-probe` | 仅备份源码 | 无前端 | 问题较少，更偏回归探针 | 继续保留为系统测试夹具，顺手升级到新 schema 即可 |
| `example-weather` | 仅备份源码 | 无前端 | 问题较少，更偏教学样例 | 用作新脚手架迁移后的样例基线 |

#### 9.4.3 `netdisk`

- 历史定位：
  - `m590_detailed_milestone_v2.md` 把它列为已启用的“页面 + API + task + skill”综合插件。
  - `plugin_status_api.json` 也保留了它的运行基线快照。
- 当前审计发现：
  - 备份源码里同时存在 `frontend/src` 与 `frontend/dist`，说明它也是双轨前端模型。
  - 但备份 manifest 仍使用 `scope: admin_and_assigned`，而当前 schema 已要求 `admin_and_selected_tenants`。
  - 这说明它不是“坏插件”，而是“完成于旧模型时期的插件”。
- 结论：
  - 不能直接拿历史备份恢复上线，然后假定它天然符合当前规范。
  - 需要先补一次 manifest/schema 迁移，再进入新方案下的前端/菜单/打包整改。

#### 9.4.4 `novus-crud-code`

- 历史定位：
  - `m590_detailed_milestone_v2.md` 把它列为已启用的低代码插件。
  - `plugin_status_api.json` 记录了它的页面、API 与运行状态。
- 当前审计发现：
  - 备份源码同时存在 `frontend/src` 与 `frontend/dist`。
  - manifest 里直接使用 `frontend.admin.entry: src/index.ts`。
  - `extensions.frontend.menus[].scope` 仍写成资源作用域语义 `admin_only`，而不是当前前端端别语义 `admin`。
  - `FormBuilder.vue` 中还存在当前规范已禁止的 `<style scoped>`。
- 结论：
  - 这是当前最典型的“旧模型前端插件”。
  - 后续如果要恢复/继续开发，必须按新的页面单一事实来源、菜单派生、release/source 分轨一起迁移，不能只修一两个字段。

#### 9.4.5 `novusdoc-pro`

- 历史定位：
  - 多份历史文档曾把它按较高优先级记录，并把它当成历史上的 license / 协作增强样例。
  - `plugin_status_api.json` 显示它有：
    - admin/tenant 双侧 API
    - 权限扩展
    - notifications
    - `frontend.admin.entry`
    - `frontend.tenant.entry`
    - `npm_dependencies`
- 当前限制：
  - 当前工作区 `backend/plugins/` 下没有 `novusdoc-pro` 正式源码根目录。
  - 因此无法像对正式插件那样继续跑同等级 validate、pack、代码细查。
- 当前业务澄清：
  - 它只是富文本测试的文档菜单页，不是当前业务上的关键插件，也不应该反向决定插件系统的总体架构优先级。
- 结论：
  - 它可以保留为“历史样例/测试插件”的参考，但不应再当成核心商业插件来驱动方案设计。
  - 也不能假装已经被完整审计，因为源码不在当前工作区。
  - 本轮必须直接定案：如果继续保留，就在本轮按新模型一起迁移；如果不再需要，就在本轮直接归档，不留后补状态。

#### 9.4.6 `regression-probe` 与 `example-weather`

- 这两个备份插件当前 validate clean。
- 它们更像：
  - 测试探针
  - 教学样例
- 结论：
  - 它们不属于商业授权链路的重点整改对象。
  - 但只要继续保留，就仍必须在本轮完成 schema、脚手架、validate/pack 契约的同步升级。
  - 升级后很适合作为“新脚手架迁移完成后的最小示例”和“回归测试夹具”。

## 10. 当前系统里做得比较好的部分

为了避免结论失衡，这里也明确指出当前系统值得保留的部分。

### 10.1 ZIP 包安全校验做得比较扎实

当前已覆盖：

- 路径穿越
- 非法绝对路径
- symlink
- 单文件大小限制
- 总解压大小限制
- 压缩比限制

这部分是插件上传/安装链路里质量较高的一块。

### 10.2 前端插槽设计整体合理

当前前端插件并没有直接侵入宿主前端源码，而是通过：

- manifest 声明
- registry 注册
- slots API 下发
- 前端动态加载

这个方向是对的，保留价值很高。

### 10.3 权限同步方式基本遵守规范

当前关键路径使用 `sync_plugin_permissions(plugin.name)`，这和 `.cursor` 规则一致，说明插件菜单与权限这一层没有走偏。

## 11. 为什么要改，为什么当前方案不合适

这一节给出最终的产品与工程层面的总结。

### 11.1 为什么要改授权系统

因为当前授权系统最核心的问题是“看起来存在，实际上不闭环”。

只要代码已经交付，License 的唯一现实价值就是“平台是否允许插件正常运行”。当前系统没有统一执行这一点，因此必须改。

### 11.2 为什么当前商业交付方式不合适

因为当前链路要求付费插件前端在运行时使用编译产物，但发布时又把源码一起交付。

这会导致：

- 付费插件前端没有真正的交付边界
- 用户对授权价值产生疑问
- 平台很难建立稳定的商业插件分发模式

### 11.3 为什么 manifest 驱动要补齐

因为插件系统的维护成本，本质上取决于“规则是否都收敛到 manifest”。

当前把 trial、前端入口等关键行为散落在 API 和运行时硬编码里，会让后续每次改动都变成多点同步，维护风险越来越高。

### 11.4 为什么当前“沙箱”说法不合适

因为它会制造错误安全预期。

当前系统更准确的定位应该是：

- 插件能力约束层
- 插件访问代理层

而不是：

- 真正的进程级隔离沙箱

### 11.5 为什么 `user` 端支持必须补齐或删除

因为“schema 允许，但运行时不支持”是最坏的一种中间态。

它既不像“不支持”那样明确，也不像“支持”那样可用，只会让后续开发和文档同时失真。

### 11.6 为什么脚手架和历史插件必须一起迁移

因为真正会决定系统未来形态的，不只是当前 7 个正式插件，还包括：

- 新插件从什么模板生成
- 老插件恢复时按什么契约迁移
- `.cursor` 和开发文档在教别人什么

如果只修正式插件，不修脚手架和历史插件，系统会长期并存两到三套插件模型，后续维护成本会持续上升。

### 11.7 为什么能力授权必须和 manifest 声明彻底分开

因为 `capabilities` 一旦既表示“插件声明”又表示“平台已授予”，就不再存在真正的审批边界。

这会让能力控制从“授权机制”退化成“插件作者说了算的声明机制”。

### 11.8 为什么静态资源分发也必须纳入授权边界

因为对前端插件来说，真正交付给浏览器执行的就是静态资源。

如果 API、菜单、slots 都做了限制，但 `frontend/dist/*` 仍然可被未授权方直接请求，那么交付边界依然是不完整的。

### 11.9 为什么升级边界必须显式，而不能由启动热同步代替

因为“目录里文件变了”不应该和“插件已经正式升级”画等号。

只要系统已经存在版本记录、升级流程、回滚流程，就必须坚持：

- 发现是发现
- 同步是同步
- 升级是升级

这三件事不能混成一件事。

## 12. 统一整改方案（全部问题同批纳入）

### 12.0 本轮整改原则

这次整改不设“后补项”“下一期再说项”或“可选项”。

原因很简单：

- 这是全新的插件系统
- 当前还没有历史包袱必须兼容旧线上行为
- 现在不一次性把边界立住，后面只会更难改

因此，本方案的执行原则是：

1. 第 4 章列出的全部问题项，全部纳入同一轮整改范围
2. `P0 / P1 / P2 / P3` 只表示实施顺序和联调顺序，不表示可以延期出范围
3. 系统验收以“全部问题关闭 + 测试补齐 + 文档同步完成”为准，不接受留下尾项

为避免理解偏差，这里明确一下：

- 第 4 章列出的全部问题项，包括本次复审新增的 `P1-14` ~ `P1-17`，全部属于本轮
- 正式插件、历史插件、脚手架、`.cursor` 规则同步都属于本轮
- 保留的历史样例插件也必须在本轮明确“迁移”或“归档”，不能悬空

### 12.1 P0：先做闭环骨架，但仍属于本轮统一交付

1. 增加统一授权闸门，接入启用、启动恢复、API 分发、Webhook 分发。
2. 重新建模 License 类型，不再使用 `perpetual + expires_at` 混合语义。

### 12.2 P1：继续修发布与运行边界，但仍属于本轮统一交付

1. 后台安装/启用流程对前端编译产物做 fail-close 校验。
2. `plugin pack` 增加 release 模式，禁止把 `frontend/src` 一起发给商业交付包。
3. 试用逻辑完全由 manifest 驱动。
4. 授权状态查询改成“最优有效记录优先”。
5. 拆分 dev / prod 前端运行契约，不再共用同一个 `/plugin-assets/{plugin}/index.js` 语义。
6. 升级 `plugin create / validate / pack`，不再继续生成和默认接受旧前端模型。
7. `granted_capabilities` 禁止被启动同步或磁盘 manifest 热同步自动覆盖。
8. `/plugin-assets` 改成受 scope / tenant assignment / license 约束的分发模型。
9. 版本变化必须走正式 upgrade 流程，禁止 discover 阶段做 silent upgrade。
10. 收敛插件依赖模型，只保留一套插件间依赖语义，并贯通 install/enable/disable/uninstall/query。
11. 为 Python 依赖建立跨宿主/跨插件冲突预检，禁止无解依赖直接装进共享环境。
12. 依赖状态、预览和管理 API 改成真实依赖模型，去掉失效的 npm 运行期语义。
13. 启动恢复不再自动 `pip install`，Python 依赖补装只允许 install/upgrade/repair。

### 12.3 P2：最后收语义、模型与文档一致性，但仍属于本轮统一交付

1. 清理 manifest 死字段，尤其是 `frontend.*.entry`。
2. 调整“沙箱”命名与文档描述。
3. 补齐开发模式与生产模式的运行矩阵文档。
4. 重写插件菜单注册与页面声明模型，避免双源配置。
5. 把 `.cursor` 规则、技能、参考文档同步到新模型。
6. 明确 `user` 端插件策略：要么补齐端到端支持，要么从 schema、registry、文档里移除。
7. 建立历史/备份插件迁移清单，避免恢复旧插件时把旧模型重新带回主线。
8. 企业分配接口补齐 scope 校验，决定是否保留 `is_active` 四态模型。
9. 收紧 admin / tenant / public API route 的端别匹配语义。

### 12.4 前端运行模型改造方案（重点补充）

这一节专门回答你提的这个点：

- 为什么现在 dev / 生产都“看起来在用 dist”不合理。
- 应该怎么改，才能既保留开发效率，又让生产发布边界清楚。

先给结论：

- 生产环境继续使用编译产物是合理的。
- 应该改掉的是“dev 也伪装成产物 URL”这件事。
- 更合理的目标模型是“源码开发链路”和“发布产物链路”彻底分轨。

#### 12.4.1 目标模型

建议把插件前端模型明确拆成两套契约。

第一套：开发契约（source contract）

- 仅在 `DEBUG/dev` 模式有效。
- 宿主前端直接加载插件源码入口，而不是伪装成 `plugin-assets/index.js`。
- 入口应该来自 manifest 的 dev 字段，或者明确约定为 `frontend/src/index.ts`。
- 这条链路负责：
  - 本地开发
  - HMR
  - 调试源码
  - 联调插件 API

第二套：发布契约（release contract）

- 仅在生产 / 正式测试环境有效。
- 宿主只读取 `frontend/dist` 下的发布产物。
- 不再假定只有一个固定的 `index.js`，而是读取一个发布 manifest，例如：
  - `frontend/dist/plugin.manifest.json`
- manifest 中记录：
  - JS 入口文件
  - CSS 文件列表
  - 其他静态资源
  - 插件版本与构建时间
  - 可选 integrity/hash

这样改完以后：

- dev 明确是源码协议
- prod 明确是发布产物协议
- 两者不再共用一个名字相同、语义不同的 URL

#### 12.4.2 建议的 manifest / 发布物结构

建议新增或重构为如下概念：

1. `plugin.yaml`
   - 负责声明插件能力、扩展点、商业属性、作用域。
   - 不再假装自己直接承载“生产静态资源路径”。

2. `frontend/dev` 约定
   - 例如：
   - `frontend.dev.entry: src/index.ts`
   - 或者继续默认约定 `frontend/src/index.ts`

3. `frontend/dist/plugin.manifest.json`
   - 由 `plugin build` 生成。
   - 例如包含：

```json
{
  "format": "umd",
  "entry": "assets/index.abcd1234.js",
  "css": ["assets/style.efgh5678.css"],
  "assets": [],
  "version": "1.0.0"
}
```

这比现在固定写死 `dist/index.js` 更合理，因为：

- 支持 hashed 文件名
- 支持拆分 CSS
- 支持 code splitting
- 宿主不需要猜测真实构建输出

#### 12.4.3 宿主加载器应该怎么改

需要一起改的核心点如下。

1. 开发态加载器
   - `plugin-loader.ts` 在 dev 下不再请求 `/plugin-assets/{plugin}/index.js`
   - 改为请求一个明确的 dev 入口，例如：
   - `/__plugin_dev__/{plugin}/entry`
   - 或者由 Vite 插件注入虚拟模块 ID

2. 生产态加载器
   - 先请求 `/plugin-assets/{plugin}/plugin.manifest.json`
   - 再按 manifest 中的 entry / css 列表加载资源
   - 不再假设入口永远叫 `index.js`

3. CSS 处理
   - CSS 文件也从发布 manifest 中取
   - 不要再让生产态样式依赖散落在 `styles` 或手工推导逻辑里

4. 全局导出约定
   - 如果继续用 UMD，则仍可保留 `window.NovusPlugin_xxx`
   - 但这个约定应写进发布 manifest 或构建规则，而不是由宿主隐式猜测

#### 12.4.4 打包与安装策略应该怎么改

这部分要和商业交付一起改，否则前端链路改了也没有意义。

建议改成三条命令语义：

1. `plugin build`
   - 专门负责生成 `frontend/dist` 和 `plugin.manifest.json`
   - 这是构建命令，不是发布命令

2. `plugin pack --release`
   - 默认发布模式
   - 只打包运行所需文件：
     - `plugin.yaml`
     - `backend/`
     - `locales/`
     - `icon.*`
     - `frontend/dist/`
     - 必要迁移文件
   - 默认排除：
     - `frontend/src/`
     - `frontend/vite.config.ts`
     - 前后端测试文件
     - 锁文件
     - 构建脚本

3. `plugin pack --source`
   - 仅用于内部开发交换或源码交付
   - 明确告诉使用者：这是源码包，不是正式发布包

同时，后台安装与启用也要跟着改：

1. 生产环境安装前端插件时
   - 必须检测 `frontend/dist/plugin.manifest.json`
   - 缺失则拒绝安装或拒绝启用

2. 开发环境本地插件
   - 可以允许 source-only 形式
   - 但只能在 `DEBUG/dev` 下启用源码链路

3. 启动恢复
   - 不应再为前端插件补装 npm 依赖
   - 前端 npm 依赖只属于开发/构建阶段，不属于生产恢复阶段

#### 12.4.5 需要修改的代码入口

这项改造不是只改一个文件，而是至少涉及这些入口：

- `frontend/apps/web-antd/src/utils/plugin-loader.ts`
- `frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts`
- `backend/scripts/plugin_cli.py`
- `backend/app/main.py`
- `backend/app/plugins/asset_resolver.py`
- `backend/app/plugins/lifecycle.py`
- `backend/app/plugins/startup.py`
- `backend/app/plugins/manifest.py`

职责分工建议如下：

1. 前端
   - 负责 dev loader、release loader、manifest 驱动资源加载

2. CLI
   - 负责 `build`、`pack --release`、`pack --source`

3. 后端
   - 负责 release 资产分发、安装/启用 fail-close、启动恢复边界收敛

4. manifest/schema
   - 负责把 dev 与 release 的前端契约显式建模

#### 12.4.6 同批实施顺序建议

这里的“三段”只是同一轮整改中的实施顺序，不是三期发布，不代表任何一段可以延期到后续版本。

第一段：先把语义拆开，但仍属于本轮交付

1. 保留生产态 `/plugin-assets/{plugin}/...`
2. 新增 dev 专用入口，例如 `/__plugin_dev__/{plugin}/entry`
3. `plugin-loader.ts` 在 dev / prod 下走不同 URL
4. `plugin pack` 默认排除 `frontend/src` 与测试文件

这一段的目标是先把“语义混乱”止住，为后续同轮改造清掉歧义。

第二段：引入 release manifest，仍属于本轮交付

1. `plugin build` 生成 `frontend/dist/plugin.manifest.json`
2. 生产态加载器改为“先拉 manifest，再加载 JS/CSS”
3. 后台安装/启用改为检查 release manifest，而不是仅检查 `dist/index.js`

这一段的目标是把固定 `index.js` 契约升级成真正可演进的发布契约。

第三段：把构建期和运行期彻底切开，仍属于本轮交付

1. 启动恢复不再补 npm 依赖
2. 前端插件 npm 依赖只在开发/构建流程处理
3. release 包与 source 包彻底分离

这一段完成后，系统才算真正建立了：

- 开发态源码模型
- 生产态发布产物模型
- 商业交付包模型

也就是说，上面三段不是“可分批慢慢做”，而是“同一轮整改里按顺序完成的三组动作”。

#### 12.4.7 为什么这个方案更合理

因为它同时解决了当前四个核心问题：

1. 解决 dev / prod 共用假同一契约的问题
2. 解决固定 `dist/index.js` 不利于演进的问题
3. 解决 `plugin pack` 混装源码与产物的问题
4. 解决生产恢复还依赖前端 npm 环境的问题

如果不做这一步，插件前端系统会长期处在一种很尴尬的状态：

- 开发态看起来像源码系统
- 生产态看起来像产物系统
- 打包态却把两者混成一个交付物

这正是你觉得“不太合理”的根源。

### 12.5 菜单注册与菜单选择改造方案

这部分单独列出来，因为它不是“前端样式问题”，而是模型和交互一起有问题。

#### 12.5.1 目标

菜单系统要达到三个目标：

1. 页面声明只有一个事实来源。
2. 菜单挂载调整只影响导航层，不影响整套插件运行期扩展。
3. 管理员在配置菜单时能看到明确结果，而不是盲选 parent code。

#### 12.5.2 建议的新模型

建议把当前：

- `menus`
- `standalone_pages`

两套并行声明收敛成“页面为主、菜单为辅”的模型。

例如：

1. `pages`
   - 声明 path、component、title、scope、ai metadata

2. `menu_entries`
   - 只声明哪些 page 需要显示为菜单入口
   - 声明 icon、sort_order、default_parent、hidden

这样一来：

- route 从 `pages` 派生
- menu 从 `menu_entries -> page` 派生
- 不再重复维护 path 和 component

#### 12.5.3 菜单位置配置应该怎么改

建议把当前“每行一个 TreeSelect”升级为三段式配置：

1. 插件页面列表
   - 显示页面名、端别、默认挂载位置、当前覆盖位置

2. 父级选择
   - 显示完整目录链，而不是只显示 short code

3. 结果预览
   - 立即展示：
     - 管理端会出现在哪
     - 企业端会出现在哪
     - 最终菜单路径是什么

同时增加三个操作：

1. 恢复 manifest 默认值
2. 仅改管理端
3. 仅改企业端
4. 若系统继续支持 `user` 端插件，则同样提供 `user` 菜单树；若不支持，管理端配置页不得再暴露 `user` 相关选项

#### 12.5.4 后端执行链路应该怎么改

当前 `menu-config` 不应再：

- `unregister_all()`
- `register_all_extensions()`

应改为：

1. 更新 `plugin.config.menu_overrides`
2. 重建该插件的菜单 PermissionMeta
3. 执行 `sync_plugin_permissions(plugin.name)`
4. 刷新前端 routes / menu cache

也就是说，菜单挂载调整应该是“导航层重算”，不是“插件功能层重建”。

### 12.6 功能/扩展注册改造方案

这里对应你说的“功能上的注册我感觉也不是很好用”。

我认为要补两个方向。

#### 12.6.1 运行时按域拆分注册

不要再把所有扩展都塞进一个大函数做统一批处理。

建议至少拆成这些域：

1. `navigation`
   - menus
   - pages
   - frontend slots

2. `runtime_api`
   - api routes
   - webhooks
   - middleware
   - socketio

3. `background`
   - tasks
   - consumers
   - notifications

4. `ai`
   - skills
   - adapters
   - ai feature bindings

这样以后才能支持：

- 只重建导航
- 只修复 skills
- 只重建周期任务
- 只刷新前端 slots

#### 12.6.2 管理端增加“扩展注册状态”视图

建议在插件详情里增加一个扩展状态视图，而不是只有 enabled / disabled / error 三种粗状态。

至少展示：

1. 哪些扩展类型已声明
2. 哪些扩展类型已成功注册
3. 哪些扩展类型失败
4. 失败原因
5. 是否允许局部重试

这样管理员才能区分：

- 是菜单注册失败
- 是 route 组件没导出
- 是 skill resolver 没加载上
- 是 webhook handler 路径写错

#### 12.6.3 历史插件迁移基线

这一项必须补上，因为当前工作区里已经同时存在：

- 正式插件
- 备份源码插件
- 文档里仍被视为核心能力、但源码不在工作区的历史插件

建议把迁移对象明确分成四组处理：

1. 正式插件
   - `aliyun-oss`
   - `amazon-s3`
   - `novusdoc`
   - `qiniu-kodo`
   - `storage-migration`
   - `tencent-cos`
   - `weather-widget`

2. 历史综合业务插件
   - `netdisk`
   - `novus-crud-code`

3. 历史富文本/测试样例插件
   - `novusdoc-pro`

4. 样例/测试插件
   - `example-weather`
   - `regression-probe`

每组的整改要求应不同：

1. 正式插件
   - 先做新运行契约与新打包契约落地

2. 历史综合业务插件
   - 先做 manifest/schema 迁移
   - 再做菜单/页面模型迁移
   - 最后做 release/source 分轨

3. 历史富文本/测试样例插件
   - 若仍保留：找回源码后按新前端契约在本轮一并迁移
   - 若不再保留：在本轮直接归档，不留悬空状态

4. 样例/测试插件
   - 若继续保留，必须在本轮跟随新脚手架一起升级
   - 升级后作为回归样例与 validate/pack 基线

### 12.7 `.cursor` 规则与技能文档同步计划

这部分你提得对，必须写进方案末尾。

如果后面把实现改了，但 `.cursor` 里的描述不更新，那么：

- 新同事会继续按旧模型开发插件
- AI / Codex 类工具会继续给出过时建议
- 文档和代码会再次分叉

建议在整改收尾时同步更新这些文件：

1. [plugin-system.md](/E:/git_clone/novusai-saas-yudi/.cursor/rules/plugin-system.md)
   - 补充 License gate 闭环要求
   - 补充 dev / release 分轨要求
   - 补充 `plugin build`、`pack --release`、`pack --source`
   - 删除或修正对 `frontend.*.entry` 的过时隐含预期

2. [plugin-development/SKILL.md](/E:/git_clone/novusai-saas-yudi/.cursor/skills/plugin-development/SKILL.md)
   - 更新插件前端开发契约
   - 更新菜单/页面单一事实来源规范
   - 更新插件打包命令与商业交付规则

3. [plugin-spec.md](/E:/git_clone/novusai-saas-yudi/.cursor/skills/novusai-saas/references/plugin-spec.md)
   - 重写 frontend dev/release 结构
   - 引入 release manifest
   - 删除“固定 `dist/index.js` 就是唯一正式契约”的旧表述
   - 明确区分页面声明、菜单入口声明、前端 slots

4. [plugin-menu-registration.md](/E:/git_clone/novusai-saas-yudi/.cursor/skills/novusai-saas/references/plugin-menu-registration.md)
   - 改成新菜单模型
   - 明确菜单调整只影响导航层
   - 补充管理端交互与预览规范

5. [menu-i18n.md](/E:/git_clone/novusai-saas-yudi/.cursor/rules/menu-i18n.md)
   - 如果菜单模型变化，要同步说明插件菜单标题与页面标题分别由谁提供

6. [plugin-system-comprehensive-audit-20260322.md](/E:/git_clone/novusai-saas-yudi/docs/audit/plugin-system-comprehensive-audit-20260322.md) 对应的 `.cursor` 描述同步要求
   - 明确正式插件、历史插件、样例插件的迁移分层
   - 明确 `user` 端插件当前是否支持
   - 明确脚手架必须生成的新前端契约
   - 明确历史样例插件（如 `novusdoc-pro`）是否继续保留，若保留则本轮一并迁移

建议把这件事作为整改任务的最后一个验收项：

1. 代码实现完成
2. 测试补齐
3. 示例插件迁移
4. `.cursor` 规则与技能文档同步完成
5. 不再保留的历史样例插件已明确归档

### 12.8 插件依赖治理改造方案（本次复审补充）

这一节专门补上这次复审新发现的“依赖问题”。

先给结论：

- 前面的总审计有部分覆盖依赖问题，但只覆盖到了“前端 npm 依赖不该在生产恢复时安装”这一层。
- 这次把插件依赖模型单独拉出来复核后，可以确认：当前依赖治理还没有收口，必须并入同一份总方案。

#### 12.8.1 本次复审结论

当前依赖体系主要有四个结构性问题：

1. Python 依赖直接装进宿主共享环境，但没有跨插件冲突求解。
2. 插件间依赖被拆成 `dependencies.plugins` 和 `compatibility.requires` 两套语义。
3. 依赖状态/预览/API 没有按真实依赖模型返回，`npm` 与 `system` 语义漂移。
4. 启动恢复仍在自动补装 Python 依赖，安装期与运行期边界没切干净。

这四项不是“以后有插件依赖时再说”的问题，而是新系统现在就应该立住的边界。

#### 12.8.2 现有正式插件依赖审计结果

对当前正式插件的 manifest 复核如下：

1. `aliyun-oss`
   - Python 依赖：`alibabacloud-oss-v2`、`anyio`
2. `amazon-s3`
   - Python 依赖：`boto3`、`anyio`
3. `qiniu-kodo`
   - Python 依赖：`qiniu`、`httpx`、`anyio`
4. `tencent-cos`
   - Python 依赖：`cos-python-sdk-v5`、`anyio`
5. `weather-widget`
   - Python 依赖：`httpx`
6. `storage-migration`
   - 当前无显式运行时依赖
7. `novusdoc`
   - 审计时未显式声明 `dependencies`，等价于空依赖
   - 本轮已补成显式空依赖，避免继续保留隐式模型

另外两个重要结论：

1. 当前正式插件里，没有任何一个真正使用：
   - `dependencies.system`
   - `compatibility.requires`
   - 插件到插件的版本依赖
2. 这说明当前问题主要是“模型不成立”，而不是“现有样例已经大量坏掉”。

也正因为现在还没有大量依赖型插件，才更应该在这一轮把规则立住。

#### 12.8.3 建议采用的目标模型

后端插件既然运行在同一个 Python 进程里，就不要继续假装存在“每个插件都能独立带自己那套 Python 版本”的隐式幻想。

更合理的目标模型是：

1. Python 依赖
   - 明确属于“共享宿主环境模式”
   - 只能在 install / upgrade / repair 阶段处理
   - 安装前必须做冲突预检
   - 启动阶段只校验，不改环境
2. 插件间依赖
   - 只保留一套声明
   - 同时支持“依赖哪个插件”和“要求什么版本”
   - disable / uninstall / query / preview 全部认同一套结果
3. system 依赖
   - 只用于前置条件校验
   - 例如二进制、环境变量、宿主能力
   - 不应该伪装成“系统会帮你自动装”
4. 前端依赖
   - 当前版本不再属于运行期 manifest 依赖模型
   - dev/build 依赖留在插件前端工作区
   - release 依赖由 `frontend/dist/plugin.manifest.json` 负责发布产物声明

#### 12.8.4 同批改造动作

这一部分也属于本轮统一整改，不是后补项。

1. manifest/schema
   - 把插件间依赖统一收敛为单一字段
   - 不再让 `dependencies.plugins` 与 `compatibility.requires` 双轨并存
   - `dependencies.system` 从正式 schema 移除
2. install preview
   - 必须真正检查：
     - Python 冲突
     - 缺失插件依赖
     - 插件版本不匹配
3. lifecycle
   - install / upgrade / repair：允许处理 Python 依赖
   - enable：必须先做共享环境预检，再按需补装未满足的 Python 依赖，不允许跳过冲突检查
   - disable / uninstall：必须按同一份依赖图阻断被依赖插件
4. startup restore
   - 只恢复扩展和做依赖校验
   - 不再自动 `pip install`
   - 缺依赖时标记 `error / repair_required`
5. admin API / 前端管理页
   - `dependency_status` 返回真实 `python/plugins`
   - 删除失效的 `npm` 安装/卸载动作语义
   - `get_dependencies / get_dependents` 返回规范化依赖对象，而不是只有名称列表
6. 正式插件与模板
   - 正式插件 manifest 统一补成显式依赖块
   - `novusdoc` 这类当前依赖为空的插件，也要按新规范补齐空结构
   - 脚手架默认生成新依赖模型，不能继续生成旧字段

#### 12.8.5 需要修改的代码入口

这部分至少会涉及：

- `backend/app/plugins/manifest.py`
- `backend/app/plugins/lifecycle.py`
- `backend/app/plugins/startup.py`
- `backend/app/plugins/preview.py`
- `backend/app/services/system/plugin_service.py`
- `backend/app/api/admin/plugins.py`
- `frontend/apps/web-antd/src/api/admin/plugin.ts`
- `frontend/apps/web-antd/src/views/admin/plugins/index.vue`
- `backend/scripts/plugin_cli.py`
- `.cursor/rules/plugin-system.md`
- `.cursor/skills/novusai-saas/references/plugin-spec.md`

#### 12.8.6 验收要求

依赖治理这一块要算“做完”，至少要同时满足：

1. 能阻止无解的 Python 依赖冲突进入共享环境。
2. versioned plugin dependency 会影响 install / enable / disable / uninstall / query 全链路。
3. 管理端展示的依赖状态与真实运行规则一致。
4. 启动恢复不再自动补装 Python 依赖。
5. 正式插件和脚手架已经迁到新依赖声明模型。

本轮实施已按上述验收要求完成，实际落地情况见第 `14.8` 节。

## 13. 最终结论

本章保留的是审计时点的原始结论。若与第 `14` 章“实施回写”冲突，以第 `14` 章为准。

插件系统目前不是不能用，而是“核心骨架可用，但商业化与授权闭环不成立，而且正式插件、历史插件、脚手架模型并存”。

如果目标只是内部研发、自用平台、完全受控环境，那么当前架构仍然有较高可维护性。

但如果目标是：

- 做市场插件
- 做付费插件
- 做自托管商业交付
- 让试用与期限授权真正具备产品意义

那么当前实现有几处必须先改：

1. 授权闭环
2. License 模型
3. 前端发布链路
4. manifest 驱动一致性
5. capability 授权边界
6. 静态资源分发边界
7. 升级/版本治理边界
8. `user` 端支持策略
9. 历史插件与脚手架迁移
10. 依赖治理边界

否则系统会长期停留在一种“看起来有收费能力、实际上没有稳定收费边界，而且新旧插件契约会不断混用”的状态。这正是当前最不合适的地方。

## 14. 实施回写（2026-03-22）

本章用于回写本次按本报告实际落地的整改结果，避免文档继续停留在“仅审计、未实现”的失真状态。

### 14.1 已落地的骨干整改

1. License 语义已收敛为三态：
   - `trial`
   - `fixed_term`
   - `perpetual`
2. 已建立统一 runtime gate，并接入：
   - 插件启用
   - 启动恢复
   - API 分发
   - webhook 分发
   - `/plugin-assets`
   - 管理端/企业端 slots 可见性
3. `/plugin-assets` 与管理态图标通道已拆分：
   - `/plugin-assets` 只承载运行时 release 资产；`plugin.manifest.json`、JS、CSS、运行时图片继续统一受 token + enabled + scope + tenant assignment + license 约束
   - 管理态图片图标改走 `/plugin-icons/{plugin}/{file}`，仅管理端可访问，不再被 `enabled` / license 运行闸门误封
   - 宿主前端已取消 `query access_token` 模式，改为 `Authorization` + 同源插件资产 Cookie；受控资产响应缓存已改为 `private`，不再返回 `public`
4. `discover` / `sync-manifest` / `upgrade` 已显式分界：
   - `discover` 只做发现和漂移标记
   - `discover` 还会清理已消失的历史漂移/旧 scope 遗留 error 状态
   - `sync-manifest` 只同步同版本 manifest 漂移
   - 版本变化必须走正式 `upgrade`
   - 启动恢复不再处理前端 npm 依赖

### 14.2 前端运行模型已改成 source / release 分轨

1. 开发态：
   - 宿主前端不再用 `/plugin-assets/{plugin}/index.js`
   - 改为 `/__plugin_dev__/{plugin}/entry`
2. 生产态：
   - 宿主先读取 `/plugin-assets/{plugin}/plugin.manifest.json`
   - 再按 manifest 的 `entry` / `css` 加载发布产物
3. `frontend/dist/plugin.manifest.json` 已成为正式契约。
4. `plugin-loader.ts` 与 `vite-plugin-novus-plugins.ts` 已同步切换到新模型。

### 14.3 菜单 / 页面模型已收敛

1. 新模型以 `extensions.frontend.pages[*]` 为单一事实来源。
2. `pages[*].menu` 用于声明该页面是否派生为菜单入口。
3. `menu-config` 更新已改为只重建导航域，不再触发整套扩展重注册。
4. 当前版本已明确移除 `user` 端插件支持，统一只保留 `admin` / `tenant`。

### 14.4 CLI 与脚手架已切换到新契约

已实现并回归：

- `novusai plugin build`
- `novusai plugin validate`
- `novusai plugin pack --release`
- `novusai plugin pack --source`
- `novusai plugin create --template=full-module`

当前行为：

1. `build`
   - 构建前端产物后生成/刷新 `frontend/dist/plugin.manifest.json`
2. `validate`
   - 校验新 manifest schema
   - 校验 `frontend.dev.entry`
   - 校验 release manifest
   - 明确拒绝旧字段：
     - `frontend.menus`
     - `frontend.standalone_pages`
     - `frontend.admin.entry`
     - `frontend.tenant.entry`
     - `frontend.npm_dependencies`
3. `pack --release`
   - 默认排除 `frontend/src`
   - 排除前端测试文件
   - 排除 `frontend/package.json` / `vite.config.*` / lockfile
   - 排除 `backend/tests`
4. `pack --source`
   - 保留源码链路，供开发/迁移使用

### 14.5 正式插件与历史对象的本轮处置

正式插件：

- `aliyun-oss`：已纳入新 CLI validate / release pack 验证
- `amazon-s3`：已纳入新 CLI validate / release pack 验证
- `novusdoc`：已迁移到 `pages + dev + release.manifest`
- `qiniu-kodo`：已纳入新 CLI validate / release pack 验证
- `storage-migration`：已迁移到 `pages + dev + release.manifest`
- `tencent-cos`：已纳入新 CLI validate / release pack 验证
- `weather-widget`：已迁移到 `pages + dev + release.manifest`

历史/备份插件：

- `netdisk`：已迁到当前 schema
  - scope 改为 `admin_and_selected_tenants`
  - 前端改为 `pages + dev + release.manifest`
- `novus-crud-code`：已迁到当前 schema
  - 移除 `menus / standalone_pages / npm_dependencies / admin.entry`
  - 改为 `pages + dev + release.manifest`
  - 修复 `<style scoped>` validate 阻塞
- `regression-probe`：已纳入 validate 基线
- `example-weather`：已纳入 validate 基线

历史样例：

- `novusdoc-pro`：当前仓库无正式源码根目录，本轮按“已归档样例”处理，不再作为现行插件架构依据

### 14.6 本轮已执行验证

后端自动化（定向新增 / 受影响用例）：

```bash
backend/.venv/Scripts/python -m pytest \
  backend/tests/test_plugin_manifest_validation.py \
  backend/tests/test_plugin_startup_restore_modes.py \
  backend/tests/test_plugin_dependency_runtime_model.py \
  backend/tests/test_plugin_cli_release_workflow.py \
  backend/tests/test_plugin_historical_validate_baseline.py -q
```

结果：`29 passed`

后端自动化（更大范围插件回归）：

```bash
backend/.venv/Scripts/python -m pytest \
  backend/tests/test_plugin_*.py \
  backend/tests/plugins/test_plugin_menu_canonical_scope.py -q
```

结果：`114 passed`

前端自动化：

```bash
pnpm --dir frontend/apps/web-antd exec vitest run \
  src/utils/__tests__/plugin-asset.test.ts \
  src/utils/__tests__/plugin-loader.test.ts
```

结果：`7 passed`

前端类型检查尝试：

```bash
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend/apps/web-antd typecheck
```

结果：

- `pretypecheck` 已成功执行 `icons:generate`
- 已生成 / 刷新：
  - `frontend/packages/icons/src/iconify/lucide-subset.generated.ts`
  - `frontend/packages/icons/src/iconify/lucide-catalog.generated.ts`
- `vue-tsc --noEmit --skipLibCheck` 已通过

正式插件实跑：

1. 7 个正式插件已实跑 `plugin validate`
   - 全部返回 `exit=0`
2. 7 个正式插件已实跑 `plugin pack --release`
   - 全部成功产出 ZIP
3. 同 7 个正式插件已实跑 `plugin pack --source`
   - 全部成功产出 ZIP
4. `novusdoc` 已额外执行 `plugin build`
   - 已生成 / 刷新 `frontend/dist/plugin.manifest.json`
5. 历史对象 `netdisk / novus-crud-code / regression-probe / example-weather`
   - 已纳入 validate 基线并通过

### 14.7 对本报告若干旧结论的校正

以下旧结论在本轮实施后已不再成立，应以第 14 章为准：

1. “`/plugin-assets` 只校验 enabled、不校验 license / scope / tenant assignment”
   - 已修正
2. “dev 和 prod 共用 `/plugin-assets/{plugin}/index.js`”
   - 已修正
3. “菜单与页面双源配置并存”
   - 已修正
4. “`plugin pack` 默认会把 `frontend/src` 一起打进商业交付包”
   - 已修正
5. “系统表面支持 `user` 端插件”
   - 已修正为当前版本不支持

本报告第 4 章与第 12 章仍保留作为问题依据与设计依据；当前代码现实以后续实现和本章回写为准。

### 14.8 复审补充：依赖治理已完成收口

本次对依赖模型的单独复审，不再只停留在“前端 npm 依赖不该进入生产恢复期”的局部修补，而是已经按第 `12.8` 节方案完成了整块收口。

1. manifest / schema 已收敛
   - `dependencies.plugins` 已成为唯一正式插件间依赖字段
   - `compatibility.requires` 已从 manifest schema 移除，并在 validate 阶段直接拒绝
   - `dependencies.system` 已从统一 runtime model 移除
   - `DependenciesSchema` / `CompatibilitySchema` 已设置 `extra="forbid"`
   - 运行时只对历史数据库里的旧 `manifest` 投影保留只读兼容读取，用于迁移和回放，不再允许新源码继续写旧字段
2. 共享宿主环境边界已落实
   - 新增 Python requirement 预检与 direct requirement 冲突检测，阻止无解依赖静默进入宿主共享 venv
   - `install / upgrade / repair / dependencies/install` 可处理 Python 依赖
   - `enable` 会在预检通过后按需补装缺失的 Python 依赖，不再跳过冲突检查
   - `startup restore` 只做 Python/插件依赖校验与恢复注册，不再自动 `pip install`
3. 生命周期与查询链路已统一
   - versioned plugin dependency 已贯通 install / enable / disable / uninstall / query
   - `disable` 只阻断仍处于 enabled 的依赖方
   - `uninstall` 阻断所有仍已安装的依赖方
   - `get_dependencies / get_dependents` 已返回结构化依赖对象，不再只是名称列表
4. 预览、管理 API 与前端管理页已切到真实模型
   - install preview 现在真实返回 `python + plugins`
   - `dependency_status` 已按真实运行规则返回 `python + plugins`
   - 运行期 `npm` 安装/卸载语义已从 API、管理端请求体和进度展示中移除
5. 正式插件、历史插件与脚手架已同步
   - `novusdoc` 已补成显式空依赖
   - `netdisk` 与 `novus-crud-code` 的历史 manifest 已迁到当前依赖 schema，用作 validate 基线
   - `plugin create` 默认生成 `dependencies.plugins: []`
   - `plugin build` 已兼容 Windows 下 `pnpm.cmd / yarn.cmd / npm.cmd`
   - `plugin validate` 已接受插件 locale 的嵌套 `plugin.{name}` 结构
6. 依赖治理验收结果
   - 无解的 Python 冲突会在进入共享环境前被阻止
   - versioned dependency 已影响 install / enable / disable / uninstall / query 全链路
   - 管理端展示的依赖状态已与真实运行规则一致
   - 启动恢复已停止自动补装 Python 依赖
   - 正式插件、历史插件和脚手架都已按新依赖模型处理
7. 同日补修
   - 修复了 `plugin_dependency_is_version_satisfied()` 中的不可达代码问题
   - 现在 `*` 和 `>=...` 等满足条件的版本约束会正确返回 `True`
   - 已补充“已安装 + 已启用 + 版本满足 => ready”的正向回归测试，避免再次出现“测试全绿但 happy path 已坏”的漏检

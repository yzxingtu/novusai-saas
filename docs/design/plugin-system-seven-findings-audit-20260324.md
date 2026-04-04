# 插件系统七项核心问题审计（2026-03-24）

> 说明：本文件保留 2026-03-24 的历史发现基线；2026-04-04 的修复现状、注入能力矩阵与最新 fail-close 约束已同步到
> [plugin-system-comprehensive-audit-20260324.md](/E:/git_clone/novusai-saas-yudi/docs/design/plugin-system-comprehensive-audit-20260324.md)。

## 结论摘要

当前插件系统的问题不是单点实现瑕疵，而是宿主运行时、权限同步、前端动态路由、国际化契约、脚手架/校验链路之间缺少单一事实源，导致插件作者即使按现有规范开发，仍然容易遇到以下高频问题：

1. 菜单显示但页面进不去
2. 菜单标题未翻译或翻译不稳定
3. 插件页面内容大量缺少多语言
4. tenant 端菜单和页面可见性不一致
5. 重启后插件权限/菜单退化
6. 菜单挂载与父级配置行为异常
7. 脚手架与文档会持续放大上述问题

## Finding 1：插件菜单路由与真实页面路由同路径双注册

- 严重度：`P1`
- 现象：
  - 菜单可见，但点击后命中占位路由，不渲染插件页面。
  - 路由守卫只修复 `FallbackNotFound`，无法修复“已命中错误占位路由”的场景。
- 证据：
  - 菜单转换阶段会把插件菜单路由转成无组件占位路由，见 [menu-transformer.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/menu-transformer.ts#L239)
  - 插件真实页面路由又在动态初始化阶段以相同路径再次注册，见 [use-plugin-frontend-init.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-plugin-frontend-init.ts#L141)
  - 守卫只在目标路由是 `FallbackNotFound` 时尝试补注册，见 [guard.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts#L302)
- 判断：
  - 这是宿主路由设计缺陷，不是某个插件页面写错。

## Finding 2：tenant 端菜单、插件可见性、路由准入是三套规则

- 严重度：`P1`
- 现象：
  - tenant 侧可能出现“菜单显示但点不开”“插件 API/slots 可见但菜单不出现”“菜单和页面授权不一致”。
- 证据：
  - tenant 菜单树来自套餐/角色有效权限，见 [permission_service.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/services/permission_service.py#L973)
  - tenant 插件 slots 来自 runtime gate 可见性过滤，见 [plugin_service.py](/E:/git_clone/novusai-saas-yudi/backend/app/services/system/plugin_service.py#L481) 和 [plugins.py](/E:/git_clone/novusai-saas-yudi/backend/app/api/tenant/plugins.py#L80)
  - 插件页面路由还会额外写入 `accessCodes` 并受前端守卫限制，见 [\_extension_registrar.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/_extension_registrar.py#L70) 和 [guard.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts#L108)
- 判断：
  - tenant 链路没有 single source of truth，是系统性不一致。

## Finding 3：启动期全量权限同步会伤到插件动作权限

- 严重度：`P1`
- 现象：
  - 重启后插件菜单、权限树、角色授权表现会退化。
  - 非超管场景下更容易出现插件菜单缩水或消失。
- 证据：
  - 启动早期先跑全量权限同步，见 [main.py](/E:/git_clone/novusai-saas-yudi/backend/app/main.py#L81)
  - 全量同步会禁用代码侧不存在的 DB 权限，见 [sync.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/sync.py#L144) 和 [sync.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/sync.py#L233)
  - 插件恢复后再次跑的仍然是全量同步，而不是逐插件 `sync_plugin_permissions()`，见 [main.py](/E:/git_clone/novusai-saas-yudi/backend/app/main.py#L394) 和 [sync.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/sync.py#L480)
  - 插件正常启用流程原本依赖逐插件权限同步，见 [lifecycle.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/lifecycle.py#L983)
  - 权限服务只读取启用状态的权限记录，见 [permission_service.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/services/permission_service.py#L629)
- 判断：
  - 启动恢复链和插件启用链不一致，属于宿主权限同步设计问题。

## Finding 4：多菜单插件的动作权限会被统一挂到第一个插件菜单下

- 严重度：`P1`
- 现象：
  - 多菜单插件会出现子菜单不显示、权限树挂错、细粒度授权不生效。
- 证据：
  - `sync_plugin_permissions()` 先选第一个 admin/tenant 插件菜单作为默认父菜单，见 [sync.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/sync.py#L395)
  - 该方法随后将插件动作权限统一挂载到默认父菜单，见 [sync.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/sync.py#L419)
  - 菜单树逻辑会根据操作权限的 `parent_id` 自动补出父菜单和祖先菜单，见 [permission_service.py](/E:/git_clone/novusai-saas-yudi/backend/app/rbac/services/permission_service.py#L945)
  - 多页面、带父子菜单层级的复杂插件最容易受到影响。
- 判断：
  - 当前 RBAC 桥接只适配“单根菜单插件”，对复杂插件不成立。

## Finding 5：插件 i18n 依赖模块加载副作用，且命名空间不统一

- 严重度：`P2`
- 现象：
  - 菜单未翻译
  - 页面标题不跟语言切换
  - 页面内容大量缺少 i18n 或显示 key
- 证据：
  - 宿主标准 locale 只加载 `./langs/**/*.json`，见 [locales/index.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/locales/index.ts#L26)
  - 插件 locale 必须依赖 `registerLocale()` 在运行时注入，见 [plugin-shared.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/utils/plugin-shared.ts#L201)
  - plugin slots 现在会保留 `titleLocaleMap`，但历史上这里曾把多语言 title 过早压平成单字符串；当前实现位于 [plugin-slots.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/stores/plugin-slots.ts#L262)
  - 切换语言时宿主现在会重建菜单、刷新插件 slots、重算 tab 与当前路由标题，相关入口见 [basic.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/layouts/basic.vue#L259) 和 [use-plugin-frontend-init.ts](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-plugin-frontend-init.ts#L251)
  - 当前审计重点已从“仓库里存在多套并行命名空间”收敛为“install/enable/sync-manifest/runtime 是否强制 canonical prefix + page/menu i18n fail-close”，相关校验入口见 [frontend_contract.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/frontend_contract.py#L116) 和 [frontend_contract_checks.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/frontend_contract_checks.py#L190)
- 判断：
  - 多语言不是插件作者偶尔漏写，而是系统没有提供稳定的一致契约。

## Finding 6：插件菜单父级配置 API 自身存在契约冲突

- 严重度：`P2`
- 现象：
  - 菜单父级候选能展示，但提交时可能被后端 schema 拒绝。
  - 父级候选名称常出现未翻译或直接显示 `title`。
- 证据：
  - 提交模型要求 `parent` 只能匹配 `[a-z0-9_]+`，见 [admin/plugins.py](/E:/git_clone/novusai-saas-yudi/backend/app/api/admin/plugins.py#L66)
  - 但候选值来自 `_short_name(m.code)`，而插件菜单 code 会携带原始 page name，现有插件大量使用带 `-` 的名字，见 [admin/plugins.py](/E:/git_clone/novusai-saas-yudi/backend/app/api/admin/plugins.py#L478) 和 [storage-billing/plugin.yaml](/E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/plugin.yaml#L273)
  - 候选 label 直接调用 `translate(perm.name)`，没有走插件菜单运行时标题解析链，见 [admin/plugins.py](/E:/git_clone/novusai-saas-yudi/backend/app/api/admin/plugins.py#L482)
  - 插件菜单标题真实缓存位于 registry 的 `_plugin_menu_titles`，见 [registry.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/registry.py#L646)
- 判断：
  - 这是宿主管理端 API 的直接缺陷。

## Finding 7：脚手架、校验器、文档与实现漂移，持续放大坏结果

- 严重度：`P2`
- 现象：
  - 文档写得像支持的能力，实际上 schema/运行时并不消费。
  - 官方模板可以直接打出缺失 JS entry 的坏 release 包。
  - `frontend.pages[*].name` 等关键字段约束过弱，后续很容易引发覆盖或串台。
- 证据：
  - 文档要求 `extensions.capabilities[*] -> extensions.skills[*].capabilities[]` 显式映射，见 [plugin-developer-guide.md](/E:/git_clone/novusai-saas-yudi/docs/guides/plugin-developer-guide.md#L73)
  - `weather-widget` 按文档写了 `extensions.capabilities`，见 [plugin.yaml](/E:/git_clone/novusai-saas-yudi/backend/plugins/weather-widget/plugin.yaml#L18)
  - 但 manifest schema 并没有 `extensions.capabilities` 或 `skills[*].capabilities`，见 [manifest.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/manifest.py#L112) 和 [manifest.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/manifest.py#L777)
  - `frontend.pages[*].name` 只校验非空，不校验字符集和唯一性，见 [manifest.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/manifest.py#L487)
  - 菜单注册按 `name` 覆盖旧项，见 [registry.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/registry.py#L640)
  - 前端 slot 也按 `(slot_type, name)` 去重，不区分 scope，见 [registry.py](/E:/git_clone/novusai-saas-yudi/backend/app/plugins/registry.py#L890)
  - `full-module` 模板会预写占位 `plugin.manifest.json`，见 [plugin_cli.py](/E:/git_clone/novusai-saas-yudi/backend/scripts/plugin_cli.py#L643)
  - `pack --release` 只检查 manifest 文件存在，不校验 `plugin.js` 资产真实存在，见 [plugin_cli.py](/E:/git_clone/novusai-saas-yudi/backend/scripts/plugin_cli.py#L938)
  - 开发者指南仍写“支持 14 天试用期”，与当前 License 语义不一致，见 [plugin-developer-guide.md](/E:/git_clone/novusai-saas-yudi/docs/guides/plugin-developer-guide.md#L227)
- 判断：
  - 这部分说明不只是系统 runtime 脆弱，作者工具链本身也在制造问题。

## 总判断

这批问题里，主因不是“插件 skill 不够全”，而是“插件系统本身缺少统一、可验证的运行时契约”。`skill`、示例插件、脚手架、文档的缺口确实存在，但更多是在把系统缺陷复制到更多插件上。

更准确的归因是：

- 第一责任：宿主插件系统设计与运行时链路
- 第二责任：脚手架、validate、pack、文档与样例未收口
- 第三责任：个别插件的遗留写法或局部硬编码

## 后续审计方向

本文件只记录当前 7 项核心问题，后续应继续扩展以下审计维度：

1. 结合现有插件逐个核对：哪些问题已实质发生，哪些仍停留在结构性风险。
2. 对 admin / tenant 端分别做真实 E2E 复现。
3. 对各插件的 i18n 命名空间、动态导出、release 产物、权限映射做批量扫描。
4. 输出一份按“必须先修 / 可以并行修 / 文档清理”分层的修复计划。

# `storage-billing` 宿主 M0 改造清单（2026-03-23）

## 1. 文档目的

本文档只解决一件事：

在正式开发 `storage-billing` 独立插件之前，宿主工程必须先补哪些扩展点，具体应该改哪些文件，改完后的验收口径是什么。

它是以下两份文档的继续收敛版本：

1. [object-storage-official-billing-reconciliation-plan-20260323.md](./object-storage-official-billing-reconciliation-plan-20260323.md)
2. [storage-billing-plugin-implementation-spec-20260323.md](./storage-billing-plugin-implementation-spec-20260323.md)

这份文档不再讨论“是否要做”“为什么这么做”，只讨论“宿主要先怎么改，才能合法支撑插件实现”。

## 2. M0 完成定义

只有同时满足以下条件，才算宿主 M0 完成：

1. 套餐可以配置 `features.storage_billing_enabled`，管理端表单和展示层都能识别该字段。
2. 当套餐开启对象存储对账收费时，宿主会在 `plan_create`、`plan_update`、`tenant_create`、`tenant_plan_switch` 四个入口做前置校验。
3. 当 `storage-billing` 或其依赖云存储驱动被禁用/卸载时，宿主可以在真正执行 lifecycle 之前阻断操作，而不是事后补救。
4. 插件沙箱可以通过只读 facade 获取套餐、插件运行态、租户有效存储上下文等宿主快照，但不能直接拿到宿主原始 `AsyncSession`。
5. 插件 tenant 菜单支持 `manual_entitlement` 策略，不再在插件启用时自动授予所有活跃套餐。
6. 插件 `extensions.permissions` 定义的 action 权限会被同步进 RBAC 数据库，并能纳入 tenant plan 生效链路。

说明：

1. M0 目标是给 `storage-billing` 提供宿主能力，不是提前把插件业务写进主工程。
2. M0 原则上不要求新增宿主业务表。
3. `features` / `quota` 继续使用现有 JSON 结构，不引入新的套餐插件关联表。

## 3. 文件级改造清单

### 3.1 套餐 feature 字段与管理端入口

### `backend/app/schemas/tenant/plan.py`

改造目标：

1. 在 `FeaturesSchema` 中新增 `storage_billing_enabled: bool | None`。
2. 保持 `to_dict()` 的“仅输出非空值”行为不变。
3. 不新增独立数据库字段，仍写入 `tenant_plans.features` JSON。

验收口径：

1. 创建和更新套餐时，后端能正确接收并返回 `storage_billing_enabled`。
2. 旧套餐未配置该字段时，不影响现有接口兼容性。

### `frontend/apps/web-antd/src/api/admin/plan.ts`

改造目标：

1. 在 `FeaturesSchema` / `FeaturesSchemaRaw` 中新增 `storageBillingEnabled` / `storage_billing_enabled`。
2. 更新 `transformFeatures()`。
3. 保证创建、更新、详情回填时新字段完整往返。

验收口径：

1. 前端打开套餐编辑抽屉时，已有配置能正确回显。
2. 保存后不会丢失其他既有 feature 字段。

### `frontend/apps/web-antd/src/views/admin/tenant/plans/data.ts`

改造目标：

1. 在套餐表单的 features 分组中新增 `features.storage_billing_enabled` 开关。
2. 文案上明确提示：
   - 启用后需要安装并启用 `storage-billing`
   - 且必须存在至少一个已启用云对象存储插件：`aliyun-oss` / `qiniu-kodo` / `tencent-cos`
3. 该提示只作为管理员理解成本，不承担真正校验职责，真正阻断仍在后端 preflight。

验收口径：

1. 表单中能看到该开关。
2. 新字段不会破坏现有表单 schema 提交结构。

### `frontend/apps/web-antd/src/views/admin/tenant/plans/modules/PlanForm.vue`

改造目标：

1. 在 `transform()` 中写入 `features.storage_billing_enabled`。
2. 在 `toFormValues()` 中回填 `data.features?.storageBillingEnabled`。

验收口径：

1. 新建、编辑、详情回填三条链路字段一致。
2. 未勾选时仍维持当前“空对象不提交”的行为。

### `frontend/apps/web-antd/src/views/admin/tenant/plans/index.vue`

改造目标：

1. 在 features 展示区域新增对象存储对账收费标记。
2. 标签只负责表达套餐能力，不承担状态校验。

验收口径：

1. 套餐列表可以直观看到哪些套餐开启了该 feature。

### `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/tenant.json`
### `frontend/apps/web-antd/src/locales/langs/en-US/admin/tenant.json`

改造目标：

1. 新增 features 开关与展示标签的中英文本。
2. 新增表单帮助文案。

### 3.2 套餐/企业前置校验 registry

### 新增 `backend/app/plugins/tenant_plan_preflight.py`

建议新增一个宿主级 registry 模块，职责只做“前置校验收集与执行”，不承载业务逻辑。

建议内容：

1. `TenantPlanPreflightPayload`
2. `TenantPlanPreflightResult`
3. `TenantPlanPreflightHandler` 类型定义
4. `TenantPlanPreflightRegistry`
5. `run_tenant_plan_preflight(...)`

执行语义：

1. 多个 handler 按优先级执行。
2. 任何一个 handler 返回 `allowed = false` 即终止。
3. 宿主统一把失败结果转换为 `BusinessException(data={"reason_code": ..., "details": ...})`。

为什么要单独建文件：

1. 这不是 AI hook，也不是 system event。
2. 它是阻断型校验，不能复用当前 `system_hooks.py` 的“通知型、失败不影响主流程”语义。

### `backend/app/services/tenant/tenant_plan_service.py`

改造目标：

1. 在 `create_plan()` 真正写库前执行 `plan_create` preflight。
2. 在 `update_plan()` 合并出最终 `features` / `quota` 快照后执行 `plan_update` preflight。
3. 失败时直接抛出带 `reason_code` 的 `BusinessException`。

建议实现方式：

1. 不在 controller 里拼业务规则。
2. service 负责构造“最终态 payload”，避免插件拿到半成品数据。

验收口径：

1. 套餐打开 `storage_billing_enabled` 时，如果宿主条件不满足，更新会被阻断。
2. 套餐不涉及该 feature 的普通修改不受影响。

### `backend/app/services/system/tenant_service.py`

改造目标：

1. 在 `create_tenant(..., plan_id=...)` 中执行 `tenant_create` preflight。
2. 在 `update_tenant()` 中，当 `plan_id` 发生变化时执行 `tenant_plan_switch` preflight。
3. preflight 应基于“目标套餐最终快照”执行，而不是仅凭 `plan_id`。

验收口径：

1. 管理员给企业分配一个开启了对象存储对账收费的套餐时，宿主会先检查前提条件。
2. 只有 `plan_id` 真正变更时才触发该类校验，避免无关更新被影响。

### `backend/app/api/admin/plans.py`
### `backend/app/api/admin/tenants.py`

改造目标：

1. 一般无需写业务逻辑。
2. 只需确认 controller 不吞掉 `BusinessException.data`，让前端能拿到 `reason_code` 和 `details`。

说明：

1. 这两个文件是接入点，但真正规则仍放 service + registry。

### 3.3 插件 lifecycle 阻断 registry

### 新增 `backend/app/plugins/lifecycle_guards.py`

建议新增阻断型 lifecycle guard registry，职责独立于 `PluginLifecycle` 本身。

建议内容：

1. `PluginLifecycleGuardPayload`
2. `PluginLifecycleGuardResult`
3. `PluginLifecycleGuardHandler`
4. `PluginLifecycleGuardRegistry`
5. `run_plugin_lifecycle_guards(...)`

执行语义：

1. `disable` / `uninstall` 均支持。
2. 支持返回 `reason_code`、`message`、`details`。
3. guard 失败时直接阻断 lifecycle。

### `backend/app/plugins/lifecycle.py`

改造目标：

1. 在 `_disable_impl()` 中，于 `_check_storage_driver_in_use()` 之前执行 `disable` guards。
2. 在 `_uninstall_impl()` 中，于真正清理扩展、权限、文件之前执行 `uninstall` guards。
3. 对 `storage-billing` 这类依赖链敏感插件，guard 必须早于任何自动回退逻辑。

特别说明：

1. 当前 `force=True` 下，`_check_storage_driver_in_use()` 可能把平台或租户存储回退到 `local`。
2. 对象存储对账收费场景下，这会破坏账单链路连续性。
3. 因此 lifecycle guard 必须先于该逻辑执行，先给 `storage-billing` 一个 veto 机会。

验收口径：

1. 若存在启用 `storage_billing_enabled` 的套餐，禁止直接禁用或卸载 `storage-billing`。
2. 若 `storage-billing` 仍依赖某个云驱动，且该驱动仍被活动账单链路使用，则禁止禁用或卸载对应驱动。

### 3.4 插件沙箱只读宿主 facade

### 新增 `backend/app/plugins/host_read_facade.py`

建议把宿主快照查询能力独立成单文件，避免把 SQL 混进 `PluginContext`。

建议方法：

1. `get_enabled_storage_drivers()`
2. `get_plugin_runtime_summary(plugin_names: list[str] | None = None)`
3. `get_plan_snapshot(plan_id: int)`
4. `get_tenant_plan_snapshot(tenant_id: int)`
5. `get_tenant_storage_context(tenant_id: int)`

建议复用：

1. 插件运行态读取复用 `evaluate_plugin_runtime_gate()` 或统一查询 `plugins` 表。
2. 租户有效存储上下文复用 `StorageConfigResolver.resolve_context()`。
3. 套餐快照只返回业务字典，不返回 ORM 实例。

约束：

1. 只读。
2. 不暴露原始 SQL 执行入口。
3. 不把宿主 `AsyncSession` 暴露给插件。

### `backend/app/plugins/context.py`

改造目标：

1. 新增 `platform:read` capability 检查。
2. 给 `PluginContext` 增加只读宿主访问入口，例如：
   - `ctx.get_host_read()`
   - 或 `ctx.host`
3. 入口必须返回 facade，而不是 session。

同时要做：

1. 继续保持 `PluginDbProxy` 只能访问 `px_*` 表。
2. 明确禁止插件仿照历史实现直接使用 `ctx._db` 读取宿主核心表。

### `backend/app/plugins/context_factory.py`

改造目标：

1. 为 `PluginContext` 注入 `HostReadFacade`。
2. 保持现有 API 版本机制不破坏兼容性。

### `backend/app/plugins/manifest.py`

改造目标：

1. 在 `_VALID_CAPABILITIES` 中新增 `platform:read`。

### `backend/app/plugins/preview.py`
### `backend/app/api/admin/plugins.py`

改造目标：

1. 让安装预览和能力授权接口都认识 `platform:read`。
2. 管理员在插件管理端可见该能力说明。

验收口径：

1. `storage-billing` 插件声明 `platform:read` 时，manifest 校验通过。
2. 插件在无该能力时访问宿主快照会被拒绝。
3. 插件在有该能力时，只能拿到业务快照，不能越权读核心表。

### 3.5 tenant 菜单授权策略与 entitlement 同步

### `backend/app/plugins/registry.py`

改造目标：

1. 保持 `custom` 扩展注册逻辑可被宿主读取。
2. 新增一个小型 helper，供宿主读取指定插件的 `tenant_menu_policy` 声明。

说明：

1. 当前 `register_custom()` / `get_custom_extensions()` 已能承载该信息。
2. 这里不需要重做 registry，只需要把读取约定固化下来。

### 新增 `backend/app/services/tenant/tenant_plan_plugin_entitlement_service.py`

建议新增一个通用 entitlement 同步服务，不把 `storage-billing` 规则写死在 `TenantPlanService` 里。

职责：

1. 读取插件 `tenant_menu_policy`
2. 找出某插件 tenant 侧菜单权限
3. 找出某插件 action 权限
4. 基于套餐 feature 开关，为指定 plan 增量授予或撤销权限

为什么要有这个服务：

1. 当前 `_auto_grant_plugin_menus_to_plans()` 是“插件启用即全部套餐拥有”。
2. `storage-billing` 需要“只有 feature 打开的套餐才拥有”。
3. 后续其他按套餐收费的插件也可能复用这套模式。

建议规则：

1. 默认策略保持现状：`auto_all_active_plans`
2. 当插件声明 `manual_entitlement` 时：
   - 插件 enable 不再自动发菜单给所有套餐
   - 套餐 create/update 后由 entitlement service 决定授予/撤销
3. 同步范围必须包含：
   - tenant 菜单权限
   - 插件 route 所需 action 权限

### `backend/app/plugins/lifecycle.py`

改造目标：

1. `_auto_grant_plugin_menus_to_plans()` 增加策略判断：
   - 默认插件仍走自动授予
   - `manual_entitlement` 插件跳过自动授予
2. `_revoke_plugin_menus_from_plans()` 需要升级成“撤销该插件相关 tenant 权限”，不能只撤菜单。

### `backend/app/services/tenant/tenant_plan_service.py`

改造目标：

1. 在 `create_plan()` 成功后，对所有 `manual_entitlement` 插件执行一次按 feature 的同步。
2. 在 `update_plan()` 成功后，基于新旧 feature 差异同步对应插件权限。

验收口径：

1. 套餐打开 `storage_billing_enabled` 后，tenant 端能看到对应菜单并通过插件 API 权限校验。
2. 套餐关闭该 feature 后，菜单和 action 权限都会被撤销。

### 3.6 插件 action 权限同步到 RBAC 数据库

### `backend/app/rbac/sync.py`

改造目标：

把当前 `sync_plugin_permissions()` 从“只同步菜单”升级为“同步菜单 + 插件 action 权限”。

建议实现：

1. 保留现有 menu 同步逻辑。
2. 新增对 `ExtensionRegistry.get_plugin_permissions(plugin_name)` 的处理。
3. 每个 `extensions.permissions` 的 `actions` 都生成单独 DB 权限记录，编码建议为：
   - `plugin.{plugin_name}.{code}:{action}`
4. scope 继续落到 admin / tenant / both。
5. 首次 enable 用 flush 模式，不破坏外层事务。

重要说明：

1. 当前插件 API dispatcher 校验的就是 `plugin.{plugin_name}.{permission_code}:{action}`。
2. 如果这些记录不进 DB，tenant_admin 的 RBAC 永远不完整。

### `backend/app/plugins/lifecycle.py`

改造目标：

1. `_set_plugin_permissions_enabled()` 升级为同时启停菜单和插件 action 权限记录。
2. 卸载时的 `_delete_plugin_permissions_from_db()` 也要覆盖 action 权限，而不只删菜单权限。

### `backend/app/plugins/registry.py`

改造目标：

1. 继续维护 in-memory 的插件权限声明。
2. 明确 code 命名约定与 `sync_plugin_permissions()` 一致，避免运行时和数据库前缀不一致。

验收口径：

1. 插件启用后，permissions 表中能看到插件 menu 权限和 plugin action 权限。
2. tenant_admin 在拥有对应套餐 feature 时，可以通过插件 API 路由 permission gate。
3. 插件禁用或卸载后，相关权限记录状态与运行态一致。

### 3.7 后端消息与错误码承载

### `backend/app/locales/zh_CN/messages.json`
### `backend/app/locales/en/messages.json`

改造目标：

1. 为以下场景新增稳定 message key：
   - 套餐开启对象存储对账收费但宿主条件不满足
   - 缺少 `storage-billing` 插件
   - 未启用任何云对象存储插件
   - 禁用或卸载被账单链路阻断
2. 前端若需要做更细提示，则通过 `BusinessException.data.reason_code` 区分。

说明：

1. 不建议为了该功能新增一套新异常体系。
2. 使用现有 `BusinessException(data=...)` 即可承载结构化原因。

## 4. 建议新增文件一览

建议 M0 至少新增以下宿主文件：

1. `backend/app/plugins/tenant_plan_preflight.py`
2. `backend/app/plugins/lifecycle_guards.py`
3. `backend/app/plugins/host_read_facade.py`
4. `backend/app/services/tenant/tenant_plan_plugin_entitlement_service.py`

说明：

1. 这四个文件都是“宿主能力文件”，不是 `storage-billing` 业务文件。
2. 它们应该保持插件无关、可复用、无厂商耦合。

## 5. 不建议的实现方式

以下做法不建议采用：

1. 直接在 `storage-billing` 插件里通过 `ctx._db` 读取 `tenant_plans`、`plugins`、`system_configs`。
2. 继续使用 `_auto_grant_plugin_menus_to_plans()` 的“全部活跃套餐自动授权”逻辑承载对象存储计费能力。
3. 把 `storage_billing_enabled` 的真校验放在前端。
4. 在禁用云驱动时依赖 `force=True` 自动回退到 `local`，再由账单插件“事后修正”。
5. 只同步 plugin menu，不同步 plugin action 权限。

## 6. 开发顺序建议

建议严格按下面顺序实施：

1. 套餐 feature 字段打通：schema、前端 API、表单、列表标签。
2. `platform:read` + `HostReadFacade`。
3. `tenant_plan_preflight` registry，并接入 plan / tenant service。
4. `lifecycle_guards` registry，并接入 plugin lifecycle。
5. `manual_entitlement` 策略与 `tenant_plan_plugin_entitlement_service`。
6. `sync_plugin_permissions()` 升级为菜单 + action 权限同步。
7. 最后才开始创建 `backend/plugins/storage-billing/` 插件骨架。

原因：

1. 第 2 到第 6 步是插件合法运行的宿主前提。
2. 如果宿主前提未完成，先写插件只会导致大量临时绕过和返工。

## 7. 测试清单建议

建议 M0 至少覆盖以下测试面：

1. manifest 校验：`platform:read` 能力被正确识别。
2. PluginContext 安全：无 `platform:read` 时不能访问宿主只读 facade。
3. 套餐 preflight：开启 `storage_billing_enabled` 但缺少前置插件时，create/update 被阻断。
4. 企业 plan 切换 preflight：tenant 切换到受限套餐时会被阻断。
5. lifecycle guard：禁用/卸载 `storage-billing` 或相关云驱动时，能被 guard 正确拦截。
6. entitlement 同步：feature 打开后授予，关闭后撤销。
7. plugin action 权限同步：插件 API permission gate 对 tenant_admin 生效。

建议测试落点：

1. `backend/tests/test_plugin_manifest_validation.py`
2. `backend/tests/test_plugin_api_dispatcher_context_safety.py`
3. `backend/tests/test_plugin_lifecycle_cleanup_safety.py`
4. `backend/tests/api/test_admin_plans.py`
5. `backend/tests/api/test_admin_tenants.py`
6. `backend/tests/services/test_tenant_service.py`
7. 新增专门的 M0 合约测试文件，例如 `backend/tests/test_storage_billing_host_m0_contracts.py`

## 8. 结论

到这一步，设计已经足够支撑“开始开发宿主 M0”。

但它还不意味着“可以直接跳过宿主改造，立刻开发完整 `storage-billing` 插件”。

正确顺序应该是：

1. 先做宿主 M0。
2. 再做 `storage-billing` 插件骨架。
3. 最后接入阿里云 OSS、腾讯云 COS、七牛 Kodo 的官方账单适配器。

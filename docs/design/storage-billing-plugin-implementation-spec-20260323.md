# `storage-billing` 插件实施规格（2026-03-23）

## 1. 文档定位

本文档是 [object-storage-official-billing-reconciliation-plan-20260323.md](./object-storage-official-billing-reconciliation-plan-20260323.md) 的 companion spec。

如需进入具体开发拆解，请同时阅读：

1. [storage-billing-host-m0-checklist-20260323.md](./storage-billing-host-m0-checklist-20260323.md)

上一份文档回答的是：

1. 为什么该功能应做成独立插件
2. 官方账单口径怎么选
3. 套餐、插件、驱动之间的治理边界是什么

本文档回答的是：

1. 宿主要补哪些扩展点
2. `storage-billing` 插件第一阶段应该长什么样
3. 表、API、权限、页面、任务怎么落

## 2. 第一阶段目标

第一阶段目标不是“一次做完所有对象存储计费”，而是交付一个可上线演进的第一版：

1. 插件名固定为 `storage-billing`
2. 支持套餐 feature 授权
3. 支持对象存储插件前置校验
4. 支持三家 provider 的官方账单接入骨架
5. 支持 D-2 正式日结、D-1 预估刷新、月关账
6. 支持管理端账单中心和企业端账单中心

第一阶段明确不做：

1. `local` 存储收费
2. 上传流量收费
3. 请求次数收费
4. 多账号多结算主体复杂编排
5. tenant_user 侧账单页面
6. 通过应用下载日志直接扣费

说明：

1. 当前插件 API dispatcher 已支持 `admin` 和 `tenant_admin` 两端。
2. tenant_user 端不在第一阶段范围内。

## 3. 宿主 M0 详细规格

### 3.1 `tenant_plan` entitlement preflight registry

宿主新增统一 preflight registry，避免每个业务插件自己 patch 控制器。

建议接口：

```python
class TenantPlanPreflightPayload(TypedDict):
    operation: Literal["plan_create", "plan_update", "tenant_create", "tenant_plan_switch"]
    plan_id: int | None
    tenant_id: int | None
    features: dict[str, Any]
    quota: dict[str, Any]
    context: dict[str, Any]


class TenantPlanPreflightResult(TypedDict):
    allowed: bool
    reason_code: str
    message: str
    details: dict[str, Any]
```

宿主执行点：

1. `AdminPlanController.create_plan`
2. `AdminPlanController.update_plan`
3. `TenantService.create_tenant`，当传入 `plan_id`
4. `TenantService.update_tenant`，当 `plan_id` 发生变化

执行规则：

1. 收集所有已启用插件注册的 preflight handler
2. 按优先级顺序执行
3. 任一 handler 返回 `allowed = false`，立即阻断请求
4. 响应错误必须保留 `reason_code` 和 `message`

`storage-billing` 插件在这里负责校验：

1. 套餐是否开启 `storage_billing_enabled`
2. `storage-billing` 插件自身是否启用
3. 三个云对象存储插件中是否至少有一个启用
4. 若套餐关闭该 feature，是否应撤销 tenant 账单菜单和 action 权限

### 3.2 `before_plugin_disable` / `before_plugin_uninstall` veto registry

当前 `system.plugin.disabled` 是事后 hook，不够。

宿主新增 veto registry：

```python
class PluginLifecycleGuardPayload(TypedDict):
    operation: Literal["disable", "uninstall"]
    plugin_id: int
    plugin_name: str
    force: bool
    manifest: dict[str, Any]


class PluginLifecycleGuardResult(TypedDict):
    allowed: bool
    reason_code: str
    message: str
    details: dict[str, Any]
```

执行点：

1. `PluginLifecycle._disable_impl()` 在 `_check_storage_driver_in_use()` 之前
2. `PluginLifecycle.uninstall()` 在清理扩展和删除权限之前

`storage-billing` 插件在这里负责阻断两类操作：

1. 禁用/卸载 `storage-billing` 自身
2. 禁用/卸载 `aliyun-oss` / `qiniu-kodo` / `tencent-cos`

阻断依据：

1. 是否存在启用 feature 的套餐
2. 是否存在活跃 tenant 绑定
3. 是否存在未完成 run
4. 是否存在未关账月账

### 3.3 插件宿主只读 facade

这是第一阶段最关键的宿主能力之一。

当前 `PluginDbProxy` 只允许访问本插件 `px_*` 表，不允许合法读取：

1. `tenant_plans`
2. `plugins`
3. 平台配置
4. 企业有效存储上下文

因此宿主需要新增只读 facade，而不是让插件仿照 `storage-migration` 使用 `ctx._db` 绕沙箱。

建议新增 capability：

1. `platform:read`

建议 `PluginContext` 新增只读方法：

```python
class HostReadFacade:
    async def get_enabled_storage_drivers(self) -> list[dict]: ...
    async def get_plugin_runtime_summary(self, plugin_names: list[str] | None = None) -> list[dict]: ...
    async def get_tenant_plan_snapshot(self, tenant_id: int) -> dict | None: ...
    async def get_plan_snapshot(self, plan_id: int) -> dict | None: ...
    async def get_tenant_storage_context(self, tenant_id: int) -> dict: ...
```

约束：

1. 只读
2. 不返回原始 `AsyncSession`
3. 不暴露通用 SQL 接口
4. 返回的是业务快照，不是 ORM 对象

`storage-billing` 只允许依赖这类 facade，不允许直接读取宿主核心表。

### 3.4 tenant 插件菜单精准授权策略

当前插件启用时，宿主会自动把 tenant 菜单授予全部活跃套餐：

1. 这对内容类插件是方便的
2. 但对 `storage-billing` 是错误的

宿主需要支持 tenant 菜单授权策略可配置。

建议在 plugin manifest 用 `extensions.custom` 先表达：

```yaml
extensions:
  custom:
    - type: tenant_menu_policy
      name: storage_billing_menu_policy
      data:
        grant_mode: manual_entitlement
```

宿主行为：

1. 默认 `grant_mode = auto_all_active_plans`
2. 若插件声明 `manual_entitlement`
   - enable 时跳过 `_auto_grant_plugin_menus_to_plans()`
   - 由业务插件或宿主 entitlement 服务按套餐 feature 精准授予/撤销

### 3.5 插件 action 权限同步到 DB

当前插件 `extensions.permissions` 已注册到内存，但 `sync_plugin_permissions()` 只同步插件菜单权限。

这会导致：

1. tenant 插件 API 的 `permission_code:action` 校验没有完整 DB 支撑
2. owner 虽可超权通过，普通 tenant_admin 的 RBAC 不完整

宿主需要把 action 权限也同步到 DB。

建议：

1. 将现有 `sync_plugin_permissions()` 升级为“菜单 + action 权限统一同步”
2. 同步前缀包含：
   - `menu:admin.plugin_{safe_name}_`
   - `menu:tenant.plugin_{safe_name}_`
   - `plugin.{plugin_name}.`
3. 套餐 entitlement 同步时，tenant plan 不只授予菜单权限，也要授予对应的 plugin action 权限

## 4. `storage-billing` 插件 manifest 草案

### 4.1 第一阶段 manifest 方向

```yaml
name: storage-billing
version: "1.0.0"
display_name:
  zh-CN: "对象存储账单中心"
  en: "Storage Billing Center"
description:
  zh-CN: "基于官方账单的对象存储对账与租户计费插件"
  en: "Official-statement-based object storage reconciliation and tenant billing plugin"
author: "NovusAI"
scope: all_tenants
tags: ["billing", "storage", "oss", "cos", "qiniu", "finance"]

capabilities:
  - db:own_tables
  - http:outbound
  - notifications:send
  - config:write
  - platform:read

extensions:
  api:
    admin_routes:
      - method: GET
        path: overview
        handler: "api.handlers.get_admin_overview"
        permission: "admin_overview:view"
      - method: GET
        path: provider-profiles
        handler: "api.handlers.list_provider_profiles"
        permission: "config:view"
      - method: PUT
        path: provider-profiles
        handler: "api.handlers.save_provider_profiles"
        permission: "config:edit"
      - method: POST
        path: "provider-profiles/{provider}/validate"
        handler: "api.handlers.validate_provider_profile"
        permission: "config:validate"
      - method: GET
        path: bindings
        handler: "api.handlers.list_bindings"
        permission: "binding:view"
      - method: POST
        path: bindings
        handler: "api.handlers.create_binding"
        permission: "binding:create"
      - method: PUT
        path: "bindings/{binding_id}"
        handler: "api.handlers.update_binding"
        permission: "binding:update"
      - method: POST
        path: "bindings/{binding_id}/validate"
        handler: "api.handlers.validate_binding"
        permission: "binding:validate"
      - method: GET
        path: runs
        handler: "api.handlers.list_runs"
        permission: "run:view"
      - method: POST
        path: runs/sync-estimated
        handler: "api.handlers.trigger_sync_estimated"
        permission: "run:trigger"
      - method: POST
        path: runs/sync-official
        handler: "api.handlers.trigger_sync_official"
        permission: "run:trigger"
      - method: POST
        path: runs/settle-daily
        handler: "api.handlers.trigger_settle_daily"
        permission: "run:trigger"
      - method: POST
        path: runs/close-month
        handler: "api.handlers.trigger_close_month"
        permission: "settlement:close"
    tenant_routes:
      - method: GET
        path: me/overview
        handler: "api.handlers.get_tenant_overview"
        permission: "tenant_bill:view"
      - method: GET
        path: me/daily
        handler: "api.handlers.list_tenant_daily"
        permission: "tenant_bill:view"
      - method: GET
        path: me/monthly
        handler: "api.handlers.list_tenant_monthly"
        permission: "tenant_bill:view"
      - method: GET
        path: me/prerequisites
        handler: "api.handlers.get_tenant_prerequisites"
        permission: "tenant_bill:view"

  tasks:
    - name: settle_official_d2
      handler: "tasks.schedulers.settle_official_d2"
      schedule_type: cron
      cron_expression: "0 3 * * *"
    - name: refresh_estimated_d1
      handler: "tasks.schedulers.refresh_estimated_d1"
      schedule_type: cron
      cron_expression: "0 11 * * *"
    - name: refresh_official_d1
      handler: "tasks.schedulers.refresh_official_d1"
      schedule_type: cron
      cron_expression: "0 19 * * *"
    - name: close_previous_month
      handler: "tasks.schedulers.close_previous_month"
      schedule_type: cron
      cron_expression: "0 3 6 * *"

  permissions:
    - code: admin_overview
      scope: admin
      actions: ["view"]
    - code: config
      scope: admin
      actions: ["view", "edit", "validate"]
    - code: binding
      scope: admin
      actions: ["view", "create", "update", "delete", "validate"]
    - code: run
      scope: admin
      actions: ["view", "trigger", "retry"]
    - code: settlement
      scope: admin
      actions: ["view", "rebuild", "close"]
    - code: exception
      scope: admin
      actions: ["view", "resolve"]
    - code: tenant_bill
      scope: tenant
      actions: ["view", "export"]

  frontend:
    pages:
      - name: storage_billing_admin
        path: /admin/plugins/storage-billing
        component: StorageBillingAdminPage
        scope: admin
        menu:
          parent: system_mgmt
          sort_order: 70
      - name: storage_billing_tenant
        path: /tenant/plugins/storage-billing
        component: StorageBillingTenantPage
        scope: tenant
        menu:
          parent: system_mgmt
          sort_order: 70

  custom:
    - type: tenant_menu_policy
      name: storage_billing_menu_policy
      data:
        grant_mode: manual_entitlement
```

### 4.2 scope 选择

第一阶段推荐：

1. `scope = all_tenants`

原因：

1. 账单中心属于平台级商业能力
2. 是否可见最终仍由：
   - 插件是否启用
   - tenant plan 是否授予相关权限
   - tenant 是否满足 feature 前置条件

若后续要做灰度：

1. 改成 `admin_and_selected_tenants`
2. 配合 `ResourceTenantAssignment` 做企业级可见性控制

## 5. 配置模型

### 5.1 第一阶段 provider 配置策略

第一阶段不做“每个 provider 多账号编排 UI”。

建议策略：

1. 每个 provider 只支持一个 active billing profile
2. profile 仍保留 `profile_code` 字段，避免未来迁移

建议插件全局配置结构：

```json
{
  "providers": {
    "aliyun": {
      "enabled": false,
      "profile_code": "aliyun-default",
      "bill_source": "oss_subscription",
      "region": "",
      "access_key_id": "",
      "access_key_secret": "",
      "bill_bucket": "",
      "bill_prefix": "",
      "account_identifier": ""
    },
    "tencent": {
      "enabled": false,
      "profile_code": "tencent-default",
      "bill_source": "cos_bill_bucket",
      "secret_id": "",
      "secret_key": "",
      "region": "",
      "bill_bucket": "",
      "bill_prefix": "",
      "account_identifier": ""
    },
    "qiniu": {
      "enabled": false,
      "profile_code": "qiniu-default",
      "bill_source": "finance_api",
      "access_key": "",
      "secret_key": "",
      "account_identifier": ""
    }
  }
}
```

约束：

1. secret 字段必须走插件配置加密
2. 插件内部表只存 `provider_profile_code`
3. 原始 secret 不落插件自有业务表

## 6. 数据模型

### 6.1 `px_storage_billing_tenant_bindings`

用途：

1. tenant 和 provider 计费范围绑定
2. 套餐 entitlement 落地结果
3. 租户账单是否激活的直接真相源

建议字段：

1. `tenant_id`
2. `provider`
3. `provider_profile_code`
4. `storage_driver_code`
5. `billing_mode`
   - `official_reconciled`
   - `official_pass_through`
6. `scope_type`
   - `bucket`
   - `domain`
   - `account`
   - `tag`
7. `scope_value`
8. `bucket_name`
9. `domain_name`
10. `account_identifier`
11. `tag_key`
12. `tag_value`
13. `validation_status`
   - `pending`
   - `valid`
   - `invalid`
14. `validation_message`
15. `entitlement_snapshot`
16. `is_active`

唯一索引建议：

1. `(tenant_id, provider, is_deleted=false)` 第一阶段可唯一

### 6.2 `px_storage_billing_runs`

用途：

1. 记录每次同步/结算/关账任务
2. 作为幂等和审计入口

建议字段：

1. `run_type`
   - `sync_estimated`
   - `sync_official`
   - `settle_daily`
   - `close_month`
   - `rebuild`
2. `provider`
3. `provider_profile_code`
4. `target_date`
5. `target_month`
6. `status`
   - `pending`
   - `running`
   - `succeeded`
   - `partial`
   - `failed`
7. `triggered_by_type`
   - `scheduler`
   - `admin`
   - `system`
8. `triggered_by_id`
9. `summary_json`
10. `error_message`
11. `idempotency_key`

唯一索引建议：

1. `(run_type, provider, provider_profile_code, target_date, target_month, idempotency_key)`

### 6.3 `px_storage_billing_raw_statements`

用途：

1. 保存原始账单文件/API 拉取结果元信息
2. 支撑审计、补算、重复导入去重

建议字段：

1. `provider`
2. `provider_profile_code`
3. `bill_date`
4. `bill_month`
5. `statement_level`
   - `estimated_daily`
   - `official_daily`
   - `official_monthly`
   - `split_reference`
6. `source_type`
   - `file`
   - `api`
7. `source_uri`
8. `checksum`
9. `raw_payload_json`
10. `parse_status`
11. `parse_error`
12. `run_id`

### 6.4 `px_storage_billing_vendor_daily`

用途：

1. 归一化后的 provider 日级真相源

建议字段：

1. `provider`
2. `provider_profile_code`
3. `bill_date`
4. `charge_type`
   - `network_egress`
   - `cdn_origin_egress`
   - `transfer_acceleration_egress`
   - `data_processing`
5. `scope_type`
6. `scope_value`
7. `usage_value`
8. `usage_unit`
9. `official_amount`
10. `currency`
11. `statement_level`
12. `raw_statement_id`
13. `run_id`

唯一索引建议：

1. `(provider, provider_profile_code, bill_date, charge_type, scope_type, scope_value, statement_level)`

### 6.5 `px_storage_billing_tenant_daily`

用途：

1. tenant 日账单
2. tenant 侧账单中心的主表

建议字段：

1. `tenant_id`
2. `provider`
3. `bill_date`
4. `charge_type`
5. `settlement_level`
   - `estimated`
   - `official`
   - `adjustment`
6. `binding_id`
7. `usage_value`
8. `usage_unit`
9. `amount`
10. `currency`
11. `status`
   - `open`
   - `confirmed`
   - `locked`
12. `vendor_daily_ids_json`
13. `run_id`

唯一索引建议：

1. `(tenant_id, provider, bill_date, charge_type, settlement_level, binding_id)`

### 6.6 `px_storage_billing_monthly_closings`

用途：

1. tenant 月关账
2. 补差汇总

建议字段：

1. `tenant_id`
2. `provider`
3. `bill_month`
4. `estimated_total_amount`
5. `official_total_amount`
6. `adjustment_amount`
7. `currency`
8. `status`
   - `open`
   - `locked`
   - `adjusted`
9. `closed_at`
10. `close_run_id`

唯一索引建议：

1. `(tenant_id, provider, bill_month)`

### 6.7 `px_storage_billing_reconcile_issues`

用途：

1. 记录无法自动对齐的问题
2. 供管理端异常中心处理

建议字段：

1. `issue_type`
   - `missing_binding`
   - `binding_invalid`
   - `vendor_total_mismatch`
   - `late_statement`
   - `driver_disabled`
2. `provider`
3. `tenant_id`
4. `bill_date`
5. `bill_month`
6. `severity`
   - `info`
   - `warning`
   - `critical`
7. `detail_json`
8. `status`
   - `open`
   - `resolved`
   - `ignored`
9. `resolved_by`
10. `resolved_at`

## 7. API 规格

### 7.1 admin routes

第一阶段建议 admin routes：

1. `GET /admin/plugins/storage-billing/api/overview`
   - 首页总览
2. `GET /admin/plugins/storage-billing/api/provider-profiles`
   - 读 provider 配置
3. `PUT /admin/plugins/storage-billing/api/provider-profiles`
   - 保存 provider 配置
4. `POST /admin/plugins/storage-billing/api/provider-profiles/{provider}/validate`
   - 校验 provider 连通性和账单源可读性
5. `GET /admin/plugins/storage-billing/api/bindings`
6. `POST /admin/plugins/storage-billing/api/bindings`
7. `PUT /admin/plugins/storage-billing/api/bindings/{binding_id}`
8. `POST /admin/plugins/storage-billing/api/bindings/{binding_id}/validate`
9. `GET /admin/plugins/storage-billing/api/runs`
10. `POST /admin/plugins/storage-billing/api/runs/sync-estimated`
11. `POST /admin/plugins/storage-billing/api/runs/sync-official`
12. `POST /admin/plugins/storage-billing/api/runs/settle-daily`
13. `POST /admin/plugins/storage-billing/api/runs/close-month`
14. `GET /admin/plugins/storage-billing/api/daily`
15. `GET /admin/plugins/storage-billing/api/monthly`
16. `GET /admin/plugins/storage-billing/api/issues`
17. `POST /admin/plugins/storage-billing/api/issues/{issue_id}/resolve`

### 7.2 tenant routes

第一阶段建议 tenant routes：

1. `GET /tenant/plugins/storage-billing/api/me/prerequisites`
   - 返回 feature 是否开启、插件是否可用、当前存储驱动是否为 local
2. `GET /tenant/plugins/storage-billing/api/me/overview`
3. `GET /tenant/plugins/storage-billing/api/me/daily`
4. `GET /tenant/plugins/storage-billing/api/me/monthly`

tenant 端第一阶段不开放：

1. 修改绑定
2. 主动触发结算
3. 导出原始对账材料

## 8. 权限与菜单策略

### 8.1 admin 侧

admin 用户在当前 dispatcher 中默认拥有插件 API 超权，因此 admin 侧重点在菜单可见性，而不是阻断。

第一阶段仍建议声明完整 action 权限，原因：

1. 便于后续平台把 admin 插件权限也纳入标准 RBAC
2. 便于审计日志和接口文档统一

### 8.2 tenant 侧

tenant 侧必须走“feature -> plan permission -> role permission”三层控制。

具体策略：

1. `storage-billing` tenant 菜单 enable 时不自动授予所有活跃套餐
2. 当套餐 `storage_billing_enabled = true` 且前置条件满足时：
   - 宿主或插件 entitlement 服务授予：
     - tenant 菜单权限
     - `plugin.storage-billing.tenant_bill:*` action 权限
3. 当套餐关闭该 feature 或前置条件失效时：
   - 撤销上述权限

### 8.3 第一阶段要避免的错误

以下做法都不应采用：

1. 只控制菜单可见，不控制 tenant API action
2. 只控制 plugin scope，不控制 plan permission
3. 允许通过 `ctx._db` 直接读宿主表来绕过 facade

## 9. 结算任务与状态机

### 9.1 日任务

1. `03:00` `settle_official_d2`
   - 目标：`D-2`
   - 流程：
     - 拉取/补齐 `D-2` 官方账单
     - 归一化 `vendor_daily`
     - 生成 `tenant_daily(settlement_level=official)`
     - 写入 `reconcile_issues`
2. `11:00` `refresh_estimated_d1`
   - 目标：`D-1`
   - 生成 `tenant_daily(settlement_level=estimated)`
3. `19:00` `refresh_official_d1`
   - 目标：`D-1`
   - 补齐已成熟的官方数据，但不锁账

### 9.2 月任务

1. 每月 `06` 日 `03:00` `close_previous_month`
   - 锁定上月月账
   - 生成 `monthly_closings`
   - 对比 estimated 和 official，写 adjustment

### 9.3 状态机

`run.status`：

1. `pending`
2. `running`
3. `succeeded`
4. `partial`
5. `failed`

`tenant_daily.status`：

1. `open`
2. `confirmed`
3. `locked`

`monthly_closings.status`：

1. `open`
2. `locked`
3. `adjusted`

## 10. 第一阶段开发顺序

建议按以下顺序落地：

1. 宿主 M0 改造
   - preflight registry
   - veto registry
   - host read facade
   - plugin action 权限同步
   - tenant 菜单精准授权策略
2. 新建 `storage-billing` 插件骨架
3. 建立插件自管表和迁移
4. 实现 provider 配置页和绑定页
5. 实现 entitlement 校验和 tenant 菜单/权限授予
6. 实现 run 中心和 D-1/D-2/月任务
7. 实现 tenant 账单中心

## 11. 审计备注

当前仓库里，`storage-migration` 这类 first-party 插件在 handler 中会直接使用 `ctx._db` 读宿主表。

对 `storage-billing` 来说，不应复制这种模式。

原因：

1. 账单插件是商业结算插件，未来会长期维护
2. 若直接依赖 `ctx._db` 私有属性，等于默认接受“插件越权读宿主核心表”
3. 正确做法是先把宿主只读 facade 补出来，再让 `storage-billing` 基于 facade 实现

## 12. 文档状态

状态：可进入开发拆解。

最后核对日期：2026-03-23（北京时间）

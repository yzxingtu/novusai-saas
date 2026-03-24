# Storage Billing Remediation Plan 2026-03-25

## 0. 当前进展

已落地：

- tenant API prerequisites hard gate
- binding mismatch / provider profile runtime 健康状态并入 ready 计算
- tenant/frontend 权限桥接与首屏 gating
- host preflight 对当前平台 active driver 的可计费性校验
- tenant readiness 与 binding validation 统一到 `platform_storage_context`

本轮新增收口：

- host preflight 增加“当前平台 active driver 对应插件必须启用”
- tenant/admin 当前 UI 文案开始统一为聚合 `charge rows`
- tenant charge rows 直接展示 `scope_values` 与 `item_count`

下一阶段仍待处理：

- 多 source 同 provider/date 的覆盖风险
- 是否需要真正资源级 line-item 数据模型

## 1. 目标

把 `storage-billing` 从“基本可跑，但语义不清、tenant gate 不够硬、明细粒度不足”的状态，收敛到下面这个清晰模型：

- 管理端负责：
  - 读取宿主平台对象存储配置
  - 维护 provider profile
  - 维护 tenant 绑定
  - 触发官方账单对账
- 企业端只在满足条件时可见：
  - 套餐 feature 开启
  - 插件与对应云驱动可用
  - 当前计费语义下的存储事实源成立
  - 当前 binding / profile / runtime 状态均 ready
- tenant 看到的内容必须与产品语义一致：
  - 如果只做汇总，就明确叫“账单汇总”
  - 如果要做明细，就必须新增资源级 charge line

## 2. 先定一个总语义

这件事必须先定，不定就不要开始改代码。

### 推荐采用的正式语义

`storage-billing` 只对“企业正在使用管理端统一对象存储”的场景计费。

也就是：

- 不是“谁当前用了任意云对象存储就计费”
- 不是“tenant 自己 custom/admin_override 存储也纳入 billing”
- 而是“tenant 复用了平台统一对象存储，平台再按官方账单向 tenant 做内部计费”

采用这个语义的原因：

1. 与当前正式规范最一致
2. 与当前 provider profile 的全局单份结构最一致
3. 与当前 reconciliation 只认 platform storage context 的实现最一致
4. 改动面最小，风险最低

### 明确不采用的语义

本轮默认不采用下面这两种语义，除非后续产品明确推翻：

1. “谁当前用了任意云对象存储就给谁计费”
2. “插件通过 assignment 手工指定部分企业可见，并与套餐 feature 并行控制”

原因：

- 这两种语义都要求更大范围重构
- 当前插件结构、provider profile 模型和对账采集链路都不是按这两种语义设计的

## 3. 修复总顺序

### 第一阶段：先修硬错误

1. tenant API 增加 prerequisites hard gate
2. binding mismatch 升级为 invalid
3. provider profile disabled / invalid / driver plugin disabled 并入 tenant ready
4. 统一事实源为 platform storage context

### 第二阶段：再修可见性语义

5. 明确 tenant 可见性是 feature-managed entitlement 还是 assignment
6. 若继续走 feature 模型，收敛 scope 表达
7. 若改走手工指定企业，改成 assignment 模型

### 第三阶段：补前端规范闭环

8. 接入 `NovusPluginShared` 权限桥接
9. admin / tenant 页面首屏请求前先判权限
10. CTA 按细粒度权限 gating
11. tenant 未 ready 时不继续展示账单工作流

### 第四阶段：处理“明细”语义

12. 如果只保留汇总，统一改文案
13. 如果要资源级明细，新增明细层数据模型与 UI

## 4. 第一阶段详细方案

### 4.1 tenant API hard gate

改动目标：

- 以下 tenant API 在读取任何账单数据前，必须先执行 prerequisites 检查：
  - `get_current_statement`
  - `list_statements`
  - `list_statement_charges`
  - `export_statement_charges`

建议做法：

1. 在 `StorageBillingBindingService` 新增一个只返回硬门槛结果的方法，例如：
   - `ensure_tenant_billing_ready(tenant_id)`
2. 返回结构中至少包含：
   - `ready`
   - `missing_reasons`
   - `current_driver`
   - `expected_provider`
3. tenant API 若 `ready=false`：
   - 读取类接口返回业务错误
   - 不再透传历史 statement / charges
4. tenant 前端页面：
   - 先请求 prerequisites
   - `ready=false` 时不再继续请求 statement / statements / charges
   - 不再继续展示导出工作流

同时补 host 侧最小收紧：

1. 套餐 / 生命周期 preflight 不再只检查“插件存在 + 任一云驱动启用”
2. 至少还要前移检查：
   - 当前 platform active driver 是否为 billable cloud driver
   - 如果业务语义锁定为“只对平台统一存储计费”，tenant 是否仍使用 `platform` storage mode

建议错误码语义：

- `storage_billing_not_ready`
- `plan_feature_disabled`
- `platform_driver_not_billable`
- `provider_profile_disabled`
- `provider_profile_invalid`
- `driver_plugin_disabled`
- `binding_missing`
- `binding_provider_mismatch`
- `binding_invalid`
- `tenant_not_using_platform_storage`

### 4.2 binding mismatch 升级为 invalid

当前问题：

- current driver mismatch 只记 warning

修复目标：

- 只要 binding.provider_code 与当前计费事实源对应 driver 不一致，就必须直接 invalid

建议做法：

1. `_validate_binding_data()` 中把 mismatch 从 warning 改成 error
2. 管理端绑定列表里 status 和 validation_message 同步反映
3. 补测试覆盖：
   - mismatch binding create -> invalid
   - mismatch binding validate -> invalid
4. 同时把“tenant 不在 platform storage mode”也纳入 invalid 语义，而不是 warning

### 4.3 ready 计算必须并入 profile/runtime 健康状态

当前问题：

- binding 历史上 valid，不代表现在仍然 valid

修复目标：

- `get_tenant_prerequisites()` 的 `ready` 必须同时看：
  - feature
  - 当前计费事实源
  - profile.enabled
  - profile validation.errors
  - driver plugin enabled
  - valid matching binding

建议做法：

在 `missing_reasons` 中新增：

- `provider_profile_disabled`
- `provider_profile_invalid`
- `driver_plugin_disabled`
- `tenant_not_using_platform_storage`
- `platform_driver_not_billable`

## 5. 事实源统一方案

### 推荐方案

统一为 `platform storage context`。

也就是：

- tenant prerequisites 不再以 tenant effective storage context 作为主判断
- 先判断 tenant 当前是否仍在使用平台统一对象存储
- 再判断 platform active driver 是否 billable
- 再判断 binding/profile/runtime 是否匹配 platform active driver

### 具体判断链

1. tenant 当前 `storage_mode` 是否为 `platform`
2. platform active driver 是否属于：
   - `qiniu-kodo`
   - `aliyun-oss`
   - `tencent-cos`
3. 对应 provider profile 是否 enabled 且 validation 通过
4. 对应 driver plugin 是否 enabled
5. tenant 是否存在匹配 platform active driver 的 valid binding

### 需要新增的 missing reason

- `tenant_not_using_platform_storage`
- `platform_driver_not_billable`

## 6. 可见性模型处理方案

### 推荐方案

保留 feature-managed entitlement，不切 assignment。

理由：

- 当前真实控制面已经是 plan feature -> permissions
- 生命周期、preflight、tenant 菜单权限都已经围绕这条线工作
- 改成 assignment 会牵扯更大范围的 scope / RTA / 管理端分配模型重做

### 需要做的治理

1. 文档明确写死：
   - tenant 可见性由 feature entitlement 控制
   - 不是 generic assignment
2. `plugin.yaml` 的 `scope` 需要收敛表达

可选两种做法：

- 做法 A：保留 `all_tenants`，但在文档里明确这只是 runtime 宽口径壳，真正可见性在 permission
- 做法 B：把 `scope` 改成更符合业务语义的值

我更倾向：

- 如果不重构 assignment，就暂时保留 `all_tenants`
- 但必须在文档与代码注释里明确“feature-managed tenant visibility”

## 7. 前端规范修复方案

### 7.1 权限桥接

前端入口的 shared API 至少扩成：

- `registerLocale`
- `getAccessCodes`
- `hasAccessByCodes`

然后 admin / tenant 页面分别在首屏加载前做：

- 页面级 permission gate
- CTA 级 permission gate

### 7.2 admin 页面动作拆权

至少按下面的粒度 gating：

- `billing_admin:view`
- `billing_admin:configure`
- `billing_admin:reconcile`

并且：

- 只有新增/编辑 binding 时才需要租户下拉数据
- `billing_admin:view` 首屏不得顺手请求宿主 `/admin/tenants/select`
- 否则会把 storage-billing 的只读角色错误耦合到宿主 `tenant:select`

### 7.3 tenant 页面动作拆权

至少按下面的粒度 gating：

- `billing_portal:view`
- `billing_statement:list`
- `billing_statement:export`

并且：

- `statement/charges` 若产品语义上属于“明细”，应考虑改为单独权限码
- 若不改权限码，至少不要再声明没消费的 `billing_statement:list`
- `billing_portal:view` 用户即使没有 `billing_statement:list`，当前账单摘要也必须正常显示，不能因为明细不可看就把 summary 卡片清空

### 7.4 not-ready 页面行为

tenant 页面当 `prerequisites.ready === false` 时：

- 不继续并行读取 statement / statements / charges
- 不显示 export 工作流
- 只显示 prerequisites 和下一步指引

## 8. “明细”语义处理方案

### 方案 A：只做汇总

如果产品不要求资源级追踪：

- 保留现有 ledger 聚合模型
- tenant 页面统一改词：
  - “费用明细” -> “账单汇总” / “费用汇总”
- `billing_statement:list` 不再作为“明细读取权限”去设计

这是低风险方案。

### 方案 B：做真正明细

如果产品要求 tenant 真能看到：

- 哪个 bucket
- 哪个 domain
- 哪个 account
- 哪个 tag
- 产生了多少费用

那么需要新增一层资源级 charge line，例如：

- `StorageTenantChargeLine`

最少字段：

- `tenant_id`
- `period_type`
- `billing_date`
- `provider_code`
- `driver_code`
- `charge_basis`
- `scope_type`
- `scope_value`
- `bucket_name`
- `domain_name`
- `account_identifier`
- `tag_key`
- `tag_value`
- `usage_bytes`
- `amount_total`
- `currency`
- `source_id`

然后：

- `StorageTenantDailyCharge` 退化成汇总层
- tenant UI 新增“汇总 / 明细”两层展示

这条方案不建议和第一阶段混在一起做，应在第一阶段硬错误收口后单独立项。

## 9. 测试补齐计划

### 必补后端测试

1. provider profile disabled -> prerequisites not ready
2. provider profile validation error -> prerequisites not ready
3. driver plugin disabled -> prerequisites not ready
4. tenant API not ready -> statement / charges / export 全拒绝
5. platform active driver != binding provider -> binding invalid
6. tenant storage mode != platform -> `tenant_not_using_platform_storage`
7. 同 tenant 同 provider 同日多个 bucket -> 当前仅汇总，不可误称资源级明细

### 必补前端测试

1. admin 页面无 `configure` 权限时不显示保存/绑定操作
2. admin 页面无 `reconcile` 权限时不显示对账触发操作
3. admin 页面只有 `billing_admin:view` 时，不应请求 `/admin/tenants/select`
4. tenant 页面无 `billing_statement:list` 时，仍能看到 current statement / summary，但不发明细请求
5. tenant 页面无 `billing_statement:export` 权限时导出按钮不显示或禁用
6. tenant 页面 `ready=false` 时不发账单读取请求

### 必补真实浏览器回归

1. 管理端
   - 菜单进入
   - direct URL
   - 硬刷新
   - 只读角色进入后不再打 `/admin/tenants/select`
   - 权限撤销后的 CTA 隐藏
2. 企业端
   - ready=true 时账单页正常
   - 只有门户权限时，当前账单仍可见，但 charge/export 不可见
   - ready=false 时只显示 prerequisites，不再读账单
3. 切语言
   - sidebar
   - breadcrumb
   - `document.title`
   - tab title

## 10. 建议执行顺序

第一轮实现：

1. 统一事实源到 platform
2. tenant API hard gate
3. binding mismatch -> invalid
4. prerequisites 并入 profile/runtime 健康状态

第二轮实现：

5. 前端权限桥接
6. CTA gating
7. not-ready 页面收口

第三轮实现：

8. 决定“汇总”还是“明细”
9. 如需明细，再做数据模型升级

## 11. 当前已开始落地的修复

截至本轮对话，已开始落地但尚未完成整体验证的项：

1. tenant API 已接入 prerequisites hard gate
2. tenant 页面改成先拉 prerequisites，再决定是否继续拉 statement / charges
3. `binding_service` 已开始把以下条件并入 `ready`：
   - `provider_profile_disabled`
   - `provider_profile_invalid`
   - `driver_plugin_disabled`
   - `tenant_not_using_platform_storage`
4. tenant 页面 capability 展示已收窄到当前 billing driver
5. `statement/charges` 的 permission 已从 `billing_portal:view` 收敛到 `billing_statement:list`
6. admin / tenant 页面已开始接入前端权限桥接与 CTA gating
7. admin 页面已避免对只读角色预取 `/admin/tenants/select`
8. tenant 页面已修正“无明细权限时误清空当前账单摘要”的问题
9. host preflight 已开始阻断“platform active driver 对应插件未启用，但其他云驱动插件仍启用”的错误放行
10. lifecycle guard 已开始阻断“当前平台正在使用的 driver 插件被禁用/卸载”的破坏性操作
11. reconciliation 已开始在写 charge row 前过滤掉已失去 feature / platform mode 资格的 stale binding
12. reconciliation 已开始把 allocation gap 抬升为 `completed_with_gaps`，避免“丢账但看起来完成”
13. reconciliation 已开始把每个 source 的 allocation rows 固化到 source snapshot，用于历史 run detail 回放
14. live tenant charge rows 已开始从“当前 run 的 source snapshots”重建，避免同 provider/date 覆盖未来多 source 贡献

这些改动还需要在第一阶段结束时统一补跑后端测试、前端构建/类型检查和浏览器回归。

## 12. 当前剩余未落地项

第一阶段里还没有完全收完的点：

1. host preflight 还需要把更多 reason code 与 tenant prerequisites 对齐
2. admin 前端的 CTA gating 还没有做完整浏览器验证
3. tenant API / prerequisites / 页面收口后，需要统一补回归测试
4. `binding_provider_mismatch` 的 message 文案和业务语义还需要最终确认
5. 需要确认 admin overview 是否继续保留全 provider capability matrix，还是拆成 capability matrix + active executable schedule
6. 当前 run snapshot 已能解决历史 run detail 漂移，但 tenant ledger 仍是聚合 charge-row，不是资源级 line-item

## 13. 当前环境阻塞

本轮对话中，主线程 shell 环境存在宿主级异常：

- `python`
- `npm`
- `git`
- `cmd`

都出现了“找不到指定模块 / 可执行程序不可用”的异常。

因此当前能做的验证主要是：

- MCP 浏览器真实页面验证
- 本地静态代码审计
- 文档与方案落地

待 shell 环境恢复后，必须补跑：

1. `pytest`
2. `npm run build`
3. 相关 `vitest` / `typecheck`

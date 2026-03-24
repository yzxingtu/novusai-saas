# Storage Billing Deep Audit 2026-03-25

## 0. 本轮已处理更新

- tenant readiness / binding validation 现已只认 `platform_storage_context` 作为 billable driver 事实源，不再在 platform driver 缺失时回退到 tenant effective driver
- host preflight 现已补上“当前平台 active driver 对应插件必须启用”的阻断
- tenant/admin 当前 UI 文案已开始从“费用明细”收敛为“聚合账单行 / charge rows”，并补出 `scope_values` / `item_count` 这类可解释字段

仍保留为后续阶段问题：

- `StorageTenantDailyCharge` 仍是聚合 charge-row 模型，不是独立资源级 line-item 表
- `_replace_daily_charges_for_source()` 的多 source 同 provider/date 覆盖风险仍需单独做数据模型级治理

## 1. 审计目标

审计 `backend/plugins/storage-billing/` 是否真正符合以下业务目标：

- 管理端启用并配置宿主对象存储后，`storage-billing` 只负责官方账单计费与对账
- 企业端如果实际使用了管理端对象存储，且套餐/权限满足条件，则只能看到“自己的费用明细”
- 可见性模型应符合“管理端 + 部分企业”，而不是语义漂移
- 写法必须同时遵守：
  - 项目 skill
  - `.cursor/rules/plugin-system.md`
  - 插件开发规范
  - `storage-billing` 自己的实施规范

## 1.1 当前结论

说明：

- 本文记录的是审计发现本身，后续修复状态以 `storage-billing-remediation-plan-20260325.md` 为准。
- 同一天内已经开始落地的修复，不会回写抹掉这里的原始问题，只会在整改方案里单独记录“已开始落地的修复”。

当前 `storage-billing` 的问题已经不是“某几个接口漏判空”这么简单，而是三类结构性问题叠在一起：

1. tenant 可见性与 tenant 可用性不是同一个控制面
   - tenant 菜单/页面主要由套餐 feature -> permission grant 控制
   - runtime gate 又由 `scope: all_tenants` 宽放行
   - tenant 真正是否 ready 则要等 prerequisites 才知道

2. tenant readiness 与实际对账采集不是同一个事实源
   - tenant prerequisites 看的是 tenant effective storage context
   - provider profile / reconciliation 看的是 platform storage context

3. tenant 看到的不是资源级费用明细，而是汇总账单
   - ledger 与 UI 都是聚合后的 provider/basis 级视图

因此当前系统的真实状态更接近：

- “一个可以工作的官方账单汇总插件”
- 但还不是“语义完全清晰、tenant gate 完整、能表达资源级费用明细的成熟计费系统”

## 2. 当前已确认问题

### P1

1. tenant 账单读取接口没有把 prerequisites 作为硬门槛。
   - `tenant` API 直接读取 statement / statements / charges / export，没有先要求 `storage_billing_enabled`、当前 driver、binding readiness 全部满足。
   - 证据：
     - `backend/plugins/storage-billing/backend/api/tenant.py`
     - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`

2. binding 与当前 active driver 不一致时只记 warning，不会落成 invalid。
   - `_validate_binding_data()` 对 current driver mismatch 只追加 warning。
   - 最终 `validation_status` 只由 `errors` 是否为空决定，因此 mismatch binding 仍可能是 `valid`。
   - 证据：
     - `backend/plugins/storage-billing/backend/services/binding_service.py`

3. tenant prerequisites 没有把“当前 provider profile 已禁用/失效”作为 ready 的硬门槛。
   - `get_tenant_prerequisites()` 只使用历史保存的 binding.validation_status 与 current driver 计算 ready。
   - provider profile 当前状态没有并入 `missing_reasons`。
   - 证据：
     - `backend/plugins/storage-billing/backend/services/binding_service.py`

4. 历史 `valid` binding 在 profile/runtime 健康状态变化后，仍可能造成 stale ready。
   - 如果变化直接导致 `current_driver` 不再匹配，当前实现会落成 `binding_provider_mismatch`。
   - 但如果变化的是 profile enabled / validation errors / driver plugin enabled 等运行时健康状态，而不是 provider_code 与 current_driver 的字符串关系，tenant 仍可能继续 `ready=true`。
   - 证据：
     - `backend/plugins/storage-billing/backend/services/binding_service.py`
     - `backend/plugins/storage-billing/backend/services/profile_service.py`

5. tenant 可见性的真实控制面是“套餐 feature -> tenant_plan_permissions”，不是 plugin scope / assignment。
   - `storage_billing_enabled` 被映射到 `storage-billing`，再授予 tenant scoped plugin permissions。
   - 插件自己又声明 `manual_entitlement`，生命周期 auto-grant 被跳过，plan entitlement 成为权威来源。
   - 证据：
     - `backend/app/services/tenant/tenant_plan_plugin_entitlement_service.py`
     - `backend/plugins/storage-billing/plugin.yaml`
     - `backend/app/plugins/lifecycle.py`

### P2

6. `manifest.scope=all_tenants` 与“管理端 + 部分企业”的业务语义存在冲突。
   - 当前 scope 会让 runtime gate 把所有 tenant 视为 scope 允许。
   - 真正限制 tenant 菜单/页面的是 feature-permission，不是 assignment。
   - 证据：
     - `backend/plugins/storage-billing/plugin.yaml`
     - `backend/app/core/scope.py`
     - `backend/app/plugins/runtime_gate.py`

7. 前端几乎没有接入权限桥接，CTA 仍有“点了再 403”的风险。
   - admin / tenant 页面里没有显式使用 `NovusPluginShared.getAccessCodes()` / `hasAccessByCodes()`。
   - tenant 导出按钮、admin 对账/绑定相关操作没有细粒度 permission gating。
   - 证据：
     - `backend/plugins/storage-billing/frontend/src/index.ts`
     - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`
     - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

8. tenant 页面在确认 prerequisites 之前就并行请求账单接口。
   - `loadPage()` 先并行请求 `getTenantPrerequisitesApi()`、`getCurrentStatementApi()`、`getTenantStatementsApi()`。
   - 这会把“可见性/就绪校验”和“实际账单读取”拆成两条并行链路，形成先读数据、后显示 not ready 的模型。
   - 证据：
     - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

9. host preflight 只检查“storage-billing 插件 + 任一云驱动插件启用”，没有把“当前 active storage driver 已切到 billable cloud driver”作为 plan/tenant 前置阻断。
   - 这与实施规范正文不完全一致。
   - 证据：
     - `backend/app/plugins/feature_entitlement_guards.py`
     - `backend/plugins/storage-billing/docs/implementation-spec.zh-CN.md`

10. host preflight 当前能阻断的是“feature 开启但 billing 插件不存在 / 没有任何云驱动插件启用”，阻断不了的是“feature 已发、tenant 页面才发现 not ready”这类半开半关状态。
   - host 侧已阻断：
     - `storage-billing` 插件未启用
     - 三个 billable cloud driver 插件一个都没启用
     - 停用 `storage-billing` 本体且 active plans 仍在使用
     - 停用最后一个 billable cloud driver 且 active plans 仍在使用
   - host 侧未阻断：
     - 当前 platform active driver 不是 billable cloud driver
     - tenant 当前不是 platform storage mode
     - provider profile disabled / invalid
     - binding 缺失 / binding mismatch / binding invalid
   - 这些条件都要等 tenant prerequisites 或页面阶段才暴露。
   - 证据：
     - `backend/app/plugins/feature_entitlement_guards.py`
     - `backend/plugins/storage-billing/backend/services/binding_service.py`
     - `backend/plugins/storage-billing/backend/api/tenant.py`

### P3

11. tenant 侧当前更像“费用汇总”，不是足够细的“费用明细”。
   - `StorageTenantDailyCharge` 的唯一键不含 bucket/domain/account/tag。
   - 落账时按 `(tenant, charge_basis, currency)` 聚合，同一天同 provider 下多个 bucket/domain/account/tag 会被合并到一条 charge row，scope 维度仅保存在 `details_json.scope_values`。
   - tenant UI 也只展示 provider / basis / usage / amount / currency。
   - 证据：
     - `backend/plugins/storage-billing/backend/models/ledger.py`
     - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`
     - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

12. tenant prerequisites 当前会把所有 provider 的 capabilities 都返回给 tenant，而不是只返回当前 active provider。
   - 如果产品目标是“企业只关心自己当前账单来源”，这会制造理解噪音。
   - 证据：
     - `backend/plugins/storage-billing/backend/services/binding_service.py`
     - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

13. tenant readiness 与实际对账采集不是同一个事实源。
   - tenant prerequisites 使用企业自己的有效存储上下文。
   - provider profile 校验与 reconciliation billable driver 选择只认平台对象存储上下文。
   - 尤其在“平台 active driver 或 tenant storage mode 已切换，但旧 binding.validation_status 还停留在历史 valid”时，tenant 可能继续显示 ready，而平台对账已经不会再采集对应 provider。
   - 证据：
     - `backend/app/services/common/storage_config_resolver.py`
     - `backend/app/plugins/host_read_facade.py`
     - `backend/plugins/storage-billing/backend/services/binding_service.py`
      - `backend/plugins/storage-billing/backend/services/profile_service.py`
      - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`

14. 当前前端交互模型更接近“半开半关”，不符合本项目插件规范。
    - tenant 页面即使 `prerequisites.ready === false`，仍继续渲染 statement / statements / charges / export 区块。
    - admin / tenant 页面都在 `onMounted()` 时直接发请求，没有先做前端 permission gate。
    - 证据：
      - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`
      - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

15. `billing_statement:list` 这个动作码已声明，但 tenant 侧接口没有真正消费。
    - `statement/charges` 仍然使用 `billing_portal:view`，只有导出使用 `billing_statement:export`。
    - 这让“账单门户权限”和“账单明细权限”继续混在一起。
    - 证据：
      - `backend/plugins/storage-billing/plugin.yaml`

16. admin 只读角色页面会误打宿主 `tenant:select` 接口，导致 `billing_admin:view` 也可能首屏 403。
    - `loadAll()` 无论当前角色是否具备 `billing_admin:configure`，都会并行请求 `/admin/tenants/select`。
    - 宿主 `/admin/tenants/select` 需要 `tenant:select`，并不属于 storage-billing 自己的 view 权限闭环。
    - 因此只读对账角色会出现“插件菜单能进，但页面首屏直接失败”的权限串扰。
    - 证据：
      - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`
      - `backend/app/api/admin/tenants.py`

17. tenant 只有 `billing_portal:view`、没有 `billing_statement:list` 时，当前账单卡片会被前端误清空。
    - tenant 页面已经把“账单明细”权限拆到 `billing_statement:list`，但 summary / current statement 的展示状态仍绑在 `selectedStatement` 上。
    - `loadPage()` 在拿到 `current statement` 之后还会继续调用 `loadChargesForDate()`；该函数在无明细权限时会把 `selectedStatement` 置空。
    - 最终导致“有门户查看权、也能读当前账单接口，但页面上看到的是空状态”。
    - 证据：
      - `backend/plugins/storage-billing/frontend/src/views/tenant/index.vue`

18. 当前 statement 模型本身也是汇总账单，不是资源级明细账单。
    - `StorageTenantStatement` 只保留 `amount_total / charge_count / summary_json` 这种 period 级聚合信息，没有 statement line 层。
    - tenant API 只是返回汇总 statement + 聚合 charge rows。
    - 证据：
      - `backend/plugins/storage-billing/backend/models/ledger.py`
      - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`

19. 当前没有立即可见的“多 source 覆盖”线上 bug，但存在结构性潜在风险。
    - `_replace_daily_charges_for_source()` 会先删除同 `provider_code + period_type + billing_date` 的现有 charge rows，再写本次 source 的结果。
    - 现在每个 provider/day 基本只有一个 `BillingFetchResult`，所以暂时不容易炸。
    - 但如果未来同一 provider/date 返回多个 source 分片，这里会把前面 source 写出的 rows 清掉。
    - 证据：
     - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`

## 3. 已确认正确的部分

1. 宿主对象存储配置仍是运行时单一事实源，插件没有复制 AK/SK / region / bucket。
2. `local` 不计费、只认当前 active cloud driver、host preflight 与 feature entitlement guard 已落地。
3. 现有后端测试基线通过：
   - `pytest backend/tests/services/test_storage_billing_provider_profile_service.py backend/tests/plugins/test_storage_billing_admin_services.py backend/tests/services/test_storage_billing_binding_service.py backend/tests/services/test_storage_billing_reconciliation_service.py backend/tests/plugins/test_storage_billing_tenant_services.py backend/tests/services/test_storage_billing_host_preflight.py -q`
   - 结果：`54 passed`
4. 但当前测试基线没有覆盖以下关键裂缝：
   - tenant effective storage context 与 platform storage context 分裂
   - platform active driver / tenant storage mode 变化后，旧 binding.validation_status 残留导致的 stale ready
   - tenant API 在 prerequisites 未就绪时仍可直接读取历史 statement / charges

## 4. 本轮六个深审方向

1. scope / tenant assignment 语义是否与“管理端 + 部分企业”一致
2. 套餐 feature、权限同步、tenant menu policy 是否闭环
3. binding / prerequisites / tenant readiness 是否严格正确
4. reconciliation / ledger / statement model 是否真能表达“企业自己的费用明细”
5. 宿主对象存储复用是否完全去重、是否仍有宿主配置复制风险
6. 前端页面是否遵守插件 skill / rules / 权限桥接 / 多语言 / CTA 规范

## 5. 处理原则

这一轮先深审、补证据、补记录，不仓促修。

修复前必须先回答三件事：

1. 真实产品语义到底是“套餐驱动可见性”还是“插件 assignment 驱动可见性”
2. tenant 看到的是“账单汇总”还是“资源级明细”
3. `storage-billing` 是否允许 tenant 在自身 custom/admin_override 存储模式下继续展示，还是只支持平台统一存储

## 6. 后续输出格式

后续统一处理前，结论按以下结构汇总：

1. Findings
2. Evidence
3. Spec mismatch
4. Risk
5. Recommended fix order

## 7. 当前风险分层

### A. 会直接导致错误业务结果

- tenant 在 prerequisites 未 ready 时仍可读取历史账单
- binding 与当前 active driver 不一致仍可能显示为 `valid`
- provider profile / driver plugin 当前失效时，tenant 仍可能 `ready=true`
- tenant effective storage context 与 platform storage context 分裂，可能导致“页面 ready 但永远不对账”
- 当前平台 driver 插件被禁用/卸载时，active plan 仍可能继续保留 feature，造成控制面与运行时脱节
- stale binding 可能在 tenant 已失去 feature 或切到自管存储后继续参与 charge row 写入
- allocation 存在 unmatched / ambiguous item 时，run 仍可能显示为 `completed`
- historical run charge detail 依赖 live `StorageTenantDailyCharge` 时会被 rerun 覆盖，run detail 不具备快照不可变性
- 当前 `StorageTenantDailyCharge` 仍是 tenant/provider/charge_basis 聚合行，不是资源级账单 line-item

### B. 会持续制造语义漂移或维护误判

- `scope: all_tenants` 与“管理端 + 部分企业”口径冲突
- tenant 可见性真实控制面是 feature entitlement，但 manifest / scope / runtime gate 没把这个表达清楚
- host preflight 与 tenant prerequisites 不是同一层级的硬门槛
- `billing_statement:list` 已声明但未实际消费

### C. 会让前端交互长期不稳定

- admin / tenant 页面先请求再看权限
- CTA 没有按细粒度 permission gating
- tenant 页面在 not ready 时仍继续暴露 statement / charges / export
- admin 只读角色会被不必要的 `/admin/tenants/select` 请求拖成 403
- tenant 门户只读角色会把当前账单卡片误清空
- tenant 页面把所有 provider capabilities 都展示给企业用户

### D. 与“费用明细”产品语义不一致

- ledger 只保留按 tenant / provider / charge basis 聚合后的 charge row
- tenant 页面展示的是汇总账单，不是资源级明细

## 8. 建议处理顺序

### 第一批：先修硬错误

1. 把 tenant API 改成 prerequisites hard gate
2. 把 binding current-driver mismatch 升级为 invalid
3. 把 provider profile disabled / invalid / driver plugin disabled 并入 `ready` 计算
4. 明确统一事实源：
   - 如果业务是“只对平台统一存储计费”，统一使用 platform storage context

### 第二批：再修模型表达

5. 明确 tenant 可见性模型到底是：
   - 套餐开通企业
   - 还是手工指定企业
6. 如果继续走套餐模型：
   - 文档里明确 tenant 可见性由 feature entitlement 控制
   - 收敛 `scope` 语义，避免误读
7. 如果改成手工指定企业：
   - scope 改为 `admin_and_selected_tenants`
   - assignment 成为唯一来源

### 第三批：最后修前端规范闭环

8. 接入 `NovusPluginShared` 权限桥接
9. admin / tenant 页面首屏请求前做 permission gate
10. CTA 按具体 permission 拆分 gating
11. tenant 页面未 ready 时不再继续展示 statement / charges / export 工作流

### 第四批：决定产品层到底要“汇总”还是“明细”

12. 如果只需要汇总：
   - 改文案，不再称“费用明细”
13. 如果需要真正明细：
   - 新增资源级 charge line 模型
   - bucket/domain/account/tag 变成一等字段

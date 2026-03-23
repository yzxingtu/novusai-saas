# 对象存储官方账单对齐计费插件方案（2026-03-23）

## 1. 文档目的

本文档用于规划 NovusAI SaaS 在“对象存储流量收费”场景下的正式实现边界、官方对账口径、平台架构与实施路线。

目标不是做一个“下载次数统计功能”，而是建立一套遵循云厂商官方账单能力的收费体系：

1. 平台只对云对象存储收费，本地存储不参与流量收费。
2. 计费口径优先使用厂商官方账单、官方账单订阅文件、官方财务 API。
3. 存储驱动插件只负责上传、下载、签名 URL、图片处理等驱动职责，不承载跨租户账单、结算、对账和商业规则。
4. 主体实现建议采用独立 full-module 插件，按“官方账单真相源 + 平台租户映射 + 结算任务”三层结构实现，避免把结算逻辑散落在 `aliyun-oss`、`qiniu-kodo`、`tencent-cos` 等插件中。

## 2. 关键结论

### 2.1 是否写进 OSS/COS/Qiniu 插件，还是做独立插件

结论：适合做独立插件，但不应写进单个存储插件。

原因：

1. 当前插件体系已经支持完整业务插件，而不只是驱动插件。开发者指南明确支持 full-module 插件自带 `DB/API/前端/迁移/定时任务`，因此这个能力完全可以作为独立业务插件落地，而不必写死在 `backend/app` 主工程里。[plugin-developer-guide.md](../../docs/guides/plugin-developer-guide.md)
2. 当前存储插件的职责是“驱动扩展”，不是“商业结算扩展”。现有三个插件只声明了 `storage:read` 和 `storage:write` 能力，配置也明确由平台存储设置统一管理，而不是插件自管配置。[aliyun-oss/plugin.yaml](../../backend/plugins/aliyun-oss/plugin.yaml) [qiniu-kodo/plugin.yaml](../../backend/plugins/qiniu-kodo/plugin.yaml) [tencent-cos/plugin.yaml](../../backend/plugins/tencent-cos/plugin.yaml)
3. 官方账单拉取、跨厂商调度、租户账单映射、日结/月结、补差、月关账，都属于跨厂商、跨租户、跨套餐的商业结算逻辑，不是某个驱动特有逻辑。
4. 若把结算写进某个存储插件，会出现同一平台规则在三个插件中重复实现的问题，包括：
   - 账单落库规则
   - 租户绑定规则
   - 正式结算与补差规则
   - 账期冻结规则
   - 管理端账单页面
5. 若做成独立插件，未来新增华为云 OBS、AWS S3、中国移动 EOS 时，只需扩展该账单插件的 provider 适配器，不需要在每个存储驱动插件里重复复制商业逻辑。
6. 但这个方案不是“零主工程改动”。当前宿主没有 `tenant_plan` 生命周期钩子，也没有“插件停用前 veto”扩展点，因此仍需要在主工程补最小扩展点，让独立插件能合法接管套餐校验和依赖阻断。

### 2.2 官方口径下，什么才算“严格对齐”

“严格对齐”必须拆成两个层次：

1. 厂商账单真相源对齐：平台认的总费用必须来自厂商官方账单文件或官方财务 API。
2. 租户费用分摊对齐：平台把厂商账单中的某部分费用分配给某个租户时，必须依赖厂商认可的资源维度，例如 bucket、domain、tag、bill item、split item。

只有同时满足这两个层次，平台内部账单才算“官方对齐”。

### 2.3 本地存储是否收费

本方案明确规定：

1. `local` 驱动不参与流量收费。
2. 本地存储继续保留现有容量配额和单文件大小限制。
3. 云对象存储计费驱动仅包括：
   - `aliyun-oss`
   - `qiniu-kodo`
   - `tencent-cos`

## 3. 官方能力与约束总表

| 厂商 | 官方能力 | 日级数据窗口 | 月度最终窗口 | 适合作为平台真相源 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 阿里云 OSS | BSS OpenAPI + 账单订阅到 OSS | 每日 18:00 前推送前一天全量或本月至今全量数据 | 次月 3 日或 4 日 18:00 前推送月度最终数据 | 是 | 分账账单适合成本分摊，不适合作为开票/结算依据 |
| 腾讯云 COS | 账单存储至 COS + `DescribeBillDetail` | Day+1 03:00-22:00 或 08:00-13:00 分批投递；系统日账单通常约 08:00 生成 | 每月 2 日或 4 日更新月度完整账单 | 是 | 文档支持按存储桶出账，最适合做 bucket 级租户计费 |
| 七牛 Kodo | 财务对外 API + 分账账单 | 当天快照需 08:00 后调用 | 按量计费账单每月 4 号出账，建议 5 号后查看上月账单 | 是，但需区分“正式账单”和“内部资源分摊” | 分账账单支持 bucket/domain 维度，但官方明确其不作为对账依据 |

## 4. 官方规则摘录与实现影响

### 4.1 阿里云

官方能力：

1. 阿里云支持把账单自动订阅到 OSS，也支持通过 BSS OpenAPI 查询账单与分账数据。
2. 账单订阅可选择“计费项账单明细”“实例明细账单”“分账账单按天汇总”等文件类型。
3. 官方说明：
   - 每日 18:00 前推送前一天全量数据。
   - 次月 3 日或 4 日 18:00 前推送月度最终全量数据。
4. 阿里云账单分析文档明确指出：
   - OSS 费用包含“存储费用”“外网流出流量费用”“请求费用”“数据处理费用”“数据取回费用”“传输加速费用”。
   - OSS 支持基于 Bucket 的分账，可通过 Bucket 标签和分拆项定位成本归属。

实现影响：

1. 阿里云应优先采用“账单订阅到 OSS”模式，不建议只依赖在线 API 逐条查询。
2. 平台日结不能在 `03:00` 直接正式结算“昨天”，因为阿里云日账通常要到当日 `18:00` 前才稳定。
3. 阿里云的“分账明细”适合内部租户分摊，但官方文档中该数据用于内部成本管理，不作为结算或开票依据。因此：
   - 对外部客户的正式 pass-through 账单，建议以官方消费明细或计费项明细为总额真相源。
   - Bucket/标签分摊只作为租户分配依据，不作为厂商账单真相源本身。

### 4.2 腾讯云

官方能力：

1. 腾讯云支持“账单存储至 COS 桶”。
2. 文档提供多种文件类型：
   - 标准账单日明细
   - 分账账单日明细
   - 消耗账单日明细
   - 月明细
3. `DescribeBillDetail` 是官方在线账单明细 API，但官方明确说明数据量大时更建议使用“账单存储到 COS”。
4. COS 按量计费官方文档明确说明：
   - 各计费项按日结算。
   - 费用在次日结算。
   - 日账单通常在 `08:00` 左右生成。
5. 腾讯云 COS 官方 FAQ 明确支持“按存储桶出账”。

实现影响：

1. 腾讯云是三家里最适合做“Bucket 级租户计费”的厂商。
2. 对腾讯云场景，推荐的正式策略是：
   - 一个付费租户绑定一个专属 bucket。
   - 平台启用按存储桶出账。
   - 日结以 COS 账单文件为主，`DescribeBillDetail` 作为补查接口。
3. 由于腾讯云日账单通常在 `08:00` 左右生成，因此 `03:00` 不适合结算昨天，只适合结算前天。

### 4.3 七牛

官方能力：

1. 七牛提供财务对外 API。
2. 官方文档说明：
   - 按量计费账单每月 4 号出账。
   - 为保证完整性，建议 5 号后查看上月账单。
3. 七牛提供“按量计费预估每日快照详情接口”，并明确要求：
   - 如请求当天数据，请在上午 `08:00` 后调用。
4. 七牛提供“分账账单详情接口”，资源维度可到：
   - `bucket`
   - `domain`
5. 但七牛“分账账单”文档明确说明：
   - 其用途是企业内部成本分摊参考。
   - 不作为对账依据。

实现影响：

1. 七牛不能把“分账账单详情”直接当作正式厂商结算真相源。
2. 七牛应采用“双层口径”：
   - 第一层：月结算单详情 / 每日快照作为厂商真相源。
   - 第二层：分账账单详情作为 bucket/domain 分配依据。
3. 如果业务要求“某租户账单必须与七牛官方账单一一对应，且可作为对外收费依据”，推荐策略不是共用一个七牛账号下多个 bucket，而是：
   - 一租户一七牛账号，或者
   - 一租户一独立结算主体。

## 5. 平台正式设计决策

### 5.1 收费范围

平台只对以下费用项开放“租户二次收费”能力：

1. 外网下行流量
2. CDN 回源流量
3. 传输加速流量
4. 图片处理、数据处理等与下载链路紧耦合且厂商明确独立计费的费用

平台暂不在第一阶段对以下项目做租户二次收费：

1. 上传流量
2. 请求次数
3. 存储容量
4. 数据取回
5. 生命周期、清单、对象标签等管理功能费用

说明：

1. 存储容量配额仍然由现有套餐能力控制，不并入本方案。
2. 后续若要扩大收费项，仍在账单插件内核增加，不进入驱动插件。

### 5.2 插件职责边界

存储驱动插件保留以下职责：

1. 上传文件
2. 生成签名 URL
3. 删除对象
4. 获取对象信息
5. 图片处理 URL 拼接
6. 厂商 SDK 适配

存储驱动插件不承载以下职责：

1. 租户账单映射
2. 厂商账单拉取调度
3. 日结/月结
4. 月度补差
5. 租户超额策略
6. 套餐计费规则
7. 管理端账单页面

独立账单插件承载以下职责：

1. 厂商账单采集
2. 官方账单解析
3. 租户账单绑定与对账
4. 日结/月结/补差
5. 套餐 entitlement 校验逻辑
6. 管理端与租户端账单页面
7. 依赖影响分析与运维工具

### 5.3 严格模式下的租户资源映射规则

平台提供两种官方模式：

1. `official_reconciled`
   - 以厂商官方账单为真相源。
   - 允许使用厂商官方的 bucket/tag/split 明细做租户分摊。
   - 适合平台内部计费与企业内部成本归集。
2. `official_pass_through`
   - 要求租户费用与厂商账单可直接一一映射。
   - 必须使用独立可结算范围，例如独立 bucket、独立账号、独立 domain、独立 billing owner。
   - 若厂商官方仅提供“内部成本分摊”型数据，不允许该模式落地。

各厂商建议：

1. 腾讯云 COS：
   - 推荐 `official_pass_through`
   - 条件：一租户一 bucket，并启用按存储桶出账
2. 阿里云 OSS：
   - 推荐 `official_reconciled`
   - 若要 `official_pass_through`，建议一租户一结算账号或一租户一明确财务主体，不建议只依赖分账账单
3. 七牛 Kodo：
   - 默认只支持 `official_reconciled`
   - 若要 `official_pass_through`，建议一租户一七牛账号

## 6. 插件架构方案

### 6.1 新增独立 full-module 插件

建议把主体实现做成独立插件，例如 `storage-billing`，而不是继续放在 `backend/app` 主工程里，也不是写进 `aliyun-oss` / `qiniu-kodo` / `tencent-cos`。

建议目录：

```text
backend/plugins/storage-billing/
  plugin.yaml
  README.md
  backend/
    main.py
    api/
    services/
    repositories/
    models/
    tasks/
    hooks/
    migrations/versions/
  frontend/
    src/
  locales/
    zh-CN.json
    en.json
```

推荐插件能力：

1. `db:own_tables`
   - 账单插件自管账单表、绑定表、任务表
2. `http:outbound`
   - 访问阿里云、腾讯云、七牛官方财务 API
3. `notifications:send`
   - 账单异常、同步失败、超额提醒

推荐 manifest 方向：

1. `scope`
   - 推荐 `all_tenants`
   - 若希望灰度开放给特定企业，也可选 `admin_and_selected_tenants`
2. `extensions.api`
   - 同时提供 `admin_routes` 和 `tenant_routes`
3. `extensions.frontend.pages`
   - 提供管理端账单中心和租户端账单中心页面
4. `extensions.tasks`
   - 注册 `03:00` 正式日结、`11:00` 预估更新、`19:00` 官方补齐等定时任务

说明：

1. 不建议把三个存储驱动插件都写进 `dependencies.plugins`。
2. 原因不是不能依赖插件，而是当前 manifest 依赖模型表达的是“全部依赖必须满足”，无法表达“七牛/OSS/COS 任意一个即可”。
3. 因此“至少安装并启用一个对象存储插件”必须通过账单插件自身的 runtime preflight 和宿主校验完成，而不是靠 manifest 静态依赖表达。

### 6.2 插件内核心组件

1. `StorageBillingAdapter`
   - 每个厂商一个适配器
   - 负责读取官方账单文件或官方财务 API
2. `StorageBillingScopeResolver`
   - 负责把厂商资源维度映射到平台租户
   - 例如 bucket、domain、tag、account
3. `StorageBillingReconciler`
   - 负责“厂商真相源总额”和“平台租户分配总额”对齐
4. `StorageBillingSettlementService`
   - 负责日结、月结、补差、关账
5. `StorageBillingEntitlementService`
   - 负责套餐 entitlement、插件前置依赖和租户激活前置检查
6. `StorageBillingScheduler`
   - 负责定时任务调度

### 6.3 插件自管数据模型建议

建议由账单插件自管数据表，而不是继续把统计写进 `attachments.meta`。

建议表前缀：`px_storage_billing_*`

建议表：

1. `px_storage_billing_scopes`
   - `tenant_id`
   - `provider`
   - `billing_mode`
   - `scope_type`
   - `scope_value`
   - `account_identifier`
   - `bucket_name`
   - `domain_name`
   - `tag_key`
   - `tag_value`
   - `is_active`
2. `px_storage_billing_raw_statements`
   - 保存官方原始账单文件或 API 快照元信息
   - 用于审计、重放和补算
3. `px_storage_billing_vendor_daily`
   - 保存厂商日级真相源
   - 粒度至少到 `provider + account + bill_date + item_type + resource_scope`
4. `px_storage_billing_tenant_daily`
   - 保存租户日结结果
   - 粒度至少到 `tenant + provider + settle_date + charge_type`
5. `px_storage_billing_month_closings`
   - 保存月关账结果、补差结果、锁账状态
6. `px_storage_billing_runs`
   - 保存每次采集、对账、结算任务的运行记录

### 6.4 宿主需要补的最小扩展点

独立插件方案可行，但宿主仍需补最小扩展点，否则插件无法干净接管关键校验链路。

建议新增：

1. `tenant_plan` 生命周期扩展点
   - 至少覆盖：创建套餐、更新套餐、企业切换套餐
   - 用于账单插件拦截“套餐已开对象存储计费，但前置插件条件不满足”的保存请求
2. 插件禁用/卸载前的 veto 扩展点
   - 当前只有 `system.plugin.disabled` 这种事后 hook，不足以提前阻断
   - 需要在真正 disable/uninstall 前允许账单插件返回“不可继续”的业务结果
3. 可复用的已启用对象存储驱动查询接口
   - 账单插件与宿主共用同一份驱动真相源，避免各自扫描插件 manifest

说明：

1. 这些是宿主通用扩展点，不属于账单业务本身。
2. 账单采集、对账、日结、月结、页面、表结构仍归独立插件所有。

### 6.5 账单真相源优先级

账单插件统一采用以下优先级：

1. 厂商账单落地文件
2. 厂商财务 API 正式明细
3. 厂商预估快照
4. 平台应用日志

说明：

1. 第 4 层只允许用于监控和异常排查，不允许用于正式扣费。
2. 现有项目里的 `download_count` / `download_bytes` 只能作为辅助观测值，不可作为正式收费依据。

### 6.6 深入审计结论

基于当前仓库实现，独立 `storage-billing` 插件方案的结论不是“不可行”，而是“可行，但宿主尚未具备完整承载条件”。

#### 6.6.1 当前已经具备的能力

以下能力宿主已经具备，说明独立插件方向是成立的：

1. full-module 插件模型已存在
   - 插件可以自带 `DB/API/前端/迁移/定时任务`
2. 插件自管表已具备标准沙箱
   - `db:own_tables` 允许插件只操作 `px_{plugin}_*` 表
3. 插件 API 已具备 admin/tenant/public 三端统一分发
4. 插件前端页面和菜单扩展已具备
5. 插件定时任务已具备注册、启停、卸载联动
6. 插件运行时闸门已具备
   - 可按 `status + scope + license` 控制插件是否对某企业可见
7. 插件可按企业做可见性分配
   - `ResourceTenantAssignment` 已可表达 `selected_tenants` / `admin_and_selected_tenants`

这意味着：

1. 账单采集
2. 账单解析
3. 自管账单表
4. 账单中心前后端页面
5. 定时同步任务

以上都适合直接放进独立插件。

#### 6.6.2 当前的硬缺口

以下问题若不补，独立插件方案会在实现中途卡住：

1. 缺少 `tenant_plan` 生命周期 preflight
   - 当前套餐创建、更新直接走 `AdminPlanController -> TenantPlanService`
   - 没有“保存前让插件校验”的标准入口
2. 缺少企业绑定/切换套餐的 entitlement 校验入口
   - 当前 `AdminTenantController` 和 `TenantService` 直接接受 `plan_id`
   - 没有“切换到某套餐前先校验账单插件前置条件”的标准入口
3. 缺少插件停用/卸载前 veto
   - 当前只有 `system.plugin.disabled` 这类事后 hook
   - 账单插件无法在真正 disable/uninstall 前阻断宿主操作
4. 插件沙箱无法合法读取宿主核心数据
   - `PluginDbProxy` 只允许访问本插件 `px_*` 表
   - `PluginContext` 没有读取 `tenant_plans`、插件状态、平台配置、企业存储上下文的正式只读 API
5. tenant 插件菜单会被自动授予所有活跃套餐
   - 当前 `_auto_grant_plugin_menus_to_plans()` 会把 tenant 端插件菜单权限自动写给全部活跃套餐
   - 这与“只有开启 `storage_billing_enabled` 的套餐才能显示账单中心”直接冲突
6. 驱动插件 `force` 停用会自动降级到 `local`
   - 当前 `_check_storage_driver_in_use(..., force=True)` 会自动把平台或企业存储模式切回 `local`
   - 这与“本地不收费”和“账单链路不可静默断裂”冲突
7. 插件 action 权限未形成完整 DB/RBAC 闭环
   - 当前插件 `extensions.permissions` 已注册到内存，但宿主现有 `sync_plugin_permissions()` 只同步插件菜单权限
   - 这意味着 tenant 端插件 API 若依赖标准 `permission_code:action` 校验，RBAC 仍不完整

#### 6.6.3 当前的次级缺口

以下不是第一优先级阻塞项，但最好一并规划：

1. 插件级企业配置写入通道不足
   - 当前 `PluginContext` 只有 `get_tenant_config()`，没有标准 `update_tenant_config()`
   - 不过账单插件可以优先把租户绑定关系写入自有 `px_storage_billing_*` 表，因此这不是第一阶段 blocker
2. manifest 依赖语义只有 AND，没有 OR
   - 这会影响“依赖七牛/OSS/COS 任意一个”的表达
   - 第一阶段只能靠 runtime preflight 解决

#### 6.6.4 宿主必须补的四个能力

如果独立插件方案要落地，建议宿主至少补以下四项：

1. `tenant_plan` entitlement preflight registry
   - 在套餐创建、更新、企业切换套餐前统一调用
2. `before_plugin_disable` / `before_plugin_uninstall` veto registry
   - 允许账单插件在真正禁用前返回阻断结果
3. 插件侧可用的宿主只读 facade
   - 例如：
     - 获取已启用对象存储驱动列表
     - 获取某套餐 feature 快照
     - 获取企业当前有效存储上下文
     - 获取平台存储驱动与插件状态摘要
4. tenant 插件菜单授权策略可配置
   - 至少支持对某类插件关闭“启用时自动授予全部活跃套餐”
   - 改为由业务插件或宿主 entitlement 服务按套餐 feature 精确授予
5. 插件 action 权限同步到 DB 的标准能力
   - 让 `extensions.permissions` 与 tenant/admin RBAC 真正打通
   - 避免 tenant 端插件 API 只能依赖菜单可见性或 owner 超权

#### 6.6.5 结论收束

因此，当前最准确的结论是：

1. “做独立插件”是对的
2. “完全不改宿主，只靠现有插件体系直接做完”是不成立的
3. 最合理的方式是：
   - 把账单主体逻辑放进 `storage-billing`
   - 把 entitlement/veto/只读 facade/菜单授权策略/插件 action 权限同步这五类通用能力补进宿主

## 7. 定时任务与结算窗口

### 7.1 每天 03:00 是否能跑

能跑，但不能正式结算“昨天”。

正式规则：

1. 每天 `03:00` 执行“D-2 正式日结”
2. 每天 `11:00` 可选执行“D-1 预估更新”
3. 每天 `19:00` 可选执行“D-1 官方补齐更新”

原因：

1. 腾讯云日账单通常在 `08:00` 左右生成。
2. 七牛当天快照要求 `08:00` 后调用。
3. 阿里云前一天全量账单通常在 `18:00` 前推送。

因此：

1. `03:00` 是稳定的“前天正式结算时间”
2. “昨天”只能做预估，不宜正式关账

### 7.2 月结与补差

建议账单插件月结规则：

1. 每月 `06` 日 `03:00`
   - 锁定上月月账
   - 生成补差记录
2. 若厂商月度最终账单晚到：
   - 不覆盖已锁账结果
   - 新增“月度补差单”

厂商参考窗口：

1. 阿里云：
   - 月账单 PDF 次月 2 日 12:00 后
   - 消费明细次月 3 日 12:00 后
   - 分账明细次月 4 日 12:00 后
2. 腾讯云：
   - 月明细通常 2 日更新
   - 分账月明细通常 4 日更新
3. 七牛：
   - 按量计费账单每月 4 号出账
   - 官方建议 5 号后查看上月账单

## 8. 厂商接入策略

### 8.1 阿里云

主方案：

1. 使用 `SubscribeBillToOSS`
2. 把官方账单文件推到专用账单 Bucket
3. 账单插件从专用 Bucket 拉取账单文件
4. 必要时使用 `DescribeInstanceBill` / `DescribeSplitItemBill` 等 BSS OpenAPI 补查

不建议：

1. 直接从业务对象存储 Bucket 内扫描账单文件
2. 在 `aliyun-oss` 插件里直接调 BSS OpenAPI

### 8.2 腾讯云

主方案：

1. 开启“账单存储至 COS 桶”
2. 选择：
   - 消耗账单日明细
   - 标准账单日明细
   - 分账账单日明细
3. 账单插件从专用账单 COS 桶拉取账单 zip
4. `DescribeBillDetail` 仅作为补查接口

推荐配置：

1. 启用按存储桶出账
2. 每个付费租户独立 bucket

### 8.3 七牛

主方案：

1. 使用财务对外 API
2. 每日通过“按量计费预估每日快照详情接口”拉取预估日账
3. 每月通过“月结算单详情接口”获取正式月账
4. 如需 bucket/domain 分摊，使用“分账账单详情接口”

重要限制：

1. 七牛分账账单不作为对账依据
2. 因此 bucket/domain 分摊应被视为“官方辅助分摊口径”，不是厂商正式结算单本身

## 9. 管理端与租户端能力规划

### 9.1 管理端

由 `storage-billing` 插件新增管理端页面：

1. 对象存储计费总览
2. 厂商账单同步任务
3. 租户账单绑定关系
4. 日结结果
5. 月结与补差
6. 对账异常中心

### 9.2 租户端

由 `storage-billing` 插件新增租户端页面：

1. 云对象存储账单概览
2. 当月预估费用
3. 已结算日账
4. 月账与补差
5. 资源范围明细

### 9.3 套餐配置

套餐层新增的不是“流量硬编码规则”，而是“能力开关 + 可见性 + 前置依赖”。

结合当前仓库现状：

1. 套餐后端当前通过 `quota` 和 `features` 两个 JSON 字段承载扩展能力。
2. 套餐请求结构在 `backend/app/schemas/tenant/plan.py` 的 `QuotaSchema` / `FeaturesSchema` 中定义。
3. 套餐保存逻辑在 `backend/app/services/tenant/tenant_plan_service.py`。
4. 管理端套餐表单在 `frontend/apps/web-antd/src/views/admin/tenant/plans/data.ts`。

因此第一阶段建议继续沿用现有结构，不额外新建 `plan_plugin_bindings` 表，先把“套餐 entitlement + 插件依赖校验 + 运行时守卫”落地。

#### 9.3.1 第一阶段推荐字段

`features` 中新增布尔能力位：

1. `storage_billing_enabled`
   - 是否为该套餐开启“对象存储官方对账计费”主开关
   - 这是后续所有能力的总开关
2. `storage_billing_allow_official_pass_through`
   - 是否允许该套餐下的租户使用 `official_pass_through`
   - 只是套餐上限，不代表租户一定满足厂商隔离条件
3. `storage_billing_allow_overage`
   - 是否允许超出套餐内含额度后继续生成应收费用
4. `storage_billing_show_bill_center`
   - 是否向租户侧显示对象存储账单页

`quota` 中按需新增数值字段：

1. `cloud_storage_egress_included_gb_monthly`
   - 每月内含下行流量额度
   - `0` 表示无内含额度，直接按账单收费
2. `cloud_storage_egress_alert_gb`
   - 告警阈值
   - 仅用于提醒，不影响正式结算

说明：

1. 第一阶段不建议把“允许的厂商列表”直接塞进 `features`，因为当前仓库的 `get_feature()` 语义是布尔开关，先保持一致。
2. 实际使用哪个厂商、哪个 bucket/domain/account、采用 `official_reconciled` 还是 `official_pass_through`，应放在租户级对象存储账单绑定关系中，不直接写死在套餐上。
3. 套餐只负责回答“有没有资格开这个能力”，不负责回答“具体怎么和哪家云对账”。

#### 9.3.2 套餐开启前置条件

新增明确平台规则：

1. 当 `features.storage_billing_enabled = true` 时，平台必须同时满足两个条件：
   - `storage-billing` 插件已安装且已启用
   - 至少存在一个“已安装且已启用”的对象存储插件
   - `aliyun-oss`
   - `qiniu-kodo`
   - `tencent-cos`
2. `local` 不计入前置条件，因为本方案明确规定本地存储不参与流量收费。
3. 若平台当前没有任何可用云对象存储插件，则：
   - 创建套餐时禁止开启该功能
   - 编辑套餐时禁止保存该功能为开启状态
   - 已有套餐若因插件被停用而失去前置条件，必须进入“依赖失效”状态，不能继续默默生效
4. 若 `storage-billing` 插件本身未启用，则：
   - 创建套餐时禁止开启该功能
   - 编辑套餐时禁止保存该功能为开启状态

第一阶段推荐的校验来源：

1. 复用 `backend/app/api/shared/_storage_helpers.py` 中的 `get_known_plugin_storage_drivers()`
2. 只认 `plugin_status = enabled`
3. 账单插件本身也只认 `plugin_status = enabled`
4. 驱动编码只认：
   - `aliyun-oss`
   - `qiniu-kodo`
   - `tencent-cos`

#### 9.3.3 套餐 entitlement 与租户实际启用要分层

这里必须严格区分两件事：

1. 套餐 entitlement
   - 表示该租户“有资格使用官方对象存储对账计费能力”
   - 需校验 `storage-billing` 插件可用，且平台至少有一个可用云存储插件
2. 租户实际启用
   - 表示该租户已经配置了可对账的云对象存储计费绑定
   - 需要校验该租户当前有效存储驱动、账单范围映射、厂商账单能力是否满足要求

因此允许出现以下状态：

1. 套餐已开通 `storage_billing_enabled`
2. `storage-billing` 插件已启用，且平台已启用至少一个云对象存储插件
3. 某个租户当前仍然使用 `local`
4. 该租户此时不产生对象存储流量费用，账单页显示“当前存储驱动为本地，功能未激活”

这不构成异常，因为用户已明确要求“本地就不要收费”。

#### 9.3.4 套餐保存、分配、租户激活三道校验链

为避免规则散落，第一阶段应统一成三道校验：

1. 套餐保存校验
   - 入口：创建套餐、编辑套餐
   - 规则：只要 `storage_billing_enabled = true`，就必须满足“账单插件已启用 + 至少一个云对象存储插件已启用”
2. 套餐分配校验
   - 入口：企业绑定套餐、切换套餐、续费升级
   - 规则：若目标套餐开启了对象存储对账计费，则再次校验平台前置条件
3. 租户激活校验
   - 入口：租户创建/修改对象存储账单绑定关系
   - 规则：
     - 套餐必须开启 `storage_billing_enabled`
     - `storage-billing` 插件必须处于启用状态
     - 租户当前有效存储驱动不能是 `local`
     - 对应厂商插件必须处于启用状态
     - 若选择 `official_pass_through`，必须额外校验厂商隔离条件

#### 9.3.5 `official_pass_through` 的套餐与租户关系

套餐里的 `storage_billing_allow_official_pass_through` 只代表“允许申请”，不代表“默认可用”。

租户真正启用 `official_pass_through` 时，仍需按厂商分别校验：

1. 腾讯云 COS
   - 推荐一租户一 bucket
   - 需启用按存储桶出账
   - 满足后可作为第一阶段主推的 `official_pass_through`
2. 阿里云 OSS
   - 若只是共用账号下的分账账单，不应视为 `official_pass_through`
   - 必须是独立结算账号或独立财务主体才允许进入该模式
3. 七牛 Kodo
   - 共用账号下的分账账单不能视为 `official_pass_through`
   - 只有独立七牛账号或独立结算主体时才允许进入该模式

结论：

1. 套餐可以允许 `official_pass_through`
2. 但租户是否真的能启用，最终取决于该租户的资源隔离与账单主体隔离是否满足官方要求

### 9.4 插件生命周期治理

#### 9.4.1 `storage-billing` 插件本身的停用/卸载治理

若主体实现采用独立插件，则 `storage-billing` 插件本身也必须被纳入强依赖治理。

停用/卸载前必须检查：

1. 是否存在 `features.storage_billing_enabled = true` 的套餐
2. 是否存在租户已经建立对象存储账单绑定关系
3. 是否存在未关账账期、未完成同步任务、待处理补差单

处理原则：

1. 默认阻断停用/卸载
2. 返回受影响套餐、受影响租户、受影响账期和未完成任务
3. 只有在管理员显式完成迁移、关账或下线流程后才允许继续

#### 9.4.2 对象存储驱动插件的停用/卸载治理

仅靠当前“存储驱动是否正在使用”检查还不够。新增对象存储账单能力后，驱动插件停用/卸载前必须再检查两类依赖：

1. 套餐依赖
   - 是否存在 `features.storage_billing_enabled = true` 的启用套餐
   - 且在停用当前驱动后，平台将不再剩余任何可用云对象存储插件
2. 租户依赖
   - 是否存在租户已经建立该厂商的对象存储账单绑定关系
   - 是否存在租户当前有效存储驱动就是该插件提供的驱动

处理原则：

1. 默认阻断停用/卸载
2. 返回受影响套餐列表和受影响租户列表
3. 管理员必须先完成迁移，再允许继续操作

#### 9.4.3 当前宿主为何还需要 pre-disable veto

当前宿主已有 `system.plugin.disabled` 之类的事后 hook，但这不足以支撑独立账单插件治理。

原因：

1. 账单插件需要在“真正禁用前”阻断，而不是禁用完成后再感知
2. 账单插件还需要区分：
   - 禁用的是账单插件自身
   - 禁用的是某个云存储驱动插件
3. 因此宿主需要补一个“before disable / before uninstall”类的扩展点或 guard registry

#### 9.4.4 不允许的自动降级

以下行为在本方案中都不允许：

1. 因驱动插件停用，自动把仍在官方对账链路中的租户静默切回 `local`
2. 因 `storage-billing` 插件停用，自动把已启用该能力的套餐静默改成关闭
3. 用 `force=True` 跳过对象存储账单依赖检查

原因：

1. 这些行为会直接破坏“本地不收费”和“官方账单真相源”两条核心规则
2. 一旦静默切换，租户账单连续性和审计链都会断掉

#### 9.4.5 插件页面应展示依赖影响

插件管理页建议新增“对象存储账单依赖影响”信息块：

1. 账单插件自身的受影响套餐数
2. 账单插件自身的受影响租户数
3. 某驱动插件的受影响账单绑定数
4. 若当前驱动插件是最后一个可用云对象存储插件，明确提示：
   - “停用后，所有开启对象存储官方对账计费的套餐都会失效”

### 9.5 与当前仓库的对接点

第一阶段建议直接落在以下位置：

1. `backend/app/schemas/tenant/plan.py`
   - 扩展 `FeaturesSchema` 与 `QuotaSchema`
   - 只增加第一阶段需要的布尔/数值字段
2. `backend/app/services/tenant/tenant_plan_service.py`
   - 不承载账单业务本身
   - 只负责调用宿主侧 entitlement/preflight 扩展点
3. `frontend/apps/web-antd/src/views/admin/tenant/plans/data.ts`
   - 增加套餐表单字段与依赖提示文案
   - 当前账单插件未启用或无可用云对象存储插件时，相关开关禁用并展示原因
4. `backend/app/api/shared/_storage_helpers.py`
   - 复用已知插件存储驱动查询能力
   - 作为套餐校验与管理端提示的数据来源
5. `backend/app/services/common/storage_config_resolver.py`
   - 继续作为“驱动必须可用”这一规则的底层先例
   - 对租户实际启用账单能力时复用相同的驱动可用性判断
6. `backend/app/plugins/lifecycle.py`
   - 在禁用、卸载插件前新增“对象存储账单依赖检查”
   - 该检查必须早于当前 `force=True` 的自动切换逻辑
7. `backend/app/plugins/system_hooks.py` 或等效 preflight registry
   - 新增 `tenant_plan` 生命周期扩展点
   - 新增 `before plugin disable/uninstall` veto 扩展点
8. 新增独立插件目录
   - `backend/plugins/storage-billing/plugin.yaml`
   - `backend/plugins/storage-billing/backend/main.py`
   - `backend/plugins/storage-billing/backend/services/`
   - `backend/plugins/storage-billing/backend/tasks/`
   - `backend/plugins/storage-billing/backend/migrations/versions/`
   - `backend/plugins/storage-billing/frontend/src/`

#### 9.5.1 第一阶段为什么不单独建套餐-插件关系表

第一阶段不建专门关系表，原因是：

1. 用户当前新增要求的核心是“套餐开启能力时，账单插件已可用，且平台至少有一个可用对象存储插件”
2. 这属于平台级 capability prerequisite，不是套餐与某个具体插件的静态绑定
3. 当前仓库已有 `features/quota` JSON 和统一 feature 读取路径，先做轻量扩展更符合现状

但第二阶段可以预留升级方向：

1. 若未来需要“某套餐只允许腾讯云，不允许七牛”
2. 或“某套餐启用对象存储账单时必须依赖指定插件集合”
3. 再引入显式依赖表，例如 `plan_feature_dependencies`

#### 9.5.2 第一阶段为什么不直接写 manifest 插件依赖

第一阶段也不建议把 `storage-billing` 的 `dependencies.plugins` 写成对三个对象存储插件的硬依赖，原因是：

1. 当前 manifest 依赖语义是 AND，不是 OR
2. 本需求是“七牛 / OSS / COS 任意一个即可”
3. 若直接声明三个硬依赖，会错误地要求三个插件必须同时安装

因此第一阶段应采用：

1. manifest 不声明这三个驱动为硬依赖
2. 由账单插件 runtime preflight 校验“任意一个已启用”
3. 由宿主在套餐保存和插件停用时复用相同规则

### 9.6 管理端交互要求

管理端套餐表单建议按以下方式交互：

1. 永远展示“对象存储官方对账计费”开关，但在前置条件不满足时禁用
2. 开关下方固定提示：
   - “需要先启用 `storage-billing` 插件，并至少启用一个对象存储插件：aliyun-oss / qiniu-kodo / tencent-cos；local 不计费”
3. 若当前没有任何可用插件：
   - 提示“请先启用 `storage-billing` 插件，并安装启用七牛云、阿里云 OSS、腾讯云 COS 中的任意一个插件”
4. 若当前只有一个插件可用：
   - 明确展示当前可用厂商，方便管理员理解套餐能力边界
5. 若套餐允许 `official_pass_through`：
   - 需增加提示“是否真正可启用，仍取决于租户是否满足厂商官方隔离条件”

## 10. 实施阶段

### M0：宿主能力补齐

1. 增加 `tenant_plan` entitlement preflight registry
2. 增加企业创建/更新时的套餐 entitlement 校验入口
3. 增加 `before_plugin_disable` / `before_plugin_uninstall` veto registry
4. 增加插件可用的宿主只读 facade
5. 增加 tenant 插件菜单“禁止自动授予全部活跃套餐”的策略开关
6. 增加插件 action 权限同步到 DB/RBAC 的标准能力
7. 禁止对象存储驱动插件在账单链路存在时 `force` 自动切回 `local`

### M1：账单插件骨架与数据建模

1. 建立 `storage-billing` 插件骨架
2. 建立插件自管账单表
3. 建立租户资源映射表
4. 建立任务运行日志
5. 扩展套餐 `features/quota` 字段
6. 建立套餐 entitlement 校验服务
7. 建立插件依赖检查服务

### M2：厂商采集器

1. 阿里云账单文件采集器
2. 腾讯云账单文件采集器
3. 七牛财务 API 采集器

### M3：日结与月结

1. D-2 正式日结
2. D-1 预估刷新
3. 月度关账
4. 月度补差

### M4：页面与对账运维

1. 管理端任务中心
2. 管理端租户账单视图
3. 租户端账单页
4. 异常告警与人工复算入口

## 11. 本方案的强约束

1. 不把厂商账单抓取、日结、月结写进存储驱动插件。
2. 主体商业逻辑优先放进独立插件 `storage-billing`，宿主主工程只保留通用扩展点和闸门。
3. 不用应用层下载统计作为正式收费依据。
4. 本地存储不收费。
5. `03:00` 只能做 `D-2` 正式结算，不做“昨天正式结算”。
6. 如需“租户账单可直接对外 pass-through”，必须满足厂商官方可结算范围隔离条件。
7. 对阿里云和七牛，若无法提供独立结算主体，只能标记为 `official_reconciled`，不能标记为 `official_pass_through`。
8. 当套餐开启 `storage_billing_enabled` 时，平台必须同时存在：
   - 已安装且已启用的 `storage-billing` 插件
   - 至少一个已安装且已启用的云对象存储插件：`aliyun-oss`、`qiniu-kodo`、`tencent-cos`
9. 插件的“已安装但未启用”不满足套餐前置条件，只有插件真正可用才算满足。
10. 不把三个对象存储插件直接写成 `storage-billing` 的 manifest 硬依赖，因为当前依赖模型不能表达“任意一个”。
11. tenant 端账单插件菜单不得在插件启用时自动授予所有活跃套餐，必须按套餐 feature 精确授予。
12. 插件停用/卸载不得破坏已生效套餐和租户的对象存储官方对账能力；若会破坏，必须阻断操作并提示迁移。
13. `force=True` 不能绕过对象存储账单依赖检查，也不能把仍在计费链路中的租户静默切回 `local`。

## 12. 推荐落地结论

如果本项目现在要启动实现，推荐按下面的顺序推进：

1. 第一阶段先做独立插件 `storage-billing`，不把商业逻辑塞回主工程，也不写进存储驱动插件。
2. 第一阶段只支持：
   - 腾讯云 COS `official_pass_through`
   - 阿里云 OSS `official_reconciled`
   - 七牛 Kodo `official_reconciled`
3. 第一阶段套餐层继续沿用现有 `features/quota` JSON，不新增复杂绑定表。
4. 第一阶段先补宿主最小扩展点：
   - `tenant_plan` 生命周期校验入口
   - 企业创建/切换套餐 entitlement 校验入口
   - `before plugin disable/uninstall` veto 入口
   - 插件宿主只读 facade
   - tenant 插件菜单精准授权策略
   - 插件 action 权限同步能力
5. 第一阶段先把“套餐开启前置条件 + 插件停用依赖拦截 + 租户激活校验 + tenant 账单菜单精确可见性”做严，再进入账单采集与日结。
6. 本地存储继续只做容量配额，不进入流量收费。
7. 等账单插件稳定后，再决定是否为阿里云和七牛引入“独立账号结算主体”模式。

## 13. 官方参考文档

### 阿里云

1. 导出和订阅账单
   - https://help.aliyun.com/zh/user-center/bill-export
2. 查看和分析账单
   - https://help.aliyun.com/document_detail/90900.html
3. 账单域 API 使用手册
   - https://help.aliyun.com/zh/user-center/developer-reference/overview-of-bill-related-api-operations
4. BSS OpenAPI 概览
   - https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-overview

### 腾讯云

1. 账单存储至 COS 桶
   - https://intl.cloud.tencent.com/zh/document/product/555/43521
2. DescribeBillDetail
   - https://intl.cloud.tencent.com/zh/document/product/555/30756
3. COS 按量计费
   - https://intl.cloud.tencent.com/ind/document/product/436/32534
4. COS 计费计量问题
   - https://cloud.tencent.com/document/product/436/30747

### 七牛

1. 财务对外 API 文档
   - https://developer.qiniu.com/af/10420/financial-external-api-documentation
2. 分账账单
   - https://developer.qiniu.com/af/12391/separate_bill
3. 实时消费明细
   - https://developer.qiniu.com/af/6167/real-spending-detail

## 14. 文档状态

状态：规划完成，待进入平台级详细设计和数据模型拆分。

最后核对日期：2026-03-23（北京时间）

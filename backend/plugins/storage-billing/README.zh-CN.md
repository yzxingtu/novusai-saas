# 对象存储对账计费插件

`storage-billing` 是独立的对象存储对账计费插件，负责按云厂商官方账单口径归集对象存储流量费用，并生成企业侧可见的账单与明细。它故意不写入 `qiniu-kodo`、`aliyun-oss`、`tencent-cos` 这三个存储插件内部，而是作为单独插件维护计费台账与对账流程。

插件只基于云厂商官方账单进行计费。`local` 存储永远不计费。

## 插件定位

- 插件自有台账、账单、对账运行表统一使用 `px_storage_billing_` 前缀。
- 企业侧可见性由宿主套餐 feature `storage_billing_enabled` 控制。
- 运行前置条件通过运行时校验完成，不通过 `plugin.yaml` 写死为硬依赖。
- 插件不替代云厂商发票、税务单据和最终结算，只负责平台内部对账、归集和企业分摊。

## 官方对账策略

实现严格以各云厂商公开账单接口为准，不根据上传/下载日志自行估算流量费用。

| 云厂商 | 账单源 | 当前插件使用的官方接口 | 结算模式 | 插件账期类型 | 是否进入严格日对账任务 | 推荐绑定范围 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 七牛云 Kodo | `finance_api` | 七牛财务接口 `/billing-api/v2/bill/detail` | `monthly_settled` | `monthly` | 否 | `account` | 已实现 |
| 阿里云 OSS | `bss_openapi` | `DescribeSplitItemBill` | `strict_daily_reconciliation` | `daily` | 是，默认 `03:00` 对 `D-3` | `bucket`、`domain`、`account`、`tag` | 已实现 |
| 腾讯云 COS | `describe_bill_detail` | `DescribeBillDetail` | `strict_daily_reconciliation` | `daily` | 是，默认 `03:00` 对 `D-2` | `bucket`、`domain`、`account`、`tag` | 已实现 |

### 各云厂商说明

- 七牛云官方财务文档明确说明，按量计费月账单通常在次月 4 号出账，建议在 5 号后查询。插件因此不把七牛纳入严格日对账链路，而是默认在每月 6 号 `03:00`（Asia/Shanghai）拉取上月月结账单。
- 阿里云 `DescribeSplitItemBill` 支持日粒度查询，但官方文档同时说明：分账账单相对实际费用延迟 48 小时更新，像 OSS 这类分拆型产品的分拆项明细最多可能延迟到 72 小时。插件当前保留每天 `03:00` 的日对账任务，并支持管理员对迟到数据进行手动补跑。
- 腾讯云 `DescribeBillDetail` 作为当前的日对账官方明细源已经接入。腾讯官方文档也说明，账单明细量极大时更适合开通账单数据存储到 COS；当前正式方案仍以官方 API 明细为准，并采用 `D-2` 作为稳定默认窗口。

## 账期与调度

- 每日日对账任务：`0 3 * * *`
- 阿里云 OSS 日对账默认目标账期：`D-3`
- 腾讯云 COS 日对账默认目标账期：`D-2`
- 当手动执行未显式指定日账期时，会和定时任务一样，按上述 provider 规则拆分执行
- 七牛月结账单任务：`0 3 6 * *`
- 七牛月结默认目标账期：上一个自然月
- 插件账期模型同时支持 `daily` 与 `monthly`
- 对账运行、账单源、企业账单序列化结果会返回 `period_type`、`period_start`、`period_end`、`period_label`

## 运维指导

运维人员应把各云厂商的日对账调度当作事实源。插件在 Asia/Shanghai 时区每天 `03:00` 触发定时任务，默认阿里云 OSS 对应 `D-3`，腾讯云 COS 对应 `D-2`，任何手动补跑与审计都需围绕这个周期展开，以保持企业账单与官方账单一致。

### 手动补跑

- 只有在确认目标账期的官方账单已经可以从云平台控制台正常下载时，再在管理端发起 `Daily reconciliation run`。
- 在出现补跑需求时，优先显式填写 `provider` 与 `billing_date`。若省略 `billing_date`，插件会按所选日对账提供方拆分执行，并分别套用各自的默认官方滞后规则。
- 补跑时在备注中说明原因并记录官方账单的原始出账时间，必要时与官方账单时间窗口比对避免遗漏或重复计费。
- 若必须在同一次补跑中包括多个 provider，补跑前务必确认它们各自的滞后窗口并确保官方数据都已经落地。

### 审计复核

- 定时 `03:00` 任务之后，检查运行 payload 中的 `period_type`、`period_label` 和 provider metadata 是否与官方 API 返回的一致，尤其关注 OSS `D-3` 与 COS `D-2`，它们决定企业账单的准确性。
- 使用插件后台的 UI 与云厂商控制台或已导出的官方账单文件逐条核对。总额或明细不一致通常意味着遗漏了补跑或同步延迟。
- 保留每次手动补跑的参数与说明，作为异常处理或审计的唯一可查证记录。
- 若对账结果因补跑而偏离定时任务批次，务必在对外可见的账单描述中写明原因，方便下游支持与客户沟通。

## 套餐与运行前置条件

企业要完整使用本插件，必须同时满足以下条件：

1. 企业套餐开启 `storage_billing_enabled`
2. 企业当前存储驱动是 `qiniu-kodo`、`aliyun-oss`、`tencent-cos` 之一
3. 对应的存储插件已安装并启用
4. 管理员已在本插件中配置并校验通过账单 Profile
5. 管理员已为该企业创建至少一个有效计费绑定

补充说明：

- `local` 存储会在前置校验阶段直接判定为不可计费。
- “必须安装三选一存储插件”属于运行前置条件，而不是当前 manifest 里的硬依赖；宿主侧套餐控制、驱动启用状态、插件启用状态由运行时综合判断。
- 企业端前置接口会返回 provider capability 元数据，前端据此提示当前云厂商是否支持严格日对账、是否仅支持月结、是否支持手动拉取、推荐使用什么 scope 绑定等信息。

## 绑定模型

当前支持的绑定范围：

- `bucket`
- `domain`
- `account`
- `tag`

云厂商规则：

- 七牛云第一阶段只允许 `account` 范围绑定。
- 七牛云第一阶段不支持 `official_pass_through`，仅支持官方账单归集后再分摊。
- 阿里云 OSS 与腾讯云 COS 可根据官方账单可识别字段，按 `bucket`、`domain`、`account`、`tag` 进行归集。

## 管理端使用流程

1. 安装并启用 `storage-billing`
2. 安装并启用至少一个受支持的对象存储插件
3. 在宿主套餐中开启 `storage_billing_enabled`
4. 先在宿主系统存储配置中选定并配置当前实际生效的对象存储提供方
5. 在插件管理端只配置计费插件自己的账单参数，例如 `enabled`、`bill_source`、`account_identifier`
6. 校验 Provider Profile。运行时凭证与地域来自宿主当前生效的对象存储配置，因此管理端只展示当前激活的那一个提供方卡片
7. 创建企业计费绑定
8. 手动触发对账，或等待定时任务执行
9. 查看对账运行记录、账单源、归集摘要，并按需导出明细

当前管理端支持的主要动作：

- 手动触发日对账
- 手动触发七牛月结账单拉取
- 导出单次对账的费用明细 CSV

手动日补跑规则：

- 如果显式传入 `billing_date`，一次手动日对账可以同时覆盖多个日对账提供方。
- 如果未传 `billing_date`，插件会按所选日对账提供方拆分执行，并分别套用各自的默认官方滞后规则。

## 实施规范

- 详细协作关系、边界、校验规则与实施流程见：[docs/implementation-spec.zh-CN.md](docs/implementation-spec.zh-CN.md)

## 企业端体验

当前置条件满足时，企业端可以：

- 查看当前账单摘要
- 浏览最近账单列表
- 查看账单费用明细
- 导出账单明细 CSV
- 查看前置条件与云厂商能力提示

当前置条件不满足时，企业端不会静默展示空页面，而是收到结构化失败原因。

## 当前限制

- `local` 存储永远不计费。
- 七牛云当前仅支持月结口径，且只支持 `account` 范围计费。
- 插件只负责按官方账单进行内部对账与企业分摊，最终发票、税务、支付结算仍以云厂商平台为准。

## 官方文档参考

- 七牛云财务对外 API 文档：[https://developer.qiniu.com/af/10420/financial-external-api-documentation](https://developer.qiniu.com/af/10420/financial-external-api-documentation)
- 七牛云账单查询说明：[https://developer.qiniu.com/af/12835/bill_review](https://developer.qiniu.com/af/12835/bill_review)
- 阿里云 `DescribeSplitItemBill`：[https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-describesplititembill](https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-describesplititembill)
- 腾讯云 `DescribeBillDetail`：[https://cloud.tencent.com/document/product/555/19182](https://cloud.tencent.com/document/product/555/19182)
- 腾讯云 COS 计费概述：[https://cloud.tencent.com/document/product/436/36522](https://cloud.tencent.com/document/product/436/36522)

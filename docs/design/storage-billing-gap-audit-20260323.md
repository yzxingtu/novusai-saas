# `storage-billing` 现状审计与下一阶段设计（2026-03-23）

## 1. 文档目的

本文档不重复回答“为什么做独立插件”。

它只回答三件事：

1. 当前仓库里的 `storage-billing` 到了什么成熟度
2. 三家云厂商的官方账单能力应如何约束实现
3. 下一阶段应该按什么顺序把插件从脚手架推进到可联调版本

建议与以下文档一起阅读：

1. [object-storage-official-billing-reconciliation-plan-20260323.md](./object-storage-official-billing-reconciliation-plan-20260323.md)
2. [storage-billing-plugin-implementation-spec-20260323.md](./storage-billing-plugin-implementation-spec-20260323.md)
3. [storage-billing-host-m0-checklist-20260323.md](./storage-billing-host-m0-checklist-20260323.md)

## 2. 审计结论

一句话结论：

1. 独立插件方向是对的
2. 宿主 M0 主干现在已经基本接通
3. `storage-billing` 本体仍然是 `M1 scaffold`
4. 距离“真实按官方账单收费”还差 provider 采集、租户绑定、分摊落账三段核心闭环

更准确地说：

1. 当前仓库已经证明“这件事可以做成独立插件，而不是写死进 OSS/COS/Qiniu 驱动”
2. 当前仓库还没有证明“这个插件已经能对接真实账单并产生可收费的 tenant 日账”

## 3. 宿主现状

### 3.1 已接通的宿主能力

本次审计后，以下能力已经具备：

1. 套餐 `features.storage_billing_enabled` 已进入后端 schema 和前端表单链路
2. `TenantPlanService` 与 `TenantService` 已在 `plan_create`、`plan_update`、`tenant_create`、`tenant_plan_switch` 上接入 preflight
3. 宿主只读 facade 已支持插件读取套餐快照、插件运行态、租户有效存储上下文
4. lifecycle guard 已在禁用/卸载前置执行，而不是事后通知
5. 插件 action 权限已纳入 RBAC DB 同步，不再只同步菜单权限
6. `manual_entitlement` 现在已经有真正的 feature 驱动授权路径，不再只是“跳过自动授权”
7. `tenant_plan_preflight` 与 `lifecycle_guards` runner 现在会自动引导注册内建 host guard，不再是空 registry

### 3.2 仍然未完成的宿主能力

宿主 M0 还没有做到“完全上线无忧”，当前仍缺：

1. 更细粒度的 lifecycle veto
2. 基于真实 binding/run/month closing 状态的阻断条件
3. 若未来引入更多 feature-managed 插件，当前 host guard 还需要进一步泛化

当前 host guard 只覆盖第一阶段最核心的阻断条件：

1. 套餐开启 `storage_billing_enabled` 时，必须启用 `storage-billing`
2. 套餐开启 `storage_billing_enabled` 时，必须至少启用 `qiniu-kodo`、`aliyun-oss`、`tencent-cos` 中的一个
3. 若仍有启用该 feature 的活跃套餐，则不能直接禁用/卸载 `storage-billing`
4. 若仍有启用该 feature 的活跃套餐，则不能把最后一个云对象存储计费依赖插件禁掉

## 4. 插件现状

### 4.1 已完成的部分

当前 `storage-billing` 插件已经具备以下骨架：

1. 独立 manifest、独立任务、独立 API、独立迁移、独立模型、独立表前缀
2. `03:00` 定时任务和 `D-2` 官方结算窗口的基本策略
3. `px_storage_billing_runs`
4. `px_storage_billing_provider_sources`
5. `px_storage_billing_tenant_statements`
6. `px_storage_billing_tenant_daily_charges`
7. 管理端概览接口和企业端当前账单快照接口

### 4.2 仍然只是占位的部分

当前真正阻塞上线的不是“页面没做”，而是账单主链路仍未落地：

1. 七牛、阿里云、腾讯云 provider adapter 仍全部返回 `not_implemented`
2. 没有 provider profile 配置模型
3. 没有 tenant 与 bucket/domain/tag/account 的绑定模型
4. 没有 raw statement 导入与去重模型
5. 没有 `provider source -> tenant daily charge` 的分摊器
6. 没有 month closing / adjustment / exception center
7. 没有导出链路
8. 没有管理端和企业端正式页面

因此当前插件的真实成熟度是：

1. 可以证明插件边界是对的
2. 不能拿去接真实账单
3. 不能拿去正式收费

## 5. 官方能力矩阵

以下结论仅使用官方资料或官方域名资料整理。

### 5.1 七牛 Kodo

官方资料：

1. [查看账单](https://developer.qiniu.com/af/12835/bill_review)
2. [下载账单](https://developer.qiniu.com/af/12836/bill_download)
3. [按量计费预估明细](https://developer.qiniu.com/af/6167/real-spending-detail)
4. [财务对外 API 文档](https://developer.qiniu.com/af/10420/financial-external-api-documentation)
5. [分账账单](https://developer.qiniu.com/af/12391/separate_bill)

官方约束：

1. 上月账单于每月第 `4` 个自然日出具
2. 为保证完整性，官方建议在次月 `5` 号后查看上月账单
3. 当天预估快照要求在 `08:00` 后查询
4. 预估快照只用于参考，不是最终账单
5. 分账账单只适用于企业内部成本分摊参考，不作为对账依据

实现落点：

1. 七牛第一阶段只能做 `official_reconciled`
2. 七牛 `D-1` 只能做预估刷新，不能做正式结算
3. 七牛若要 `official_pass_through`，应按“一租户一七牛账号”设计，而不是共用账号下做 bucket/domain 分摊

### 5.2 阿里云 OSS

官方资料：

1. [了解阿里云账单](https://help.aliyun.com/zh/user-center/product-overview/quickly-understand-alibaba-cloud-billing)
2. [查看和分析账单](https://help.aliyun.com/zh/user-center/bill-view)
3. [导出和订阅账单](https://help.aliyun.com/zh/user-center/export-and-subscribe-bills/)
4. [DescribeSplitItemBill 分账账单接口](https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-describesplititembill)

官方约束：

1. 月账单 `PDF` 于次月 `2` 日 `12:00` 出具
2. 消费明细最终完整数据于次月 `3` 日 `12:00` 稳定
3. 分账明细于次月 `4` 日 `12:00` 稳定
4. 账单可自动订阅到 `OSS` 或 `MaxCompute`
5. 前一天全量账单通常在当日 `18:00` 前推送
6. 分账账单仅供内部管理参考，不作为结算或开票依据

实现落点：

1. 阿里云推荐 `账单订阅到 OSS + 必要时 BSS OpenAPI 补查`
2. `03:00` 不能结算昨天，只能结算 `D-2`
3. 阿里云第一阶段推荐 `official_reconciled`
4. 若业务要求 `official_pass_through`，应采用独立财务主体或独立账号，而不是只依赖分账明细

### 5.3 腾讯云 COS

官方资料：

1. [账单介绍](https://cloud.tencent.com/document/product/555/30250)
2. [账单确认和盖章](https://cloud.tencent.com/document/product/555/36482)
3. [账单导出中心](https://cloud.tencent.com/document/product/555/67364)
4. [账单订阅](https://cloud.tencent.com/document/product/555/32870)
5. [账单存储至 COS 桶](https://cloud.tencent.com/document/product/555/61275)
6. [用量明细](https://cloud.tencent.com/document/product/555/30314)
7. [分账账单](https://cloud.tencent.com/document/product/555/102975)
8. [COS 计费常见问题](https://cloud.tencent.com/document/product/436/30747)

官方约束：

1. 费用账单是腾讯云与用户对账的凭据
2. 月账单通常在次月 `1` 日 `19:00` 完成出账
3. `账单存储至 COS 桶` 的日明细通常在 `Day+1 03:00-22:00` 投递
4. 月末最后一天的日账单要到次月 `2` 号后才会完整
5. 分账账单 `T+1` 出账，通常每天 `09:00` 后可查前一日
6. 月度分账账单建议次月 `4` 号 `09:00` 后查询
7. COS 支持按存储桶出账

实现落点：

1. 腾讯云是最适合优先实现 `official_pass_through` 的 provider
2. 推荐一租户一 bucket，并启用按存储桶出账
3. `03:00` 仍只适合正式结算 `D-2`
4. 分账账单更适合成本分析与内部映射

补充说明：

1. 腾讯云文档不像阿里云和七牛那样直接写出“分账账单不作为对账依据”
2. 因此“腾讯云分账账单不应用作正式对外结算依据”这一条，在文档中应标记为基于官方用途定位的实现推断，而不是原文硬性条款

## 6. 第一阶段正式规则

### 6.1 收费范围

第一阶段只允许对以下费用项做 tenant 二次收费：

1. 外网下行流量
2. CDN 回源流量
3. 传输加速流量
4. 与下载链路紧耦合且官方单列计费的数据处理费用

第一阶段明确不做：

1. `local` 收费
2. 上传流量收费
3. 请求次数收费
4. 存储容量收费
5. 数据取回收费

### 6.2 结算时间

第一阶段固定结算规则：

1. 每天 `03:00` 跑 `D-2` 正式日结
2. 每天 `11:00` 跑 `D-1` 预估刷新
3. 每天 `19:00` 跑 `D-1` 官方补齐刷新
4. 每月 `06` 日 `03:00` 关闭上月账期并生成补差

### 6.3 模式边界

平台继续保留两种模式：

1. `official_reconciled`
2. `official_pass_through`

第一阶段建议：

1. 七牛默认只开放 `official_reconciled`
2. 阿里云默认主推 `official_reconciled`
3. 腾讯云优先落 `official_pass_through`

## 7. 下一阶段开发顺序

### 7.1 P0：把真实账单采集打通

先做一条真实 provider 采集链，不要三家一起铺开。

建议顺序：

1. 腾讯云 COS
2. 阿里云 OSS
3. 七牛 Kodo

原因：

1. 腾讯云 bucket 级账单口径最适合做 tenant 映射
2. 阿里云订阅能力强，但正式 pass-through 约束更重
3. 七牛日级只有预估快照，正式对齐更依赖月账

### 7.2 P1：补齐配置与绑定模型

下一阶段必须新增的表，不建议再拖：

1. `px_storage_billing_provider_profiles`
2. `px_storage_billing_tenant_bindings`
3. `px_storage_billing_raw_statements`
4. `px_storage_billing_vendor_daily`
5. `px_storage_billing_month_closings`
6. `px_storage_billing_exceptions`

### 7.3 P2：实现分摊器

最关键的业务断点是：

1. 把 provider 原始账单映射成归一化 vendor daily
2. 再把 vendor daily 按 binding 规则分摊为 tenant daily charge

若没有这一段，即使 run/source 可以落表，tenant statement 仍然没有真实输入。

### 7.4 P3：补管理端与租户端页面

页面排位必须后置于数据闭环，不要本末倒置。

建议顺序：

1. provider profile 页面
2. binding 页面
3. run 中心
4. exception center
5. tenant statement 页面
6. export 页面

## 8. 当前最重要的设计约束

最终实现时，以下约束不要退：

1. `storage-billing` 继续作为独立插件，不回写进各对象存储驱动插件
2. `local` 永远不收费
3. 正式扣费只认官方账单、官方账单订阅文件、官方财务 API
4. 应用日志、下载日志、附件表统计只能做观测，不得做正式扣费依据
5. `03:00` 只能做 `D-2` 正式结算，不做“昨天正式结算”
6. 七牛和阿里云的分账数据只能当 tenant 分配依据，不能当厂商正式结算真相源
7. 腾讯云若使用分账账单做 tenant 分配，应在文档中明确标注其用途定位，并避免把它写成“官方结算凭据原文”

## 9. 收口结论

接下来的工作不应该继续扩散概念，而应该收敛到一条真实闭环：

1. 先选腾讯云 COS 做第一条官方账单链
2. 补 provider profile 和 tenant binding
3. 落 raw statement -> vendor daily -> tenant daily charge
4. 最后再补 month closing、export 和正式页面

在这个顺序里，真正的核心不是“多做几个接口”，而是先让一条 tenant 日账可以从官方账单稳定落出来。

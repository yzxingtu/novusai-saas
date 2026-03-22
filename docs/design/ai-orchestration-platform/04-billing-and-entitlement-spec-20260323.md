# AI 编排与工作流平台计费与授权规范（2026-03-23）

## 一、文档目标

本文档定义平台的计费与授权规则，目标是把以下几条线统一起来：

- 平台基础能力订阅
- 行业解决方案插件授权
- 插件 License 与试用机制
- 企业定制交付
- 企业运行时可见性和可执行性

本规范重点不在支付渠道实现，而在：

- 商业对象如何建模
- 授权如何传播到运行时
- 现有 `TenantPlan`、插件定价与 License 机制如何衔接

---

## 二、核心结论

### 2.1 对外采用“两重付费”

对客户表达仍然保持两层：

1. 平台基础订阅
2. 行业方案 / 工作流方案授权

### 2.2 对内采用“三层授权”

系统内部建议拆成三类授权：

- `platform_subscription`
- `solution_package_entitlement`
- `custom_delivery_entitlement`

原因：

- 方便和现有套餐模型衔接
- 方便区分标准行业包与企业定制交付
- 方便后续做暂停、过期、退款、补授权

### 2.3 平台订阅优先复用现有 `TenantPlan`

现有模型已有：

- `Tenant.plan_id`
- `TenantPlan.price`
- `TenantPlan.billing_cycle`
- `TenantPlan.quota`
- `TenantPlan.features`

因此平台基础订阅不建议重新发明一套“平台套餐主表”，建议以 `TenantPlan` 为平台基础能力订阅模型。

### 2.4 行业方案授权与插件 License 衔接

行业解决方案中心并入插件市场后，行业方案插件的付费能力建议优先复用：

- `plugin.yaml.pricing`
- `PluginLicense`

但需要补一层“企业授权语义”，避免 License 只是插件启停标志，而无法表达：

- 哪个企业获得了哪个方案
- 企业是否只拿到标准方案还是还拿到定制交付
- 方案包是否可见但不可运行

因此：

- `PluginLicense` 继续负责插件级许可与运行时闸门
- `TenantEntitlement` 负责企业级授权与可见性

### 2.5 授权才是运行时真相

最终是否可以运行某个行业插件、模板、Agent、工作流，不应由“页面是否显示”决定，而应由授权链路决定。

推荐链路：

```text
TenantPlan
-> TenantEntitlement
-> Plugin / WorkflowTemplate / SkillPackage Binding
-> WorkflowRun / Agent Run
```

---

## 三、现有模型复用策略

### 3.1 复用 `TenantPlan`

适用范围：

- 平台基础订阅
- 平台基础功能开关
- 平台基础配额

建议继续使用：

- `price`
- `billing_cycle`
- `quota`
- `features`

建议将以下能力明确纳入 `TenantPlan.features` 或 `TenantPlan.quota`：

- 是否开启 AI 编排平台
- 可创建简单工作流数量
- 可启用的 Agent 数量
- 每月可运行工作流次数
- 每月模型调用额度
- 是否支持 `agentic` 模式
- 是否支持 L4 高自治执行

### 3.2 复用插件定价与 License 机制

插件市场已有：

- `plugin.yaml.pricing`
- `PluginLicense`
- 试用、固定期限、永久 License 模型

这些应继续作为行业解决方案插件的商业基础。

建议行业方案插件在 `plugin.yaml` 中声明：

- 是否免费
- 是否试用
- 定价类型
- 是否需要 License
- 是否支持企业定制交付

### 3.3 新增统一授权层

虽然现有套餐和插件 License 已存在，但缺少“企业最终拿到了什么”的统一授权表，因此必须新增 `TenantEntitlement`。

---

## 四、商业对象模型

### 4.1 平台订阅

定义：

- 企业是否拥有平台基础能力
- 企业的基础配额和功能边界

实现建议：

- 使用 `Tenant.plan_id -> TenantPlan`

承载内容：

- 平台基础可用性
- 基础工作流数量
- 基础 Agent 数量
- 基础模型额度
- 是否支持企业端自建简单工作流
- 是否支持企业端查看运行监控

### 4.2 行业方案授权

定义：

- 企业是否有权启用某个行业解决方案插件
- 企业可用的是标准方案还是增强版

实现建议：

- 插件侧：`Plugin + PluginLicense`
- 企业侧：`TenantEntitlement(entitlement_type = solution_package)`

承载内容：

- 是否获得某行业插件使用权
- 授权起止时间
- 授权状态
- 是否包含特定模板、Agent、Skill

### 4.3 企业定制交付

定义：

- 平台方为某企业专门制作并交付的工作流或能力配置

实现建议：

- `TenantEntitlement(entitlement_type = custom_delivery)`
- 可辅以 `CustomDeliveryRecord`

承载内容：

- 企业专属工作流
- 企业专属模板版本
- 企业专属 Agent 配置
- 企业专属 Prompt / 审核规则

---

## 五、统一授权模型

### 5.1 推荐新增 `TenantEntitlement`

表：`tenant_entitlements`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `entitlement_type` | enum | `platform_subscription` / `solution_package` / `custom_delivery` |
| `target_type` | enum | `plugin` / `workflow_template` / `skill_package` / `agent_profile` |
| `target_id` | int | 授权目标 |
| `status` | enum | `draft` / `active` / `expired` / `suspended` / `revoked` |
| `source_type` | enum | `plan_included` / `manual_grant` / `license_activated` / `custom_delivery` |
| `starts_at` | datetime | 生效时间 |
| `ends_at` | datetime nullable | 结束时间 |
| `granted_by_admin_id` | int nullable | 发放人 |
| `order_ref` | string nullable | 商业订单号 |
| `meta_json` | json nullable | 授权细节 |

### 5.2 授权状态建议

- `draft`
- `active`
- `expired`
- `suspended`
- `revoked`

说明：

- `expired`：自然到期
- `suspended`：欠费、风控、人工临时停用
- `revoked`：永久撤销

### 5.3 授权传播规则

#### 平台基础订阅

当企业绑定某个 `TenantPlan` 后，系统根据套餐的 `features` 与 `quota` 决定企业是否有资格：

- 打开工作流中心
- 创建简单工作流
- 使用 `hybrid` / `agentic`
- 查看运行与复盘

#### 行业方案授权

当企业获得某个 `solution_plugin` 授权后：

- 插件可见
- 插件页面可见
- 插件内方案模板可见
- 插件投影出的 SkillPackage / Skill 可参与企业可见性计算

但前提仍是：

- 插件启用
- 插件 License 有效
- 企业 Entitlement 为 `active`

#### 企业定制交付

当企业获得定制交付授权后：

- 可见指定模板或企业工作流副本
- 可见指定 Agent 预设
- 可见定制页面和配置入口

---

## 六、插件 License 与企业授权的关系

### 6.1 不要把二者混为一谈

`PluginLicense` 和 `TenantEntitlement` 不是一回事。

#### PluginLicense 解决的问题

- 这个插件是否被允许运行
- 插件本身是否试用有效
- 插件是否过期

#### TenantEntitlement 解决的问题

- 这个企业是否有资格看到和使用该方案
- 这个企业是否买的是标准版还是定制版
- 该授权从什么时候开始到什么时候结束

### 6.2 推荐联合判断规则

企业是否可运行某个行业方案插件，建议同时满足：

1. 企业 `TenantPlan` 开启了平台能力
2. 插件已安装且已启用
3. 插件 License 有效
4. 企业拥有 `active` 的 `solution_package` 授权

结论：

```text
可运行 = 平台订阅有效
      AND 插件运行许可有效
      AND 企业方案授权有效
```

---

## 七、套餐、方案包、定制交付之间的关系

### 7.1 推荐链路

```text
TenantPlan
-> included_features / quotas
-> TenantEntitlement(plan_included)

SolutionPlugin
-> pricing / license
-> TenantEntitlement(solution_package)

CustomDelivery
-> WorkflowTemplate / TenantWorkflow / AgentProfile
-> TenantEntitlement(custom_delivery)
```

### 7.2 推荐原则

#### 原则一

平台订阅决定“企业有没有进入平台能力区”的资格。

#### 原则二

行业方案授权决定“企业能不能用某个行业包”。

#### 原则三

定制交付决定“企业能不能用平台专门为它做的那套东西”。

---

## 八、运行时授权校验顺序

建议所有入口统一校验顺序，避免各接口判断逻辑漂移。

### 8.1 进入企业端页面

```text
校验 TenantPlan
-> 校验 Solution Entitlement
-> 校验插件启用与 License
-> 渲染页面
```

### 8.2 运行工作流模板

```text
校验模板可见性
-> 校验企业 Entitlement
-> 校验模板状态
-> 校验节点能力是否都已授权
-> 创建 WorkflowRun
```

### 8.3 执行 Agent / Skill

```text
校验 Agent 可见性
-> 校验 Skill 是否在企业授权范围内
-> 校验插件来源 Skill 的插件 License
-> 执行
```

### 8.4 安全禁用优先级

如以下任一项失效，建议立即阻断运行：

- `TenantPlan` 不允许
- `TenantEntitlement.status != active`
- 插件 License 失效
- 模板或插件被禁用
- 风控策略强制冻结

---

## 九、建议的商业状态流转

### 9.1 平台订阅

建议状态：

- `trial`
- `active`
- `grace_period`
- `expired`
- `suspended`

### 9.2 行业方案授权

建议状态：

- `pending_payment`
- `active`
- `grace_period`
- `expired`
- `revoked`

### 9.3 定制交付

建议状态：

- `quoted`
- `in_delivery`
- `delivered`
- `accepted`
- `disabled`

说明：

- 定制交付不一定直接等于“已激活”，可能还存在交付中和验收中状态。

---

## 十、第一阶段建议如何落地

### 10.1 优先复用，不先大改现有支付系统

第一阶段不建议马上重做整个支付系统。

优先策略：

- 基础订阅继续走 `TenantPlan`
- 行业方案继续挂插件 `pricing + license`
- 增加 `TenantEntitlement` 补齐企业授权语义

这样能最快形成平台闭环。

### 10.2 第一阶段最少需要补的东西

#### 数据层

- `tenant_entitlements`
- 如有需要，再补 `custom_delivery_records`

#### 业务规则

- 基础套餐与行业方案授权的联合校验
- 插件 License 与 Entitlement 的联合闸门
- 模板 / Agent / Skill 的授权传播

#### 页面层

- 管理端：企业授权管理页
- 管理端：方案包授权页
- 企业端：我已授权的方案页

### 10.3 第一阶段暂不做的内容

- 复杂发票系统
- 外部支付网关详细实现
- 自动退款与财务对账
- 多币种与税率体系

这些属于后续扩展，不是当前“授权和运行时闭环”的阻塞项。

---

## 十一、与现有文档的关系

本文档与以下文档配套：

- `01-platform-architecture-20260323.md`
- `02-platform-data-model-20260323.md`
- `03-page-and-permission-map-20260323.md`

关系如下：

- `01` 负责平台架构与原则
- `02` 负责数据模型
- `03` 负责页面与权限
- `04` 负责商业与授权规则

---

## 十二、关键结论

1. 平台基础订阅建议复用现有 `TenantPlan` 体系，不重新造一套套餐模型。
2. 行业方案授权建议基于插件市场的 `pricing + PluginLicense` 继续扩展，而不是绕开插件体系。
3. 必须新增 `TenantEntitlement`，作为企业最终授权与运行时可见性的统一事实来源。
4. `PluginLicense` 负责插件运行许可，`TenantEntitlement` 负责企业是否获得该方案，两者不能混用。
5. 运行时入口必须统一做联合校验：平台订阅 + 方案授权 + 插件 License + 资源状态。
6. 第一阶段先补“授权与可运行”闭环，不急着上复杂支付和发票系统。


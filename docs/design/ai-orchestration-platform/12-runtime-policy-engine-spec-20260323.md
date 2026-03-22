# AI 编排与工作流平台运行时策略引擎规范（2026-03-23）

## 一、文档目标

本文档用于定义平台所有“运行时裁决”应如何统一收口到一个策略引擎中。

之所以必须单独写这份文档，是因为前面的文档已经分别定义了：

- 套餐和授权
- 插件 License
- 审批和风险闸门
- 构建器能力矩阵
- 触发和发布
- 定制交付边界

但这些规则如果分散在：

- Controller
- Service
- Workflow Runtime
- Plugin Dispatcher
- Agent Runtime

里分别判断，后面一定会出现：

- 规则漂移
- 相同对象在不同入口判断结果不一致
- 临时 if/else 越来越多
- 企业侧出现“页面上能点，运行时报不允许”的混乱体验

本文档的目标就是把这些规则统一收口为一个“运行时策略引擎”。

---

## 二、核心结论

### 2.1 所有运行时入口都必须走统一裁决层

统一策略引擎应成为以下入口的共同前置层：

- 工作流触发
- 工作流节点执行
- Agent 调度
- Skill / Tool 调用
- 插件 API 分发
- Webhook 分发
- 前端插件页面和资产加载

### 2.2 策略引擎输出的不只是“允许/拒绝”

策略引擎不应只返回布尔值，而应至少返回：

- 是否允许
- 命中的规则
- 拒绝原因
- 需要的后续动作
- 风险与审批要求

这样运行时才能做出不同动作：

- 直接执行
- 要求用户确认
- 创建审批任务
- 转入平台托管
- 直接阻断

### 2.3 运行时策略引擎是统一内核，不是某个模块的 helper

它不能只是工作流模块的一个函数，应该是平台级能力。

建议角色定位：

> 统一判断“当前主体在当前上下文下，是否有权以当前方式运行当前资源”。

### 2.4 现有 `plugin runtime gate` 应被视为策略引擎的一个子域

当前项目已经有统一的插件运行时闸门，这个方向是对的。

后续不应推翻它，而应把它纳入更大的运行时策略引擎中，成为：

- `plugin_policy_domain`

而不是让其它运行时入口各写一套平行逻辑。

### 2.5 策略引擎负责裁决，不负责真正执行

需要明确边界：

- 策略引擎负责判断
- Runtime 负责执行
- 审批中心负责审批实例
- 授权中心负责授权数据

策略引擎不要变成一个“大总管服务”，否则会越来越重。

---

## 三、为什么现在就必须定义这层

当前平台正在同时建设：

- 插件化行业方案
- 工作流运行时
- 企业简单构建器
- 审批闸门
- 企业授权与方案授权

如果没有统一策略引擎，后面实现通常会演变成：

```text
某接口查 TenantPlan
某接口查 TenantEntitlement
某接口查 PluginLicense
某接口查审批
某接口查 scope
某接口忘了查其中一个
```

结果就是：

- 同一个企业在 A 页面能看到资源，在 B 入口不能运行
- 同一个模板在手动触发能跑，定时触发不能跑
- 同一个插件在 API 分发能跑，前端页面加载被挡住

所以，这层不是“以后再说”的优化，而是平台内核一致性的前提。

---

## 四、策略引擎的正式定义

建议将运行时策略引擎定义为：

> 一个统一解析多来源规则，并对运行时动作给出标准化裁决结果的核心服务。

### 4.1 它要解析哪些来源

至少包括：

1. 平台基线策略
2. 套餐能力
3. 企业授权
4. 插件 License
5. 资源作用域
6. 风险与审批策略
7. 触发器与发布状态
8. 构建器能力边界
9. 定制交付边界

### 4.2 它的输入是什么

建议统一收敛为一个标准化输入对象：

- 当前主体是谁
- 当前动作是什么
- 当前目标资源是什么
- 当前运行上下文是什么

---

## 五、策略引擎输入模型

建议正式定义一个运行时输入对象，例如：`RuntimePolicyContext`

建议字段：

| 字段 | 说明 |
|---|---|
| `actor_type` | `platform_admin` / `tenant_admin` / `system` / `trigger` |
| `actor_id` | 操作主体 ID |
| `tenant_id` | 当前企业 |
| `entrypoint` | `workflow_trigger` / `workflow_node` / `agent_run` / `plugin_api` / `plugin_asset` |
| `action_type` | `view` / `trigger` / `execute` / `load_asset` / `call_tool` / `publish` |
| `target_type` | `plugin` / `workflow_template` / `tenant_workflow` / `agent` / `skill` / `trigger` |
| `target_id` | 目标资源 ID |
| `target_version_id` | 目标版本 |
| `capability_class` | 能力分类，如 `external_write_high` |
| `risk_level` | 当前动作风险等级 |
| `autonomy_level` | 当前自治等级 |
| `trigger_type` | `manual` / `schedule` / `api` / `webhook` / `event` |
| `input_schema_ok` | 输入是否通过 Schema |
| `runtime_metadata` | 额外运行时上下文 |

### 5.1 策略引擎不应自己去猜业务动作

例如：

- “这是一个高风险写操作”
- “这是一个只读分析”

这些最好由上游运行时在标准化后传入，而不是由引擎内部再去猜。

这样职责更清晰。

---

## 六、策略引擎输出模型

建议正式定义一个标准化输出对象，例如：`RuntimePolicyDecision`

建议字段：

| 字段 | 说明 |
|---|---|
| `allowed` | 是否允许继续 |
| `decision_code` | 标准决策码 |
| `reason_code` | 拒绝或限制原因 |
| `enforcement_mode` | `allow` / `confirm` / `approval` / `managed_only` / `deny` |
| `approval_required` | 是否需要审批 |
| `approval_policy_id` | 命中的审批策略 |
| `risk_level` | 最终风险等级 |
| `matched_rules` | 命中的规则列表 |
| `resolved_version_id` | 最终解析的版本 |
| `entitlement_snapshot` | 授权快照 |
| `license_snapshot` | License 快照 |
| `notes` | 说明文本 |

### 6.1 `allowed=false` 也应细分

不要把所有拒绝都塞成一个错误。

至少建议区分：

- `plan_denied`
- `entitlement_missing`
- `plugin_disabled`
- `license_inactive`
- `scope_denied`
- `trigger_disabled`
- `release_unpublished`
- `capability_not_allowed`
- `risk_hard_block`

---

## 七、建议的裁决域拆分

为了可维护，建议策略引擎内部拆成多个“裁决域”，而不是一个超大函数。

## 7.1 建议的裁决域

| 裁决域 | 作用 |
|---|---|
| `subscription_policy_domain` | 套餐和基础能力判断 |
| `entitlement_policy_domain` | 企业授权判断 |
| `plugin_policy_domain` | 插件启用、Scope、License 判断 |
| `release_policy_domain` | 发布版本与触发器判断 |
| `builder_policy_domain` | 构建器能力边界判断 |
| `risk_policy_domain` | 风险等级和强阻断判断 |
| `approval_policy_domain` | 审批要求解析 |
| `knowledge_policy_domain` | 知识源可用性与隔离判断 |

### 7.2 域的顺序应固定

建议按“越基础越前置”的顺序执行：

```text
subscription
-> entitlement
-> plugin
-> release
-> builder
-> risk
-> approval
-> knowledge
```

如果前面已经判定硬拒绝，后面就不必继续。

---

## 八、和现有 `plugin runtime gate` 的关系

当前项目已有：

- `evaluate_plugin_runtime_gate`

这很好，说明插件入口已经开始统一。

### 8.1 后续建议

建议把它纳入策略引擎架构：

- 保留现有函数
- 作为 `plugin_policy_domain` 的底层实现
- 由更高层策略引擎统一聚合其它域结果

### 8.2 不建议反向复制插件 gate 逻辑到别处

比如：

- 不要在工作流运行里再手写一遍插件启用 + License + scope 判断
- 不要在前端资产加载和插件 API 分发之外再各写一套

应该统一调用同一套域逻辑。

---

## 九、策略优先级建议

所有规则不是平级的，必须有固定优先级。

推荐优先级：

```text
硬阻断规则
> 平台基线
> 套餐能力
> 企业授权
> 插件运行许可
> 发布与触发状态
> 企业覆盖策略
> 工作流局部策略
```

### 9.1 为什么企业覆盖策略排在后面

因为企业只能在平台允许的范围内加严或调整，不能覆盖平台底线。

### 9.2 为什么发布与触发状态不能太靠后

因为即使其它都允许，如果目标版本根本未发布或触发器已停用，也不应创建运行实例。

---

## 十、决策类型建议

建议把策略引擎的最终行为收敛成 5 类：

| 类型 | 含义 |
|---|---|
| `allow` | 直接运行 |
| `confirm` | 需要请求发起人确认 |
| `approval` | 需要正式审批 |
| `managed_only` | 必须走平台托管模式 |
| `deny` | 直接阻断 |

### 10.1 为什么不建议返回更多动作类型

最终执行层真正需要的动作不多。

如果决策类型过多，反而会让 Runtime 和 UI 适配更复杂。

复杂语义可以放在：

- `reason_code`
- `matched_rules`
- `notes`

中表达。

---

## 十一、策略引擎应服务哪些核心场景

## 11.1 工作流触发

在创建 `WorkflowRun` 前，应统一判断：

- 目标版本是否可运行
- 企业是否有权限
- 触发器是否启用
- 风险是否允许自动启动

## 11.2 工作流节点执行

在节点真正执行前，应统一判断：

- 当前节点能力是否允许
- 是否命中审批
- 是否命中高风险硬阻断

## 11.3 Agent / Skill 调用

在 Agent 调度某个 Skill 前，应统一判断：

- Agent 是否可见
- Skill 是否直接授权
- Skill 来源插件是否可运行
- 对应知识库是否可用

## 11.4 插件入口

包括：

- 插件 API
- 插件 webhook
- 插件页面
- 插件前端资源

都应走统一策略层。

---

## 十二、与审批系统的关系

策略引擎不负责审批本身，但负责判断“是否要进入审批”。

### 12.1 正确职责分层

```text
策略引擎
-> 产出 decision = approval
-> 审批中心创建 ApprovalTask
-> WorkflowRun 进入 waiting_approval
```

### 12.2 不建议让策略引擎直接创建审批任务

否则策略引擎会耦合：

- 审批数据模型
- 审批通知
- 审批 UI

这会让它过重。

---

## 十三、与知识注入系统的关系

知识注入也应该经过策略引擎判断。

例如：

- 某企业是否有权限使用某知识库
- 某平台知识库是否被该企业停用
- 某页面上下文是否超出预算
- 某知识源是否适用于当前工作流

### 13.1 知识策略不是“AI 内部细节”，而是运行时安全边界

这点必须明确。

如果不做统一判断，很容易出现：

- 用错企业知识
- 把平台全局知识错误注入企业私有流程
- 超出 `page_context` 预算

---

## 十四、缓存与性能建议

策略引擎本身会被高频调用，因此需要考虑性能，但不能用缓存破坏正确性。

### 14.1 可缓存的内容

例如：

- 套餐能力快照
- 企业授权快照
- 插件 License 状态短期快照
- 发布版本快照

### 14.2 不建议长时间缓存的内容

例如：

- 审批是否通过
- 触发器是否被刚停用
- 当前版本是否已回滚

这些变化更敏感，缓存过久容易出错。

### 14.3 建议缓存策略

第一阶段建议：

- 短 TTL
- 变更时主动失效
- 所有关键裁决结果都带快照，便于审计

---

## 十五、审计要求

策略引擎本身的裁决结果也应该成为审计对象。

建议至少记录：

- 输入上下文摘要
- 最终决策
- 命中规则
- 解析出的版本
- 使用的授权与 License 快照

### 15.1 为什么要审计策略决策

因为后续经常会出现问题：

- 为什么这次能跑
- 为什么这次不能跑
- 为什么某企业看到页面却不能执行

如果没有策略决策快照，就无法还原原因。

---

## 十六、建议的实现结构

建议实现上采用如下层次：

```text
RuntimePolicyEngine
  -> PolicyContextBuilder
  -> subscription_policy_domain
  -> entitlement_policy_domain
  -> plugin_policy_domain
  -> release_policy_domain
  -> risk_policy_domain
  -> approval_policy_domain
  -> knowledge_policy_domain
  -> RuntimePolicyDecision
```

### 16.1 为什么要有 `PolicyContextBuilder`

因为各个入口传入的上下文不一样。

例如：

- 插件 API 入口有 `plugin_name`
- 工作流节点入口有 `node_type`
- Agent 入口有 `agent_id`、`skill_id`

不应让每个域自己去拼上下文，建议由统一 builder 先标准化。

---

## 十七、第一阶段实施建议

### Phase 1：先统一四个最关键的判断

优先整合：

- 套餐能力
- 企业授权
- 插件运行时 gate
- 发布与触发判断

### Phase 2：再整合风险和审批裁决

补齐：

- 风险等级解析
- 审批要求输出
- `allow/confirm/approval/deny` 标准化

### Phase 3：最后整合知识与上下文策略

补齐：

- 知识库可用性
- 平台知识停用
- 页面上下文预算
- 来源可信度策略

---

## 十八、关键结论

1. 运行时策略引擎是平台级统一裁决层，必须服务于工作流、Agent、插件和知识注入等所有执行入口。
2. 它不应只返回允许/拒绝，而应返回标准化决策结果、命中规则、后续动作和快照信息。
3. 现有 `plugin runtime gate` 不应被推翻，而应被纳入策略引擎作为 `plugin_policy_domain` 的实现基础。
4. 企业覆盖策略和工作流局部策略都不能突破平台基线、套餐能力和授权底线。
5. 策略引擎负责裁决，不负责真正执行或创建审批实例，职责边界必须保持清晰。
6. 第一阶段先统一套餐、授权、插件 gate、发布触发四块判断，再逐步扩展到风险审批和知识注入策略。

# AI 编排与工作流平台工作流数据契约与 Schema 规范（2026-03-23）

## 一、文档目标

本文档用于定义平台里“数据如何稳定进入工作流、在节点之间流动、被产出为 Artifact、再被审批和评估消费”的统一规则。

这份文档要解决的不是某个行业字段怎么命名，而是平台级的几个根问题：

1. 工作流输入输出到底靠什么约束，Prompt 还是契约。
2. 不同节点之间如何传数据，什么该内联，什么该传引用。
3. 触发器、节点、Artifact、审批包、评估记录之间是否有统一 Schema 体系。
4. 行业方案、企业模板、企业简单工作流如何在“不写代码”的前提下复用同一套数据契约体系。

如果没有这份文档，后面平台会非常快地陷入以下问题：

- 每个工作流都在自创字段名
- 触发器能进来的数据，节点吃不下
- Agent 输出一段自然语言，下游节点没法可靠消费
- Artifact、审批包、评估记录各自一套格式
- 一升级模板，企业历史运行和新版本数据就不兼容

所以，这份文档的核心目标是：

> 让工作流从“靠提示词拼起来”升级为“靠可验证的数据契约运行”。

---

## 二、核心结论

### 2.1 工作流必须遵循“契约优先”，不能只靠 Prompt

Prompt 可以表达任务意图，但不能承担全部结构约束。

真正稳定的平台级工作流，必须至少明确：

- 输入契约
- 节点端口契约
- Artifact 契约
- 审批包契约
- 评估记录契约

### 2.2 必须区分“控制信封”和“业务负载”

建议正式区分两层数据：

1. 控制信封 `control_envelope`
2. 业务负载 `business_payload`

控制信封用于承载：

- `tenant_id`
- `run_id`
- `trace_id`
- 版本快照
- 策略与风险元信息

业务负载用于承载：

- 订单数据
- 内容草稿
- 指标结果
- 选题建议
- 审批材料

这两层如果不拆开，后面所有节点都会把“业务数据”和“运行控制元数据”混成一坨。

### 2.3 大对象默认传引用，小对象才适合内联

工作流运行时不能把所有内容都直接塞在节点输入输出里。

建议原则：

- 小型结构化对象可内联
- 大文本、长表格、多媒体、联网证据默认走 `artifact_ref`

否则会直接带来：

- 上下文膨胀
- 重复序列化
- 运行成本失控
- 审计与回放困难

### 2.4 契约必须版本化，并独立于工作流版本管理

工作流版本说明“流程结构变了没有”。

数据契约版本说明“输入输出格式变了没有”。

这两者不能混成一个版本号。

### 2.5 企业允许绑定字段和映射规则，但不允许编写任意数据变换代码

企业端可以做：

- 字段映射
- 默认值设置
- 枚举映射
- 低风险格式转换
- 可视化表单映射

企业端不可以做：

- 任意脚本变换
- 任意 Python/JS 数据处理
- 任意自定义序列化逻辑

复杂变换仍属于平台托管能力。

---

## 三、为什么这是平台内核级文档

前面的文档已经把很多关键方向确定了：

- 方案插件是资源包
- 触发和发布必须拆开
- 平台要有统一运行时策略引擎
- 企业知识注入必须分通道
- 企业能编排，但不能扩核

但如果没有统一数据契约规范，前面这些设计很难真正落地。

因为最终会卡在几个非常现实的问题上：

1. `webhook` 进来的 payload 到底怎么标准化。
2. `planner` 节点输出的计划，下游怎么知道字段齐不齐。
3. 联网分析节点给出的证据，审批节点怎么稳定读取。
4. 企业上传的一批资产，是以 `artifact`、`dataset` 还是 `knowledge context` 形态流转。

所以，数据契约不是实现细节，而是 AI 编排平台真正能规模化复用的基础。

---

## 四、正式对象模型

建议把工作流数据契约相关对象正式抽出来。

### 4.1 核心对象建议

| 对象 | 作用 |
|---|---|
| `schema_contract` | 一个可被复用的正式数据契约定义 |
| `schema_contract_version` | 契约版本，支持兼容性判断 |
| `workflow_port_binding` | 某个工作流节点输入/输出端口绑定哪个契约 |
| `mapping_rule_set` | 字段映射、默认值、枚举映射、低风险转换规则集合 |
| `artifact_descriptor` | 大对象、文件、表格、证据、草稿等 Artifact 的统一描述 |
| `evidence_reference` | 联网来源、知识来源、表格来源、页面上下文来源等证据引用 |
| `validation_result` | 每次契约验证的标准化结果 |
| `contract_registry` | 平台、行业方案、企业级契约的统一注册视图 |

### 4.2 契约定义的三层来源

建议明确三层来源：

| 来源层 | 说明 |
|---|---|
| 平台层 | 平台统一标准契约，如触发器、Artifact、审批包、评估记录 |
| 方案层 | 行业方案插件随包交付的业务契约 |
| 企业层 | 企业在可视化配置层做的字段映射与参数约束 |

### 4.3 企业层不应产生“新的底层运行时契约类型”

企业可以绑定已有契约、扩充允许扩展的字段、配置映射规则。

但企业不应：

- 定义新的系统级端口类型
- 定义新的执行期解释器
- 定义新的任意变换语言

---

## 五、统一数据信封模型

建议平台所有节点之间传递数据时，统一使用一个标准外层信封，例如：

- `WorkflowDataEnvelope`

### 5.1 建议结构

```json
{
  "envelope_version": "1.0.0",
  "contract_ref": {
    "contract_code": "analysis.report",
    "contract_version": "1.2.0",
    "schema_hash": "sha256:..."
  },
  "control": {
    "tenant_id": 1001,
    "run_id": "wr_001",
    "node_run_id": "wnr_008",
    "trace_id": "trace_xxx",
    "workflow_version_id": "wfv_20260323_01",
    "entrypoint": "schedule",
    "risk_level": "medium",
    "autonomy_level": "L2"
  },
  "payload": {
    "title": "本次分析报告",
    "summary": "..."
  },
  "artifacts": [
    {
      "artifact_id": "art_001",
      "artifact_type": "dataset",
      "schema_ref": "dataset.timeseries.v1",
      "storage_uri": "artifact://..."
    }
  ],
  "evidence": [
    {
      "source_type": "web_search",
      "source_uri": "https://example.com/...",
      "captured_at": "2026-03-23T10:00:00Z",
      "trust_level": "medium"
    }
  ],
  "meta": {
    "produced_at": "2026-03-23T10:00:03Z",
    "producer_node_type": "llm"
  }
}
```

### 5.2 为什么必须有统一外层信封

这样做的价值很直接：

- 任意节点都能先读控制信息
- 契约版本和真实 payload 不会失联
- 回放、审计、评估都能复用同一套外围元数据

---

## 六、契约分层模型

建议平台正式拆成 6 层数据契约。

### 6.1 `trigger_contract`

定义：

- 外部或内部触发器进入工作流时的标准输入结构

覆盖：

- `manual`
- `schedule`
- `api`
- `webhook`
- `event`

### 6.2 `workflow_input_contract`

定义：

- 工作流开始执行时可被首节点消费的标准输入结构

它是触发器输入被标准化后的结果，不一定等于原始触发 payload。

### 6.3 `node_port_contract`

定义：

- 任意节点输入端口和输出端口的数据类型与字段约束

这是工作流图里最关键的一层。

### 6.4 `artifact_contract`

定义：

- 工作流运行中产生的大对象、文档、图片、表格、草稿、证据包等 Artifact 的统一结构

### 6.5 `approval_contract`

定义：

- 供审批节点和审批中心消费的标准审批包结构

### 6.6 `evaluation_contract`

定义：

- 供评估、复盘、人工反馈、版本对比使用的标准记录结构

---

## 七、基础契约类型目录

为了避免每个行业都从零自造类型，建议平台先内置一批基础契约类型。

### 7.1 建议的基础类型

| 类型编码 | 说明 |
|---|---|
| `scalar.text` | 简单文本 |
| `scalar.number` | 数值 |
| `scalar.boolean` | 布尔值 |
| `object.record` | 结构化对象 |
| `dataset.table` | 表格型数据集 |
| `dataset.timeseries` | 时间序列数据集 |
| `document.bundle` | 文档包 |
| `media.bundle` | 图片/音频/视频集合 |
| `analysis.report` | 分析报告结构 |
| `plan.steps` | 计划/步骤集合 |
| `decision.packet` | 决策建议包 |
| `approval.packet` | 审批材料包 |
| `evaluation.record` | 评估记录 |
| `write.intent` | 受控写动作执行意图 |
| `write.receipt` | 写动作执行回执 |

### 7.2 为什么要内置 `analysis.report`、`plan.steps` 这类类型

因为 AI 编排平台里最常见的并不是简单文本，而是：

- 分析结论
- 行动计划
- 建议列表
- 审批材料

如果平台不先内置这类中阶契约，后面所有行业方案都会重复造轮子。

---

## 八、触发器输入契约规范

### 8.1 `manual`

建议结构至少包含：

- 发起人信息
- 表单输入
- 当前页面上下文引用
- 手动备注

### 8.2 `schedule`

建议结构至少包含：

- 调度计划 ID
- 计划执行时间窗口
- 调度生成参数
- 上次运行引用

### 8.3 `api`

建议结构至少包含：

- 调用方身份
- 幂等键
- 标准化请求体
- 签名或认证结果

### 8.4 `webhook`

建议结构至少包含：

- 来源系统标识
- 签名校验结果
- 原始 payload 摘要
- 标准化后的业务负载
- 重放防护标记

### 8.5 `event`

建议结构至少包含：

- 事件编码
- 事件发生时间
- 事件生产者
- 事件正文
- 相关资源引用

### 8.6 触发器进入工作流前必须经过标准化

建议固定执行以下过程：

```text
原始触发 payload
-> Trigger Contract 校验
-> 标准化映射
-> Workflow Input Contract 校验
-> 创建 WorkflowRun
```

不要让首节点直接去解析各种原始触发格式。

---

## 九、节点输入输出契约矩阵

不同类型节点吃的数据不同，应该预定义推荐契约组合。

### 9.1 建议矩阵

| 节点类型 | 推荐输入契约 | 推荐输出契约 |
|---|---|---|
| `input` | `workflow_input_contract` | `object.record` |
| `condition` | `object.record` / `dataset.table` | `decision.packet` |
| `router` | `decision.packet` | `decision.packet` |
| `llm` | `object.record` / `analysis.report` / `plan.steps` | `analysis.report` / `plan.steps` / `document.bundle` |
| `planner` | `object.record` / `analysis.report` | `plan.steps` |
| `knowledge_lookup` | `object.record` / 查询对象 | `document.bundle` / `evidence_reference[]` |
| `data_read` | `object.record` / 查询参数 | `dataset.table` / `dataset.timeseries` |
| `tool.readonly` | `object.record` / `write.intent` 之外的受控参数 | `object.record` / `dataset.table` / `write.receipt` |
| `approval` | `approval.packet` | `decision.packet` |
| `review` | `analysis.report` / `document.bundle` / `approval.packet` | `evaluation.record` |
| `external_write` | `write.intent` + 审批令牌 | `write.receipt` |
| `output` | 任意已校验契约 | `artifact_descriptor` / 终态回执 |

### 9.2 `llm` 节点不应默认只输出自由文本

建议平台要求：

- 有明确输出契约时，优先输出结构化对象
- 纯文本输出也要附带 `contract_ref`

否则下游节点会非常难接。

---

## 十、Artifact 契约规范

Artifact 是工作流稳定运行的关键，因为真正有价值的大对象通常不适合直接在节点间全量内联传输。

### 10.1 `artifact_descriptor` 建议字段

| 字段 | 说明 |
|---|---|
| `artifact_id` | Artifact ID |
| `artifact_type` | `dataset` / `draft` / `report` / `approval_packet` / `evidence_bundle` / `media` |
| `schema_ref` | Artifact 使用的数据契约 |
| `mime_type` | 文件或内容类型 |
| `storage_uri` | 存储位置 |
| `summary` | 摘要说明 |
| `producer_node_run_id` | 由哪个节点产生 |
| `retention_policy` | 保留策略 |
| `visibility_scope` | 可见范围 |
| `size_bytes` | 大小 |
| `hash` | 内容摘要 |

### 10.2 Artifact 的基本原则

建议坚持：

1. 大对象默认以 Artifact 形式存储
2. 节点间默认传 `artifact_ref`
3. 审批、评估、复盘优先消费 Artifact 摘要和引用

### 10.3 什么时候允许内联

例如：

- 小型 JSON 对象
- 少量统计数字
- 小于预算的小型表格摘要

其余内容更适合转 Artifact。

---

## 十一、证据与联网来源契约

用户前面特别强调过，未来平台会有很多“数据 + 联网分析”场景。

这类能力如果没有统一证据契约，会非常危险。

### 11.1 `evidence_reference` 建议字段

| 字段 | 说明 |
|---|---|
| `source_type` | `web_search` / `website` / `knowledge_base` / `page_context` / `dataset` / `human_input` |
| `source_id` | 来源对象 ID 或 URL |
| `title` | 来源标题 |
| `excerpt` | 摘要内容 |
| `captured_at` | 获取时间 |
| `freshness_level` | 新鲜度 |
| `trust_level` | 可信度 |
| `license_or_rights` | 权限或使用权信息 |
| `citation_required` | 是否要求最终输出引用 |

### 11.2 联网结果不能只留下最终总结

建议平台要求：

- 最终分析结果必须能回溯证据引用
- 关键结论必须能关联来源
- 重要时间敏感结论必须标明获取时间

否则后面无法做：

- 审批
- 复盘
- 追责
- 版本对比

### 11.3 时间序列和分析结果应包含预测语义

对于分析、预测、推荐类结果，建议正式增加：

- `time_horizon`
- `assumptions`
- `confidence_level`
- `sensitivity_notes`

这样后续评估系统才能判断：

- 这是结论
- 还是假设
- 还是带置信度的预测

---

## 十二、审批包与评估记录契约

### 12.1 `approval.packet`

审批包建议至少包含：

- 审批对象摘要
- 关键输入
- 关键输出
- 风险等级
- 证据引用
- 待审批动作
- 可选执行路径

### 12.2 `evaluation.record`

评估记录建议至少包含：

- 评估对象引用
- 评估版本引用
- 评估标签
- 评分或等级
- 评估原因
- 证据或对照样本
- 人工反馈或系统反馈来源

### 12.3 审批包和评估记录都不应只是纯文本备注

它们必须可结构化查询，否则后续：

- 无法按原因聚合驳回
- 无法按标签统计效果
- 无法做版本比较

---

## 十三、Schema 注册与治理模型

建议平台维护一个统一的契约注册表，而不是让每个模块各自保存一份 JSON Schema。

### 13.1 `contract_registry` 应至少支持以下能力

1. 契约编码与版本管理
2. 契约归属识别
3. 兼容性判断
4. 引用关系追踪
5. 废弃状态标记

### 13.2 契约归属建议

| 归属 | 说明 |
|---|---|
| `platform_managed` | 平台内置标准契约 |
| `solution_managed` | 行业方案插件交付契约 |
| `tenant_bound` | 企业基于现有契约做的绑定与映射 |

### 13.3 企业层的边界

企业层可以：

- 绑定已有契约
- 对允许扩展字段做补充
- 保存自己的映射规则集

企业层不可以：

- 发布新的系统级标准契约
- 替换平台内置基础契约
- 绕过平台契约校验器

---

## 十四、字段映射与低风险变换规则

企业要想真正可用，必须允许做一定程度的可视化映射。

### 14.1 建议允许的变换

| 变换类型 | 说明 |
|---|---|
| 字段重命名映射 | `source_field -> target_field` |
| 默认值补全 | 当源字段缺失时补默认值 |
| 枚举标准化 | 把不同来源枚举映射到统一枚举 |
| 类型安全转换 | 如字符串转数字、时间格式标准化 |
| 字段裁剪 | 删除低优先级字段 |
| 结构投影 | 从大对象里选择指定字段子集 |

### 14.2 建议禁止的变换

| 禁止项 | 原因 |
|---|---|
| 任意脚本执行 | 等于把代码能力下放到企业 |
| 任意网络请求参与变换 | 会把映射层变成执行层 |
| 任意 SQL/DSL | 风险过高，难治理 |
| 隐式跨租户字段引用 | 直接破坏隔离模型 |

### 14.3 复杂变换如何处理

如果企业确实需要：

- 多表合并
- 跨系统聚合
- 高复杂度清洗
- 动态计算逻辑

则应进入：

- 平台托管数据节点
- 行业方案插件增强
- 定制交付

而不是放给企业在映射面板里随意表达。

---

## 十五、契约版本化与兼容性规则

### 15.1 建议契约使用语义化版本

建议采用：

- `major.minor.patch`

### 15.2 版本变更建议

| 变更类型 | 版本建议 |
|---|---|
| 文档、备注、非语义修正 | `patch` |
| 新增可选字段、补充枚举 | `minor` |
| 删除字段、重命名字段、改变必填规则 | `major` |

### 15.3 契约兼容性等级

建议平台统一返回以下判断结果：

| 等级 | 说明 |
|---|---|
| `exact_match` | 完全匹配 |
| `backward_compatible` | 向后兼容，可直接使用 |
| `coercible` | 可通过低风险转换兼容 |
| `migration_required` | 必须先迁移 |
| `incompatible` | 禁止连接 |

### 15.4 契约升级和方案升级的关系

契约升级属于方案升级的重要组成部分，但两者不是同一件事。

建议规则：

- 方案升级前必须先跑契约兼容性预检
- 契约破坏性升级必须进入 `major_upgrade`
- 企业副本若绑定旧契约，必须显示风险提示

---

## 十六、验证时机与校验链路

建议把契约校验拆成 6 个时点。

### 16.1 设计时校验

检查：

- 节点输出契约是否能接到下游输入契约
- 映射规则是否合法
- 是否引用了已废弃契约

### 16.2 保存时校验

检查：

- 图结构是否存在未绑定端口
- 必填契约是否缺失
- 是否存在未解析的映射占位符

### 16.3 发布时校验

检查：

- 所有正式触发入口是否有明确输入契约
- 高风险节点是否有审批包契约
- 产出是否有 Artifact 或输出契约

### 16.4 触发时校验

检查：

- 原始 payload 是否符合 `trigger_contract`
- 标准化后是否符合 `workflow_input_contract`

### 16.5 节点运行前后校验

运行前：

- 输入是否符合端口契约

运行后：

- 输出是否符合声明契约
- 大对象是否正确转为 Artifact

### 16.6 评估与反馈入库校验

检查：

- 评估记录字段是否完整
- 反馈是否绑定到具体版本和对象

---

## 十七、预算、裁剪与传输规则

前面知识注入规范已经强调了预算问题，这里要把它落到数据契约层。

### 17.1 建议的预算分类

| 预算 | 说明 |
|---|---|
| `inline_payload_budget` | 允许在节点间直接传输的 JSON 预算 |
| `artifact_inline_preview_budget` | Artifact 摘要预览预算 |
| `page_context_budget` | 页面上下文预算 |
| `retrieval_context_budget` | 检索结果预算 |
| `approval_packet_budget` | 审批预览包预算 |

### 17.2 裁剪原则

如果超预算，建议优先裁剪：

1. 重复证据
2. 次要样本
3. 大型表格明细
4. 低优先级历史上下文

不要优先裁掉：

- 关键控制信封
- 风险与审批字段
- 主结论和关键证据

### 17.3 裁剪结果应记录在元数据里

建议每次裁剪都可追溯：

- 裁剪前大小
- 裁剪后大小
- 被裁掉的部分
- 裁剪原因

---

## 十八、与运行时策略引擎的关系

数据契约并不只服务于设计器，它也必须进入运行时策略裁决。

### 18.1 策略引擎应至少判断这些问题

1. 当前主体是否有权使用该契约
2. 当前契约是否属于允许的版本
3. 当前 Artifact 是否超出作用域或预算
4. 当前节点是否在尝试输出未声明契约

### 18.2 为什么契约问题要进入策略层

因为很多问题不是“字段对不对”，而是：

- 该企业有没有资格用这类高风险数据输出
- 该节点能不能产出 `write.intent`
- 该审批节点能不能接收这个未审计的外部证据包

这些都已经超出纯技术校验，属于运行时治理问题。

---

## 十九、最小示范链路

为了帮助后续实现，下面给一个平台级而非行业专属的最小示范。

### 19.1 示例：分析型工作流

```text
API / Schedule Trigger
-> workflow_input_contract: analysis.request
-> data_read 输出 dataset.timeseries
-> knowledge_lookup 输出 evidence_reference[]
-> llm 输出 analysis.report
-> approval 输出 approval.packet / decision.packet
-> output 生成 report Artifact
-> evaluation.record 记录采用与反馈
```

### 19.2 这条链路说明了什么

它说明平台至少要稳定支持：

- 标准化触发输入
- 数据集契约
- 联网证据契约
- 结构化分析报告契约
- 审批包契约
- 评估记录契约

只要这几层成立，后面无论是：

- 电商分析
- 短视频增长
- 线索筛选
- 售后复盘

都能复用同一套运行框架。

---

## 二十、第一阶段实施建议

### Phase 1：先把最核心的标准契约做出来

优先建设：

- `trigger_contract`
- `workflow_input_contract`
- `artifact_descriptor`
- `approval.packet`
- `evaluation.record`

### Phase 2：再补节点端口绑定与映射规则

补齐：

- `workflow_port_binding`
- `mapping_rule_set`
- 设计时校验
- 发布时校验

### Phase 3：最后补契约注册表与升级兼容工具

补齐：

- `contract_registry`
- 契约差异对比
- 兼容性判断
- 企业副本契约升级建议

---

## 二十一、关键结论

1. 工作流平台必须坚持“契约优先”，不能只靠 Prompt 和自然语言约定来传递数据。
2. 必须明确区分控制信封与业务负载，并让所有节点通过统一数据信封流转。
3. 触发器、节点端口、Artifact、审批包、评估记录都应属于同一套正式 Schema 体系。
4. 大对象默认走 Artifact 引用，小对象才适合内联传输，这样才能控制成本、回放与审计复杂度。
5. 契约必须独立版本化，并在设计、保存、发布、触发、节点执行、评估入库六个阶段都可被验证。
6. 企业可以做字段映射和低风险转换，但不能编写任意数据变换代码；复杂数据处理仍应属于平台托管能力。

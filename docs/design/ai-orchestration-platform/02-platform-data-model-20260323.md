# AI 编排与工作流平台数据模型草案（2026-03-23）

## 一、文档目标

本文档定义“AI 编排与工作流平台”在数据层面的推荐模型，目标是回答三个问题：

1. 哪些模型应该直接复用当前项目已有对象。
2. 哪些平台级实体必须新增，才能承载工作流、审批、授权和行业方案分发。
3. 如何让“插件市场 + 行业解决方案 + 企业自建简单工作流”落在同一套模型里。

本文档是平台级草案，不直接绑定某个行业。

---

## 二、设计原则

### 2.1 优先复用现有成熟对象

当前项目已经具备以下基础模型或能力，不建议重复造轮子：

- `Plugin`
- `PluginVersion`
- `SkillPackage`
- `Skill`
- `Agent`
- `AgentSkillGrant`
- 现有租户、权限、通知、任务、配额模型

平台化设计应优先在这些成熟模型上增加必要字段和关联，而不是再造一套平行概念。

### 2.2 插件与行业方案统一建模

“行业解决方案中心”既然并入插件市场，则行业方案的发行单元建议仍然以 `Plugin` 为中心建模。

换句话说：

- `Plugin` 是统一发行单元
- “能力插件”和“行业解决方案插件”只是在分类和授权上不同

### 2.3 工作流模板与运行实例分离

必须区分：

- 模板定义
- 企业派生版本
- 运行实例

否则后续无法支持：

- 平台模板分发
- 企业复制模板
- 模板升级不破坏企业已运行实例

### 2.4 审批必须是一级对象

审批不能只做工作流中的一个布尔字段，必须是正式模型，否则无法支持：

- 多级审批
- 双人审批
- 审批超时
- 审批意见记录
- 审批实例回放

---

## 三、模型分层

建议按 6 个层次组织数据模型：

1. 插件与发行层
2. 授权与计费层
3. 模板与配置层
4. 运行时层
5. 审批与治理层
6. 企业知识与资产层

---

## 四、插件与发行层

### 4.1 复用 `Plugin`

建议继续使用现有 `Plugin` 作为统一发行单元。

新增或规范化的字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `plugin_kind` | enum | `capability_plugin` / `solution_plugin` / `ui_plugin` / `content_plugin` |
| `solution_category` | string nullable | 行业分类，如 `short_video` / `ecommerce` / `sales` |
| `ownership_scope` | enum | `system` / `platform` / `tenant` |
| `availability_scope` | enum | `global_public` / `licensed_tenants` / `selected_tenants` / `owner_only` |
| `billing_scope` | enum | `included` / `addon` / `custom_delivery` / `usage_metered` |
| `is_marketplace_listed` | bool | 是否在市场上架 |
| `delivery_mode` | enum | `self_service` / `managed_delivery` / `custom_delivery` |
| `product_code` | string nullable | 商业 SKU 编码 |
| `solution_metadata` | json nullable | 行业包元数据、展示文案、能力摘要 |

说明：

- `plugin_kind` 用于区分能力插件和解决方案插件。
- 行业方案不新增单独发行主表，直接挂在 `Plugin` 上。
- 若后续插件市场已有类似字段，可在实现时做字段归并，而不是机械新增。

### 4.2 复用 `PluginVersion`

建议继续使用 `PluginVersion` 管理版本快照。

建议增加或规范化：

| 字段 | 类型 | 说明 |
|---|---|---|
| `release_channel` | enum | `stable` / `beta` / `internal` |
| `breaking_level` | enum | `none` / `minor` / `major` |
| `compatible_workflow_schema_version` | string nullable | 对应工作流 schema 版本 |

---

## 五、授权与计费层

### 5.1 新增 `TenantEntitlement`

建议引入统一授权表，避免把套餐、方案包、定制交付散落在多个地方。

表：`tenant_entitlements`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `entitlement_type` | enum | `platform_subscription` / `solution_package` / `custom_delivery` |
| `target_type` | enum | `plugin` / `workflow_template` / `skill_package` / `agent_profile` |
| `target_id` | int | 对应目标 ID |
| `status` | enum | `active` / `expired` / `suspended` / `revoked` |
| `starts_at` | datetime | 生效时间 |
| `ends_at` | datetime nullable | 结束时间 |
| `granted_by_admin_id` | int nullable | 管理端发放人 |
| `order_ref` | string nullable | 订单或交付记录 |
| `notes` | text nullable | 备注 |

作用：

- 统一承载平台订阅、行业方案授权、定制交付授权
- 所有企业可见能力均应由 Entitlement 驱动

### 5.2 新增 `PlanPluginBinding`

如果要支持“某套餐自动包含某些方案插件”，建议新增绑定表。

表：`plan_plugin_bindings`

建议字段：

- `plan_id`
- `plugin_id`
- `default_enabled`
- `sort_order`

### 5.3 新增 `CustomDeliveryRecord`

如果后续要管理“管理端为某企业定制了一套流程并交付”，建议新增交付记录表。

表：`custom_delivery_records`

建议字段：

- `tenant_id`
- `plugin_id` nullable
- `workflow_template_id` nullable
- `delivery_type`
- `status`
- `quoted_price`
- `delivered_at`
- `owner_admin_id`
- `notes`

---

## 六、模板与配置层

### 6.1 新增 `WorkflowTemplate`

平台必须有正式的工作流模板对象。

表：`workflow_templates`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `code` | string unique | 稳定模板编码 |
| `name` | string | 模板名 |
| `description` | text nullable | 描述 |
| `mode` | enum | `deterministic` / `hybrid` / `agentic` |
| `template_type` | enum | `platform` / `solution` / `tenant_custom` |
| `ownership_scope` | enum | 归属作用域 |
| `availability_scope` | enum | 可用作用域 |
| `billing_scope` | enum | 计费作用域 |
| `source_plugin` | string nullable | 来源插件名 |
| `owner_tenant_id` | int nullable | 企业自建模板归属 |
| `parent_template_id` | int nullable | 派生来源模板 |
| `is_system` | bool | 系统模板 |
| `is_editable_by_tenant` | bool | 企业是否可复制并编辑 |
| `risk_level` | enum | `low` / `medium` / `high` / `critical` |
| `default_agent_id` | int nullable | 默认执行 Agent |
| `default_config` | json nullable | 默认参数 |
| `status` | enum | `draft` / `published` / `disabled` |

### 6.2 新增 `WorkflowTemplateVersion`

模板必须版本化。

表：`workflow_template_versions`

建议字段：

- `workflow_template_id`
- `version`
- `schema_version`
- `snapshot_json`
- `change_summary`
- `published_by`
- `published_at`

### 6.3 新增 `WorkflowTemplateNode`

表：`workflow_template_nodes`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `workflow_template_id` | FK | 模板 ID |
| `node_key` | string | 模板内唯一标识 |
| `node_type` | enum | `trigger` / `input` / `router` / `planner` / `llm` / `tool` / `condition` / `approval` / `merge` / `memory` / `output` |
| `title` | string | 节点名 |
| `config` | json | 节点配置 |
| `ui_position` | json nullable | 画布位置 |
| `sort_order` | int | 排序 |

### 6.4 新增 `WorkflowTemplateEdge`

表：`workflow_template_edges`

建议字段：

- `workflow_template_id`
- `source_node_key`
- `target_node_key`
- `edge_type`
- `condition_expr` nullable
- `label` nullable

### 6.5 新增 `TenantWorkflow`

企业复制平台模板后，不建议直接改 `WorkflowTemplate` 原表，而是形成企业工作流副本。

表：`tenant_workflows`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `source_template_id` | FK nullable | 来自哪个模板 |
| `name` | string | 企业自己的工作流名 |
| `description` | text nullable | 描述 |
| `mode` | enum | 同模板 |
| `is_simple_builder` | bool | 是否企业简单工作流 |
| `status` | enum | `draft` / `published` / `disabled` |
| `editable_level` | enum | `tenant_simple` / `managed_locked` / `managed_partial` |
| `workflow_json` | json | 企业当前可执行版本 |

说明：

- 企业端自建简单工作流落在这里。
- 管理端交付但允许企业改少量参数的流程，也可落在这里。

---

## 七、运行时层

### 7.1 新增 `WorkflowRun`

表：`workflow_runs`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `workflow_template_id` | FK nullable | 来源平台模板 |
| `tenant_workflow_id` | FK nullable | 来源企业工作流 |
| `trigger_source` | enum | `manual` / `schedule` / `api` / `webhook` / `event` |
| `mode` | enum | `deterministic` / `hybrid` / `agentic` |
| `status` | enum | `draft` / `queued` / `planning` / `running` / `waiting_approval` / `resumed` / `completed` / `failed` / `cancelled` |
| `started_by_type` | enum | `platform_admin` / `tenant_admin` / `system` |
| `started_by_id` | int nullable | 发起人 |
| `current_node_key` | string nullable | 当前节点 |
| `input_payload` | json nullable | 初始输入 |
| `final_output` | json nullable | 最终输出 |
| `error_summary` | text nullable | 错误摘要 |
| `cost_summary` | json nullable | 成本汇总 |
| `started_at` | datetime nullable | 开始时间 |
| `ended_at` | datetime nullable | 结束时间 |

### 7.2 新增 `WorkflowNodeRun`

表：`workflow_node_runs`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `workflow_run_id` | FK | 运行实例 |
| `node_key` | string | 节点标识 |
| `node_type` | enum | 节点类型 |
| `status` | enum | `pending` / `running` / `waiting_approval` / `success` / `failed` / `skipped` / `cancelled` |
| `attempt_no` | int | 重试次数 |
| `executor_type` | enum | `llm` / `tool` / `planner` / `approval` / `system` |
| `executor_ref` | string nullable | 对应 Agent / Skill / policy 编码 |
| `input_payload` | json nullable | 输入 |
| `output_payload` | json nullable | 输出 |
| `error_detail` | text nullable | 错误详情 |
| `duration_ms` | int nullable | 耗时 |
| `started_at` | datetime nullable | 开始时间 |
| `ended_at` | datetime nullable | 结束时间 |

### 7.3 新增 `ExecutionArtifact`

表：`execution_artifacts`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `workflow_run_id` | FK | Run |
| `workflow_node_run_id` | FK nullable | NodeRun |
| `artifact_type` | enum | `prompt` / `tool_result` / `search_result` / `analysis` / `action_preview` / `approval_packet` / `report` |
| `title` | string | 标题 |
| `content_json` | json nullable | 结构化内容 |
| `content_text` | text nullable | 文本内容 |
| `visibility` | enum | `internal` / `tenant_visible` / `approval_only` |

说明：

- Artifact 是后续回放、审计、评估的基础。
- 不建议把所有中间产物都塞进 Run 的 JSON 大字段里。

---

## 八、审批与治理层

### 8.1 新增 `ApprovalPolicy`

表：`approval_policies`

建议字段：

- `code`
- `name`
- `owner_type`
- `owner_tenant_id`
- `risk_level`
- `rule_json`
- `is_system`
- `status`

作用：

- 定义哪些节点需要审批
- 定义审批人选择规则
- 定义双人审批或超时规则

### 8.2 新增 `ApprovalPolicyBinding`

表：`approval_policy_bindings`

建议字段：

- `target_type`：`workflow_template` / `tenant_workflow` / `plugin`
- `target_id`
- `approval_policy_id`
- `priority`

### 8.3 新增 `ApprovalTask`

表：`approval_tasks`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `workflow_run_id` | FK | 关联 Run |
| `workflow_node_run_id` | FK | 关联节点 |
| `approval_policy_id` | FK nullable | 命中的审批策略 |
| `status` | enum | `pending` / `approved` / `rejected` / `expired` / `cancelled` |
| `approval_type` | enum | `single` / `dual` / `sequential` |
| `risk_level` | enum | 风险级别 |
| `subject` | string | 审批标题 |
| `preview_payload` | json nullable | 动作预览 |
| `expires_at` | datetime nullable | 过期时间 |
| `resolved_at` | datetime nullable | 完成时间 |

### 8.4 新增 `ApprovalDecision`

表：`approval_decisions`

建议字段：

- `approval_task_id`
- `approver_type`
- `approver_id`
- `decision`
- `comment`
- `created_at`

---

## 九、企业知识与资产层

### 9.1 尽量复用现有知识库体系

企业知识建议优先复用现有知识库和附件体系，不建议为“行业知识”再造一套完全独立的文件系统。

### 9.2 建议新增“企业业务配置”总表

表：`tenant_solution_configs`

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | 主键 |
| `tenant_id` | FK | 企业 ID |
| `plugin_id` | FK | 所属行业解决方案插件 |
| `config_key` | string | 配置键 |
| `config_value` | json | 配置值 |
| `scope` | enum | `global` / `workflow` / `agent` |

作用：

- 承载企业品牌规范、审核规范、变量配置、Prompt 参数
- 避免每个行业插件自己发明一套配置存储方式

### 9.3 建议新增“企业资产集合”总表

如果后续企业需要管理素材、样例、SOP、脚本草稿等行业资产，建议新增统一资产抽象。

表：`tenant_solution_assets`

建议字段：

- `tenant_id`
- `plugin_id`
- `asset_type`
- `title`
- `attachment_id` nullable
- `content_json` nullable
- `tags` nullable
- `status`

---

## 十、与现有 AI / 插件模型的衔接

### 10.1 与 `Plugin` 的关系

- 方案包的分发单元仍是 `Plugin`
- 行业能力通过 `solution_plugin` 分类挂入插件市场
- 启用后仍通过现有插件生命周期加载

### 10.2 与 `SkillPackage` / `Skill` 的关系

- 方案插件启用后，可继续同步 `SkillPackage + Skill` 目录投影
- 运行时能力授权真相仍然由 `AgentSkillGrant` 决定
- 工作流节点中的 `tool` 或 `planner` 可引用 Agent / Skill 能力，但不应把 `SkillPackage` 重新拉回运行时真相

### 10.3 与 `Agent` 的关系

- Agent 仍是 AI 执行主体
- Workflow 可选择默认 Agent，也可在节点内指定 Agent
- Agent 不等于 Workflow，二者应是组合关系，不是互相替代

---

## 十一、推荐实施顺序

### P0：先建平台级基础表

优先级最高：

- `tenant_entitlements`
- `workflow_templates`
- `workflow_template_versions`
- `workflow_template_nodes`
- `workflow_template_edges`
- `tenant_workflows`
- `workflow_runs`
- `workflow_node_runs`
- `execution_artifacts`
- `approval_tasks`
- `approval_decisions`

### P1：再扩 `Plugin` 与商业字段

推荐在平台级工作流基础稳定后，再补：

- `plugin_kind`
- `solution_category`
- `ownership_scope`
- `availability_scope`
- `billing_scope`
- `delivery_mode`
- `solution_metadata`

### P2：最后补企业方案配置和资产层

- `tenant_solution_configs`
- `tenant_solution_assets`
- 定制交付记录与方案运营字段

---

## 十二、关键结论

1. 行业解决方案不建议另起一套发行主表，建议继续以 `Plugin` 作为统一发行单元。
2. 平台必须新增正式的工作流模板、运行实例、节点运行、产物、审批模型。
3. 企业复制平台模板后，应形成 `tenant_workflows` 企业副本，而不是直接改平台模板。
4. 审批必须是一级模型，不能只做节点配置字段。
5. 企业知识和业务配置建议通过统一配置表与资产表承载，避免每个行业插件自创存储方式。
6. 运行时仍应保持 `Agent -> Skill -> AIGateway` 的主链路，不因为工作流引入新的运行时真相。


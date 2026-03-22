# AI 编排平台跨 AI 契约矩阵（2026-03-23）

## 一、文档目标

本文档用于定义 4 个 AI 并行开发时必须共同遵守的跨域契约，尤其是：

- `AI-1` 与 `AI-2` 的后端共享口径
- `AI-2` 与 `AI-3` / `AI-4` 的前后端接口口径
- 权限、状态、字段、命名、分页、错误与时间格式的统一规则

本文档不是实现细节文档，而是跨 AI 的接口裁决文档。

---

## 二、核心结论

### 2.1 共享契约必须先于并行编码被固定

如果没有共享契约，4 个 AI 会各自实现出“局部合理”的结构，最终在集成时爆炸。

### 2.2 设计时域归 `AI-1`，运行时域归 `AI-2`

这条必须明确。

- `AI-1` 是设计时对象真相源
- `AI-2` 是运行时对象真相源

如果一个字段的所有权不明确，就会在集成时来回扯。

### 2.3 前端不拥有业务字段真相，只拥有页面组织权

也就是说：

- `AI-3` / `AI-4` 不能自行发明后端字段
- 如果前端需要假设字段，必须写进 handoff
- 最终以后端共享契约为准

---

## 三、对象所有权矩阵

| 对象 | 所有者 | 使用者 |
|---|---|---|
| `solution` | `AI-1` | `AI-2` / `AI-3` |
| `workflow` | `AI-1` | `AI-2` / `AI-3` / `AI-4` |
| `release` | `AI-1` | `AI-2` / `AI-3` |
| `trigger` | `AI-1` | `AI-2` / `AI-3` |
| `environment` | `AI-1` | `AI-2` / `AI-3` |
| `change_set` | `AI-1` | `AI-3` |
| `activation` | `AI-2` | `AI-4` / `AI-3` |
| `run` | `AI-2` | `AI-3` / `AI-4` |
| `node_run` | `AI-2` | `AI-3` |
| `approval` | `AI-2` | `AI-3` / `AI-4` |
| `artifact` | `AI-2` | `AI-3` / `AI-4` |
| `recommendation` | `AI-2` | `AI-3` / `AI-4` |
| `feedback` | `AI-2` | `AI-4` |
| `market_review` | `AI-2` | `AI-3` |

### 3.1 所有者的含义

所有者负责定义：

- 主字段
- 状态枚举
- 主体生命周期
- 与其他对象的主外键关系

使用者只能消费，不应重定义。

---

## 四、跨域 ID 与字段命名规则

## 4.1 主键与外键

统一规则：

- 主键统一为 `id`
- 外键统一为 `<object>_id`
- 禁止同义字段混用，例如同时出现 `workflow_id` / `orchestration_workflow_id`

推荐外键如下：

- `solution_id`
- `workflow_id`
- `release_id`
- `trigger_id`
- `environment_id`
- `activation_id`
- `run_id`
- `approval_id`
- `artifact_id`
- `recommendation_id`

## 4.2 多租户与归属字段

统一规则：

- 企业隔离字段统一为 `tenant_id`
- 创建人统一为 `created_by`
- 更新人统一为 `updated_by`
- 时间统一为 `created_at` / `updated_at`

## 4.3 可读编码字段

如某对象需要人类可读编码，统一命名为：

- `code`

禁止同一层再出现：

- `key`
- `biz_code`
- `identifier`

除非有明确语义差异。

---

## 五、状态与枚举规则

## 5.1 枚举统一要求

所有状态枚举必须：

- 使用字符串枚举
- 使用 snake_case 值
- 由后端定义为真相源
- 前端只消费，不自行重命名

## 5.2 推荐的核心状态集

### 5.2.1 设计时对象

- `draft`
- `published`
- `deprecated`
- `archived`

### 5.2.2 运行时对象

- `pending`
- `running`
- `waiting_human`
- `succeeded`
- `failed`
- `cancelled`

### 5.2.3 审批对象

- `pending`
- `approved`
- `rejected`
- `expired`
- `cancelled`

### 5.2.4 激活对象

- `provisioned`
- `activated`
- `pilot`
- `live`
- `suspended`

### 5.2.5 市场审核对象

- `draft`
- `in_review`
- `pilot_only`
- `published`
- `deprecated`
- `suspended`
- `removed`

### 5.2.6 推荐对象

- `draft`
- `ready`
- `adopted`
- `rejected`
- `expired`

如果需要扩展，必须由对象所有者在 handoff 中声明。

---

## 六、前后端接口契约规则

## 6.1 响应包装

后端统一使用项目响应结构：

- `success()`
- `created()`
- `updated()`
- `paginated()`
- `deleted()`

前端不得假设裸数据返回。

## 6.2 分页与过滤

统一遵守 JSON:API 风格：

- `page[number]`
- `page[size]`
- `filter[field][operator]`
- `sort=-created_at`

## 6.3 字段风格

后端返回 snake_case。

前端页面表单如需 camelCase / snake_case 转换，必须走项目既有 `fields` 或 adapter 机制，不得自行发明一套。

## 6.4 时间字段

统一使用 ISO 8601。

前端展示必须使用项目时间工具，不得自己用原生 `toLocaleString`。

## 6.5 错误与消息

后端只返回 message key 对应的国际化消息，不允许写死中文字符串。

前端页面层也不允许写死中文字符串。

---

## 七、权限与资源命名约定

## 7.1 后端资源名约定

建议统一使用以下 `permission_resource` 命名：

- `orchestration_solution`
- `orchestration_workflow`
- `orchestration_release`
- `orchestration_trigger`
- `orchestration_environment`
- `orchestration_change_set`
- `orchestration_run`
- `orchestration_approval`
- `orchestration_activation`
- `orchestration_recommendation`
- `orchestration_market_review`

### 7.1.1 为什么要提前写死

因为如果不提前统一：

- 后端资源名
- 前端权限码
- 菜单翻译键

会在最后集成时全部错位。

## 7.2 菜单与页面 key 约定

建议统一使用：

- `menu.orchestration.*` 作为菜单翻译前缀
- `admin.orchestration.*` 作为管理端页面文案前缀
- `tenant.orchestration.*` 作为企业端页面文案前缀

---

## 八、AI-1 与 AI-2 的共享边界

## 8.1 `AI-1` 输出给 `AI-2` 的对象

`AI-2` 只能引用，不得重定义以下对象的主结构：

- `solution`
- `workflow`
- `release`
- `trigger`
- `environment`

## 8.2 `AI-2` 依赖 `AI-1` 的最小字段

建议最少假设以下字段存在：

- `workflow.id`
- `workflow.tenant_id`
- `workflow.code`
- `workflow.status`
- `release.id`
- `release.workflow_id`
- `release.status`
- `environment.id`
- `environment.code`
- `trigger.id`
- `trigger.workflow_id`

如果 `AI-1` 使用不同字段，必须在 handoff 中明确说明。

## 8.3 `AI-2` 不得自行发明设计时状态

运行时如需引用设计时状态或版本信息，只能消费 `AI-1` 已定义字段。

---

## 九、AI-2 与 AI-3 / AI-4 的共享边界

## 9.1 `AI-2` 是运行时 API 真相源

以下对象的接口字段，以 `AI-2` 为准：

- `run`
- `approval`
- `activation`
- `recommendation`
- `artifact`

## 9.2 `AI-3` / `AI-4` 可以先做页面占位，但必须记录字段假设

如果前端先开发而后端还未完全落地，允许：

- 页面结构先行
- mock 字段先行

但必须：

- 把字段假设写进 handoff
- 标注“待以后端为准”

## 9.3 推荐对象的最小结构

为避免企业端和管理端各自猜测，建议 `recommendation` 至少包含：

- `id`
- `tenant_id`
- `workflow_id`
- `recommendation_type`
- `status`
- `decision_goal`
- `primary_option`
- `alternative_options`
- `evidence_summary`
- `assumptions`
- `confidence_level`
- `risk_notes`
- `requires_approval`
- `created_at`

---

## 十、测试与验收契约

## 10.1 后端

每个后端 AI 至少要提供：

- 自己负责 API 的最小 pytest 结果
- 自己负责 Service 的最小单测结果

## 10.2 前端

每个前端 AI 至少要提供：

- `pnpm typecheck` 结果
- 最小页面联调记录
- 至少一张关键页面截图路径

---

## 十一、冲突裁决规则

如果出现口径冲突，统一按以下优先级裁决：

1. 本文档
2. 对象所有者定义
3. 主协调者裁决
4. 集成人最终实现

前端视觉偏好不能覆盖后端契约真相。

非对象所有者不能擅自改对象主字段。

---

## 十二、结论

并行开发真正要避免的，不只是“改同一个文件”，更是“同一个概念被不同 AI 写成不同真相”。

本文档的作用，就是提前把这种概念冲突压住。

# 审批

本模块提供飞书审批流程操作能力，支持查看审批定义、列出可用审批类型、创建审批实例、查询审批状态和撤回审批。

## 所需权限

- `approval:approval` — 读写审批信息
- `approval:approval.list:readonly` — 查询审批列表（`GET /approval/list` 需要）
- `approval:task` — 执行审批人操作（同意/拒绝/转交、查询任务）

## 如何获取 Approval Code（审批定义 Code）

飞书不提供"列出所有审批定义"的 API，需要手动从管理后台获取：

1. 打开 [飞书审批管理后台（开发者模式）](https://www.feishu.cn/approval/admin/approvalList?devMode=on)
2. 找到目标审批，点击 **编辑** 按钮
3. 在浏览器地址栏中复制 `definitionCode=` 后面的值，例如：
   `https://www.feishu.cn/approval/admin/edit?definitionCode=48D49517-C979-447E-AD93-4BAE0FBC57EA`
4. 将获取到的 Code 配置在 `.env` 的 `FEISHU_APPROVAL_CODES` 中，方便 Agent 自动查询

## API 端点

### 1. 列出可用审批类型

列出已配置的审批类型，或从用户历史审批中自动发现。

```
GET /approval/types
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 否 | 用户 open_id，传入后会从该用户的历史审批中发现审批类型 |

**数据来源：**
- 环境变量 `FEISHU_APPROVAL_CODES` 中预配置的审批类型（`source: config`）
- 用户历史审批实例中发现的审批类型（`source: discovered`）

**响应示例：**

```json
{
  "approval_types": [
    {"name": "请假", "approval_code": "CODE1", "source": "config"},
    {"name": "补卡", "approval_code": "48D49517-...", "source": "discovered"}
  ],
  "hint": ""
}
```

### 2. 查看审批定义

获取审批定义详情，包括表单控件结构和审批节点。Agent 可通过此接口了解需要填写哪些字段。

```
GET /approval/definitions/{approval_code}
```

**响应示例：**

```json
{
  "approval_code": "48D49517-C979-447E-AD93-4BAE0FBC57EA",
  "approval_name": "补卡",
  "form": "[{\"id\":\"widgetRemedyGroupV2\",\"type\":\"remedyGroupV2\",\"name\":\"补卡\"}]",
  "node_list": [{"node_id": "6dbe...", "node_type": "AND", "name": "审批"}]
}
```

### 3. 创建审批实例

发起一个新的审批申请。

```
POST /approval/create
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_code` | string | ✅ | 审批定义 Code |
| `open_id` | string | ✅ | 发起人的 open_id（`ou_` 开头） |
| `form` | string | ✅ | 审批表单内容（JSON 字符串，控件结构可通过查看审批定义获取） |
| `department_id` | string | 否 | 发起人所属部门 ID（多部门用户需填写） |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/approval/create \
  -H "Content-Type: application/json" \
  -d '{
    "approval_code": "48D49517-C979-447E-AD93-4BAE0FBC57EA",
    "open_id": "ou_xxx",
    "form": "[{\"id\":\"widgetRemedyGroupV2\",\"type\":\"remedyGroupV2\",\"value\":[{\"date\":\"2026-02-12\",\"remedy_time\":\"2026-02-12T09:00:00+08:00\",\"reason\":\"忘记打卡\"}]}]"
  }'
```

**响应示例：**

```json
{
  "instance_code": "619697E7-DCB5-431A-B7BC-33724C4BB1E9"
}
```

### 4. 查询审批实例列表

根据条件查询审批实例。

```
GET /approval/list
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_code` | string | 否 | 审批定义 Code |
| `user_id` | string | 否 | 发起人 open_id |
| `instance_status` | string | 否 | 状态：`PENDING`/`APPROVED`/`REJECT`/`RECALL`/`ALL` |
| `start_time` | string | 否 | 起始时间（Unix 毫秒时间戳） |
| `end_time` | string | 否 | 结束时间（Unix 毫秒时间戳） |
| `page_size` | int | 否 | 每页数量，默认 10 |

**请求示例：**

```bash
# 查询所有补卡审批实例
curl "http://127.0.0.1:8002/approval/list?approval_code=48D49517-...&instance_status=ALL"
```

### 5. 获取审批详情

获取单个审批实例的详细信息，包括状态、表单数据、任务列表和审批动态。

```
GET /approval/{instance_code}
```

**请求示例：**

```bash
curl "http://127.0.0.1:8002/approval/619697E7-DCB5-431A-B7BC-33724C4BB1E9"
```

### 6. 撤回审批

撤回审批中或已通过的审批实例。

```
POST /approval/cancel
```

### 7. 查询用户待办/已办任务

查询某个审批人的任务列表，常用于“帮我同意张三的请假申请”这类需求的任务定位。

```
GET /approval/tasks
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | ✅ | 审批人 open_id |
| `approval_code` | string | 否 | 审批定义 Code |
| `instance_code` | string | 否 | 审批实例 Code |
| `task_status` | string | 否 | 任务状态（默认 `PENDING`） |
| `page_size` | int | 否 | 每页数量（默认 10） |
| `page_token` | string | 否 | 翻页令牌 |

**响应示例：**

```json
{
  "has_more": false,
  "page_token": "",
  "tasks": [
    {
      "task": {"id": "7605931414537653476", "status": "PENDING"},
      "instance": {"code": "619697E7-...", "title": "张三 · 病假"},
      "approval": {"code": "48D49517-...", "name": "请假"}
    }
  ]
}
```

### 8. 同意审批任务

```
POST /approval/tasks/approve
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_code` | string | ✅ | 审批定义 Code |
| `instance_code` | string | ✅ | 审批实例 Code |
| `task_id` | string | ✅ | 任务 ID |
| `open_id` | string | ✅ | 审批人 open_id |
| `comment` | string | 否 | 同意意见 |
| `form` | string | 否 | 表单补充（部分审批可能需要） |

### 9. 拒绝审批任务

```
POST /approval/tasks/reject
```

参数同上，`comment` 为拒绝理由。

### 10. 转交审批任务

```
POST /approval/tasks/transfer
```

在请求体中额外提供 `transfer_open_id`（目标审批人 open_id）。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_code` | string | ✅ | 审批定义 Code |
| `instance_code` | string | ✅ | 审批实例 Code |
| `user_id` | string | ✅ | 审批提交人 open_id |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/approval/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "approval_code": "48D49517-C979-447E-AD93-4BAE0FBC57EA",
    "instance_code": "619697E7-DCB5-431A-B7BC-33724C4BB1E9",
    "user_id": "ou_xxx"
  }'
```

> **注意**：撤回需要在审批后台对应审批定义中勾选"允许撤销审批中的申请"或"允许撤销 x 天内通过的审批"。

## 典型工作流

### 发起审批（发起人视角）

1. 调用 `GET /approval/types` 查看可用审批类型，获取 `approval_code`
2. 调用 `GET /approval/definitions/{approval_code}` 查看表单控件结构
3. 根据控件结构组装 `form` JSON 字符串
4. 调用 `POST /approval/create` 发起审批
5. 调用 `GET /approval/{instance_code}` 查询审批状态

### 处理审批（审批人视角）

1. 调用 `GET /approval/tasks?user_id=ou_xxx&task_status=PENDING` 获取待办
2. 根据标题/申请人匹配到目标任务，拿到 `task_id` 和 `instance_code`
3. 同意：`POST /approval/tasks/approve`（或拒绝/转交）

### 常见表单控件类型

| 控件类型 | 说明 | value 格式 |
|----------|------|------------|
| `input` | 单行文本 | `"文本内容"` |
| `textarea` | 多行文本 | `"文本内容"` |
| `number` | 数字 | `123.45` |
| `date` | 日期 | `"2026-02-12T09:00:00+08:00"` (RFC3339) |
| `leaveGroup` | 请假控件组 | `{"name":"年假","start":"...","end":"...","interval":2.0}` |
| `remedyGroupV2` | 补卡控件组 | `[{"date":"2026-02-12","remedy_time":"...","reason":"..."}]` |
| `tripGroup` | 出差控件组 | `{"schedule":[...],"interval":2.0,"reason":"..."}` |

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `GET /approval/types` | 环境变量 + `POST /open-apis/approval/v4/instances/query` |
| `GET /approval/definitions/{code}` | `GET /open-apis/approval/v4/approvals/:approval_code` |
| `POST /approval/create` | `POST /open-apis/approval/v4/instances` |
| `GET /approval/list` | `POST /open-apis/approval/v4/instances/query` |
| `GET /approval/{instance_code}` | `GET /open-apis/approval/v4/instances/:instance_code` |
| `POST /approval/cancel` | `POST /open-apis/approval/v4/instances/cancel` |
| `GET /approval/tasks` | `POST /open-apis/approval/v4/tasks/search` |
| `POST /approval/tasks/approve` | `POST /open-apis/approval/v4/tasks/approve` |
| `POST /approval/tasks/reject` | `POST /open-apis/approval/v4/tasks/reject` |
| `POST /approval/tasks/transfer` | `POST /open-apis/approval/v4/tasks/transfer` |

# AI 操作审计日志规范

> 本文档覆盖 AI 工具执行与确认流的审计日志写入、查询和前端展示规范。目标是保证 AI 行为可追踪、可过滤、可按租户隔离审计。

---

## 一、职责边界

AI 操作审计日志用于记录：

- `query`：查询类动作
- `action`：执行类动作
- `confirm`：需要确认或确认后的动作

典型来源：

- `crud_executor.py`
- 其他新增的 AI 工具执行器

规则：

- 新增 AI 工具执行器时，若会产生可审计业务动作，必须接入审计日志
- 禁止在 Controller 中零散 `db.add(AIActionLog(...))`
- 必须统一复用 `write_ai_action_log()`

---

## 二、模型与字段

模型：`backend/app/models/ai/action_log.py`

核心字段：

- `tenant_id`
- `agent_id`
- `conversation_id`
- `skill_id`
- `operator_id`
- `action_name`
- `action_type`
- `action_level`
- `request_data`
- `response_data`
- `status`
- `error_message`
- `duration_ms`

### 固定枚举语义

状态值固定为：

- `success`
- `failed`
- `rejected`
- `pending_confirm`

安全等级固定为：

- `read`
- `safe_write`
- `dangerous`

规则：

- 耗时字段统一用 `duration_ms`
- 禁止前后端另造 `execution_time_ms`
- 禁止把 `pending_confirm` 简化成 `pending`

---

## 三、统一写入方式

统一 helper：

```python
from app.services.ai.action_log_service import (
    resolve_action_level,
    write_ai_action_log,
)
```

### 写入规则

- `request_data` / `response_data` 必须经过 helper 规范化为 JSON-safe 结构
- dataclass / Enum / `BaseModel` / `datetime` / `Decimal` 等值不要手工序列化，交给 helper 处理
- 动作等级优先显式传入；无法确定时可用 `resolve_action_level(action_name)`

### 推荐模式

```python
await write_ai_action_log(
    db,
    tenant_id=tenant_id,
    agent_id=agent_id,
    conversation_id=conversation_id,
    operator_id=operator_id,
    action_name=operation_name,
    action_type=ActionTypeEnum.ACTION.value,
    action_level=resolve_action_level(operation_name),
    status=ActionStatusEnum.SUCCESS.value,
    request_data=request_payload,
    response_data=response_payload,
    duration_ms=duration_ms,
)
```

---

## 四、查询接口

### 查询接口：企业端

| 接口 | 说明 |
|------|------|
| `GET /tenant/ai/action-logs` | 本企业日志列表 |
| `GET /tenant/ai/action-logs/stats` | 本企业统计与类型分布 |
| `GET /tenant/ai/action-logs/{id}` | 本企业单条详情 |

### 查询接口：平台端

| 接口 | 说明 |
|------|------|
| `GET /admin/ai/action-logs` | 全局日志列表 |
| `GET /admin/ai/action-logs/{id}` | 全局单条详情 |

### 查询规则

- 列表统一走 JSON:API filter/sort/page
- Tenant 端必须通过 `AIActionLogService(db, tenant_id)` 自动隔离
- Admin 端通过 `AdminAIActionLogService` 序列化 tenant 元信息
- 日志只读，不提供编辑或删除接口

---

## 五、前端页面

### 前端页面：平台端

- 页面：`frontend/apps/web-antd/src/views/admin/ai/action-logs/index.vue`
- API：`frontend/apps/web-antd/src/api/admin/action-logs.ts`
- 模式：`useCrudPage` + 详情 Drawer
- 展示补充：tenant 名称/编码、请求载荷、响应载荷、错误信息

### 前端页面：企业端

- 页面：`frontend/apps/web-antd/src/views/tenant/ai/action-logs/index.vue`
- API：`frontend/apps/web-antd/src/api/tenant/action-logs.ts`
- 模式：`useCrudPage` + 顶部统计卡片

前端规则：

- 字段命名必须与后端保持一致，耗时使用 `duration_ms`
- 状态筛选必须使用 `pending_confirm`
- 页面为只读审计视图，禁止加入编辑/删除行为
- 时间显示遵循统一时间格式规范：主显示 `formatDate`，不要直接 `toLocaleString`

---

## 六、RBAC 与菜单

资源统一为 `ai_action_log`：

- 平台端菜单：`/admin/ai/action-logs`
- 企业端菜单：`/tenant/ai/action-logs`

要求：

- Controller 仍需 `@permission_resource(... parent_resource=...)`
- `action.ai_action_log.*` i18n 必须在 `messages.json` 中补齐
- 新增统计或详情接口时，保持只读权限模型，不要混入写操作

---

## 七、Checklist

- [ ] 新增 AI 工具执行器通过 `write_ai_action_log()` 写入
- [ ] 状态值使用 `success/failed/rejected/pending_confirm`
- [ ] 耗时字段统一为 `duration_ms`
- [ ] Tenant 端列表受租户隔离
- [ ] Admin 端序列化补齐 `tenant_name` / `tenant_code`
- [ ] 前端页面保持只读，不新增编辑/删除操作

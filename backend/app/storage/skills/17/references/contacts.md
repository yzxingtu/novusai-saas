# 通讯录

本模块提供飞书通讯录查询能力，支持查询用户信息、搜索部门和浏览组织架构。全部基于 `tenant_access_token`，Agent 可直接使用。

## 所需权限

- `contact:contact.base:readonly` — 读取通讯录基本信息
- `contact:department.base:readonly` — 获取部门基础信息
- `contact:user.employee_id:readonly` — 获取用户 ID（可选）

## API 端点

### 1. 获取用户信息

根据用户 ID 获取用户详细信息。

```
GET /contacts/user/{user_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_id` | string | 用户 ID（open_id 或 user_id） |

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id_type` | string | 否 | ID 类型：`open_id`(默认)/`user_id`/`union_id` |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/contacts/user/ou_xxx"
```

**响应示例：**

```json
{
  "user_id": "ou_xxx",
  "name": "张三",
  "en_name": "Zhang San",
  "email": "zhangsan@example.com",
  "mobile": "+86 138xxxx0000",
  "department_ids": ["od-xxx"],
  "status": {"is_activated": true, "is_frozen": false}
}
```

### 2. 搜索用户

通过关键词搜索用户。

```
POST /contacts/users/search
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词（姓名） |
| `page_size` | int | 否 | 每页数量，默认 20 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/contacts/users/search \
  -H "Content-Type: application/json" \
  -d '{"query": "张三"}'
```

> **实现方式**：基于部门成员遍历 + 姓名模糊匹配，使用 `tenant_access_token`，无需用户授权。

### 3. 获取部门信息

获取单个部门的详细信息。

```
GET /contacts/department/{department_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `department_id` | string | 部门 ID（open_department_id 或 department_id） |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/contacts/department/od-xxx"
```

**响应示例：**

```json
{
  "department_id": "D096",
  "open_department_id": "od-xxx",
  "name": "产品部",
  "parent_department_id": "D067",
  "leader_user_id": "ou_xxx",
  "member_count": 25
}
```

### 4. 搜索部门

通过部门名称搜索部门。

```
POST /contacts/departments/search
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词（部门名称） |
| `page_size` | int | 否 | 每页数量，默认 20 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/contacts/departments/search \
  -H "Content-Type: application/json" \
  -d '{"query": "产品"}'
```

### 5. 获取部门成员

获取指定部门的直属成员列表。

```
GET /contacts/department/{department_id}/users
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page_size` | int | 否 | 每页数量，默认 50 |
| `page_token` | string | 否 | 分页标记 |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/contacts/department/od-xxx/users"
```

**响应示例：**

```json
{
  "items": [
    {"user_id": "ou_xxx1", "name": "张三", "email": "zhangsan@example.com"},
    {"user_id": "ou_xxx2", "name": "李四", "email": "lisi@example.com"}
  ],
  "has_more": false
}
```

## 典型工作流

### 查找某部门所有成员

1. **搜索部门** → `POST /contacts/departments/search` (query="市场部")
2. **获取部门成员** → `GET /contacts/department/{dept_id}/users`

### 查找用户所在部门

1. **获取用户信息** → `GET /contacts/user/{user_id}`
2. 从返回的 `department_ids` 获取部门 ID
3. **获取部门详情** → `GET /contacts/department/{dept_id}`

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `GET /contacts/user/{user_id}` | `GET /open-apis/contact/v3/users/:user_id` |
| `POST /contacts/users/search` | `POST /open-apis/contact/v3/users/search` |
| `GET /contacts/department/{dept_id}` | `GET /open-apis/contact/v3/departments/:department_id` |
| `POST /contacts/departments/search` | `POST /open-apis/contact/v3/departments/search` |
| `GET /contacts/department/{dept_id}/users` | `GET /open-apis/contact/v3/users/find_by_department` |

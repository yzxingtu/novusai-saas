# 考勤

本模块提供飞书考勤打卡查询能力，支持查询打卡结果、补卡记录和考勤组信息。

## 所需权限

- `attendance:task:readonly` — 导出打卡数据
- `attendance:rule:readonly` — 导出打卡管理规则（查询考勤组时需要）
- `contact:user.employee_id:readonly` — 获取用户 ID（传入 open_id 时自动转换为 employee_id）

## API 端点

### 1. 查询打卡结果

获取员工在指定日期范围内的实际打卡结果。

```
POST /attendance/tasks
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_ids` | list[string] | ✅ | 员工 ID 列表，最多 50 个 |
| `check_date_from` | int | ✅ | 起始日期，格式 yyyyMMdd，如 `20260213` |
| `check_date_to` | int | ✅ | 结束日期，格式 yyyyMMdd |
| `employee_type` | string | 否 | ID 类型：`employee_id`(默认)/`employee_no` |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/attendance/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": ["abd754f7"],
    "check_date_from": 20260209,
    "check_date_to": 20260213
  }'
```

**响应示例：**

```json
{
  "tasks": [
    {
      "user_id": "abd754f7",
      "employee_name": "张三",
      "day": 20260213,
      "group_id": "6737202939523236110",
      "records": [
        {
          "check_in_result": "Normal",
          "check_out_result": "Normal",
          "check_in_time": "1739422800",
          "check_out_time": "1739455200"
        }
      ]
    }
  ]
}
```

**打卡结果说明：**

| 值 | 含义 |
|----|------|
| `Normal` | 正常 |
| `Late` | 迟到 |
| `Early` | 早退 |
| `Lack` | 缺卡 |
| `Todo` | 未打卡 |
| `NoNeedCheck` | 无需打卡 |

### 2. 获取补卡记录

获取员工的补卡申请记录。

```
POST /attendance/remedys
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_ids` | list[string] | ✅ | 员工 ID 列表 |
| `check_time_from` | string | ✅ | 起始时间（Unix 秒时间戳） |
| `check_time_to` | string | ✅ | 结束时间（Unix 秒时间戳） |
| `status` | int | 否 | 状态：0=待审批, 1=未通过, 2=已通过(默认), 3=已取消, 4=已撤回 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/attendance/remedys \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": ["abd754f7"],
    "check_time_from": "1738800000",
    "check_time_to": "1739404800",
    "status": 2
  }'
```

**响应示例：**

```json
{
  "remedys": [
    {
      "user_id": "abd754f7",
      "remedy_date": 20260210,
      "remedy_time": "2026-02-10 09:00",
      "status": 2,
      "reason": "忘记打卡"
    }
  ]
}
```

### 3. 查询考勤组

获取考勤组的详细配置信息。

```
GET /attendance/group/{group_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `group_id` | string | 考勤组 ID（从打卡结果中获取） |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/attendance/group/6737202939523236110"
```

**响应示例：**

```json
{
  "group_id": "6737202939523236110",
  "group_name": "产品部考勤",
  "time_zone": "Asia/Shanghai",
  "group_type": 0,
  "locations": [
    {
      "location_name": "杭州总部",
      "latitude": 30.28994,
      "longitude": 120.04509,
      "gps_range": 300
    }
  ],
  "allow_out_punch": true,
  "allow_remedy": true
}
```

**考勤组类型说明：**

| 值 | 含义 |
|----|------|
| 0 | 固定班制 |
| 2 | 排班制 |
| 3 | 自由班制 |

## 典型工作流

### 查看本周考勤

1. **查询打卡结果** → `POST /attendance/tasks` (本周日期范围)
2. 汇总每天的上下班打卡状态
3. 标记异常（迟到/早退/缺卡）

### 查看考勤规则

1. **查询打卡结果** → 获取 `group_id`
2. **查询考勤组** → `GET /attendance/group/{group_id}`
3. 查看考勤地点、打卡方式等配置

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `POST /attendance/tasks` | `POST /open-apis/attendance/v1/user_tasks/query` |
| `POST /attendance/remedys` | `POST /open-apis/attendance/v1/user_task_remedys/query` |
| `GET /attendance/group/{group_id}` | `GET /open-apis/attendance/v1/groups/:group_id` |

# 日历与会议室

本模块提供飞书日历和会议室相关操作能力，支持创建日程、预约会议室、查询忙闲状态等核心办公场景。

## 所需权限

- `calendar:calendar` — 读写日历及日程信息
- `vc:room:readonly` — 获取会议室信息（查询/搜索会议室时需要）
- `contact:user.employee_id:readonly` — 获取用户 ID（可选）

## API 端点

### 1. 创建日程

创建一个日程，可同时添加参与人和会议室。

```
POST /calendar/events
```

### 1b. 更新日程

按需更新标题、时间、描述等字段。

```
PATCH /calendar/events/{event_id}
```

可选字段：`summary`、`start_time`、`end_time`、`description`、`calendar_id`

示例：
```bash
curl -X PATCH http://127.0.0.1:8002/calendar/events/<event_id> \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "产品评审会议（更新）",
    "end_time": "2026-02-13T15:30:00+08:00"
  }'
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `summary` | string | ✅ | 日程标题 |
| `start_time` | string | ✅ | 开始时间，RFC3339 格式，如 `2026-02-13T14:00:00+08:00` |
| `end_time` | string | ✅ | 结束时间，RFC3339 格式 |
| `description` | string | 否 | 日程描述 |
| `attendee_user_ids` | list[string] | 否 | 参与人 open_id 列表 |
| `room_id` | string | 否 | 会议室 ID（预约会议室） |
| `calendar_id` | string | 否 | 日历 ID，默认使用主日历 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/calendar/events \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "产品评审会议",
    "start_time": "2026-02-13T14:00:00+08:00",
    "end_time": "2026-02-13T15:00:00+08:00",
    "description": "Q1 产品路线图评审",
    "attendee_user_ids": ["ou_xxx1", "ou_xxx2"],
    "room_id": "omm_xxx"
  }'
```

**响应示例：**

```json
{
  "event_id": "xxxxxxxxx_0",
  "summary": "产品评审会议",
  "start_time": "2026-02-13T14:00:00+08:00",
  "end_time": "2026-02-13T15:00:00+08:00",
  "organizer": "ou_xxx"
}
```

> **提示**：添加会议室后，会议室进入异步预约流程。请求成功不代表会议室预约成功，需后续查询会议室的预约状态（通过日程参与人的 `rsvp_status` 判断）。

### 2. 获取日程列表

获取指定时间范围内的日程。

```
GET /calendar/events
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start_time` | string | ✅ | 起始时间，RFC3339 格式 |
| `end_time` | string | ✅ | 结束时间，RFC3339 格式 |
| `calendar_id` | string | 否 | 日历 ID，默认主日历 |
| `page_size` | int | 否 | 每页数量，默认 50 |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/calendar/events?start_time=2026-02-13T00:00:00%2B08:00&end_time=2026-02-14T00:00:00%2B08:00"
```

> 提示：已删除的事件在其时间窗口内仍可能出现在列表中，状态为 `cancelled`。

### 2b. 获取单个日程详情

获取指定 event_id 的详情。

```
GET /calendar/events/{event_id}
```

可选查询参数：`calendar_id`（不传默认主日历）

示例：
```bash
curl "http://127.0.0.1:8002/calendar/events/<event_id>"
```

### 3. 查询忙闲状态

查询用户或会议室在指定时间段内的忙闲情况。

```
POST /calendar/freebusy
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `time_min` | string | ✅ | 查询起始时间，RFC3339 格式 |
| `time_max` | string | ✅ | 查询结束时间，RFC3339 格式 |
| `user_id` | string | 否 | 用户 open_id（与 room_id 二选一） |
| `room_id` | string | 否 | 会议室 ID（与 user_id 二选一） |

**请求示例：**

```bash
# 查询会议室忙闲
curl -X POST http://127.0.0.1:8002/calendar/freebusy \
  -H "Content-Type: application/json" \
  -d '{
    "time_min": "2026-02-13T09:00:00+08:00",
    "time_max": "2026-02-13T18:00:00+08:00",
    "room_id": "omm_xxx"
  }'
```

**响应示例：**

```json
{
  "busy_times": [
    {
      "start_time": "2026-02-13T10:00:00+08:00",
      "end_time": "2026-02-13T11:30:00+08:00"
    },
    {
      "start_time": "2026-02-13T14:00:00+08:00",
      "end_time": "2026-02-13T15:00:00+08:00"
    }
  ]
}
```

### 4. 查询会议室列表

查询某个层级下的会议室列表。

```
GET /calendar/rooms
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `room_level_id` | string | 否 | 层级 ID，为空时返回租户所有会议室 |
| `page_size` | int | 否 | 每页数量，默认 20 |
| `page_token` | string | 否 | 分页标记 |

**请求示例：**

```bash
# 查询所有会议室
curl "http://127.0.0.1:8002/calendar/rooms"
```

### 4b. 搜索会议室

通过关键词搜索会议室。

```
POST /calendar/rooms/search
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keyword` | string | 否 | 搜索关键词（会议室名称） |
| `room_level_id` | string | 否 | 在该层级下搜索 |
| `page_size` | int | 否 | 每页数量，默认 10 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/calendar/rooms/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "大会议室"}'  
```

### 5. 添加日程参与人

为已有日程添加参与人或预约会议室。

```
POST /calendar/events/{event_id}/attendees
```

### 6. 删除日程

删除指定的日程事件。

```
DELETE /calendar/events/{event_id}
```

可选查询参数：
- `calendar_id`（string）— 日历 ID，默认主日历

示例：
```bash
curl -X DELETE "http://127.0.0.1:8002/calendar/events/381e074d-c843-4f01-b3bb-1d9105751df9_0"
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `attendees` | list | ✅ | 参与人列表 |
| `attendees[].type` | string | ✅ | 参与人类型：`user`/`chat`/`resource` |
| `attendees[].user_id` | string | 否 | 用户 open_id（type=user 时） |
| `attendees[].chat_id` | string | 否 | 群组 ID（type=chat 时） |
| `attendees[].room_id` | string | 否 | 会议室 ID（type=resource 时） |
| `need_notification` | boolean | 否 | 是否发送通知，默认 true |

## 典型工作流

### 清理测试数据

- 通过 `DELETE /calendar/events/{event_id}` 删除测试产生的日程

### 预约会议室

1. **查询会议室** → `GET /calendar/rooms` 或 `POST /calendar/rooms/search`
2. **查询会议室忙闲** → `POST /calendar/freebusy` (room_id)
3. **创建日程并预约** → `POST /calendar/events` (含 room_id)
4. **确认预约状态** → 查看日程参与人中会议室的 `rsvp_status`

### 安排团队会议

1. **查询团队成员忙闲** → 分别对每位成员调用 `POST /calendar/freebusy`
2. **找到共同空闲时间段**
3. **查询可用会议室** → `GET /calendar/rooms`
4. **创建日程** → `POST /calendar/events` (含参与人和会议室)

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `POST /calendar/events` | `POST /open-apis/calendar/v4/calendars/:calendar_id/events` |
| `PATCH /calendar/events/{event_id}` | `PATCH /open-apis/calendar/v4/calendars/:calendar_id/events/:event_id` |
| `GET /calendar/events` | `GET /open-apis/calendar/v4/calendars/:calendar_id/events` |
| `GET /calendar/events/{event_id}` | `GET /open-apis/calendar/v4/calendars/:calendar_id/events/:event_id` |
| `POST /calendar/freebusy` | `POST /open-apis/calendar/v4/freebusy/list` |
| `GET /calendar/rooms` | `GET /open-apis/vc/v1/rooms` |
| `POST /calendar/rooms/search` | `POST /open-apis/vc/v1/rooms/search` |
| `POST /calendar/events/{event_id}/attendees` | `POST /open-apis/calendar/v4/calendars/:calendar_id/events/:event_id/attendees` |
| `DELETE /calendar/events/{event_id}` | `DELETE /open-apis/calendar/v4/calendars/:calendar_id/events/:event_id` |

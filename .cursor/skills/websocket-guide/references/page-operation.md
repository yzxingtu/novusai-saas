# 页面运行时双向通信

## 目录

- [总体流程](#总体流程)
- [Room 约定](#room-约定)
- [事件载荷](#事件载荷)
- [安全模型](#安全模型)
- [实现检查清单](#实现检查清单)

## 总体流程

当前页面运行时通过 `page_session` 房间承载 `ui_*` 读取与操作请求：

```text
Backend page-runtime tool
  -> page_session.py helper
  -> sio.emit("ui_action_invoke" / "ui_snapshot_request" / "ui_read_*_request", ...)
  -> 前端 use-ui-action-channel.ts 在对应 page_session 房间收到请求
  -> 必要时弹确认框或执行 shared runtime reader/action
  -> sio.emit("ui_action_result" / "ui_snapshot_result" / "ui_read_*_result", ...)
  -> 后端 resolve Future / request result
```

关键文件：

- `backend/app/sio/page_session.py`
- `frontend/apps/web-antd/src/composables/use-page-session.ts`
- `frontend/apps/web-antd/src/composables/use-ui-action-channel.ts`
- `backend/app/ai/tools/page_runtime/definitions.py`

当前 helper：

- `invoke_ui_action()`
- `request_ui_snapshot()`
- `request_ui_read_region()`
- `request_ui_read_table()`
- `request_ui_list_interactables()`

## Room 约定

页面操作精确定位到：

- `page_session:{page_session_id}`

不要用普通 `user:{id}` room 承载页面操作，否则会误投递到错误标签页。

## 事件载荷

服务端下发：

```python
{
    "invoke_id": "uuid",  # ui_action only
    "trace_id": "trace-id",
    "page_key": "tenant.orders.list",
    "action_type": "ui_click",
    "target_locator": "text:新增",
    "confirm": False,
    "form_session_id": None,
}
```

或读取请求：

```python
{
    "request_id": "uuid",
    "trace_id": "trace-id",
    "surface_id": "drawer-1",
    "mode": "compact",
    "region_locator": "text:统计卡片",
    "table_locator": "css:table",
    "page": 1,
    "page_size": 20,
    "requires_confirmation": False,
}
```

前端回传：

```python
{
    "invoke_id": "uuid",  # or request_id for read requests
    "success": True,
    "message": "ok",
    "data": {},
    "error_type": None,
}
```

最重要字段：

- `invoke_id`
- `request_id`
- `trace_id`
- `page_key`
- `action_type`
- `target_locator` / `surface_id` / `region_locator` / `table_locator`
- `confirm`
- `error_type`

## 安全模型

- 读取请求通过 shared runtime reader 直接执行
- 写动作由 `ui_action_invoke` 承载，当前 action type 主要包括：
  - `ui_click`
  - `ui_open_surface`
  - `ui_get_form_state`
  - `ui_set_field`
  - `ui_fill_form`
  - `ui_submit_form`
- 写操作或确认型动作必须由前端执行确认策略
- `page_key` 不匹配时返回 `page_key_mismatch`
- 相同 `invoke_id` 只能回放缓存结果，禁止重复执行
- 相同 `request_id` 同样要做去重回放
- 超时固定 `60s`

这几条都不能在某个页面里单独放宽。

## 实现检查清单

- 后端通过 `page_session:{id}` 房间精确投递
- 当前活动页面和 `page_key` 一致
- `invoke_id` / `request_id` 做了幂等缓存
- 前端 `use-ui-action-channel.ts` 已注册：
  - `ui_action_invoke`
  - `ui_snapshot_request`
  - `ui_read_region_request`
  - `ui_read_table_request`
  - `ui_list_interactables_request`
- 写操作确认弹窗可正常回传结果
- 成功、失败、拒绝、超时路径都能回传
- 后端 Future 在完成后会清理，避免泄漏

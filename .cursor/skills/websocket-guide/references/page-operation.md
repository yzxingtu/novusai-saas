# 页面操作双向通信

## 目录

- [总体流程](#总体流程)
- [Room 约定](#room-约定)
- [事件载荷](#事件载荷)
- [安全模型](#安全模型)
- [实现检查清单](#实现检查清单)

## 总体流程

页面操作由 `invoke_page_operation` builtin skill 触发：

```text
LLM function call
  -> PageOperationExecutor
  -> invoke_page_operation()
  -> sio.emit("page_operation_invoke", ...)
  -> 前端查找 page session 与 operation handler
  -> 必要时弹确认框
  -> 执行 handler
  -> sio.emit("page_operation_result", ...)
  -> 后端 resolve Future
```

关键文件：

- `backend/app/sio/page_session.py`
- `frontend/apps/web-antd/src/composables/use-page-session.ts`
- `frontend/apps/web-antd/src/composables/use-page-operation-channel.ts`

## Room 约定

页面操作精确定位到：

- `page_session:{page_session_id}`

不要用普通 `user:{id}` room 承载页面操作，否则会误投递到错误标签页。

## 事件载荷

服务端下发：

```python
{
    "invoke_id": "uuid",
    "trace_id": "trace-id",
    "page_key": "tenant.orders.list",
    "operation_name": "refresh_list",
    "params": {},
    "requires_confirmation": False,
}
```

前端回传：

```python
{
    "invoke_id": "uuid",
    "success": True,
    "message": "ok",
    "data": {},
    "error_type": None,
}
```

最重要字段：

- `invoke_id`
- `trace_id`
- `page_key`
- `operation_name`
- `requires_confirmation`
- `error_type`

## 安全模型

- `readonly=true` 可直接执行
- 写操作或 `requires_confirmation=true` 必须前端确认
- `page_key` 不匹配时返回 `page_key_mismatch`
- 相同 `invoke_id` 只能回放缓存结果，禁止重复执行
- 超时固定 `60s`

这几条都不能在某个页面里单独放宽。

## 实现检查清单

- 前端操作 registry 已注册目标操作
- 当前活动页面和 `page_key` 一致
- `invoke_id` 做了幂等缓存
- 写操作确认弹窗可正常回传结果
- 成功、失败、拒绝、超时路径都能回传
- 后端 Future 在完成后会清理，避免泄漏

# Trace ID 与日志规范

本文档覆盖：trace_id 请求追踪中间件、日志注入、前端 header、Celery 传播、WebSocket 覆盖、Loguru 日志分类器使用方式。

---

## 一、Trace ID 获取方式

```python
from app.middleware.trace import trace_id_var

tid = trace_id_var.get()  # 返回当前请求的 trace_id，无请求时返回 ""
```

---

## 二、日志中 trace_id 格式

每条日志自动带上 `[trace_id=xxx]`，由 LogManager/Loguru formatter 自动读取 `trace_id_var.get()`，开发者无需手动传入。

---

## 三、前端请求

- 每个请求在 header 中自动加入 `X-Trace-ID`（使用 `crypto.randomUUID()` 生成）
- 后端优先使用前端传入的值；若前端未传，则后端自行生成

---

## 四、Celery 任务

- `BaseTask.apply_async()` 自动从 `trace_id_var.get()` 读取 trace_id，注入 `headers={"trace_id": tid}`
- `BaseTask.before_start()` 自动从 `self.request.headers.get("trace_id")` 恢复到 `trace_id_var.set(tid)`
- 开发者无需关心，使用 `@register_task` 装饰器即可

---

## 五、WebSocket

Socket.IO 请求不走 HTTP 中间件，在 namespace 的 `connect` 事件中自动生成 trace_id 并写入 ContextVar，确保 WS 事件也能追踪。

---

## 六、Loguru 日志分类器

与旧 API 完全一致，必须通过 `app.core.logging` 暴露的封装使用：

```python
from app.core.logging import get_logger, LogManager

logger = get_logger(__name__)
category_logger = LogManager.get_logger("app")
logger = LogManager.get_category_logger("auth")
logger.info("message")
```

**禁令**：
- 禁止直接 `from loguru import logger`
- 禁止 `print()` / `logging.getLogger()`

---

## 七、5xx 错误弹窗

- 5xx 错误使用 `notification.error()` 替代 `message.error()`
- 显示追踪 ID（从响应 header `X-Trace-ID` 读取）
- 追踪 ID 旁带「复制」按钮，不自动关闭

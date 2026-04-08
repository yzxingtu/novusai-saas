# 运行日志分析报告

## 一、正常运行日志（无问题）

启动阶段日志表现正常，各项初始化均成功完成：

| 步骤 | 状态 | 说明 |
|------|------|------|
| Uvicorn 启动 | ✓ | http://0.0.0.0:8000 |
| Storage 驱动 | ✓ | local 已注册 |
| AI 适配器 | ✓ | 已注册 |
| 数据库 | ✓ | 迁移完成、连接验证通过 |
| Redis | ✓ | localhost:6379/0 |
| 权限同步 | ✓ | 513 更新、3 禁用 |
| 配置同步 | ✓ | 12 组、114 项 |
| Socket.IO | ✓ | Redis manager、ping 25/20 |
| Celery broker | ✓ | 已连接 |
| 插件恢复 | ✓ | 4 个（qiniu-kodo, novusdoc, weather-widget, storage-migration） |

## 二、WatchFiles 热重载（正常）

开发模式下 `--reload` 会监控文件变更并自动重启，日志中的 `WatchFiles detected changes... Reloading...` 属于正常行为。

## 三、Ctrl+C 关闭时的异常（有问题）

按 Ctrl+C 结束服务时会出现错误堆栈，根因如下。

### 3.1 错误链条

1. **KeyboardInterrupt**：用户 Ctrl+C 触发
2. **asyncio 取消所有任务**：`_cancel_all_tasks()` 开始取消
3. **BaseHTTPMiddleware 内的 anyio.create_task_group**：正在处理的 HTTP 请求所在的 TaskGroup 被取消
4. **数据库事务被取消**：某次请求中的 `session.commit()` 收到 `CancelledError`
5. **连接池关闭失败**：SQLAlchemy 在 `dispose()` 时调用 `asyncpg.terminate()` 再次被取消

### 3.2 技术原因

`TraceIdMiddleware` 和 `NoCacheAPIMiddleware` 继承自 `starlette.middleware.base.BaseHTTPMiddleware`。该基类内部使用 `anyio.create_task_group()` 来运行下游应用，在 Ctrl+C 时会：

- 通过任务取消强制结束下游应用
- 不符合 ASGI 的“优雅断开”设计
- 导致进行中的 DB 操作被取消，进而产生 `CancelledError` 和后续级联错误

Starlette 官方已计划弃用 BaseHTTPMiddleware，建议改用纯 ASGI 中间件。

### 3.3 涉及的文件

- `app/middleware/trace.py`（TraceIdMiddleware）
- `app/main.py`（NoCacheAPIMiddleware 内联类）

### 3.4 修复方案（已实施）

将 `TraceIdMiddleware` 和 `NoCacheAPIMiddleware` 改为**纯 ASGI** 实现（类似 `I18nMiddleware`），避免使用 `BaseHTTPMiddleware`，从而在 Ctrl+C 时不再触发任务取消，关闭过程会更干净。

- `app/middleware/trace.py`： TraceIdMiddleware 已改为纯 ASGI
- `app/middleware/nocache.py`： 新增 NoCacheAPIMiddleware 纯 ASGI 实现

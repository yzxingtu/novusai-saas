# WebSocket 调试与检查清单

## 目录

- [浏览器侧排查](#浏览器侧排查)
- [Redis 与后端日志](#redis-与后端日志)
- [常见问题](#常见问题)
- [发布前检查清单](#发布前检查清单)

## 浏览器侧排查

优先看浏览器 Network 的 WS 面板：

1. 检查握手是否成功
2. 检查 namespace 是否正确
3. 检查是否能收到预期事件
4. 检查重连后 handler 是否还在

Socket.IO 帧格式通常类似：

```text
42["event",{...}]
```

## Redis 与后端日志

Redis：

```bash
redis-cli MONITOR | grep socketio
```

后端日志重点看：

- connect
- disconnect
- auth failure
- reconnect

## 常见问题

### CORS 错误

- Socket.IO 的 `cors_allowed_origins` 和 FastAPI 的 CORS 是两套配置
- 两边都要对齐

### Token 过期 / 鉴权失败

- 看 `connect_error`
- 认证连续失败后前端应停止无意义重试
- token 刷新后要确认 store/composable 能读取到最新 token

### Presence 残留

- Presence 使用 TTL
- worker 崩溃后脏数据会延迟清理
- 启动时应执行 presence 初始化清理

### 连接过频

- 连接速率限制使用 Lua 原子脚本
- 超限时会返回 `rate_limited`

### 多 worker 部署

- 所有 worker 必须共享同一个 Redis URL
- 事件跨 worker 同步依赖 Redis manager，不要局部绕过

## 发布前检查清单

- 后端 emit 都带 `room` 和 `namespace`
- Celery 发送都走 `sio_bridge`
- 前端 handler 都有注销
- 连接失败、鉴权失败、超时路径已验证
- presence HTTP 接口和实时事件都验证过

---
name: websocket-guide
description: Socket.IO 实时通信技能。当需要开发或排查通知推送、在线状态、AI typing，或新增 WebSocket 事件/room/namespace 时使用。
---

# Socket.IO 实时通信技能

> 本文件只保留入口与路由规则。具体实现细节放在 `references/`。

## 何时使用

- 新增或排查 `/admin`、`/tenant`、`/user` namespace 的实时事件。
- 排查通知推送、在线状态、AI typing WebSocket 通道。
- 需要在 Celery 同步环境发送 Socket.IO 消息。
- 需要确认前端 `useSocketIOStore` / `useSocketIO` 的接入方式。

## 先记住这几条

- Namespace 固定为 `/admin`、`/tenant`、`/user`。
- Room 约定固定为 `user:{user_id}`、`tenant:{tenant_id}`、`admins`。
- 后端 `emit` 必须显式带 `room` 和 `namespace`，不要做无 room 广播。
- Celery 同步环境统一走 `app.core.sio_bridge`，不要在 worker 里直接复用异步 `sio`。

## 按任务读取

- 后端事件、room、presence、Celery 同步发送：
  读 [references/backend-usage.md](references/backend-usage.md)
- 前端连接、监听、发送、store/composable 接入：
  读 [references/frontend-usage.md](references/frontend-usage.md)
- CORS、鉴权失败、重连、presence 残留、rate limit、浏览器排查：
  读 [references/debugging-and-checklist.md](references/debugging-and-checklist.md)

## 不要在这里找

- 用户端路由和域名隔离，去 [../user-endpoint/SKILL.md](../user-endpoint/SKILL.md)
- 项目级总规则，去 [../novusai-saas/SKILL.md](../novusai-saas/SKILL.md)

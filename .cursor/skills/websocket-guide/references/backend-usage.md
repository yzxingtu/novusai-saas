# WebSocket 后端接入

## 目录

- [核心架构](#核心架构)
- [Namespace 与 Room 约定](#namespace-与-room-约定)
- [从后端发送事件](#从后端发送事件)
- [Namespace 侧处理事件](#namespace-侧处理事件)
- [连接会话数据](#连接会话数据)
- [在线状态](#在线状态)
- [Celery 同步环境发送](#celery-同步环境发送)

## 核心架构

项目使用 `python-socketio` + Redis manager：

```text
frontend socket.io-client
  <-> backend python-socketio AsyncServer
  <-> Redis AsyncRedisManager
```

关键文件：

- `backend/app/core/socketio_server.py`
- `backend/app/sio/__init__.py`
- `backend/app/sio/admin_ns.py`
- `backend/app/sio/tenant_ns.py`
- `backend/app/sio/user_ns.py`
- `backend/app/sio/presence.py`
- `backend/app/core/sio_bridge.py`

## Namespace 与 Room 约定

Namespace：

- `/admin`
- `/tenant`
- `/user`

Room：

- `user:{user_id}`：指定用户所有设备
- `tenant:{tenant_id}`：指定企业广播
- `admins`：所有平台管理员

规则：

- `emit` 时必须显式带 `namespace`
- 后端广播必须显式带 `room`
- 不要把 tenant 事件发到 `/admin`
- 不要在业务代码里自己发明新的 room 前缀

## 从后端发送事件

```python
from app.core.socketio_server import sio

await sio.emit("notification", data, room=f"user:{user_id}", namespace="/tenant")
await sio.emit("notification", data, room=f"tenant:{tenant_id}", namespace="/tenant")
await sio.emit("notification", data, room="admins", namespace="/admin")
```

适用场景：

- 通知推送
- presence 变更广播
- AI typing 状态

## Namespace 侧处理事件

```python
class AdminNamespace(socketio.AsyncNamespace):
    async def on_my_custom_event(self, sid, data):
        session = await self.get_session(sid)
        user_id = session["user_id"]
        await self.emit("my_response", {"result": "ok"}, to=sid)
```

规则：

- 事件名按领域命名，不要发散成无前缀裸名字
- 认证、权限、租户隔离必须先依赖 namespace session
- 业务逻辑仍应下沉到 service，不要把 service 逻辑写进 namespace

## 连接会话数据

常用字段：

- `user_id`
- `user_type`
- `tenant_id`
- `username`

这些字段来自 namespace 建连后的 session，不要重复从 token 手拆。

## 在线状态

通过 `PresenceManager` 查询：

```python
from app.sio.presence import PresenceManager

online_ids = await PresenceManager.get_online_ids("admin")
is_online = await PresenceManager.is_online("admin", user_id=5)
details = await PresenceManager.get_online_details("admin")
```

HTTP 观测面：

- `GET /admin/ws/presence`
- `GET /admin/ws/presence/tenant/{id}`
- `GET /tenant/ws/presence`

## Celery 同步环境发送

Worker 是同步环境，统一使用 `app.core.sio_bridge`：

```python
from app.core.sio_bridge import notify_user_sync, notify_admins_sync, notify_tenant_sync

notify_user_sync("admin", user_id=5, notification_data={"type": "task.completed"})
notify_admins_sync({"type": "system.alert"})
notify_tenant_sync(tenant_id=1, notification_data={"type": "notification"})
```

规则：

- 不要在 Celery worker 里直接 await `sio.emit(...)`
- 不要绕过 `sio_bridge` 手工初始化异步 Redis manager

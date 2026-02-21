---
description: Socket.IO 实时通信系统使用指南。当需要使用 WebSocket 实时推送（通知、在线状态、AI 对话通知）或新增实时事件类型时，参考此文档。
---

# Socket.IO 实时通信系统 — 使用指南

## 一、架构概述

本项目使用 **python-socketio** + **socket.io-client** 实现实时通信。

```
前端 (socket.io-client)  ←→  后端 (python-socketio AsyncServer)  ←→  Redis (AsyncRedisManager)
```

### 三端 Namespace 隔离

| Namespace | 用户类型 | JWT Scope | 对应 HTTP 前缀 |
|-----------|----------|-----------|---------------|
| `/admin` | 平台管理员 | `admin` | `/admin/*` |
| `/tenant` | 租户管理员 | `tenant_admin` | `/tenant/*` |
| `/user` | 租户业务用户 | `tenant_user` | `/api/v1/*` |

### Room 自动加入

| Room | 用途 | 加入时机 |
|------|------|---------|
| `user:{user_id}` | 指定用户所有设备 | on_connect |
| `tenant:{tenant_id}` | 租户广播 | on_connect（tenant/user namespace） |
| `admins` | 所有平台管理员 | on_connect（admin namespace） |

### 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/core/socketio_server.py` | AsyncServer + AsyncRedisManager 单例 |
| `backend/app/sio/__init__.py` | register_namespaces() 注册入口 |
| `backend/app/sio/admin_ns.py` | /admin namespace（JWT 认证 + rooms） |
| `backend/app/sio/tenant_ns.py` | /tenant namespace |
| `backend/app/sio/user_ns.py` | /user namespace |
| `backend/app/sio/presence.py` | PresenceManager（Redis Hash 在线状态） |
| `frontend/.../composables/use-socketio.ts` | useSocketIO composable |
| `frontend/.../store/shared/socketio.ts` | useSocketIOStore 全局连接管理 |

---

## 二、后端使用

### 2.1 启动依赖

```bash
# 安装
pip install python-socketio>=5.11.0

# 依赖
- Redis 必须运行（AsyncRedisManager 需要）
- main.py 中 ASGIApp 自动挂载到 /sio 路径
```

### 2.2 从任意位置发送消息

```python
from app.core.socketio_server import sio

# 发送给指定用户（所有设备）
await sio.emit("notification", data, room=f"user:{user_id}", namespace="/tenant")

# 广播给租户所有人
await sio.emit("notification", data, room=f"tenant:{tenant_id}", namespace="/tenant")

# 广播给所有平台管理员
await sio.emit("notification", data, room="admins", namespace="/admin")
```

### 2.3 在 Namespace 中处理自定义事件

```python
# 在 admin_ns.py 中添加事件处理
class AdminNamespace(socketio.AsyncNamespace):
    async def on_my_custom_event(self, sid, data):
        """处理客户端发来的 my_custom_event 事件"""
        session = await self.get_session(sid)
        user_id = session["user_id"]
        # 处理业务逻辑...
        await self.emit("my_response", {"result": "ok"}, to=sid)
```

### 2.4 获取连接会话数据

```python
# 在 namespace 方法中
session = await self.get_session(sid)
user_id = session["user_id"]       # int
user_type = session["user_type"]   # "admin" | "tenant_admin" | "tenant_user"
tenant_id = session["tenant_id"]   # int | None
username = session["username"]     # str
```

### 2.5 在线状态查询

```python
from app.sio.presence import PresenceManager

# 获取在线用户 ID 列表
online_ids = await PresenceManager.get_online_ids("admin")
online_ids = await PresenceManager.get_online_ids("tenant_admin", tenant_id=1)

# 检查单个用户是否在线
is_online = await PresenceManager.is_online("admin", user_id=5)

# 获取详情（含连接数）
details = await PresenceManager.get_online_details("admin")
# { 5: {"connections": 2}, 8: {"connections": 1} }
```

### 2.6 Celery 同步环境发送（sio_bridge）

Celery Worker 是同步环境，通过 `sio_bridge` 模块的 `RedisManager(write_only=True)` 发布：

```python
from app.core.sio_bridge import (
    sio_emit_sync,           # 底层：指定 event/room/namespace
    notify_user_sync,        # 发送给指定用户
    notify_admins_sync,      # 广播所有平台管理员
    notify_tenant_sync,      # 广播指定租户
)

# 发送给指定用户
notify_user_sync("admin", user_id=5, notification_data={
    "type": "task.completed", "category": "task",
    "title": "Task done", "priority": "normal",
})

# 广播所有管理员
notify_admins_sync({"type": "system.alert", ...})

# 广播指定租户
notify_tenant_sync(tenant_id=1, notification_data={...})
```

---

## 三、前端使用

### 3.1 全局连接（自动）

layout 加载时 `useSocketIOStore.connect()` 自动建立连接，无需手动调用。

### 3.2 监听事件

```typescript
import { useSocketIOStore } from '#/store';

const sioStore = useSocketIOStore();

// 注册 handler
const handler = (data: { type: string; message: string }) => {
  console.warn('Notification received:', data);
};
sioStore.registerHandler('notification', handler);

// 注销 handler（组件卸载时）
onUnmounted(() => {
  sioStore.unregisterHandler('notification', handler);
});
```

### 3.3 发送事件

```typescript
sioStore.emit('my_custom_event', { key: 'value' });
```

### 3.4 检查连接状态

```typescript
const sioStore = useSocketIOStore();

// 响应式状态
sioStore.status;       // 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
sioStore.isConnected;  // computed boolean
```

### 3.5 直接使用 composable（非全局场景）

```typescript
import { useSocketIO } from '#/composables/use-socketio';

const { socket, status, connect, on, emit } = useSocketIO({
  namespace: '/admin',
  token: accessTokenRef,
});

connect();
on('my_event', (data) => { ... });
```

---

## 四、事件命名规范

| 事件名 | 方向 | 说明 |
|--------|------|------|
| `notification` | S→C | 通知推送（payload.type 区分子类型） |
| `presence:online` | S→C | 用户上线 |
| `presence:offline` | S→C | 用户下线 |
| `presence:list` | S→C | 初始在线列表（连接时自动推送） |
| `ai:typing:start` | S→C | AI 开始回复 |
| `ai:typing:stop` | S→C | AI 回复完成 |

### 自定义事件命名规则

- 使用 `命名空间:动作` 格式（冒号分隔）
- 命名空间：`notification` / `presence` / `ai` / `im`（预留）
- 全部小写，单词间用下划线

---

## 五、如何新增一种事件

### 后端

1. 在对应 Namespace 类中添加 `on_xxx` 方法（处理客户端发来的事件）
2. 或在业务代码中 `await sio.emit("new_event", data, room=..., namespace=...)`

### 前端

1. 在需要监听的组件/store 中：
   ```typescript
   sioStore.registerHandler('new_event', (data) => { ... });
   ```
2. 组件卸载时注销 handler

---

## 六、Room 使用规范

```python
# 发送给指定用户（推荐，支持多设备）
await sio.emit("event", data, room=f"user:{user_id}", namespace="/admin")

# 发送给租户所有人
await sio.emit("event", data, room=f"tenant:{tenant_id}", namespace="/tenant")

# 发送给所有管理员
await sio.emit("event", data, room="admins", namespace="/admin")

# 发送给指定连接（sid）
await sio.emit("event", data, to=sid, namespace="/admin")
```

**禁止**直接广播到整个 namespace（无 room 参数），会发送给所有连接。

---

## 七、在线状态 API

### HTTP 查询（页面初始化加载）

```
GET /admin/ws/presence                    → 平台管理员在线列表
GET /admin/ws/presence/tenant/{id}        → 指定租户管理员在线列表
GET /tenant/ws/presence                   → 当前租户管理员在线列表
```

### Socket.IO 实时推送

连接时自动收到 `presence:list`，之后实时收到 `presence:online` / `presence:offline`。

---

## 八、调试方法

### 浏览器 DevTools

1. 打开 Network → WS tab
2. 查看 Socket.IO 握手和消息
3. 注意：Socket.IO 使用自己的协议格式（`42["event",{data}]`）

### Redis MONITOR

```bash
redis-cli MONITOR | grep socketio
```

查看 Socket.IO 通过 Redis 发布的消息。

### 后端日志

Socket.IO 连接/断开事件记录在 `logs/app.log` 中：
```
SIO /admin connected: sid=xxx user_id=5 username=admin connections=1
SIO /admin disconnected: sid=xxx user_id=5 reason=client namespace disconnect
```

---

## 九、常见问题

### CORS 错误

Socket.IO 的 CORS 在 `socketio_server.py` 中配置 `cors_allowed_origins`，与 FastAPI 的 CORSMiddleware 独立。确保两处配置一致。

### Token 过期

后端区分两种认证错误：
- `token_expired` — Token 已过期（前端可检测到 Token 已刷新后自动重连）
- `authentication_failed` — Token 无效

`useSocketIO` composable 的 `connect_error` handler 会在 3 次认证失败后停止重连。成功连接时 `authErrorCount` 自动重置。socketio store 使用 getter 函数实时从 `TokenStorage` 读取最新 token，axios 拦截器刷新 token 后 Socket.IO 能自动检测到。

### 多 Worker 部署

`AsyncRedisManager` 自动处理跨 Worker 消息同步。无需额外配置。确保所有 Worker 使用相同的 Redis URL。

### 连接数限制

连接频率限制：`check_connect_rate` Lua 原子脚本，60 秒内最多 20 次连接。超限返回 `rate_limited`。

### Presence 数据残留

Presence Hash 设有 24h TTL，`set_online` 时自动刷新。即使 worker 崩溃，stale 数据也会在 TTL 后自动清除。启动时 `clear_all()` 清空所有 presence key。

---

## 十、检查清单

### 后端

- [ ] 新事件使用常量定义事件名（禁止魔法字符串）
- [ ] emit 时指定 room 和 namespace（禁止无 room 广播）
- [ ] Celery 环境使用 sync RedisManager
- [ ] 日志使用 LogManager.get_logger("app")
- [ ] 面向用户文本使用 `_()`

### 前端

- [ ] 使用 sioStore.registerHandler() 注册事件（禁止直接操作 socket 实例）
- [ ] 组件卸载时 unregisterHandler()
- [ ] 不使用 console.log（使用 console.warn / console.error）
- [ ] 不使用 any 类型
- [ ] 文字使用 $t() 国际化

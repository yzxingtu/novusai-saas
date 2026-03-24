# WebSocket 前端接入

## 目录

- [全局连接](#全局连接)
- [监听事件](#监听事件)
- [发送事件](#发送事件)
- [检查连接状态](#检查连接状态)
- [直接使用 composable](#直接使用-composable)
- [新增事件的前端接入步骤](#新增事件的前端接入步骤)

## 全局连接

默认使用全局 store：

- `frontend/apps/web-antd/src/store/shared/socketio.ts`
- layout 加载时自动 `connect()`

业务页面通常不需要自己手动建第二条连接。

## 监听事件

```ts
import { useSocketIOStore } from '#/store';

const sioStore = useSocketIOStore();

const handler = (data: { type: string; message: string }) => {
  console.warn('Notification received:', data);
};

sioStore.registerHandler('notification', handler);

onUnmounted(() => {
  sioStore.unregisterHandler('notification', handler);
});
```

规则：

- 使用 `registerHandler()` / `unregisterHandler()`
- 组件卸载必须注销 handler
- 不要直接长期持有裸 `socket.on(...)`

## 发送事件

```ts
sioStore.emit('my_custom_event', { key: 'value' });
```

事件名要和后端 namespace 对齐，不要在前端擅自改名。

## 检查连接状态

```ts
const sioStore = useSocketIOStore();

sioStore.status;
sioStore.isConnected;
```

典型状态：

- `connecting`
- `connected`
- `disconnected`
- `reconnecting`

## 直接使用 composable

非全局场景才使用 `useSocketIO`：

```ts
import { useSocketIO } from '#/composables/use-socketio';

const { connect, on, emit } = useSocketIO({
  namespace: '/admin',
  token: accessTokenRef,
});

connect();
on('my_event', (data) => {
  // handle
});
```

适用场景：

- 局部独立连接实验
- 脱离全局 store 的特殊页面

普通业务页优先复用全局 store。

## 新增事件的前端接入步骤

1. 明确事件属于哪个 namespace。
2. 在 store 或页面注册 handler。
3. 组件卸载时注销 handler。
4. 如需发送，统一从 store/composable `emit`。
5. 验证重连后是否仍能收到事件。

常见事件：

- `notification`
- `presence:list`
- `presence:online`
- `presence:offline`
- `ai:typing:start`
- `ai:typing:stop`
- `page_operation_invoke`

/**
 * useCollaboration 组合式函数
 *
 * 封装实时协作功能：Y.js Doc + SocketIOProvider + Awareness
 * 可通过 enabled 开关控制，关闭时不创建连接
 */
import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue';

import * as Y from 'yjs';

import {
  SocketIOProvider,
  type SocketIOProviderOptions,
} from '../extensions/socket-io-provider';

export interface CollaborationUser {
  id: number;
  name: string;
  color: string;
}

export interface UseCollaborationOptions {
  /** 是否启用协作 */
  enabled: Ref<boolean>;
  /** 文档 ID */
  documentId: Ref<number | undefined>;
  /** Socket.IO 服务器 URL */
  serverUrl: string;
  /** JWT Token */
  token: Ref<string>;
  /** 当前用户 */
  user: CollaborationUser;
}

export function useCollaboration(options: UseCollaborationOptions) {
  const ydoc = shallowRef<Y.Doc | null>(null);
  const provider = shallowRef<SocketIOProvider | null>(null);
  const connected = ref(false);
  const synced = ref(false);
  const onlineUsers = ref<CollaborationUser[]>([]);

  function connect() {
    if (!options.enabled.value || !options.documentId.value || !options.token.value) {
      return;
    }

    // 清理之前的连接
    disconnect();

    const doc = new Y.Doc();
    ydoc.value = doc;

    const providerOptions: SocketIOProviderOptions = {
      serverUrl: options.serverUrl,
      token: options.token.value,
      documentId: options.documentId.value,
      user: options.user,
    };

    const p = new SocketIOProvider(doc, providerOptions);
    provider.value = p;

    // 监听连接状态变化（轮询，因为 SocketIOProvider 没有 EventEmitter）
    const statusInterval = setInterval(() => {
      connected.value = p.connected;
      synced.value = p.synced;

      // 更新在线用户
      const states = p.awareness.getStates();
      const users: CollaborationUser[] = [];
      for (const [, state] of states) {
        const userState = (state as Record<string, unknown>)?.user as CollaborationUser | undefined;
        if (userState?.id && userState.id !== options.user.id) {
          users.push(userState);
        }
      }
      onlineUsers.value = users;
    }, 1000);

    // 存储清理函数
    (p as unknown as Record<string, unknown>)._statusInterval = statusInterval;
  }

  function disconnect() {
    if (provider.value) {
      const p = provider.value as unknown as Record<string, unknown>;
      if (p._statusInterval) {
        clearInterval(p._statusInterval as ReturnType<typeof setInterval>);
      }
      provider.value.destroy();
      provider.value = null;
    }
    if (ydoc.value) {
      ydoc.value.destroy();
      ydoc.value = null;
    }
    connected.value = false;
    synced.value = false;
    onlineUsers.value = [];
  }

  // 监听 enabled / documentId 变化自动连接/断开
  watch(
    [options.enabled, options.documentId],
    ([enabled, docId]) => {
      if (enabled && docId) {
        connect();
      } else {
        disconnect();
      }
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    disconnect();
  });

  return {
    ydoc,
    provider,
    connected,
    synced,
    onlineUsers,
    connect,
    disconnect,
  };
}

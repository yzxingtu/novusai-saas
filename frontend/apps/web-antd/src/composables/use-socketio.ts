/**
 * Socket.IO 连接 Composable
 *
 * 封装 socket.io-client 的连接管理，提供响应式状态跟踪、
 * Token 刷新重连、事件监听/发送等能力。
 */

import type { Socket } from 'socket.io-client';

import type { Ref, ShallowRef } from 'vue';

import { ref, shallowRef, toValue, watch } from 'vue';

import { io } from 'socket.io-client';

/** 连接状态 */
export type SocketIOStatus =
  | 'connected'
  | 'connecting'
  | 'disconnected'
  | 'reconnecting';

/** Composable 选项 */
export interface UseSocketIOOptions {
  /** Socket.IO namespace，如 '/admin'、'/tenant'、'/user' */
  namespace: string;
  /** JWT access token（响应式 Ref、静态字符串、或 getter 函数） */
  token: (() => string) | Ref<string> | string;
  /** 服务器 URL，默认当前 origin */
  serverUrl?: string;
  /** Socket.IO path，默认 '/sio' */
  path?: string;
  /** 是否自动连接，默认 false */
  autoConnect?: boolean;
}

/** Composable 返回值 */
export interface UseSocketIOReturn {
  /** Socket.IO 客户端实例 */
  socket: ShallowRef<null | Socket>;
  /** 连接状态 */
  status: Ref<SocketIOStatus>;
  /** 手动连接 */
  connect: () => void;
  /** 手动断开 */
  disconnect: () => void;
  /** 监听事件 */
  on: <T = unknown>(event: string, handler: (data: T) => void) => void;
  /** 取消监听 */
  off: (event: string, handler?: (...args: unknown[]) => void) => void;
  /** 发送事件 */
  emit: (event: string, data?: unknown) => void;
}

/**
 * Socket.IO 连接 composable
 *
 * @example
 * ```ts
 * const { socket, status, connect, on } = useSocketIO({
 *   namespace: '/admin',
 *   token: accessTokenRef,
 * });
 * connect();
 * on('notification', (data) => { ... });
 * ```
 */
export function useSocketIO(options: UseSocketIOOptions): UseSocketIOReturn {
  const {
    namespace,
    token,
    serverUrl,
    path = '/sio',
    autoConnect = false,
  } = options;

  const socket: ShallowRef<null | Socket> = shallowRef(null);
  const status = ref<SocketIOStatus>('disconnected');

  let isManualDisconnect = false;
  let authErrorCount = 0;
  const MAX_AUTH_ERRORS = 3;

  /** 获取当前 token 值（支持 Ref、getter 函数、静态字符串） */
  function getToken(): string {
    if (typeof token === 'function') {
      return token();
    }
    return toValue(token);
  }

  /** 创建 Socket.IO 连接 */
  function createSocket(): Socket {
    const url = serverUrl || window.location.origin;
    const currentToken = getToken();

    const sock = io(`${url}${namespace}`, {
      path,
      auth: { token: currentToken ? `Bearer ${currentToken}` : '' },
      autoConnect: false,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Number.POSITIVE_INFINITY,
      transports: ['websocket'],
    });

    // 连接状态事件
    sock.on('connect', () => {
      status.value = 'connected';
      authErrorCount = 0;
    });

    sock.on('disconnect', (_reason) => {
      if (!isManualDisconnect) {
        status.value = 'disconnected';
      }
    });

    sock.io.on('reconnect_attempt', () => {
      status.value = 'reconnecting';
    });

    sock.io.on('reconnect', () => {
      status.value = 'connected';
    });

    sock.io.on('reconnect_failed', () => {
      status.value = 'disconnected';
      console.error('[Socket.IO] Reconnection failed');
    });

    // Token 过期 / 认证失败处理
    sock.on('connect_error', (err: Error) => {
      if (
        err.message === 'token_expired' ||
        err.message === 'authentication_failed'
      ) {
        authErrorCount++;
        const latestToken = getToken();

        if (latestToken && latestToken !== currentToken) {
          // Token 已刷新，用新 token 重连
          sock.auth = { token: `Bearer ${latestToken}` };
          authErrorCount = 0;
          console.warn(
            '[Socket.IO] Token refreshed, reconnecting with new token',
          );
        } else if (authErrorCount >= MAX_AUTH_ERRORS) {
          // 多次认证失败且 token 未刷新，停止重连
          sock.disconnect();
          status.value = 'disconnected';
          console.warn(
            '[Socket.IO] Auth failed after max retries, stopped reconnecting',
          );
        } else {
          console.warn(
            `[Socket.IO] Auth error: ${err.message} (attempt ${authErrorCount}/${MAX_AUTH_ERRORS})`,
          );
        }
      }
    });

    return sock;
  }

  /** 连接 */
  function connect() {
    isManualDisconnect = false;
    authErrorCount = 0;

    const currentToken = getToken();
    if (!currentToken) {
      return;
    }

    // 如果已有连接且 connected，忽略
    if (socket.value?.connected) {
      return;
    }

    // 如果已有 socket 但未连接，先销毁
    if (socket.value) {
      socket.value.removeAllListeners();
      socket.value.disconnect();
    }

    status.value = 'connecting';
    const sock = createSocket();
    socket.value = sock;
    sock.connect();
  }

  /** 断开连接 */
  function disconnect() {
    isManualDisconnect = true;
    if (socket.value) {
      socket.value.removeAllListeners();
      socket.value.disconnect();
      socket.value = null;
    }
    status.value = 'disconnected';
  }

  /** 监听事件 */
  function on<T = unknown>(event: string, handler: (data: T) => void) {
    socket.value?.on(event, handler as (...args: unknown[]) => void);
  }

  /** 取消监听 */
  function off(event: string, handler?: (...args: unknown[]) => void) {
    if (handler) {
      socket.value?.off(event, handler);
    } else {
      socket.value?.off(event);
    }
  }

  /** 发送事件 */
  function emit(event: string, data?: unknown) {
    if (socket.value?.connected) {
      socket.value.emit(event, data);
    }
  }

  // Token 变化时断开重连（仅对 Ref 类型有效，getter 函数无需 watch）
  if (typeof token !== 'string' && typeof token !== 'function') {
    watch(token, (newToken, oldToken) => {
      if (newToken === oldToken) return;

      if (!newToken) {
        // Token 清空 → 断开
        disconnect();
        return;
      }

      if (socket.value) {
        // Token 更新 → 重连（更新 auth）
        socket.value.auth = { token: `Bearer ${newToken}` };
        if (socket.value.connected) {
          // 已连接状态下 token 变化：断开重连以使用新 token
          socket.value.disconnect();
          socket.value.connect();
        } else {
          socket.value.connect();
        }
      } else if (oldToken === '') {
        // 首次获得 token → 连接
        connect();
      }
    });
  }

  // 自动连接
  if (autoConnect && getToken()) {
    connect();
  }

  return {
    socket,
    status,
    connect,
    disconnect,
    on,
    off,
    emit,
  };
}

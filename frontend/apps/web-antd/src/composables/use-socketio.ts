/**
 * Socket.IO connection composable
 * Socket.IO 连接 Composable
 *
 * Encapsulates socket.io-client connection management with reactive status tracking,
 * token refresh reconnection, and event listen/emit capabilities.
 * 封装 socket.io-client 的连接管理，提供响应式状态跟踪、Token 刷新重连、事件监听/发送等能力。
 */

import type { Socket } from 'socket.io-client';

import type { Ref, ShallowRef } from 'vue';

import { ref, shallowRef, toValue, watch } from 'vue';

import { io } from 'socket.io-client';

import { isDevErrorMode } from '#/utils/request';
import { ensureTraceIdHeader } from '#/utils/request/trace';

const SOCKET_TRACE_HEADERS: Record<string, unknown> = {};

export function getSocketTraceId(): string {
  return ensureTraceIdHeader(SOCKET_TRACE_HEADERS);
}

function isSocketPayloadObject(
  data: unknown,
): data is Record<string, unknown> {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(data);
  return prototype === null || prototype === Object.prototype;
}

export function withSocketTracePayload<T>(data: T): T {
  if (!isSocketPayloadObject(data)) {
    return data;
  }

  const traceId =
    typeof data.trace_id === 'string' && data.trace_id.trim()
      ? data.trace_id.trim()
      : getSocketTraceId();

  return traceId ? ({ ...data, trace_id: traceId } as T) : data;
}

interface SocketConnectErrorData {
  debug?: { detail?: string; message?: string };
  message?: string;
  reason?: string;
  trace_id?: string;
}

function getSocketConnectErrorInfo(err: Error & { data?: SocketConnectErrorData }) {
  const reason = err.data?.reason || err.message;
  const traceId = err.data?.trace_id || '';
  const debugMessage =
    err.data?.debug?.detail || err.data?.debug?.message || '';
  return { debugMessage, reason, traceId };
}

/** 连接状态 / Connection status */
export type SocketIOStatus =
  | 'connected'
  | 'connecting'
  | 'disconnected'
  | 'reconnecting';

/** Composable options / Composable 选项 */
export interface UseSocketIOOptions {
  /** Socket.IO namespace, e.g. '/admin', '/tenant', '/user' / Socket.IO 命名空间 */
  namespace: string;
  /** JWT access token (reactive Ref, static string, or getter function) / JWT 访问令牌 */
  token: (() => string) | Ref<string> | string;
  /** Server URL, defaults to current origin / 服务器 URL */
  serverUrl?: string;
  /** Socket.IO path, default '/sio' / Socket.IO 路径 */
  path?: string;
  /** Whether to auto-connect, default false / 是否自动连接 */
  autoConnect?: boolean;
}

/** Composable return value / Composable 返回值 */
export interface UseSocketIOReturn {
  /** Socket.IO client instance / Socket.IO 客户端实例 */
  socket: ShallowRef<null | Socket>;
  /** Connection status / 连接状态 */
  status: Ref<SocketIOStatus>;
  /** Manual connect / 手动连接 */
  connect: () => void;
  /** Manual disconnect / 手动断开 */
  disconnect: () => void;
  /** Listen to event / 监听事件 */
  on: <T = unknown>(event: string, handler: (data: T) => void) => void;
  /** Remove event listener / 取消监听 */
  off: (event: string, handler?: (...args: unknown[]) => void) => void;
  /** Emit event / 发送事件 */
  emit: (event: string, data?: unknown) => void;
}

/**
 * Socket.IO connection composable / Socket.IO 连接 composable
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

  /** Get current token value (supports Ref, getter function, static string) / 获取当前 token 值 */
  function getToken(): string {
    if (typeof token === 'function') {
      return token();
    }
    return toValue(token);
  }

  /** Create Socket.IO connection / 创建 Socket.IO 连接 */
  function createSocket(): Socket {
    const url = serverUrl || window.location.origin;
    const currentToken = getToken();
    const traceId = getSocketTraceId();

    const authPayload: Record<string, string> = {
      token: currentToken ? `Bearer ${currentToken}` : '',
    };
    if (traceId) {
      authPayload.trace_id = traceId;
    }

    const sock = io(`${url}${namespace}`, {
      path,
      auth: authPayload,
      autoConnect: false,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Number.POSITIVE_INFINITY,
      transports: ['websocket'],
    });

    // Connection status events / 连接状态事件
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

    // Token expired / auth failure handling / Token 过期认证失败处理
    sock.on('connect_error', (err: Error & { data?: SocketConnectErrorData }) => {
      const { debugMessage, reason, traceId } = getSocketConnectErrorInfo(err);
      const traceSuffix = traceId ? ` (trace_id=${traceId})` : '';
      if (
        reason === 'token_expired' ||
        reason === 'authentication_failed'
      ) {
        authErrorCount++;
        const latestToken = getToken();

        if (latestToken && latestToken !== currentToken) {
          // Token refreshed, reconnect with new token / Token 已刷新，用新 token 重连
          const refreshedTraceId = getSocketTraceId();
          sock.auth = refreshedTraceId
            ? { token: `Bearer ${latestToken}`, trace_id: refreshedTraceId }
            : { token: `Bearer ${latestToken}` };
          authErrorCount = 0;
          console.warn(
            `[Socket.IO] Token refreshed, reconnecting with new token${traceSuffix}`,
          );
        } else if (authErrorCount >= MAX_AUTH_ERRORS) {
          // Multiple auth failures without token refresh, stop reconnecting / 多次认证失败停止重连
          sock.disconnect();
          status.value = 'disconnected';
          console.warn(
            `[Socket.IO] Auth failed after max retries, stopped reconnecting${traceSuffix}`,
          );
        } else {
          console.warn(
            `[Socket.IO] Auth error: ${reason} (attempt ${authErrorCount}/${MAX_AUTH_ERRORS})${traceSuffix}`,
          );
        }
      } else {
        const debugSuffix =
          isDevErrorMode() && debugMessage ? ` | debug=${debugMessage}` : '';
        console.warn(`[Socket.IO] Connect error: ${reason}${traceSuffix}${debugSuffix}`);
      }
    });

    return sock;
  }

  /** Connect / 连接 */
  function connect() {
    isManualDisconnect = false;
    authErrorCount = 0;

    const currentToken = getToken();
    if (!currentToken) {
      return;
    }

    // Ignore if already connected / 如果已有连接且 connected，忽略
    if (socket.value?.connected) {
      return;
    }

    // Destroy existing socket if not connected / 如果已有 socket 但未连接，先销毁
    if (socket.value) {
      socket.value.removeAllListeners();
      socket.value.disconnect();
    }

    status.value = 'connecting';
    const sock = createSocket();
    socket.value = sock;
    sock.connect();
  }

  /** Disconnect / 断开连接 */
  function disconnect() {
    isManualDisconnect = true;
    if (socket.value) {
      socket.value.removeAllListeners();
      socket.value.disconnect();
      socket.value = null;
    }
    status.value = 'disconnected';
  }

  /** Listen to event / 监听事件 */
  function on<T = unknown>(event: string, handler: (data: T) => void) {
    socket.value?.on(event, handler as (...args: unknown[]) => void);
  }

  /** Remove event listener / 取消监听 */
  function off(event: string, handler?: (...args: unknown[]) => void) {
    if (handler) {
      socket.value?.off(event, handler);
    } else {
      socket.value?.off(event);
    }
  }

  /** Emit event / 发送事件 */
  function emit(event: string, data?: unknown) {
    if (socket.value?.connected) {
      socket.value.emit(event, withSocketTracePayload(data));
    }
  }

  // Disconnect and reconnect on token change (only for Ref type, getter functions don't need watch) / Token 变化时断开重连
  if (typeof token !== 'string' && typeof token !== 'function') {
    watch(token, (newToken, oldToken) => {
      if (newToken === oldToken) return;

      if (!newToken) {
        // Token cleared → disconnect / Token 清空 → 断开
        disconnect();
        return;
      }

      if (socket.value) {
        // Token updated → reconnect (update auth) / Token 更新 → 重连
        const traceId = getSocketTraceId();
        socket.value.auth = traceId
          ? { token: `Bearer ${newToken}`, trace_id: traceId }
          : { token: `Bearer ${newToken}` };
        if (socket.value.connected) {
          // Token changed while connected: disconnect and reconnect with new token / 已连接状态下断开重连
          socket.value.disconnect();
          socket.value.connect();
        } else {
          socket.value.connect();
        }
      } else if (oldToken === '') {
        // First token received → connect / 首次获得 token → 连接
        connect();
      }
    });
  }

  // Auto-connect / 自动连接
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

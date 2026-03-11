/**
 * Global Socket.IO connection management store / 全局 Socket.IO 连接管理 Store
 *
 * Automatically connects after login, disconnects on logout.
 * Provides event handler registration/unregistration and dispatches events to registered handlers.
 * 登录后自动建立连接，登出时断开。提供事件 handler 注册/注销机制。
 */

import type { SocketIOStatus } from '#/composables/use-socketio';

import { computed, ref, watch } from 'vue';

import { useAppConfig } from '@vben/hooks';

import { defineStore } from 'pinia';

import { getApiEndpoint } from '#/api';
import { useSocketIO } from '#/composables/use-socketio';

import { TokenStorage } from './token-storage';

/** Namespace 映射：API endpoint → Socket.IO namespace */
const NAMESPACE_MAP: Record<string, string> = {
  admin: '/admin',
  tenant: '/tenant',
  user: '/user',
};

export const useSocketIOStore = defineStore('socketio', () => {
  // ============================================================
  // State / 状态
  // ============================================================

  /** Current connection status / 当前连接状态 */
  const status = ref<SocketIOStatus>('disconnected');

  /** Currently connected endpoint / 当前连接的 endpoint */
  const currentEndpoint = ref<string>('');

  /** Registered event handlers / 已注册的事件 handlers */
  const handlers = new Map<string, Set<(data: unknown) => void>>();

  /** Socket.IO composable instance (lazy-created) / Socket.IO composable 实例 */
  let sioInstance: null | ReturnType<typeof useSocketIO> = null;
  /** Status watch stop function (avoids accumulating watchers on reconnect) / status watch 停止函数 */
  let stopStatusWatch: (() => void) | null = null;

  // ============================================================
  // Connection management / 连接管理
  // ============================================================

  /** Whether connected / 是否已连接 */
  const isConnected = computed(() => status.value === 'connected');

  /**
   * Establish connection / 建立连接
   *
   * @param endpoint - API endpoint type ('admin' | 'tenant' | 'user') / API 端类型
   */
  function connect(endpoint?: string) {
    const ep = endpoint || _detectEndpoint();
    if (!ep) return;

    const token = TokenStorage.getToken(ep as 'admin' | 'tenant' | 'user');
    if (!token) return;

    const ns = NAMESPACE_MAP[ep];
    if (!ns) return;

    // If already connected to same endpoint, ignore / 已连接到同一 endpoint 则忽略
    if (
      sioInstance &&
      currentEndpoint.value === ep &&
      status.value === 'connected'
    ) {
      return;
    }

    // Disconnect old connection (avoid orphaned socket on endpoint switch) / 断开旧连接
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }
    if (stopStatusWatch) {
      stopStatusWatch();
      stopStatusWatch = null;
    }

    currentEndpoint.value = ep;

    // Create new connection (use backend API URL; dev env can't use window.location.origin) / 创建新连接
    const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
    // Use getter function to read TokenStorage in real-time, ensuring Socket.IO gets the latest token after refresh / 实时读取 Token
    const tokenGetter = () =>
      TokenStorage.getToken(ep as 'admin' | 'tenant' | 'user') || '';
    sioInstance = useSocketIO({
      namespace: ns,
      token: tokenGetter,
      serverUrl: apiURL,
      autoConnect: true,
    });

    // Sync status / 同步 status
    stopStatusWatch = watch(
      sioInstance.status,
      (newStatus) => {
        status.value = newStatus;
      },
      { immediate: true },
    );

    // Bind all registered handlers / 绑定所有已注册的 handlers
    _bindHandlers();
  }

  /**
   * Disconnect / 断开连接
   *
   * Note: Does not clear handlers map; keeps registered handlers so that
   * _bindHandlers() can auto-rebind on reconnect. Call $reset() on logout to clear handlers.
   * 注意：不清 handlers map，保留已注册 handler 以便重连。登出时需调用 $reset()。
   */
  function disconnect() {
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }
    if (stopStatusWatch) {
      stopStatusWatch();
      stopStatusWatch = null;
    }
    currentEndpoint.value = '';
    status.value = 'disconnected';
  }

  // ============================================================
  // Event dispatch / 事件分发
  // ============================================================

  /**
   * Register event handler / 注册事件 handler
   *
   * @param event - Event name (e.g. 'notification', 'presence:online') / 事件名
   * @param handler - Callback function / 回调函数
   */
  function registerHandler(event: string, handler: (data: unknown) => void) {
    if (!handlers.has(event)) {
      handlers.set(event, new Set());
    }
    const eventHandlers = handlers.get(event);
    if (eventHandlers) {
      eventHandlers.add(handler);
    }

    // If already connected, bind immediately / 如果已有连接，立即绑定
    if (sioInstance) {
      sioInstance.on(event, handler);
    }
  }

  /**
   * Unregister event handler / 注销事件 handler
   *
   * @param event - Event name / 事件名
   * @param handler - Callback to remove (omit to remove all handlers for this event) / 要移除的回调
   */
  function unregisterHandler(event: string, handler?: (data: unknown) => void) {
    const eventHandlers = handlers.get(event);
    if (!eventHandlers) return;

    if (handler) {
      eventHandlers.delete(handler);
      if (sioInstance) {
        sioInstance.off(event, handler as (...args: unknown[]) => void);
      }
      if (eventHandlers.size === 0) {
        handlers.delete(event);
      }
    } else {
      // Remove all handlers for this event / 移除该事件所有 handlers
      if (sioInstance) {
        sioInstance.off(event);
      }
      handlers.delete(event);
    }
  }

  /**
   * Emit event / 发送事件
   */
  function emit(event: string, data?: unknown) {
    sioInstance?.emit(event, data);
  }

  // ============================================================
  // Internal methods / 内部方法
  // ============================================================

  /** Bind all registered handlers to current socket (off first to prevent duplicates) / 绑定已注册 handlers */
  function _bindHandlers() {
    if (!sioInstance) return;
    for (const [event, eventHandlers] of handlers) {
      for (const handler of eventHandlers) {
        sioInstance.off(event, handler as (...args: unknown[]) => void);
        sioInstance.on(event, handler);
      }
    }
  }

  /** Detect current endpoint type / 检测当前端类型 */
  function _detectEndpoint(): string {
    try {
      const path = window.location.hash
        ? window.location.hash.slice(1)
        : window.location.pathname;
      return getApiEndpoint(path);
    } catch {
      return 'admin';
    }
  }

  /**
   * Full reset (called on logout) / 完全重置（登出时调用）
   * Disconnects + clears handlers map to prevent duplicate registrations on re-login.
   */
  function $reset() {
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }
    if (stopStatusWatch) {
      stopStatusWatch();
      stopStatusWatch = null;
    }
    handlers.clear();
    currentEndpoint.value = '';
    status.value = 'disconnected';
  }

  return {
    status,
    currentEndpoint,
    isConnected,
    connect,
    disconnect,
    registerHandler,
    unregisterHandler,
    emit,
    $reset,
  };
});

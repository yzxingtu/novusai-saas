/**
 * 全局 Socket.IO 连接管理 Store
 *
 * 登录后自动建立 Socket.IO 连接，登出时断开。
 * 提供事件 handler 注册/注销机制，收到事件后分发给已注册 handlers。
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
  // 状态
  // ============================================================

  /** 当前连接状态 */
  const status = ref<SocketIOStatus>('disconnected');

  /** 当前连接的 endpoint */
  const currentEndpoint = ref<string>('');

  /** 已注册的事件 handlers */
  const handlers = new Map<string, Set<(data: unknown) => void>>();

  /** Socket.IO composable 实例（延迟创建） */
  let sioInstance: ReturnType<typeof useSocketIO> | null = null;

  // ============================================================
  // 连接管理
  // ============================================================

  /** 是否已连接 */
  const isConnected = computed(() => status.value === 'connected');

  /**
   * 建立连接
   *
   * @param endpoint - API 端类型 ('admin' | 'tenant' | 'user')
   */
  function connect(endpoint?: string) {
    const ep = endpoint || _detectEndpoint();
    if (!ep) return;

    const token = TokenStorage.getToken(ep as 'admin' | 'tenant' | 'user');
    if (!token) return;

    const ns = NAMESPACE_MAP[ep];
    if (!ns) return;

    // 如果已连接到同一 endpoint，忽略
    if (sioInstance && currentEndpoint.value === ep && status.value === 'connected') {
      return;
    }

    // 断开旧连接（避免 endpoint 切换时 socket 被孤立）
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }

    currentEndpoint.value = ep;

    // 创建新连接（使用后端 API URL，开发环境不能用 window.location.origin）
    const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
    // 使用 getter 函数实时读取 TokenStorage，确保 token 刷新后 Socket.IO 能获取最新值
    const tokenGetter = () => TokenStorage.getToken(ep as 'admin' | 'tenant' | 'user') || '';
    sioInstance = useSocketIO({
      namespace: ns,
      token: tokenGetter,
      serverUrl: apiURL,
      autoConnect: true,
    });

    // 同步 status
    watch(sioInstance.status, (newStatus) => {
      status.value = newStatus;
    }, { immediate: true });

    // 绑定所有已注册的 handlers
    _bindHandlers();
  }

  /**
   * 断开连接
   */
  function disconnect() {
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }
    // 清理所有 handlers，防止重登录后 initSocketHandlers() 重复注册
    handlers.clear();
    currentEndpoint.value = '';
    status.value = 'disconnected';
  }

  // ============================================================
  // 事件分发
  // ============================================================

  /**
   * 注册事件 handler
   *
   * @param event - 事件名（如 'notification'、'presence:online'）
   * @param handler - 回调函数
   */
  function registerHandler(event: string, handler: (data: unknown) => void) {
    if (!handlers.has(event)) {
      handlers.set(event, new Set());
    }
    handlers.get(event)!.add(handler);

    // 如果已有连接，立即绑定
    if (sioInstance) {
      sioInstance.on(event, handler);
    }
  }

  /**
   * 注销事件 handler
   *
   * @param event - 事件名
   * @param handler - 要移除的回调（不传则移除该事件所有 handler）
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
      // 移除该事件所有 handlers
      if (sioInstance) {
        sioInstance.off(event);
      }
      handlers.delete(event);
    }
  }

  /**
   * 发送事件
   */
  function emit(event: string, data?: unknown) {
    sioInstance?.emit(event, data);
  }

  // ============================================================
  // 内部方法
  // ============================================================

  /** 将所有已注册 handlers 绑定到当前 socket */
  function _bindHandlers() {
    if (!sioInstance) return;
    for (const [event, eventHandlers] of handlers) {
      for (const handler of eventHandlers) {
        sioInstance.on(event, handler);
      }
    }
  }

  /** 检测当前端类型 */
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

  /** 重置 */
  function $reset() {
    disconnect();
    handlers.clear();
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

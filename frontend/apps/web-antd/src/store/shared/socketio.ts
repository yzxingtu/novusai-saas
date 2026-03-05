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
  let sioInstance: null | ReturnType<typeof useSocketIO> = null;
  /** status watch 停止函数（避免重复 connect 时累积 watcher） */
  let stopStatusWatch: (() => void) | null = null;

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
    if (
      sioInstance &&
      currentEndpoint.value === ep &&
      status.value === 'connected'
    ) {
      return;
    }

    // 断开旧连接（避免 endpoint 切换时 socket 被孤立）
    if (sioInstance) {
      sioInstance.disconnect();
      sioInstance = null;
    }
    if (stopStatusWatch) {
      stopStatusWatch();
      stopStatusWatch = null;
    }

    currentEndpoint.value = ep;

    // 创建新连接（使用后端 API URL，开发环境不能用 window.location.origin）
    const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
    // 使用 getter 函数实时读取 TokenStorage，确保 token 刷新后 Socket.IO 能获取最新值
    const tokenGetter = () =>
      TokenStorage.getToken(ep as 'admin' | 'tenant' | 'user') || '';
    sioInstance = useSocketIO({
      namespace: ns,
      token: tokenGetter,
      serverUrl: apiURL,
      autoConnect: true,
    });

    // 同步 status
    stopStatusWatch = watch(
      sioInstance.status,
      (newStatus) => {
        status.value = newStatus;
      },
      { immediate: true },
    );

    // 绑定所有已注册的 handlers
    _bindHandlers();
  }

  /**
   * 断开连接
   *
   * 注意：不清 handlers map，保留已注册的 handler，以便重新 connect() 时
   * _bindHandlers() 能自动回绑，避免断线重连后收不到 Socket.IO 事件。
   * 明确登出时需调用 $reset()（会同时清 handlers）。
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
    const eventHandlers = handlers.get(event);
    if (eventHandlers) {
      eventHandlers.add(handler);
    }

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

  /** 将所有已注册 handlers 绑定到当前 socket（先 off 防止重复注册） */
  function _bindHandlers() {
    if (!sioInstance) return;
    for (const [event, eventHandlers] of handlers) {
      for (const handler of eventHandlers) {
        sioInstance.off(event, handler as (...args: unknown[]) => void);
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

  /**
   * 完全重置（登出时调用）
   * 断开连接 + 清空 handlers map（防止重登录后重复注册）
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

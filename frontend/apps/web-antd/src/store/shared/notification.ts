/**
 * Notification store / 通知 Store
 *
 * Manages notification data, unread count, and integrates Socket.IO real-time push.
 * 管理通知数据、未读计数，集成 Socket.IO 实时推送。
 */

import { ref } from 'vue';

import { defineStore } from 'pinia';

import { resolveEndpointByPath } from '#/constants/endpoints';
import { useNotificationToast } from '#/composables/use-notification-toast';
import { requestClient } from '#/utils/request';

import { useSocketIOStore } from './socketio';

/** Notification item / 通知项 */
export interface NotificationItem {
  id: number;
  template_code?: null | string;
  category: string;
  title: string;
  body?: null | string;
  data?: null | Record<string, unknown>;
  link?: null | string;
  priority: string;
  is_read: boolean;
  read_at?: null | string;
  created_at?: null | string;
}

/** Notification list API response / 通知列表 API 响应 */
interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Socket.IO pushed notification data / Socket.IO 推送的通知数据 */
interface NotificationPushData {
  type: string;
  category: string;
  title: string;
  body?: null | string;
  data?: null | Record<string, unknown>;
  link?: null | string;
  priority: string;
}

const LOCAL_NOTIF_KEY = 'novus_local_notifications';

/** Load local notifications from localStorage / 从 localStorage 恢复本地通知 */
function _loadLocalNotifications(): NotificationItem[] {
  try {
    const raw = localStorage.getItem(LOCAL_NOTIF_KEY);
    return raw ? (JSON.parse(raw) as NotificationItem[]) : [];
  } catch {
    return [];
  }
}

/** Save local notifications to localStorage / 保存本地通知到 localStorage */
function _saveLocalNotifications(items: NotificationItem[]) {
  try {
    const local = items.filter((n) => n.id < 0);
    if (local.length > 0) {
      localStorage.setItem(LOCAL_NOTIF_KEY, JSON.stringify(local));
    } else {
      localStorage.removeItem(LOCAL_NOTIF_KEY);
    }
  } catch {
    // Silent failure / 静默失败 (Silent failure)
  }
}

export const useNotificationStore = defineStore('notification', () => {
  // ============================================================
  // State / 状态
  // ============================================================

  const notifications = ref<NotificationItem[]>(_loadLocalNotifications());
  const unreadCount = ref(notifications.value.filter((n) => !n.is_read).length);
  const loading = ref(false);
  const initialized = ref(false);

  /** Explicit endpoint override (fallback only) / 显式端覆盖（仅作为兜底） */
  let currentEndpoint: 'admin' | 'tenant' | null = null;
  /** Fixed reference for unregister, avoiding handler leak / 固定引用避免泄漏 */
  const handleSocketNotification = (raw: unknown) => {
    const data = raw as NotificationPushData;
    if (!data?.title) return;

    // Increment unread count / 增加未读计数
    unreadCount.value++;

    // Add to top of list (temp ID, will be updated on refresh) / 添加到列表顶部
    notifications.value.unshift({
      id: -Date.now(),
      template_code: data.type,
      category: data.category,
      title: data.title,
      body: data.body,
      data: data.data,
      link: data.link,
      priority: data.priority,
      is_read: false,
      created_at: new Date().toISOString(),
    });

    _saveLocalNotifications(notifications.value);

    // Trigger toast popup / 触发 Toast 弹窗
    try {
      const { pushToast } = useNotificationToast();
      pushToast({
        template_code: data.type,
        category: data.category,
        title: data.title,
        body: data.body,
        data: data.data,
        link: data.link,
        priority: data.priority,
      });
    } catch {
      // Silent if toast not initialized / toast 未初始化时静默
    }
  };

  // ============================================================
  // API prefix / API 前缀
  // ============================================================

  function resolveNotificationEndpoint(): 'admin' | 'tenant' | null {
    if (typeof window !== 'undefined') {
      const endpoint = resolveEndpointByPath(
        window.location.pathname,
        window.location.hostname,
      );
      if (endpoint === 'admin' || endpoint === 'tenant') {
        return endpoint;
      }
    }
    return currentEndpoint;
  }

  function getApiPrefix(): null | string {
    const endpoint = resolveNotificationEndpoint();
    if (!endpoint) {
      return null;
    }
    return endpoint === 'tenant' ? '/tenant' : '/admin';
  }

  function setEndpoint(endpoint: 'admin' | 'tenant') {
    currentEndpoint = endpoint;
  }

  // ============================================================
  // Loading / 加载
  // ============================================================

  async function loadUnreadCount(): Promise<void> {
    const apiPrefix = getApiPrefix();
    if (!apiPrefix) {
      return;
    }
    try {
      const data = await requestClient.get<{ count: number }>(
        `${apiPrefix}/notifications/unread-count`,
      );
      if (data && typeof data.count === 'number') {
        unreadCount.value = data.count;
      }
    } catch {
      // Silent failure / 静默失败
    }
  }

  async function loadNotifications(
    category?: string,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<void> {
    const apiPrefix = getApiPrefix();
    if (!apiPrefix) {
      return;
    }
    loading.value = true;
    try {
      const params = new URLSearchParams();
      if (category) params.set('category', category);
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const data = await requestClient.get<NotificationListResponse>(
        `${apiPrefix}/notifications?${params.toString()}`,
      );
      if (data?.items) {
        if (page === 1) {
          // Keep local temp notifications (negative ID = real-time pushed, not persisted) / 保留本地临时通知
          const localOnly = notifications.value.filter((n) => n.id < 0);
          notifications.value = [...localOnly, ...data.items];
        } else {
          notifications.value.push(...data.items);
        }
      }
    } catch {
      console.error('[Notification] Failed to load notifications');
    } finally {
      loading.value = false;
    }
  }

  // ============================================================
  // Local notifications / 本地通知
  // ============================================================

  /** Add local temp notification (no backend, persisted to localStorage) / 添加本地临时通知 */
  function addLocalNotification(
    item: Omit<NotificationItem, 'created_at' | 'id' | 'is_read'>,
  ) {
    const notif: NotificationItem = {
      ...item,
      id: -Date.now(),
      is_read: false,
      created_at: new Date().toISOString(),
    };
    notifications.value.unshift(notif);
    unreadCount.value++;
    _saveLocalNotifications(notifications.value);

    // Trigger toast popup / 触发 Toast 弹窗
    try {
      const { pushToast } = useNotificationToast();
      pushToast({
        template_code: item.template_code,
        category: item.category,
        title: item.title,
        body: item.body,
        data: item.data,
        link: item.link,
        priority: item.priority,
      });
    } catch {
      // Silent / 静默
    }
  }

  // ============================================================
  // Operations / 操作
  // ============================================================

  async function markRead(id: number): Promise<void> {
    const apiPrefix = getApiPrefix();
    const item = notifications.value.find((n) => n.id === id);
    if (item) {
      item.is_read = true;
    }
    if (unreadCount.value > 0) {
      unreadCount.value--;
    }
    // Local temp notifications (negative ID) don't call backend API / 本地临时通知不调后端
    if (id < 0) {
      _saveLocalNotifications(notifications.value);
      return;
    }
    if (!apiPrefix) {
      return;
    }
    try {
      await requestClient.put(`${apiPrefix}/notifications/${id}/read`);
    } catch {
      // Silent / 静默
    }
  }

  async function markAllRead(category?: string): Promise<void> {
    const apiPrefix = getApiPrefix();
    if (!apiPrefix) {
      return;
    }
    try {
      const params = category ? `?category=${category}` : '';
      await requestClient.put(`${apiPrefix}/notifications/read-all${params}`);
      for (const n of notifications.value) {
        if (!category || n.category === category) {
          n.is_read = true;
        }
      }
      unreadCount.value = 0;
    } catch {
      // Silent / 静默
    }
  }

  async function deleteNotification(id: number): Promise<void> {
    const apiPrefix = getApiPrefix();
    const idx = notifications.value.findIndex((n) => n.id === id);
    if (idx !== -1) {
      const removed = notifications.value[idx];
      notifications.value.splice(idx, 1);
      if (!removed?.is_read && unreadCount.value > 0) {
        unreadCount.value--;
      }
    }
    // Local temp notifications (negative ID) don't call backend API / 本地临时通知不调后端
    if (id < 0) {
      _saveLocalNotifications(notifications.value);
      return;
    }
    if (!apiPrefix) {
      return;
    }
    try {
      await requestClient.delete(`${apiPrefix}/notifications/${id}`);
    } catch {
      // Silent / 静默
    }
  }

  // ============================================================
  // Socket.IO real-time push / Socket.IO 实时推送
  // ============================================================

  function initSocketHandlers(): void {
    if (initialized.value) return;
    initialized.value = true;

    const sioStore = useSocketIOStore();
    sioStore.unregisterHandler('notification', handleSocketNotification);
    sioStore.registerHandler('notification', handleSocketNotification);
  }

  // ============================================================
  // Reset / 重置
  // ============================================================

  function $reset() {
    try {
      useSocketIOStore().unregisterHandler(
        'notification',
        handleSocketNotification,
      );
    } catch {
      // Silent / 静默
    }
    notifications.value = [];
    unreadCount.value = 0;
    loading.value = false;
    initialized.value = false;
    localStorage.removeItem(LOCAL_NOTIF_KEY);
    try {
      useNotificationToast().clearAll();
    } catch {
      // 静默
    }
  }

  return {
    notifications,
    unreadCount,
    loading,
    setEndpoint,
    loadUnreadCount,
    loadNotifications,
    addLocalNotification,
    markRead,
    markAllRead,
    deleteNotification,
    initSocketHandlers,
    $reset,
  };
});

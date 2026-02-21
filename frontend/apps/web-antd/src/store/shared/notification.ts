/**
 * 通知 Store
 *
 * 管理通知数据、未读计数，集成 Socket.IO 实时推送。
 */

import { ref } from 'vue';

import { defineStore } from 'pinia';

import { requestClient } from '#/utils/request';

import { useSocketIOStore } from './socketio';

/** 通知项 */
export interface NotificationItem {
  id: number;
  category: string;
  title: string;
  body?: string | null;
  data?: Record<string, unknown> | null;
  link?: string | null;
  priority: string;
  is_read: boolean;
  read_at?: string | null;
  created_at?: string | null;
}

/** 通知列表 API 响应 */
interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Socket.IO 推送的通知数据 */
interface NotificationPushData {
  type: string;
  category: string;
  title: string;
  body?: string | null;
  data?: Record<string, unknown> | null;
  link?: string | null;
  priority: string;
}

const LOCAL_NOTIF_KEY = 'novus_local_notifications';

/** 从 localStorage 恢复本地通知 */
function _loadLocalNotifications(): NotificationItem[] {
  try {
    const raw = localStorage.getItem(LOCAL_NOTIF_KEY);
    return raw ? (JSON.parse(raw) as NotificationItem[]) : [];
  } catch {
    return [];
  }
}

/** 保存本地通知到 localStorage */
function _saveLocalNotifications(items: NotificationItem[]) {
  try {
    const local = items.filter((n) => n.id < 0);
    if (local.length > 0) {
      localStorage.setItem(LOCAL_NOTIF_KEY, JSON.stringify(local));
    } else {
      localStorage.removeItem(LOCAL_NOTIF_KEY);
    }
  } catch {
    // 静默
  }
}

export const useNotificationStore = defineStore('notification', () => {
  // ============================================================
  // 状态
  // ============================================================

  const notifications = ref<NotificationItem[]>(_loadLocalNotifications());
  const unreadCount = ref(notifications.value.filter((n) => !n.is_read).length);
  const loading = ref(false);
  const initialized = ref(false);

  /** 当前端类型（决定 API 前缀） */
  let currentEndpoint: 'admin' | 'tenant' = 'admin';

  // ============================================================
  // API 前缀
  // ============================================================

  function getApiPrefix(): string {
    return currentEndpoint === 'tenant' ? '/tenant' : '/admin';
  }

  function setEndpoint(endpoint: 'admin' | 'tenant') {
    currentEndpoint = endpoint;
  }

  // ============================================================
  // 加载
  // ============================================================

  async function loadUnreadCount(): Promise<void> {
    try {
      const data = await requestClient.get<{ count: number }>(
        `${getApiPrefix()}/notifications/unread-count`,
      );
      if (data && typeof data.count === 'number') {
        unreadCount.value = data.count;
      }
    } catch {
      // 静默失败
    }
  }

  async function loadNotifications(
    category?: string,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<void> {
    loading.value = true;
    try {
      const params = new URLSearchParams();
      if (category) params.set('category', category);
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const data = await requestClient.get<NotificationListResponse>(
        `${getApiPrefix()}/notifications?${params.toString()}`,
      );
      if (data?.items) {
        if (page === 1) {
          // 保留本地临时通知（负 ID = 实时推送的未持久化通知）
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
  // 本地通知
  // ============================================================

  /** 添加本地临时通知（不走后端，持久化到 localStorage） */
  function addLocalNotification(item: Omit<NotificationItem, 'id' | 'is_read' | 'created_at'>) {
    const notif: NotificationItem = {
      ...item,
      id: -Date.now(),
      is_read: false,
      created_at: new Date().toISOString(),
    };
    notifications.value.unshift(notif);
    unreadCount.value++;
    _saveLocalNotifications(notifications.value);
  }

  // ============================================================
  // 操作
  // ============================================================

  async function markRead(id: number): Promise<void> {
    const item = notifications.value.find((n) => n.id === id);
    if (item) {
      item.is_read = true;
    }
    if (unreadCount.value > 0) {
      unreadCount.value--;
    }
    // 本地临时通知（负 ID）不调用后端 API
    if (id < 0) {
      _saveLocalNotifications(notifications.value);
      return;
    }
    try {
      await requestClient.put(`${getApiPrefix()}/notifications/${id}/read`);
    } catch {
      // 静默
    }
  }

  async function markAllRead(category?: string): Promise<void> {
    try {
      const params = category ? `?category=${category}` : '';
      await requestClient.put(`${getApiPrefix()}/notifications/read-all${params}`);
      for (const n of notifications.value) {
        if (!category || n.category === category) {
          n.is_read = true;
        }
      }
      unreadCount.value = 0;
    } catch {
      // 静默
    }
  }

  async function deleteNotification(id: number): Promise<void> {
    const idx = notifications.value.findIndex((n) => n.id === id);
    if (idx !== -1) {
      const removed = notifications.value[idx];
      notifications.value.splice(idx, 1);
      if (!removed?.is_read && unreadCount.value > 0) {
        unreadCount.value--;
      }
    }
    // 本地临时通知（负 ID）不调用后端 API
    if (id < 0) {
      _saveLocalNotifications(notifications.value);
      return;
    }
    try {
      await requestClient.delete(`${getApiPrefix()}/notifications/${id}`);
    } catch {
      // 静默
    }
  }

  // ============================================================
  // Socket.IO 实时推送
  // ============================================================

  function initSocketHandlers(): void {
    if (initialized.value) return;
    initialized.value = true;

    const sioStore = useSocketIOStore();

    sioStore.registerHandler('notification', (raw: unknown) => {
      const data = raw as NotificationPushData;

      // 增加未读计数
      unreadCount.value++;

      // 添加到列表顶部（临时 ID，刷新后会更新）
      notifications.value.unshift({
        id: -Date.now(),
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
      // 高优先级通知弹窗处理由 layout 层负责
    });
  }

  // ============================================================
  // 重置
  // ============================================================

  function $reset() {
    notifications.value = [];
    unreadCount.value = 0;
    loading.value = false;
    initialized.value = false;
    localStorage.removeItem(LOCAL_NOTIF_KEY);
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

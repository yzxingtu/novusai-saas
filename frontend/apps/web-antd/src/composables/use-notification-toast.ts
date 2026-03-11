/**
 * Notification toast manager
 * 通知 Toast 弹窗管理器
 *
 * Manages toast notification queue, stacking, and auto-dismiss in bottom-right corner.
 * Triggered by Socket.IO notification events, respects user preferences.
 * 管理右下角 toast 通知的队列、堆叠、自动消失。由 Socket.IO 通知事件触发。
 */
import { ref } from 'vue';

export type NotificationPriority = 'high' | 'low' | 'normal' | 'urgent';

export interface ToastItem {
  id: number;
  template_code?: null | string;
  category: string;
  title: string;
  body?: null | string;
  data?: null | Record<string, unknown>;
  link?: null | string;
  priority: NotificationPriority;
  createdAt: number;
}

const MAX_VISIBLE = 3;
const toasts = ref<ToastItem[]>([]);
const queue: ToastItem[] = [];
const timers = new Map<number, ReturnType<typeof setTimeout>>();
let idCounter = 0;

function getAutoCloseMs(priority: string): number {
  switch (priority) {
    case 'high': {
      return 8000;
    }
    case 'urgent': {
      return 0;
    }
    default: {
      return 5000;
    }
  }
}

function removeToast(id: number) {
  const timer = timers.get(id);
  if (timer) {
    clearTimeout(timer);
    timers.delete(id);
  }
  toasts.value = toasts.value.filter((t) => t.id !== id);
  // Pop next item from queue / 从队列中弹出下一条
  if (queue.length > 0 && toasts.value.length < MAX_VISIBLE) {
    const next = queue.shift();
    if (!next) return;
    toasts.value.push(next);
    scheduleAutoClose(next);
  }
}

function scheduleAutoClose(item: ToastItem) {
  const ms = getAutoCloseMs(item.priority);
  if (ms > 0) {
    const timer = setTimeout(() => {
      timers.delete(item.id);
      removeToast(item.id);
    }, ms);
    timers.set(item.id, timer);
  }
}

function pushToast(data: {
  body?: null | string;
  category: string;
  data?: null | Record<string, unknown>;
  link?: null | string;
  priority?: NotificationPriority | string;
  template_code?: null | string;
  title: string;
}) {
  const item: ToastItem = {
    id: ++idCounter,
    template_code: data.template_code,
    category: data.category,
    title: data.title,
    body: data.body,
    data: data.data,
    link: data.link,
    priority: (data.priority || 'normal') as NotificationPriority,
    createdAt: Date.now(),
  };

  if (toasts.value.length >= MAX_VISIBLE) {
    queue.push(item);
  } else {
    toasts.value.push(item);
    scheduleAutoClose(item);
  }
}

function clearAll() {
  for (const timer of timers.values()) {
    clearTimeout(timer);
  }
  timers.clear();
  toasts.value = [];
  queue.length = 0;
}

export function useNotificationToast() {
  return {
    toasts,
    pushToast,
    removeToast,
    clearAll,
  };
}

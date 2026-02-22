/**
 * 通知 Toast 弹窗管理器
 *
 * 管理右下角 toast 通知的队列、堆叠、自动消失。
 * 由 Socket.IO 通知事件触发，尊重用户偏好。
 */
import { ref } from 'vue';

export interface ToastItem {
  id: number;
  category: string;
  title: string;
  body?: string | null;
  link?: string | null;
  priority: string;
  createdAt: number;
}

const MAX_VISIBLE = 3;
const toasts = ref<ToastItem[]>([]);
const queue: ToastItem[] = [];
let idCounter = 0;

function getAutoCloseMs(priority: string): number {
  switch (priority) {
    case 'urgent': return 0;
    case 'high': return 8000;
    default: return 5000;
  }
}

function removeToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
  // 从队列中弹出下一条
  if (queue.length > 0 && toasts.value.length < MAX_VISIBLE) {
    const next = queue.shift()!;
    toasts.value.push(next);
    scheduleAutoClose(next);
  }
}

function scheduleAutoClose(item: ToastItem) {
  const ms = getAutoCloseMs(item.priority);
  if (ms > 0) {
    setTimeout(() => removeToast(item.id), ms);
  }
}

function pushToast(data: {
  category: string;
  title: string;
  body?: string | null;
  link?: string | null;
  priority: string;
}) {
  const item: ToastItem = {
    id: ++idCounter,
    category: data.category,
    title: data.title,
    body: data.body,
    link: data.link,
    priority: data.priority || 'normal',
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

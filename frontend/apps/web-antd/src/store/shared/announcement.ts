import type {
  AnnouncementAnswers,
  AnnouncementModalItem,
} from '#/types/announcement';

import { computed, ref } from 'vue';

import { defineStore } from 'pinia';

import {
  getMyAnnouncementApi as getAdminMyAnnouncementApi,
  getPendingAnnouncementsApi as getAdminPendingAnnouncementsApi,
  markAnnouncementReadApi as markAdminAnnouncementReadApi,
  submitAnnouncementResponseApi as submitAdminAnnouncementResponseApi,
} from '#/api/admin/announcement';
import {
  getMyAnnouncementApi as getTenantMyAnnouncementApi,
  getPendingAnnouncementsApi as getTenantPendingAnnouncementsApi,
  markAnnouncementReadApi as markTenantAnnouncementReadApi,
  submitAnnouncementResponseApi as submitTenantAnnouncementResponseApi,
} from '#/api/tenant/announcement';

import { useNotificationStore } from './notification';
import { useSocketIOStore } from './socketio';

type AnnouncementEndpoint = 'admin' | 'tenant';
interface AnnouncementNotificationPush {
  category?: string;
}

function sortPendingAnnouncements(
  items: AnnouncementModalItem[],
): AnnouncementModalItem[] {
  return items.toSorted((left, right) => {
    const leftTime = left.publishedAt
      ? new Date(left.publishedAt).getTime()
      : Number.MAX_SAFE_INTEGER;
    const rightTime = right.publishedAt
      ? new Date(right.publishedAt).getTime()
      : Number.MAX_SAFE_INTEGER;
    if (leftTime !== rightTime) {
      return leftTime - rightTime;
    }
    return left.id - right.id;
  });
}

export const useAnnouncementStore = defineStore('announcement', () => {
  const endpoint = ref<AnnouncementEndpoint>('tenant');
  const pendingQueue = ref<AnnouncementModalItem[]>([]);
  const loading = ref(false);
  const submitting = ref(false);
  const initialized = ref(false);
  let pendingLoadEndpoint: AnnouncementEndpoint | null = null;
  let pendingLoadPromise: null | Promise<void> = null;
  let pendingLoadToken: null | symbol = null;

  const current = computed(() => pendingQueue.value[0] ?? null);
  const visible = computed(() => Boolean(current.value));
  const pendingCount = computed(() => pendingQueue.value.length);

  const handleSocketAnnouncement = (raw: unknown) => {
    const data = raw as AnnouncementNotificationPush;
    if (data?.category === 'announcement') {
      void loadPending();
    }
  };

  function setEndpoint(value: AnnouncementEndpoint) {
    endpoint.value = value;
  }

  async function loadPending(): Promise<void> {
    const loadEndpoint = endpoint.value;
    if (pendingLoadPromise && pendingLoadEndpoint === loadEndpoint) {
      return pendingLoadPromise;
    }
    loading.value = true;
    pendingLoadEndpoint = loadEndpoint;
    const loadToken = Symbol('announcement-pending-load');
    pendingLoadToken = loadToken;
    const activePromise = (async () => {
      try {
        const loader =
          loadEndpoint === 'admin'
            ? getAdminPendingAnnouncementsApi
            : getTenantPendingAnnouncementsApi;
        const rows = sortPendingAnnouncements(await loader());
        if (endpoint.value === loadEndpoint) {
          pendingQueue.value = rows;
        }
      } catch {
        if (endpoint.value === loadEndpoint) {
          pendingQueue.value = [];
        }
      } finally {
        if (pendingLoadToken === loadToken) {
          pendingLoadPromise = null;
          pendingLoadEndpoint = null;
          pendingLoadToken = null;
          loading.value = false;
        }
      }
    })();
    pendingLoadPromise = activePromise;
    return activePromise;
  }

  async function openAnnouncement(id: number): Promise<void> {
    if (!Number.isFinite(id) || id <= 0) {
      await loadPending();
      return;
    }

    loading.value = true;
    try {
      const loader =
        endpoint.value === 'admin'
          ? getAdminMyAnnouncementApi
          : getTenantMyAnnouncementApi;
      const item = await loader(id);
      pendingQueue.value = [
        item,
        ...pendingQueue.value.filter(
          (candidate) => candidate.deliveryId !== item.deliveryId,
        ),
      ];
    } finally {
      loading.value = false;
    }
  }

  async function submitCurrent(answers: AnnouncementAnswers): Promise<void> {
    const item = current.value;
    if (!item || item.deliveryStatus !== 'pending') {
      return;
    }

    submitting.value = true;
    try {
      const submitter =
        endpoint.value === 'admin'
          ? submitAdminAnnouncementResponseApi
          : submitTenantAnnouncementResponseApi;
      await submitter(item.id, answers);
      pendingQueue.value = pendingQueue.value.filter(
        (candidate) => candidate.deliveryId !== item.deliveryId,
      );
      await useNotificationStore().loadUnreadCount();
    } finally {
      submitting.value = false;
    }
  }

  async function markCurrentRead(): Promise<void> {
    const item = current.value;
    if (!item || item.requireResponse) {
      return;
    }
    if (item.deliveryStatus !== 'pending') {
      dismissCurrent();
      return;
    }

    submitting.value = true;
    try {
      const marker =
        endpoint.value === 'admin'
          ? markAdminAnnouncementReadApi
          : markTenantAnnouncementReadApi;
      await marker(item.id);
      pendingQueue.value = pendingQueue.value.filter(
        (candidate) => candidate.deliveryId !== item.deliveryId,
      );
      await useNotificationStore().loadUnreadCount();
    } finally {
      submitting.value = false;
    }
  }

  function dismissCurrent(): void {
    const item = current.value;
    if (!item) {
      return;
    }
    pendingQueue.value = pendingQueue.value.filter(
      (candidate) => candidate.deliveryId !== item.deliveryId,
    );
  }

  function initSocketHandlers(): void {
    if (initialized.value) return;
    initialized.value = true;
    const socketIOStore = useSocketIOStore();
    socketIOStore.unregisterHandler('notification', handleSocketAnnouncement);
    socketIOStore.registerHandler('notification', handleSocketAnnouncement);
  }

  function $reset() {
    try {
      useSocketIOStore().unregisterHandler(
        'notification',
        handleSocketAnnouncement,
      );
    } catch {
      // Silent reset cleanup / 静默清理
    }
    pendingQueue.value = [];
    loading.value = false;
    submitting.value = false;
    initialized.value = false;
    pendingLoadEndpoint = null;
    pendingLoadPromise = null;
    pendingLoadToken = null;
    endpoint.value = 'tenant';
  }

  return {
    $reset,
    current,
    endpoint,
    initSocketHandlers,
    dismissCurrent,
    loadPending,
    loading,
    markCurrentRead,
    openAnnouncement,
    pendingCount,
    pendingQueue,
    setEndpoint,
    submitCurrent,
    submitting,
    visible,
  };
});

export type { AnnouncementEndpoint };

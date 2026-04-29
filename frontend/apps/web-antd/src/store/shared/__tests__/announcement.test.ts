// Test type: behavioral
// Scope: Pending announcement queue ordering and submit progression.
// Mock strategy: API modules and notification unread refresh transport are mocked; Pinia store logic runs real.
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAnnouncementStore, useNotificationStore } from '#/store';

const {
  adminPendingMock,
  adminReadMock,
  adminSubmitMock,
  adminMineMock,
  requestGetMock,
  tenantMineMock,
  tenantPendingMock,
  tenantReadMock,
  tenantSubmitMock,
} = vi.hoisted(() => ({
  adminMineMock: vi.fn(),
  adminPendingMock: vi.fn(),
  adminReadMock: vi.fn(),
  adminSubmitMock: vi.fn(),
  requestGetMock: vi.fn(),
  tenantMineMock: vi.fn(),
  tenantPendingMock: vi.fn(),
  tenantReadMock: vi.fn(),
  tenantSubmitMock: vi.fn(),
}));

vi.mock('#/api/admin/announcement', () => ({
  getMyAnnouncementApi: adminMineMock,
  getPendingAnnouncementsApi: adminPendingMock,
  markAnnouncementReadApi: adminReadMock,
  submitAnnouncementResponseApi: adminSubmitMock,
}));

vi.mock('#/api/tenant/announcement', () => ({
  getMyAnnouncementApi: tenantMineMock,
  getPendingAnnouncementsApi: tenantPendingMock,
  markAnnouncementReadApi: tenantReadMock,
  submitAnnouncementResponseApi: tenantSubmitMock,
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGetMock,
  },
}));

function pending(id: number, publishedAt: string) {
  return {
    id,
    deliveryId: id + 100,
    tenantId: 0,
    scope: 'admin',
    title: `Notice ${id}`,
    content: '',
    status: 'published',
    deliveryStatus: 'pending',
    priority: 'normal',
    requireResponse: true,
    formSchema: [],
    publishedAt,
    recipientCount: 1,
    responseCount: 0,
    sortOrder: 0,
    createdAt: publishedAt,
    updatedAt: publishedAt,
  };
}

function optionalPending(id: number, publishedAt: string) {
  return {
    ...pending(id, publishedAt),
    requireResponse: false,
  };
}

describe('useAnnouncementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    window.history.pushState({}, '', '/admin/system/announcements');
    adminMineMock.mockReset();
    adminPendingMock.mockReset();
    adminReadMock.mockReset();
    adminSubmitMock.mockReset();
    tenantMineMock.mockReset();
    tenantPendingMock.mockReset();
    tenantReadMock.mockReset();
    tenantSubmitMock.mockReset();
    requestGetMock.mockReset();
    requestGetMock.mockResolvedValue({ count: 0 });
  });

  it('loads pending admin announcements from old to new', async () => {
    adminPendingMock.mockResolvedValue([
      pending(2, '2026-04-28T17:00:00Z'),
      pending(1, '2026-04-28T16:00:00Z'),
    ]);

    const store = useAnnouncementStore();
    store.setEndpoint('admin');
    await store.loadPending();

    expect(adminPendingMock).toHaveBeenCalledOnce();
    expect(store.pendingQueue.map((item) => item.id)).toEqual([1, 2]);
    expect(store.current?.id).toBe(1);
    expect(store.visible).toBe(true);
  });

  it('submits current tenant announcement and advances the queue', async () => {
    window.history.pushState({}, '', '/tenant/system/announcements');
    tenantPendingMock.mockResolvedValue([
      pending(10, '2026-04-28T16:00:00Z'),
      pending(11, '2026-04-28T17:00:00Z'),
    ]);
    tenantSubmitMock.mockResolvedValue({ status: 'submitted' });

    const notificationStore = useNotificationStore();
    notificationStore.setEndpoint('tenant');

    const store = useAnnouncementStore();
    store.setEndpoint('tenant');
    await store.loadPending();
    await store.submitCurrent({ agree: true });

    expect(tenantSubmitMock).toHaveBeenCalledWith(10, { agree: true });
    expect(store.pendingQueue.map((item) => item.id)).toEqual([11]);
    expect(requestGetMock).toHaveBeenCalledWith(
      '/tenant/notifications/unread-count',
    );
  });

  it('marks optional announcements read and advances the global modal queue', async () => {
    adminPendingMock.mockResolvedValue([
      optionalPending(20, '2026-04-28T16:00:00Z'),
      pending(21, '2026-04-28T17:00:00Z'),
    ]);
    adminReadMock.mockResolvedValue({ status: 'read' });

    const notificationStore = useNotificationStore();
    notificationStore.setEndpoint('admin');

    const store = useAnnouncementStore();
    store.setEndpoint('admin');
    await store.loadPending();
    await store.markCurrentRead();

    expect(adminReadMock).toHaveBeenCalledWith(20);
    expect(store.pendingQueue.map((item) => item.id)).toEqual([21]);
    expect(requestGetMock).toHaveBeenCalledWith(
      '/admin/notifications/unread-count',
    );
  });

  it('opens a submitted announcement from notification as read-only modal content', async () => {
    const submitted = {
      ...pending(30, '2026-04-28T16:00:00Z'),
      answers: { agree: true },
      deliveryStatus: 'submitted',
      notificationId: 900,
      submittedAt: '2026-04-28T17:00:00Z',
    };
    adminMineMock.mockResolvedValue(submitted);

    const store = useAnnouncementStore();
    store.setEndpoint('admin');
    await store.openAnnouncement(30);

    expect(adminMineMock).toHaveBeenCalledWith(30);
    expect(store.current).toMatchObject({
      id: 30,
      deliveryStatus: 'submitted',
      answers: { agree: true },
    });

    await store.submitCurrent({ agree: true });

    expect(adminSubmitMock).not.toHaveBeenCalled();
    expect(store.pendingQueue).toHaveLength(1);

    store.dismissCurrent();

    expect(store.visible).toBe(false);
  });
});

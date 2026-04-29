// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
// Test type: behavioral
// Scope: Bell notification click behavior for announcements.
// Mock strategy: Stores are mocked; the real NotificationPanel click wiring is mounted.
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationPanel from '../NotificationPanel.vue';

const stores = vi.hoisted(() => ({
  announcementStore: {
    loadPending: vi.fn(),
    openAnnouncement: vi.fn(),
  },
  notificationStore: {
    deleteNotification: vi.fn(),
    initSocketHandlers: vi.fn(),
    loadNotifications: vi.fn(),
    loading: false,
    markAllRead: vi.fn(),
    markRead: vi.fn(),
    notifications: [] as Array<Record<string, unknown>>,
  },
}));

vi.mock('#/store', () => ({
  useAnnouncementStore: () => stores.announcementStore,
  useNotificationStore: () => stores.notificationStore,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  formatRelativeTime: (value: string) => value,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('#/components/business/plugin-slots/PluginNotificationUI.vue', () => ({
  default: defineComponent({
    name: 'PluginNotificationUIStub',
    template: '<span />',
  }),
}));

vi.mock('../NotificationSettings.vue', () => ({
  default: defineComponent({
    name: 'NotificationSettingsStub',
    setup(_props, { expose }) {
      expose({ open: vi.fn() });
      return () => h('div', { class: 'notification-settings-stub' });
    },
  }),
}));

vi.mock('ant-design-vue', () => {
  const Tabs = Object.assign(
    defineComponent({
      name: 'TabsStub',
      props: {
        activeKey: {
          default: '',
          type: String,
        },
      },
      emits: ['update:activeKey'],
      setup(_props, { slots }) {
        return () => h('div', { class: 'tabs-stub' }, slots.default?.());
      },
    }),
    {
      TabPane: defineComponent({
        name: 'TabPaneStub',
        setup(_props, { slots }) {
          return () => h('div', { class: 'tab-pane-stub' }, slots.default?.());
        },
      }),
    },
  );

  return {
    Badge: defineComponent({
      name: 'BadgeStub',
      template: '<span class="badge-stub" />',
    }),
    Button: defineComponent({
      name: 'ButtonStub',
      emits: ['click'],
      template: '<button @click="$emit(\'click\')"><slot /></button>',
    }),
    Empty: defineComponent({
      name: 'EmptyStub',
      template: '<div class="empty-stub" />',
    }),
    Spin: defineComponent({
      name: 'SpinStub',
      template: '<div><slot /></div>',
    }),
    Tabs,
  };
});

describe('notificationPanel announcement click', () => {
  beforeEach(() => {
    stores.announcementStore.loadPending.mockReset();
    stores.announcementStore.openAnnouncement.mockReset();
    stores.notificationStore.deleteNotification.mockReset();
    stores.notificationStore.initSocketHandlers.mockReset();
    stores.notificationStore.loadNotifications.mockReset();
    stores.notificationStore.markAllRead.mockReset();
    stores.notificationStore.markRead.mockReset();
    stores.notificationStore.notifications = [
      {
        id: 61,
        body: 'Body',
        category: 'announcement',
        created_at: '2026-04-28T16:56:00Z',
        data: { announcement_id: 1 },
        is_read: false,
        link: '/admin/system/announcements?announcement_id=1',
        priority: 'normal',
        title: 'Notice',
      },
    ];
  });

  it('opens the global announcement modal instead of marking read or navigating', async () => {
    window.history.pushState({}, '', '/admin/system/announcements');

    const wrapper = mount(NotificationPanel);
    await flushPromises();

    await wrapper.get('[data-testid="notification-row"]').trigger('click');

    expect(stores.announcementStore.openAnnouncement).toHaveBeenCalledWith(1);
    expect(stores.notificationStore.markRead).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe('/admin/system/announcements');
  });
});

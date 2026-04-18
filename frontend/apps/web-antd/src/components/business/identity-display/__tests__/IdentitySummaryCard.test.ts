// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import IdentitySummaryCard from '../IdentitySummaryCard.vue';

const presenceMocks = vi.hoisted(() => ({
  ensurePresenceLoaded: vi.fn(),
  isOnline: vi.fn(),
}));

vi.mock('#/store', () => ({
  usePresenceStore: () => ({
    ensurePresenceLoaded: presenceMocks.ensurePresenceLoaded,
    isOnline: presenceMocks.isOnline,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value?: null | string) => value || 'shared.identity.field.empty',
  formatRelativeTime: (value?: null | string) =>
    value ? `relative:${value}` : '',
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => `avatar:${value}`,
}));

vi.mock('ant-design-vue', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    Avatar: defineComponent({
      name: 'AvatarStub',
      props: {
        size: {
          default: 40,
          type: Number,
        },
        src: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'div',
            {
              'data-size': String(props.size),
              'data-src': props.src,
              'data-testid': 'avatar',
            },
            slots.default?.(),
          );
      },
    }),
    Tag: defineComponent({
      name: 'TagStub',
      props: {
        color: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'span',
            {
              'data-color': props.color,
              'data-testid': 'tag',
            },
            slots.default?.(),
          );
      },
    }),
  };
});

vi.mock('@vben/icons', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    IconifyIcon: defineComponent({
      name: 'IconifyIconStub',
      props: {
        icon: {
          default: '',
          type: String,
        },
      },
      setup(props) {
        return () =>
          h('span', {
            'data-icon': props.icon,
            'data-testid': 'icon',
          });
      },
    }),
  };
});

describe('identitySummaryCard presence indicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    presenceMocks.ensurePresenceLoaded.mockResolvedValue(true);
    presenceMocks.isOnline.mockReturnValue(false);
  });

  it('shows a green online indicator for supported online identities', async () => {
    presenceMocks.isOnline.mockReturnValue(true);

    const wrapper = mount(IdentitySummaryCard, {
      props: {
        detailRequest: {
          id: 7,
          scope: 'tenant',
          subjectType: 'tenant_user',
        },
        model: {
          id: 7,
          nickname: '采购员',
          userType: 'tenant_user',
          username: 'tenant.buyer',
        },
        showOnlineStatus: true,
      },
    });

    await flushPromises();

    expect(presenceMocks.ensurePresenceLoaded).toHaveBeenCalledWith(
      'tenant_user',
      'tenant',
      undefined,
    );
    expect(presenceMocks.isOnline).toHaveBeenCalledWith(
      'tenant_user',
      7,
      undefined,
    );
    expect(
      wrapper.get('[data-testid="presence-indicator"]').classes(),
    ).toContain('bg-green-500');
  });

  it('shows a gray offline indicator for supported offline identities', async () => {
    const wrapper = mount(IdentitySummaryCard, {
      props: {
        detailRequest: {
          id: 11,
          scope: 'admin',
          subjectType: 'tenant_admin',
          tenantId: 23,
        },
        model: {
          id: 11,
          nickname: '企业管理员',
          tenantId: 23,
          userType: 'tenant_admin',
          username: 'tenant.admin',
        },
        showOnlineStatus: true,
      },
    });

    await flushPromises();

    expect(presenceMocks.ensurePresenceLoaded).toHaveBeenCalledWith(
      'tenant_admin',
      'admin',
      23,
    );
    expect(
      wrapper.get('[data-testid="presence-indicator"]').classes(),
    ).toContain('bg-muted-foreground/30');
  });

  it('supports admin tenant-user identities when tenantId is provided', async () => {
    const wrapper = mount(IdentitySummaryCard, {
      props: {
        detailRequest: {
          id: 19,
          scope: 'admin',
          subjectType: 'tenant_user',
          tenantId: 9,
        },
        model: {
          id: 19,
          nickname: '企业用户',
          tenantId: 9,
          userType: 'tenant_user',
          username: 'tenant.user',
        },
        showOnlineStatus: true,
      },
    });

    await flushPromises();

    expect(presenceMocks.ensurePresenceLoaded).toHaveBeenCalledWith(
      'tenant_user',
      'admin',
      9,
    );
    expect(wrapper.find('[data-testid="presence-indicator"]').exists()).toBe(
      true,
    );
  });

  it('hides the indicator when admin tenant-user identities do not include tenantId', async () => {
    const wrapper = mount(IdentitySummaryCard, {
      props: {
        detailRequest: {
          id: 20,
          scope: 'admin',
          subjectType: 'tenant_user',
        },
        model: {
          id: 20,
          nickname: '企业用户',
          userType: 'tenant_user',
          username: 'tenant.user',
        },
        showOnlineStatus: true,
      },
    });

    await flushPromises();

    expect(presenceMocks.ensurePresenceLoaded).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="presence-indicator"]').exists()).toBe(
      false,
    );
  });
});

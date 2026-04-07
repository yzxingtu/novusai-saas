// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import IdentityQuickCard from '../IdentityQuickCard.vue';

const dialogMocks = vi.hoisted(() => ({
  openIdentityDetailDialog: vi.fn(),
}));

const presenceMocks = vi.hoisted(() => ({
  ensurePresenceLoaded: vi.fn(),
  isOnline: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  usePresenceStore: () => ({
    ensurePresenceLoaded: presenceMocks.ensurePresenceLoaded,
    isOnline: presenceMocks.isOnline,
  }),
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value?: null | string) => value || 'shared.identity.field.empty',
  formatRelativeTime: (value?: null | string) =>
    value ? `relative:${value}` : '',
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => `avatar:${value}`,
}));

vi.mock('../use-identity-detail-dialog', () => ({
  openIdentityDetailDialog: dialogMocks.openIdentityDetailDialog,
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
    Button: defineComponent({
      name: 'ButtonStub',
      emits: ['click'],
      setup(_, { attrs, emit, slots }) {
        return () =>
          h(
            'button',
            {
              ...attrs,
              'data-testid': 'button',
              type: 'button',
              onClick: (event: MouseEvent) => emit('click', event),
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

describe('IdentityQuickCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    presenceMocks.ensurePresenceLoaded.mockResolvedValue(true);
    presenceMocks.isOnline.mockReturnValue(false);
  });

  it('renders read-only status chips and fallback preview fields', () => {
    const wrapper = mount(IdentityQuickCard, {
      props: {
        detailRequest: {
          fallback: {
            email: 'buyer@example.com',
            tenantName: 'Nova Tenant',
            username: 'tenant.buyer',
          },
          id: 7,
          scope: 'tenant',
          subjectType: 'tenant_user',
        },
        model: {
          id: 7,
          isActive: false,
          nickname: '采购员',
          roleName: '采购专员',
          userType: 'tenant_user',
          username: 'tenant.buyer',
        },
      },
    });

    expect(wrapper.text()).toContain('shared.identity.userTypes.tenantUser');
    expect(wrapper.text()).toContain('shared.common.statusDisabled');
    expect(wrapper.text()).toContain('tenant.buyer');
    expect(wrapper.text()).toContain('Nova Tenant');
    expect(wrapper.text()).toContain('buyer@example.com');
    expect(
      wrapper.findComponent({ name: 'IdentitySummaryCard' }).props(
        'showOnlineStatus',
      ),
    ).toBe(true);
  });

  it('shows the detail action and opens the drawer with merged fallback data', async () => {
    dialogMocks.openIdentityDetailDialog.mockResolvedValue(undefined);

    const wrapper = mount(IdentityQuickCard, {
      props: {
        detailRequest: {
          fallback: {
            tenantName: 'Nova Tenant',
          },
          id: 8,
          scope: 'admin',
          subjectType: 'admin',
        },
        model: {
          id: 8,
          nickname: '平台管理员',
          orgNodeName: '平台管理组',
          userType: 'admin',
          username: 'platform.admin',
        },
      },
    });

    expect(wrapper.get('[data-testid="button"]').text()).toContain(
      'shared.identity.action.viewDetail',
    );

    await wrapper.get('[data-testid="button"]').trigger('click');

    expect(dialogMocks.openIdentityDetailDialog).toHaveBeenCalledWith(
      expect.objectContaining({
        fallback: expect.objectContaining({
          tenantName: 'Nova Tenant',
          username: 'platform.admin',
        }),
        id: 8,
        scope: 'admin',
      }),
    );
  });
});

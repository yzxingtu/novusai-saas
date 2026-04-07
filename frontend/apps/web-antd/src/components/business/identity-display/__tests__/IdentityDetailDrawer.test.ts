// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';
import { reactive } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import IdentityDetailDrawer from '../IdentityDetailDrawer.vue';

const closeIdentityDetailDialog = vi.fn();

const presenceMocks = vi.hoisted(() => ({
  ensurePresenceLoaded: vi.fn(),
  isOnline: vi.fn(),
}));

const dialogState = reactive({
  detail: null as any,
  error: null as null | string,
  loading: false,
  open: true,
  request: null as any,
});

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
  useIdentityDetailDialog: () => ({
    closeIdentityDetailDialog,
    identityDetailDialogState: dialogState,
  }),
}));

vi.mock('ant-design-vue', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    Alert: defineComponent({
      name: 'AlertStub',
      props: {
        message: {
          default: '',
          type: String,
        },
        type: {
          default: '',
          type: String,
        },
      },
      setup(props) {
        return () =>
          h(
            'div',
            {
              'data-message': props.message,
              'data-testid': 'alert',
              'data-type': props.type,
            },
            props.message,
          );
      },
    }),
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
    Drawer: defineComponent({
      name: 'DrawerStub',
      props: {
        open: {
          default: false,
          type: Boolean,
        },
        title: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          props.open
            ? h(
                'div',
                {
                  'data-testid': 'drawer',
                  'data-title': props.title,
                },
                slots.default?.(),
              )
            : null;
      },
    }),
    Empty: defineComponent({
      name: 'EmptyStub',
      props: {
        description: {
          default: '',
          type: String,
        },
      },
      setup(props) {
        return () =>
          h(
            'div',
            {
              'data-description': props.description,
              'data-testid': 'empty',
            },
            props.description,
          );
      },
    }),
    Spin: defineComponent({
      name: 'SpinStub',
      props: {
        spinning: {
          default: false,
          type: Boolean,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'div',
            {
              'data-spinning': String(props.spinning),
              'data-testid': 'spin',
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

describe('IdentityDetailDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    presenceMocks.ensurePresenceLoaded.mockResolvedValue(true);
    presenceMocks.isOnline.mockReturnValue(false);
    closeIdentityDetailDialog.mockReset();
    dialogState.detail = null;
    dialogState.error = null;
    dialogState.loading = false;
    dialogState.open = true;
    dialogState.request = null;
  });

  it('keeps fallback content visible when detail loading previously failed', () => {
    dialogState.detail = {
      approvalStatus: 'approved',
      createdAt: '2026-04-01 08:00:00',
      displayName: '采购员',
      email: 'buyer@example.com',
      id: 7,
      isActive: false,
      isLeader: true,
      isOwner: false,
      lastLoginAt: '2026-04-05 09:00:00',
      lastLoginIp: '127.0.0.1',
      orgNodeName: '华东一区',
      roleName: '采购专员',
      tenantName: 'Nova Tenant',
      updatedAt: '2026-04-03 12:00:00',
      userType: 'tenant_user',
      username: 'tenant.buyer',
    };
    dialogState.error = 'network down';
    dialogState.request = {
      fallback: {
        tenantName: 'Nova Tenant',
      },
      id: 7,
      scope: 'tenant',
      subjectType: 'tenant_user',
    };

    const wrapper = mount(IdentityDetailDrawer);

    expect(wrapper.text()).toContain('network down');
    expect(wrapper.text()).toContain('tenant.buyer');
    expect(wrapper.text()).toContain('Nova Tenant');
    expect(wrapper.find('[data-testid="alert"]').exists()).toBe(true);
    expect(
      wrapper.findComponent({ name: 'IdentitySummaryCard' }).props(
        'showOnlineStatus',
      ),
    ).toBe(true);
  });

  it('renders the three detail sections in a fixed order', () => {
    dialogState.detail = {
      createdAt: '2026-04-01 08:00:00',
      displayName: '平台管理员',
      id: 9,
      isActive: true,
      isLeader: false,
      isOwner: true,
      lastLoginAt: '2026-04-05 09:00:00',
      lastLoginIp: '127.0.0.2',
      orgNodeName: '平台管理组',
      roleName: '平台审核角色',
      updatedAt: '2026-04-03 12:00:00',
      userType: 'admin',
      username: 'platform.admin',
    };

    const wrapper = mount(IdentityDetailDrawer);

    expect(
      wrapper
        .findAll('[data-section]')
        .map((node) => node.attributes()['data-section']),
    ).toEqual(['overview', 'account', 'activity']);

    expect(wrapper.text()).toContain('shared.identity.detail.overviewSection');
    expect(wrapper.text()).toContain('shared.identity.detail.accountSection');
    expect(wrapper.text()).toContain('shared.identity.detail.activitySection');
  });

  it('uses tenant user context rules in the overview section', () => {
    dialogState.detail = {
      createdAt: '2026-04-01 08:00:00',
      displayName: '采购员',
      id: 10,
      isActive: true,
      isLeader: false,
      isOwner: false,
      orgNodeName: '华东一区',
      roleName: '采购专员',
      updatedAt: '2026-04-03 12:00:00',
      userType: 'tenant_user',
      username: 'tenant.buyer',
    };

    const wrapper = mount(IdentityDetailDrawer);

    expect(wrapper.text()).toContain('shared.identity.field.role');
    expect(wrapper.text()).toContain('采购专员');
    expect(wrapper.text()).toContain('shared.identity.field.organization');
    expect(wrapper.text()).toContain('华东一区');
  });
});

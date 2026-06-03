// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import TenantAdminPanel from '../TenantAdminPanel.vue';

const mocks = vi.hoisted(() => ({
  forceLogoutTenantAdminApi: vi.fn(),
  getTenantAdminsApi: vi.fn(),
  loadTenantPresence: vi.fn(),
  toggleTenantAdminStatusApi: vi.fn(),
}));

vi.mock('#/api/admin/tenant', () => ({
  forceLogoutTenantAdminApi: mocks.forceLogoutTenantAdminApi,
  getTenantAdminsApi: mocks.getTenantAdminsApi,
  toggleTenantAdminStatusApi: mocks.toggleTenantAdminStatusApi,
}));

vi.mock('../TenantAdminForm.vue', () => ({
  default: defineComponent({
    name: 'TenantAdminForm',
    template: '<div data-testid="tenant-admin-form" />',
  }),
}));

vi.mock('../TenantAdminResetPwdModal.vue', () => ({
  default: defineComponent({
    name: 'TenantAdminResetPwdModal',
    template: '<div data-testid="tenant-admin-reset-pwd-modal" />',
  }),
}));

vi.mock('#/components/business/identity-display', () => ({
  IdentityDisplay: defineComponent({
    name: 'IdentityDisplay',
    props: {
      model: {
        default: null,
        type: Object,
      },
      online: Boolean,
      showOnlineStatus: Boolean,
    },
    template:
      '<div data-testid="identity-display"><slot /><slot name="after" /></div>',
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  usePresenceStore: () => ({
    loadTenantPresence: mocks.loadTenantPresence,
    tenantPresenceMap: new Map(),
  }),
}));

vi.mock('#/utils', () => ({
  useAccess: () => ({
    hasAccessByCodes: () => true,
  }),
}));

vi.mock('#/utils/common', () => ({
  formatRelativeTime: (value?: null | string) => `relative:${value}`,
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: vi.fn(),
}));

vi.mock('#/views/_shared/identity/IdentityTrigger.vue', () => ({
  default: defineComponent({
    name: 'IdentityTrigger',
    props: {
      meta: {
        default: null,
        type: Object,
      },
      model: {
        default: null,
        type: Object,
      },
    },
    template:
      '<div data-testid="identity-trigger" :data-last-login-at="meta?.lastLoginAt || \'\'"><slot /></div>',
  }),
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    template: '<span />',
  }),
}));

vi.mock('ant-design-vue', () => {
  const passthrough = (name: string) =>
    defineComponent({
      name,
      template: '<div><slot /><slot name="icon" /></div>',
    });

  return {
    Button: passthrough('Button'),
    Empty: passthrough('Empty'),
    message: {
      success: vi.fn(),
    },
    Popconfirm: passthrough('Popconfirm'),
    Spin: passthrough('Spin'),
    Switch: passthrough('Switch'),
    Tag: passthrough('Tag'),
    Tooltip: passthrough('Tooltip'),
  };
});

describe('tenant admin panel platform activity visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.loadTenantPresence.mockResolvedValue(undefined);
    mocks.getTenantAdminsApi.mockResolvedValue([
      {
        ai_enabled: true,
        avatar: null,
        can_view_activity: true,
        created_at: '2026-05-01 00:00:00',
        email: 'alice@example.com',
        id: 9,
        is_active: true,
        is_owner: false,
        last_login_at: '2026-05-15 03:54:44',
        last_login_ip: '127.0.0.1',
        nickname: 'Alice',
        org_node_id: 3,
        org_node_name: 'Sales',
        role_id: null,
        role_name: null,
        username: 'alice',
      },
    ]);
  });

  it('shows tenant-admin list activity and passes it into identity fallback meta', async () => {
    const wrapper = mount(TenantAdminPanel, {
      global: {
        directives: {
          access: () => {},
        },
      },
      props: {
        tenantId: 5,
        tenantName: 'Tenant A',
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain(
      'admin.tenant.adminPanel.lastLogin relative:2026-05-15 03:54:44',
    );
    expect(wrapper.text()).not.toContain(
      'admin.tenant.adminPanel.lastLogin *****',
    );
    expect(
      wrapper.find('[data-testid="identity-trigger"]').attributes()[
        'data-last-login-at'
      ],
    ).toBe('2026-05-15 03:54:44');
  });
});

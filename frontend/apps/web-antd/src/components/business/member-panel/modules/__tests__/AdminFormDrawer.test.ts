// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: organization member AI switch permission controls submitted payload.
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminFormDrawer from '../AdminFormDrawer.vue';

const mocks = vi.hoisted(() => ({
  canManageAi: false,
  createMemberApi: vi.fn(),
  currentDrawerData: undefined as Record<string, unknown> | undefined,
  formValues: {} as Record<string, unknown>,
  onConfirm: undefined as undefined | (() => Promise<void> | void),
  onOpenChange: undefined as undefined | ((open: boolean) => Promise<void> | void),
  updateMemberApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils', () => ({
  useAccess: () => ({
    hasAccessByCodes: (codes: string[]) =>
      codes.includes('organization:manage_member_ai') && mocks.canManageAi,
  }),
}));

vi.mock('#/utils/image', () => ({
  toAttachmentImageUrl: (value: string) => value,
}));

vi.mock('#/api', () => ({
  adminApi: {
    createMemberApi: mocks.createMemberApi,
    smartUploadFile: vi.fn(),
    updateMemberApi: mocks.updateMemberApi,
  },
  tenantApi: {
    createTenantMemberApi: vi.fn(),
    getAllTenantPermissionRoleListApi: vi.fn().mockResolvedValue([]),
    smartUploadFile: vi.fn(),
    updateTenantMemberApi: vi.fn(),
  },
}));

vi.mock('#/adapter/form', () => {
  const FormStub = defineComponent({
    name: 'FormStub',
    template: '<form data-testid="member-form"></form>',
  });
  return {
    z: {
      string: () => ({
        min: () => ({
          refine: () => ({}),
        }),
      }),
    },
    useVbenForm: () => [
      FormStub,
      {
        getValues: vi.fn(async () => ({ ...mocks.formValues })),
        resetForm: vi.fn(async () => {
          Object.keys(mocks.formValues).forEach((key) => {
            delete mocks.formValues[key];
          });
        }),
        setState: vi.fn(),
        setValues: vi.fn((values: Record<string, unknown>) => {
          Object.assign(mocks.formValues, values);
        }),
        validate: vi.fn(async () => ({ valid: true })),
      },
    ],
  };
});

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: (options: {
    onConfirm: () => Promise<void> | void;
    onOpenChange: (open: boolean) => Promise<void> | void;
  }) => {
    mocks.onConfirm = options.onConfirm;
    mocks.onOpenChange = options.onOpenChange;
    const DrawerStub = defineComponent({
      name: 'DrawerStub',
      setup(_, { slots }) {
        return () => h('div', slots.default?.());
      },
    });
    return [
      DrawerStub,
      {
        close: vi.fn(),
        getData: vi.fn(() => mocks.currentDrawerData),
        lock: vi.fn(),
        open: vi.fn(() => mocks.onOpenChange?.(true)),
        setData: vi.fn((data: Record<string, unknown>) => {
          mocks.currentDrawerData = data;
          return {
            open: () => mocks.onOpenChange?.(true),
          };
        }),
        unlock: vi.fn(),
      },
    ];
  },
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span />',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Avatar: defineComponent({
    name: 'AvatarStub',
    template: '<div><slot /></div>',
  }),
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
  Spin: defineComponent({
    name: 'SpinStub',
    template: '<span />',
  }),
  Upload: defineComponent({
    name: 'UploadStub',
    template: '<div><slot /></div>',
  }),
}));

async function openCreateAndSubmit(canManageAi: boolean) {
  mocks.canManageAi = canManageAi;
  const wrapper = mount(AdminFormDrawer, {
    props: {
      apiPrefix: 'admin',
      nodeId: 5,
      nodeName: 'Ops',
    },
  });

  (
    wrapper.vm as typeof wrapper.vm & {
      openCreate: (options?: { lockOrgNode?: boolean }) => void;
    }
  ).openCreate({ lockOrgNode: true });
  await flushPromises();

  Object.assign(mocks.formValues, {
    ai_enabled: false,
    email: 'ops@example.com',
    is_active: true,
    nickname: 'Ops',
    org_node_id: 5,
    password: 'secret123',
    phone: null,
    username: 'ops_admin',
  });

  await mocks.onConfirm?.();
  await flushPromises();
}

describe('AdminFormDrawer AI switch permission', () => {
  beforeEach(() => {
    mocks.canManageAi = false;
    mocks.createMemberApi.mockReset();
    mocks.createMemberApi.mockResolvedValue({});
    mocks.currentDrawerData = undefined;
    mocks.onConfirm = undefined;
    mocks.onOpenChange = undefined;
    Object.keys(mocks.formValues).forEach((key) => {
      delete mocks.formValues[key];
    });
  });

  it('omits ai_enabled when current admin lacks organization:manage_member_ai', async () => {
    await openCreateAndSubmit(false);

    expect(mocks.createMemberApi).toHaveBeenCalledWith(
      5,
      {
        email: 'ops@example.com',
        is_active: true,
        nickname: 'Ops',
        org_node_id: 5,
        password: 'secret123',
        phone: null,
        username: 'ops_admin',
      },
      {
        showSuccessMessage: true,
        successMessage: 'ui.actionMessage.createSuccess',
      },
    );
  });

  it('submits ai_enabled=false when current admin has organization:manage_member_ai', async () => {
    await openCreateAndSubmit(true);

    expect(mocks.createMemberApi).toHaveBeenCalledWith(
      5,
      {
        ai_enabled: false,
        email: 'ops@example.com',
        is_active: true,
        nickname: 'Ops',
        org_node_id: 5,
        password: 'secret123',
        phone: null,
        username: 'ops_admin',
      },
      {
        showSuccessMessage: true,
        successMessage: 'ui.actionMessage.createSuccess',
      },
    );
  });
});

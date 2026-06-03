// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: tenant-admin AI switch permission controls submitted payload.
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import TenantAdminForm from '../TenantAdminForm.vue';

const mocks = vi.hoisted(() => ({
  canManageAi: false,
  createTenantAdminApi: vi.fn(),
  updateTenantAdminApi: vi.fn(),
}));

vi.mock('#/api/admin/tenant', () => ({
  createTenantAdminApi: mocks.createTenantAdminApi,
  updateTenantAdminApi: mocks.updateTenantAdminApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils', () => ({
  useAccess: () => ({
    hasAccessByCodes: (codes: string[]) =>
      codes.includes('tenant_admin:manage_ai') && mocks.canManageAi,
  }),
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: vi.fn(),
}));

vi.mock('ant-design-vue', () => {
  const Button = defineComponent({
    name: 'ButtonStub',
    emits: ['click'],
    template:
      '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  });
  const Drawer = defineComponent({
    name: 'DrawerStub',
    template: '<div><slot /><slot name="footer" /></div>',
  });
  const Form = defineComponent({
    name: 'FormStub',
    template: '<form><slot /></form>',
  });
  const FormItem = defineComponent({
    name: 'FormItemStub',
    template: '<label><slot /></label>',
  });
  const Input = defineComponent({
    name: 'InputStub',
    props: {
      disabled: Boolean,
      placeholder: {
        default: '',
        type: String,
      },
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['update:value'],
    template:
      '<input :data-placeholder="placeholder" :disabled="disabled" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  }) as any;
  Input.Password = Input;

  const Switch = defineComponent({
    name: 'SwitchStub',
    props: {
      checked: {
        default: true,
        type: Boolean,
      },
      disabled: Boolean,
    },
    emits: ['update:checked'],
    template:
      '<button data-testid="ai-switch" type="button" :disabled="disabled" @click="$emit(\'update:checked\', !checked)">{{ String(checked) }}</button>',
  });

  return {
    Button,
    Drawer,
    Form,
    FormItem,
    Input,
    message: {
      success: vi.fn(),
      warning: vi.fn(),
    },
    Switch,
  };
});

function inputByPlaceholder(wrapper: ReturnType<typeof mount>, key: string) {
  return wrapper.find(`input[data-placeholder="${key}"]`);
}

async function fillCreateForm(wrapper: ReturnType<typeof mount>) {
  await inputByPlaceholder(
    wrapper,
    'admin.tenant.adminPanel.usernamePlaceholder',
  ).setValue('ops_admin');
  await inputByPlaceholder(
    wrapper,
    'admin.tenant.adminPanel.emailPlaceholder',
  ).setValue('ops@example.com');
  await inputByPlaceholder(
    wrapper,
    'admin.tenant.adminPanel.passwordPlaceholder',
  ).setValue('secret123');
}

function findButtonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((item) => item.text() === text);
  if (!button) {
    throw new Error(`Expected button with text ${text}`);
  }
  return button;
}

describe('tenantAdminForm AI switch permission', () => {
  beforeEach(() => {
    mocks.canManageAi = false;
    mocks.createTenantAdminApi.mockReset();
    mocks.updateTenantAdminApi.mockReset();
    mocks.createTenantAdminApi.mockResolvedValue({});
    mocks.updateTenantAdminApi.mockResolvedValue({});
  });

  it('omits ai_enabled when current admin lacks tenant_admin:manage_ai', async () => {
    const wrapper = mount(TenantAdminForm);
    (
      wrapper.vm as typeof wrapper.vm & {
        open: (tenantId: number, tenantName: string) => void;
      }
    ).open(9, 'Tenant');
    await flushPromises();
    await fillCreateForm(wrapper);
    await findButtonByText(wrapper, 'shared.common.confirm').trigger('click');
    await flushPromises();

    expect(mocks.createTenantAdminApi).toHaveBeenCalledWith(9, {
      email: 'ops@example.com',
      nickname: undefined,
      password: 'secret123',
      username: 'ops_admin',
    });
  });

  it('submits ai_enabled=false when current admin has tenant_admin:manage_ai', async () => {
    mocks.canManageAi = true;
    const wrapper = mount(TenantAdminForm);
    (
      wrapper.vm as typeof wrapper.vm & {
        open: (tenantId: number, tenantName: string) => void;
      }
    ).open(9, 'Tenant');
    await flushPromises();
    await fillCreateForm(wrapper);
    await wrapper.find('[data-testid="ai-switch"]').trigger('click');
    await findButtonByText(wrapper, 'shared.common.confirm').trigger('click');
    await flushPromises();

    expect(mocks.createTenantAdminApi).toHaveBeenCalledWith(9, {
      ai_enabled: false,
      email: 'ops@example.com',
      nickname: undefined,
      password: 'secret123',
      username: 'ops_admin',
    });
  });
});

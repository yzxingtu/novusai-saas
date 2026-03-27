// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { reactive } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import MaintenancePage from '../maintenance.vue';

interface MockMaintenanceConfig {
  brand: {
    siteName: string;
  };
  maintenance: {
    enabled: boolean;
    message: string;
  };
}

interface MockPublicConfigStore {
  detectDomainType: ReturnType<typeof vi.fn<() => Promise<void>>>;
  isDomainTenantDomain: boolean | null;
  loadPlatformConfig: ReturnType<
    typeof vi.fn<() => Promise<MockMaintenanceConfig | null>>
  >;
  loadTenantConfig: ReturnType<
    typeof vi.fn<
      (options?: {
        skipDomainCheck?: boolean;
      }) => Promise<MockMaintenanceConfig | null>
    >
  >;
  platformConfig: MockMaintenanceConfig;
  resetPlatformConfig: ReturnType<typeof vi.fn>;
  resetTenantConfig: ReturnType<typeof vi.fn>;
  tenantConfig: MockMaintenanceConfig;
}

const publicConfigState = reactive<MockPublicConfigStore>({
  detectDomainType: vi.fn(async () => {}),
  isDomainTenantDomain: true,
  loadPlatformConfig: vi.fn(async () => null),
  loadTenantConfig: vi.fn(async () => null),
  platformConfig: {
    brand: { siteName: 'Platform Site' },
    maintenance: { enabled: true, message: 'Platform maintenance' },
  },
  resetPlatformConfig: vi.fn(),
  resetTenantConfig: vi.fn(),
  tenantConfig: {
    brand: { siteName: 'Tenant Site' },
    maintenance: { enabled: true, message: 'Tenant maintenance' },
  },
});

vi.mock('ant-design-vue', () => ({
  Button: {
    name: 'ButtonStub',
    template: '<button><slot /><slot name="icon" /></button>',
  },
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: {
    name: 'IconifyIconStub',
    template: '<span class="icon-stub"></span>',
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  usePublicConfigStore: () => publicConfigState,
}));

describe('maintenancePage', () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('prefers tenant maintenance copy over platform copy', () => {
    const wrapper = mount(MaintenancePage);

    expect(wrapper.text()).toContain('Tenant maintenance');
    expect(wrapper.text()).toContain('Tenant Site');
    expect(wrapper.text()).not.toContain('Platform maintenance');
  });

  it('refreshes tenant maintenance status on tenant domains', async () => {
    vi.useFakeTimers();

    publicConfigState.tenantConfig = {
      brand: { siteName: 'Tenant Site' },
      maintenance: { enabled: true, message: 'Tenant maintenance' },
    };
    publicConfigState.loadTenantConfig.mockResolvedValueOnce({
      brand: { siteName: 'Tenant Site' },
      maintenance: { enabled: false, message: 'Tenant maintenance' },
    });

    mount(MaintenancePage);

    await vi.advanceTimersByTimeAsync(30_000);

    expect(publicConfigState.resetTenantConfig).toHaveBeenCalled();
    expect(publicConfigState.loadTenantConfig).toHaveBeenCalledWith({
      skipDomainCheck: true,
    });
    expect(publicConfigState.resetPlatformConfig).not.toHaveBeenCalled();
  });
});

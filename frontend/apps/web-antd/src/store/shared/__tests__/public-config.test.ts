import type {
  PlatformPublicConfig,
  TenantPublicConfig,
} from '#/api/public/config';

import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePublicConfigStore } from '../public-config';

const {
  ensureCaptchaPluginReady,
  getPlatformPublicConfigApi,
  getTenantPublicConfigApi,
  updatePreferences,
} = vi.hoisted(() => ({
  ensureCaptchaPluginReady: vi.fn(),
  getPlatformPublicConfigApi: vi.fn(),
  getTenantPublicConfigApi: vi.fn(),
  updatePreferences: vi.fn(),
}));

vi.mock('@vben/preferences', () => ({
  updatePreferences,
}));

vi.mock('#/api/public/config', () => ({
  getPlatformPublicConfigApi,
  getTenantPublicConfigApi,
}));

vi.mock('#/utils/captcha-plugin', () => ({
  ensureCaptchaPluginReady,
  fallbackToBuiltinCaptcha: (captcha: unknown) => captcha,
}));

function createPlatformConfig(): PlatformPublicConfig {
  return {
    brand: { siteName: 'NovusAI Platform' },
    domain: { suffix: '.novus.local', verificationPrefix: '_novus' },
    login: {
      allowedMethods: ['password'],
      captcha: {
        difficulty: 'medium',
        enabled: false,
        failedThreshold: 0,
        type: 'image',
      },
    },
    maintenance: { enabled: false },
    platformDomains: ['127.0.0.1'],
    security: {
      password: {},
      session: {},
    },
  };
}

function createTenantConfig(): TenantPublicConfig {
  return {
    brand: { siteName: 'Acme Tenant' },
    domain: { suffix: '.novus.local', verificationPrefix: '_novus' },
    login: {
      allowedMethods: ['password'],
      captcha: {
        difficulty: 'medium',
        enabled: false,
        failedThreshold: 0,
        type: 'image',
      },
    },
    maintenance: { enabled: false },
    security: {
      password: {},
      session: {},
    },
    tenantCode: 'acme',
    tenantId: 1,
    tenantName: 'Acme',
  };
}

describe('usePublicConfigStore tenant config guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    ensureCaptchaPluginReady.mockResolvedValue(true);
    getPlatformPublicConfigApi.mockResolvedValue(createPlatformConfig());
    getTenantPublicConfigApi.mockResolvedValue(createTenantConfig());
    localStorage.clear();
    document.head.innerHTML = '';
    document.body.innerHTML = '';
  });

  it('skips tenant public config requests on detected platform domains', async () => {
    const store = usePublicConfigStore();
    store.isDomainDetected = true;
    store.isDomainTenantDomain = false;

    const result = await store.loadTenantConfig();

    expect(result).toBeNull();
    expect(getTenantPublicConfigApi).not.toHaveBeenCalled();
    expect(store.tenantConfigLoaded).toBe(false);
  });

  it('still allows tenant config loading when domain guard is intentionally skipped', async () => {
    const store = usePublicConfigStore();

    const result = await store.loadTenantConfig({ skipDomainCheck: true });

    expect(getTenantPublicConfigApi).toHaveBeenCalledTimes(1);
    expect(result?.tenantCode).toBe('acme');
    expect(store.tenantConfigLoaded).toBe(true);
  });
});

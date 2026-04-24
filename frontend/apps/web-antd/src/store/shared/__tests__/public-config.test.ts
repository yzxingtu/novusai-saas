// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: public-config domain detection honors platform guards and the
// dev-only e2e domain override without falling back to network probes.
import type {
  PlatformPublicConfig,
  TenantPublicConfig,
} from '#/api/public/config';

import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePublicConfigStore } from '../public-config';

const {
  defineOverridesPreferences,
  ensureCaptchaPluginReady,
  getPlatformPublicConfigApi,
  getTenantPublicConfigApi,
  updatePreferences,
} = vi.hoisted(() => ({
  defineOverridesPreferences: vi.fn((value) => value),
  ensureCaptchaPluginReady: vi.fn(),
  getPlatformPublicConfigApi: vi.fn(),
  getTenantPublicConfigApi: vi.fn(),
  updatePreferences: vi.fn(),
}));

vi.mock('@vben/preferences', () => ({
  defineOverridesPreferences,
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
    brand: {
      copyright: 'Platform Copyright',
      favicon: '/platform.ico',
      icp: 'ICP 123456',
      logo: '/platform-logo.png',
      logoDark: '/platform-logo-dark.png',
      siteDescription: 'Platform Description',
      siteName: 'NovusAI Platform',
    },
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
    brand: {
      siteDescription: 'Tenant Description',
      siteName: 'Acme Tenant',
    },
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
    window.localStorage.clear();
    window.sessionStorage.clear();
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

  it('honors the dev e2e domain override before any public-config network detection', async () => {
    window.sessionStorage.setItem('__novusai_e2e_domain_type', 'tenant');
    const store = usePublicConfigStore();

    await store.detectDomainType();

    expect(store.isDomainDetected).toBe(true);
    expect(store.isDomainTenantDomain).toBe(true);
    expect(getPlatformPublicConfigApi).not.toHaveBeenCalled();
    expect(getTenantPublicConfigApi).not.toHaveBeenCalled();
  });

  it('merges tenant brand fields with platform brand before applying preferences', async () => {
    const store = usePublicConfigStore();
    getTenantPublicConfigApi.mockResolvedValueOnce({
      ...createTenantConfig(),
      brand: {
        siteDescription: 'Tenant Description',
      },
    });

    const result = await store.loadTenantConfig({ skipDomainCheck: true });

    expect(result?.brand.siteName).toBe('NovusAI Platform');
    expect(result?.brand.logo).toBe('/platform-logo.png');
    expect(result?.brand.logoDark).toBe('/platform-logo-dark.png');
    expect(result?.brand.favicon).toBe('/platform.ico');
    expect(result?.brand.copyright).toBe('Platform Copyright');
    expect(result?.brand.icp).toBe('ICP 123456');
    expect(updatePreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        app: { name: 'NovusAI Platform' },
        copyright: expect.objectContaining({
          companyName: 'Platform Copyright',
          companySiteLink: '',
          icp: 'ICP 123456',
        }),
        logo: expect.objectContaining({
          source: '/platform-logo.png',
          sourceDark: '/platform-logo-dark.png',
        }),
      }),
    );
  });

  it('applies platform favicon and meta description to the page head', async () => {
    const store = usePublicConfigStore();

    await store.loadPlatformConfig();

    const favicon = document.querySelector(
      "link[rel~='icon']",
    ) as HTMLLinkElement | null;
    const description = document.querySelector(
      "meta[name='description']",
    ) as HTMLMetaElement | null;

    expect(favicon?.href).toContain('/platform.ico');
    expect(description?.content).toBe('Platform Description');
  });

  it('restores default branding when all public configs are reset', async () => {
    const store = usePublicConfigStore();

    await store.loadPlatformConfig();
    updatePreferences.mockClear();

    store.resetAll();

    expect(updatePreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        app: { name: import.meta.env.VITE_APP_TITLE || 'NovusAI' },
        copyright: expect.objectContaining({
          companyName: 'NovusAI',
          companySiteLink: '',
          icp: '',
        }),
        logo: expect.objectContaining({
          source: undefined,
          sourceDark: undefined,
        }),
      }),
    );
  });
});

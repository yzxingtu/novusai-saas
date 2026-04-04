import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  getAdminGlobalPreferencesApi: vi.fn(),
  getAdminMyPreferencesApi: vi.fn(),
  getTenantGlobalPreferencesApi: vi.fn(),
  resetAdminMyPreferencesApi: vi.fn(),
  resetTenantMyPreferencesApi: vi.fn(),
  syncRuntimeLocale: vi.fn(),
  updateAdminGlobalPreferencesApi: vi.fn(),
  updateAdminMyPreferencesApi: vi.fn(),
  updatePreferences: vi.fn(),
  updateTenantGlobalPreferencesApi: vi.fn(),
  updateTenantMyPreferencesApi: vi.fn(),
}));

vi.mock('@vben/preferences', () => ({
  preferences: {
    app: {
      locale: 'en-US',
    },
    theme: {},
  },
  updatePreferences: mockRefs.updatePreferences,
}));

vi.mock('#/api/admin/preferences', () => ({
  getAdminGlobalPreferencesApi: mockRefs.getAdminGlobalPreferencesApi,
  getAdminMyPreferencesApi: mockRefs.getAdminMyPreferencesApi,
  resetAdminMyPreferencesApi: mockRefs.resetAdminMyPreferencesApi,
  updateAdminGlobalPreferencesApi: mockRefs.updateAdminGlobalPreferencesApi,
  updateAdminMyPreferencesApi: mockRefs.updateAdminMyPreferencesApi,
}));

vi.mock('#/api/tenant/preferences', () => ({
  getTenantGlobalPreferencesApi: mockRefs.getTenantGlobalPreferencesApi,
  getTenantMyPreferencesApi: vi.fn(),
  resetTenantMyPreferencesApi: mockRefs.resetTenantMyPreferencesApi,
  updateTenantGlobalPreferencesApi: mockRefs.updateTenantGlobalPreferencesApi,
  updateTenantMyPreferencesApi: mockRefs.updateTenantMyPreferencesApi,
}));

vi.mock('#/locales/runtime-locale', () => ({
  syncRuntimeLocale: mockRefs.syncRuntimeLocale,
}));

describe('user preference runtime sync', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockRefs.syncRuntimeLocale.mockResolvedValue(undefined);
  });

  it('syncs runtime locale before writing mapped preferences', async () => {
    const order: string[] = [];
    mockRefs.syncRuntimeLocale.mockImplementation(async () => {
      order.push('locale');
    });
    mockRefs.updatePreferences.mockImplementation(() => {
      order.push('preferences');
    });

    const { applyPreferencesToVben } = await import('../user-preference');

    await applyPreferencesToVben({
      locale: 'zh-CN',
      theme_mode: 'dark',
    });

    expect(order).toEqual(['locale', 'preferences']);
    expect(mockRefs.updatePreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        app: { locale: 'zh-CN' },
        theme: { mode: 'dark' },
      }),
    );
  });

  it('applies non-locale preferences without runtime locale sync', async () => {
    const { applyPreferencesToVben } = await import('../user-preference');

    await applyPreferencesToVben({
      color_primary: '#1677ff',
      dynamic_title: true,
    });

    expect(mockRefs.syncRuntimeLocale).not.toHaveBeenCalled();
    expect(mockRefs.updatePreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        app: { dynamicTitle: true },
        theme: { colorPrimary: '#1677ff' },
      }),
    );
  });

  it('loads admin preferences into store state and runtime', async () => {
    const prefs = {
      locale: 'zh-CN',
      theme_mode: 'dark',
    };
    mockRefs.getAdminMyPreferencesApi.mockResolvedValue(prefs);

    const { useUserPreferenceStore } = await import('../user-preference');
    const store = useUserPreferenceStore();

    const result = await store.loadPreferences('admin');

    expect(result).toEqual(prefs);
    expect(store.preferences).toEqual(prefs);
    expect(store.loaded).toBe(true);
    expect(mockRefs.syncRuntimeLocale).toHaveBeenCalledWith('zh-CN');
    expect(mockRefs.updatePreferences).toHaveBeenCalledTimes(1);
  });

  it('merges global preference updates into effective preferences', async () => {
    const updated = {
      locale: 'zh-CN',
      theme_mode: 'dark',
    };
    mockRefs.updateAdminGlobalPreferencesApi.mockResolvedValue(updated);

    const { useUserPreferenceStore } = await import('../user-preference');
    const store = useUserPreferenceStore();
    store.preferences = {
      color_primary: '#1677ff',
      locale: 'en-US',
    };

    const result = await store.updateGlobalPreferences('admin', updated);

    expect(result).toEqual(updated);
    expect(store.preferences).toEqual({
      color_primary: '#1677ff',
      locale: 'zh-CN',
      theme_mode: 'dark',
    });
    expect(mockRefs.syncRuntimeLocale).toHaveBeenCalledWith('zh-CN');
  });

  it('reapplies runtime locale when resetting my preferences', async () => {
    const resetPrefs = {
      locale: 'en-US',
      theme_mode: 'light',
    };
    mockRefs.resetAdminMyPreferencesApi.mockResolvedValue(resetPrefs);

    const { useUserPreferenceStore } = await import('../user-preference');
    const store = useUserPreferenceStore();
    store.side = 'admin';

    const result = await store.resetMyPreferences();

    expect(result).toEqual(resetPrefs);
    expect(store.preferences).toEqual(resetPrefs);
    expect(mockRefs.syncRuntimeLocale).toHaveBeenCalledWith('en-US');
    expect(mockRefs.updatePreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        app: { locale: 'en-US' },
        theme: { mode: 'light' },
      }),
    );
  });
});

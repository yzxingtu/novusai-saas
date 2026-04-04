import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  loadLocaleMessages: vi.fn(),
  preferences: {
    app: {
      locale: 'en-US',
    },
  },
  runtimeLocale: { value: '' },
}));

vi.mock('@vben/locales', () => ({
  loadLocaleMessages: mockRefs.loadLocaleMessages,
}));

vi.mock('@vben/preferences', () => ({
  preferences: mockRefs.preferences,
}));

vi.mock('../index', () => ({
  i18n: {
    global: {
      locale: mockRefs.runtimeLocale,
    },
  },
}));

describe('runtime locale helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefs.preferences.app.locale = 'en-US';
    mockRefs.runtimeLocale.value = '';
  });

  it('prefers the active i18n locale over persisted preferences', async () => {
    mockRefs.runtimeLocale.value = 'zh-CN';

    const { resolveRuntimeLocale } = await import('../runtime-locale');

    expect(resolveRuntimeLocale()).toBe('zh-CN');
  });

  it('falls back to the persisted preference locale when runtime locale is empty', async () => {
    const { resolveRuntimeLocale } = await import('../runtime-locale');

    expect(resolveRuntimeLocale()).toBe('en-US');
  });

  it('syncs the explicit locale into the runtime message loader', async () => {
    const { syncRuntimeLocale } = await import('../runtime-locale');

    await syncRuntimeLocale('zh-CN');

    expect(mockRefs.loadLocaleMessages).toHaveBeenCalledWith('zh-CN');
  });

  it('uses the persisted preference locale when no explicit locale is provided', async () => {
    const { syncRuntimeLocale } = await import('../runtime-locale');

    await syncRuntimeLocale();

    expect(mockRefs.loadLocaleMessages).toHaveBeenCalledWith('en-US');
  });
});

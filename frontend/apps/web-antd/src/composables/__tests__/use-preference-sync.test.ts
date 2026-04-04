import { nextTick, reactive } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => {
  const vbenPreferences = {
    app: {
      locale: 'zh-CN',
    },
    theme: {
      mode: 'light',
    },
  };

  const userPreferenceStore = {
    applyServerPreferences: vi.fn(),
    globalPreviewActive: false,
    loaded: true,
    side: 'admin' as 'admin' | 'tenant',
    updateMyPreferences: vi.fn(),
  };

  let registeredHandler: null | ((payload: unknown) => void) = null;

  return {
    get registeredHandler() {
      return registeredHandler;
    },
    set registeredHandler(value: null | ((payload: unknown) => void)) {
      registeredHandler = value;
    },
    sioStore: {
      registerHandler: vi.fn((_event: string, handler: (payload: unknown) => void) => {
        registeredHandler = handler;
      }),
      unregisterHandler: vi.fn(),
    },
    userPreferenceStore,
    useDebounceFn: vi.fn((fn: () => Promise<void> | void) => fn),
    vbenPreferences,
  };
});

const vbenPreferences = reactive(mockRefs.vbenPreferences);

vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue');
  return {
    ...actual,
    onUnmounted: vi.fn(),
  };
});

vi.mock('@vben/preferences', () => ({
  preferences: vbenPreferences,
}));

vi.mock('@vueuse/core', () => ({
  useDebounceFn: mockRefs.useDebounceFn,
}));

vi.mock('#/store', () => ({
  useSocketIOStore: () => mockRefs.sioStore,
}));

vi.mock('#/store/shared/user-preference', () => ({
  getVbenSnapshot: () => ({
    locale: vbenPreferences.app.locale,
    theme_mode: vbenPreferences.theme.mode,
  }),
  mapFromVbenPreferences: (value: typeof vbenPreferences) => ({
    locale: value.app.locale,
    theme_mode: value.theme.mode,
  }),
  useUserPreferenceStore: () => mockRefs.userPreferenceStore,
}));

describe('usePreferenceSync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefs.userPreferenceStore.loaded = true;
    mockRefs.userPreferenceStore.side = 'admin';
    mockRefs.userPreferenceStore.globalPreviewActive = false;
    mockRefs.userPreferenceStore.updateMyPreferences.mockResolvedValue({});
    mockRefs.userPreferenceStore.applyServerPreferences.mockResolvedValue(
      undefined,
    );
    vbenPreferences.app.locale = 'zh-CN';
    vbenPreferences.theme.mode = 'light';
    mockRefs.registeredHandler = null;
  });

  it('does not sync cached preferences before the server snapshot is initialized', async () => {
    const { usePreferenceSync } = await import('../use-preference-sync');

    const sync = usePreferenceSync();
    vbenPreferences.app.locale = 'en-US';
    await nextTick();

    expect(mockRefs.userPreferenceStore.updateMyPreferences).not.toHaveBeenCalled();
    sync.cleanup();
  });

  it('syncs locale changes after initSnapshot establishes the server truth', async () => {
    const { usePreferenceSync } = await import('../use-preference-sync');

    const sync = usePreferenceSync();
    sync.initSnapshot();

    vbenPreferences.app.locale = 'en-US';
    await nextTick();

    expect(mockRefs.userPreferenceStore.updateMyPreferences).toHaveBeenCalledWith(
      { locale: 'en-US' },
    );
    sync.cleanup();
  });

  it('blocks sync again after skipSync until a fresh snapshot is taken', async () => {
    const { usePreferenceSync } = await import('../use-preference-sync');
    const nowSpy = vi.spyOn(Date, 'now');
    nowSpy.mockReturnValue(100);

    const sync = usePreferenceSync();
    sync.initSnapshot();
    sync.skipSync();

    vbenPreferences.app.locale = 'en-US';
    await nextTick();

    expect(mockRefs.userPreferenceStore.updateMyPreferences).not.toHaveBeenCalled();

    nowSpy.mockReturnValue(1000);
    sync.initSnapshot();
    vbenPreferences.theme.mode = 'dark';
    await nextTick();

    expect(mockRefs.userPreferenceStore.updateMyPreferences).toHaveBeenCalledWith(
      { theme_mode: 'dark' },
    );
    nowSpy.mockRestore();
    sync.cleanup();
  });

  it('applies websocket preference updates through the shared store hook', async () => {
    const { usePreferenceSync } = await import('../use-preference-sync');

    const sync = usePreferenceSync();

    await mockRefs.registeredHandler?.({
      preferences: { locale: 'en-US' },
    });

    expect(mockRefs.userPreferenceStore.applyServerPreferences).toHaveBeenCalledWith(
      { locale: 'en-US' },
    );
    sync.cleanup();
  });
});

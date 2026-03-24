// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const slotStore = {
  clearAll: vi.fn(),
  dashboardWidgets: [] as Array<Record<string, unknown>>,
  fetchSlots: vi.fn(async () => ({ pageFailures: [] })),
  floatingPanels: [] as Array<Record<string, unknown>>,
  headerWidgets: [] as Array<Record<string, unknown>>,
  notificationUI: [] as Array<Record<string, unknown>>,
  pages: [] as Array<Record<string, unknown>>,
  settingsTabs: [] as Array<Record<string, unknown>>,
};

const extensionsStore = {
  captureSnapshot: vi.fn(() => ({
    conflicts: [],
    editorCommands: [],
    editorExtensions: [],
    editorPanels: [],
  })),
  clearAll: vi.fn(),
  restoreSnapshot: vi.fn(),
  unregisterPlugin: vi.fn(),
};

const unloadPluginMock = vi.fn();

vi.mock('#/utils/plugin-loader', () => ({
  unloadPlugin: unloadPluginMock,
}));

vi.mock('#/stores/plugin-slots', () => ({
  usePluginSlotsStore: () => slotStore,
}));

vi.mock('#/stores/plugin-extensions', () => ({
  usePluginExtensionsStore: () => extensionsStore,
}));

type RouterStub = {
  addRoute: ReturnType<typeof vi.fn>;
  getRoutes: ReturnType<typeof vi.fn>;
  hasRoute: ReturnType<typeof vi.fn>;
  removeRoute: ReturnType<typeof vi.fn>;
};

const createRouterStub = (overrides: Partial<RouterStub> = {}): RouterStub => ({
  addRoute: vi.fn(),
  getRoutes: vi.fn(() => []),
  hasRoute: vi.fn(() => false),
  removeRoute: vi.fn(),
  ...overrides,
});

describe('use-plugin-frontend-init regressions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    slotStore.fetchSlots.mockReset();
    slotStore.fetchSlots.mockResolvedValue({ pageFailures: [] });
    slotStore.headerWidgets = [];
    slotStore.floatingPanels = [];
    slotStore.dashboardWidgets = [];
    slotStore.settingsTabs = [];
    slotStore.notificationUI = [];
    slotStore.pages = [
      {
        component: { name: 'DemoPluginPage' },
        name: 'demo-plugin-home',
        path: '/admin/plugins/demo-plugin',
        pluginName: 'demo-plugin',
        title: 'Demo Plugin',
      },
    ];
  });

  it('does not register plugin routes when fetchSlots fails and retries on the next call', async () => {
    slotStore.fetchSlots
      .mockRejectedValueOnce(new Error('fetch failed'))
      .mockResolvedValueOnce({ pageFailures: [] });
    const router = createRouterStub();
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    const { ensurePluginRoutes } = await import('../use-plugin-frontend-init');

    try {
      await ensurePluginRoutes(router as never, '/admin');
      expect(router.addRoute).not.toHaveBeenCalled();
      expect(router.removeRoute).not.toHaveBeenCalled();

      await ensurePluginRoutes(router as never, '/admin');
      expect(slotStore.fetchSlots).toHaveBeenCalledTimes(2);
      expect(router.addRoute).toHaveBeenCalledTimes(1);
    } finally {
      consoleError.mockRestore();
    }
  });

  it('deduplicates concurrent ensurePluginRoutes calls for the same endpoint', async () => {
    const routePresence = { value: false };
    let resolveFetch: ((value: { pageFailures: never[] }) => void) | undefined;
    slotStore.fetchSlots.mockImplementation(
      () =>
        new Promise<{ pageFailures: never[] }>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    const router = createRouterStub({
      hasRoute: vi.fn(() => routePresence.value),
    });
    router.addRoute.mockImplementation(() => {
      routePresence.value = true;
    });
    const { ensurePluginRoutes } = await import('../use-plugin-frontend-init');

    const firstCall = ensurePluginRoutes(router as never, '/admin');
    const secondCall = ensurePluginRoutes(router as never, '/admin');

    expect(slotStore.fetchSlots).toHaveBeenCalledTimes(1);
    resolveFetch?.({ pageFailures: [] });
    await Promise.all([firstCall, secondCall]);

    expect(router.addRoute).toHaveBeenCalledTimes(1);
  });

  it('unloads plugins collected from all slot buckets during reset', async () => {
    slotStore.headerWidgets = [{ pluginName: 'alpha-plugin' }];
    slotStore.dashboardWidgets = [{ pluginName: 'beta-plugin' }];
    slotStore.pages = [
      {
        component: { name: 'AlphaPluginPage' },
        name: 'alpha-plugin-home',
        path: '/admin/plugins/alpha-plugin',
        pluginName: 'alpha-plugin',
        title: 'Alpha Plugin',
      },
    ];
    const router = createRouterStub();
    const { resetPluginRoutesReady } =
      await import('../use-plugin-frontend-init');

    resetPluginRoutesReady(router as never);

    expect(unloadPluginMock).toHaveBeenCalledTimes(2);
    expect(
      unloadPluginMock.mock.calls.map(([pluginName]) => pluginName).toSorted(),
    ).toEqual(['alpha-plugin', 'beta-plugin']);
  });

  it('keeps existing plugin routes intact when refreshPluginSlots fails', async () => {
    const routePresence = { value: false };
    const router = createRouterStub({
      hasRoute: vi.fn(() => routePresence.value),
    });
    router.addRoute.mockImplementation(() => {
      routePresence.value = true;
    });
    router.removeRoute.mockImplementation(() => {
      routePresence.value = false;
    });

    const { ensurePluginRoutes, refreshPluginSlots } =
      await import('../use-plugin-frontend-init');

    await ensurePluginRoutes(router as never, '/admin');
    expect(routePresence.value).toBe(true);

    slotStore.fetchSlots.mockRejectedValueOnce(new Error('refresh failed'));
    await expect(refreshPluginSlots('/admin', router as never)).rejects.toThrow(
      'refresh failed',
    );

    expect(routePresence.value).toBe(true);
    expect(router.removeRoute).not.toHaveBeenCalled();
    expect(unloadPluginMock).not.toHaveBeenCalled();
  });
});

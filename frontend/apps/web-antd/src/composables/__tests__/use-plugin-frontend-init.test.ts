// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const slotStore = {
  clearAll: vi.fn(),
  fetchSlots: vi.fn(async () => {}),
  headerWidgets: [] as Array<Record<string, unknown>>,
  floatingPanels: [] as Array<Record<string, unknown>>,
  dashboardWidgets: [] as Array<Record<string, unknown>>,
  settingsTabs: [] as Array<Record<string, unknown>>,
  notificationUI: [] as Array<Record<string, unknown>>,
  pages: [] as Array<Record<string, unknown>>,
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
  hasRoute: vi.fn(() => false),
  removeRoute: vi.fn(),
  getRoutes: vi.fn(() => []),
  ...overrides,
});

const PLUGIN_ROUTE_NAME =
  'plugin-workflow-orchestration-workflow-orchestration-admin-templates';
const EMPTY_FETCH_RESULT = { pageFailures: [] };

describe('use-plugin-frontend-init', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    slotStore.fetchSlots.mockReset();
    slotStore.fetchSlots.mockResolvedValue(EMPTY_FETCH_RESULT);
    slotStore.headerWidgets = [];
    slotStore.floatingPanels = [];
    slotStore.dashboardWidgets = [];
    slotStore.settingsTabs = [];
    slotStore.notificationUI = [];
    slotStore.pages = [
      {
        accessCodes: ['plugin.workflow-orchestration.platform_template:list'],
        component: { name: 'WorkflowOrchestrationAdminTemplateListPage' },
        name: 'workflow-orchestration-admin-templates',
        path: '/admin/plugins/workflow-orchestration/templates',
        pluginName: 'workflow-orchestration',
        title: 'Templates',
      },
    ];
  });

  it('maps plugin page access codes into dynamic route meta', async () => {
    const addedRoutes: Array<{
      parent: string;
      route: Record<string, unknown>;
    }> = [];
    const router = {
      addRoute: vi.fn((parent: string, route: Record<string, unknown>) => {
        addedRoutes.push({ parent, route });
      }),
      hasRoute: vi.fn(() => false),
      removeRoute: vi.fn(),
      getRoutes: vi.fn(() => []),
    };

    const { ensurePluginRoutes, resetPluginRoutesReady } =
      await import('../use-plugin-frontend-init');

    resetPluginRoutesReady(router as never);
    await ensurePluginRoutes(router as never, '/admin');

    expect(slotStore.fetchSlots).toHaveBeenCalledWith('admin', {
      forceReload: false,
    });
    expect(addedRoutes).toHaveLength(1);
    expect(addedRoutes[0]?.parent).toBe('AdminRoot');
    expect(addedRoutes[0]?.route.meta).toMatchObject({
      accessCodes: ['plugin.workflow-orchestration.platform_template:list'],
      hideInMenu: true,
      title: 'Templates',
    });
  });

  it('retries fetchSlots when the first attempt fails', async () => {
    slotStore.fetchSlots
      .mockRejectedValueOnce(new Error('fetch failed'))
      .mockResolvedValueOnce(EMPTY_FETCH_RESULT);
    const router = createRouterStub();
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    const { ensurePluginRoutes } = await import('../use-plugin-frontend-init');

    try {
      await ensurePluginRoutes(router as never);
      expect(slotStore.fetchSlots).toHaveBeenCalledTimes(1);
      expect(router.addRoute).not.toHaveBeenCalled();

      await ensurePluginRoutes(router as never);
      expect(slotStore.fetchSlots).toHaveBeenCalledTimes(2);
      expect(router.addRoute).toHaveBeenCalledTimes(1);
    } finally {
      consoleError.mockRestore();
    }
  });

  it('removes conflicting placeholder routes before registering plugin routes', async () => {
    const placeholderRoute = {
      name: 'placeholder-route',
      path: '/admin/plugins/workflow-orchestration/templates',
    };
    const router = createRouterStub({
      getRoutes: vi.fn(() => [placeholderRoute]),
    });
    const { ensurePluginRoutes } = await import('../use-plugin-frontend-init');

    await ensurePluginRoutes(router as never);

    expect(router.removeRoute).toHaveBeenCalledWith('placeholder-route');
    expect(router.addRoute).toHaveBeenCalledTimes(1);
  });

  it('deduplicates concurrent route initialization for the same endpoint', async () => {
    const routePresence = { value: false };
    let resolveFetch: ((value: typeof EMPTY_FETCH_RESULT) => void) | undefined;
    slotStore.fetchSlots.mockImplementation(
      () =>
        new Promise((resolve) => {
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

    const first = ensurePluginRoutes(router as never, '/admin');
    const second = ensurePluginRoutes(router as never, '/admin');

    expect(slotStore.fetchSlots).toHaveBeenCalledTimes(1);

    resolveFetch?.(EMPTY_FETCH_RESULT);
    await Promise.all([first, second]);

    expect(router.addRoute).toHaveBeenCalledTimes(1);
  });

  it('keeps existing routes intact when refresh fails before a new snapshot is ready', async () => {
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
    slotStore.fetchSlots.mockRejectedValueOnce(new Error('refresh failed'));

    await expect(refreshPluginSlots('/admin', router as never)).rejects.toThrow(
      'refresh failed',
    );

    expect(routePresence.value).toBe(true);
    expect(router.removeRoute).not.toHaveBeenCalled();
    expect(unloadPluginMock).not.toHaveBeenCalled();
  });

  it('reset clears routes and refresh re-fetches slots', async () => {
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
    const { ensurePluginRoutes, resetPluginRoutesReady, refreshPluginSlots } =
      await import('../use-plugin-frontend-init');

    await ensurePluginRoutes(router as never);
    expect(router.addRoute).toHaveBeenCalledTimes(1);
    resetPluginRoutesReady(router as never);

    expect(router.removeRoute).toHaveBeenCalledWith(PLUGIN_ROUTE_NAME);
    expect(unloadPluginMock).toHaveBeenCalledWith('workflow-orchestration', {
      endpoint: 'admin',
    });

    await ensurePluginRoutes(router as never);

    expect(slotStore.fetchSlots).toHaveBeenCalledTimes(2);
    expect(router.addRoute).toHaveBeenCalledTimes(2);

    await refreshPluginSlots('/admin', router as never, {
      reloadAssets: true,
    });

    expect(slotStore.fetchSlots).toHaveBeenCalledTimes(3);
    expect(unloadPluginMock).toHaveBeenCalledTimes(1);
    expect(extensionsStore.clearAll).toHaveBeenCalledTimes(2);
    const removeCallsForPlugin = router.removeRoute.mock.calls.filter(
      ([name]) => name === PLUGIN_ROUTE_NAME,
    );
    expect(removeCallsForPlugin).toHaveLength(2);
    expect(router.addRoute).toHaveBeenCalledTimes(3);
  });
});

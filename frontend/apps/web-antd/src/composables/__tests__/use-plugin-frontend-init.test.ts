// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const slotStore = {
  clearAll: vi.fn(),
  fetchSlots: vi.fn(async () => {}),
  pages: [] as Array<Record<string, unknown>>,
};

const extensionsStore = {
  clearAll: vi.fn(),
};

vi.mock('#/stores/plugin-slots', () => ({
  usePluginSlotsStore: () => slotStore,
}));

vi.mock('#/stores/plugin-extensions', () => ({
  usePluginExtensionsStore: () => extensionsStore,
}));

describe('use-plugin-frontend-init', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
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
    const addedRoutes: Array<{ parent: string; route: Record<string, unknown> }> =
      [];
    const router = {
      addRoute: vi.fn((parent: string, route: Record<string, unknown>) => {
        addedRoutes.push({ parent, route });
      }),
      hasRoute: vi.fn(() => false),
      removeRoute: vi.fn(),
    };

    const {
      ensurePluginRoutes,
      resetPluginRoutesReady,
    } = await import('../use-plugin-frontend-init');

    resetPluginRoutesReady(router as never);
    await ensurePluginRoutes(router as never, '/admin');

    expect(slotStore.fetchSlots).toHaveBeenCalledWith('admin');
    expect(addedRoutes).toHaveLength(1);
    expect(addedRoutes[0]?.parent).toBe('AdminRoot');
    expect(addedRoutes[0]?.route.meta).toMatchObject({
      accessCodes: ['plugin.workflow-orchestration.platform_template:list'],
      hideInMenu: true,
      title: 'Templates',
    });
  });
});

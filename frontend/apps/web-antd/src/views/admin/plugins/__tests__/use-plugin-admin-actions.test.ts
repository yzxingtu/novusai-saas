import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePluginAdminActions } from '../use-plugin-admin-actions';

const mockRefs = vi.hoisted(() => ({
  confirm: vi.fn(),
  disablePluginApi: vi.fn(),
  enablePluginApi: vi.fn(),
  forceCleanupPluginApi: vi.fn(),
  installPluginDependenciesApi: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  progressMarkComplete: vi.fn(),
  progressMarkError: vi.fn(),
  progressReset: vi.fn(),
  progressStartOperation: vi.fn(),
  refreshPluginSchedulesApi: vi.fn(),
  repairPluginApi: vi.fn(),
  uninstallPluginDependenciesApi: vi.fn(),
  uninstallPluginApi: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: mockRefs.confirm,
  },
  message: {
    error: mockRefs.messageError,
    success: mockRefs.messageSuccess,
    warning: mockRefs.messageWarning,
  },
}));

vi.mock('#/api/admin/plugin', () => ({
  disablePluginApi: mockRefs.disablePluginApi,
  enablePluginApi: mockRefs.enablePluginApi,
  forceCleanupPluginApi: mockRefs.forceCleanupPluginApi,
  installPluginDependenciesApi: mockRefs.installPluginDependenciesApi,
  refreshPluginSchedulesApi: mockRefs.refreshPluginSchedulesApi,
  repairPluginApi: mockRefs.repairPluginApi,
  uninstallPluginDependenciesApi: mockRefs.uninstallPluginDependenciesApi,
  uninstallPluginApi: mockRefs.uninstallPluginApi,
}));

vi.mock('#/composables/use-plugin-admin-refresh', () => ({
  handleDisableError: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  usePluginInstallProgressStore: () => ({
    markComplete: mockRefs.progressMarkComplete,
    markError: mockRefs.progressMarkError,
    reset: mockRefs.progressReset,
    startOperation: mockRefs.progressStartOperation,
  }),
}));

describe('usePluginAdminActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runs the refresh schedules flow and calls afterMutation', async () => {
    const afterMutation = vi.fn();
    const actions = usePluginAdminActions({ afterMutation });
    const plugin = {
      id: 7,
      display_name: 'Demo Plugin',
      manifest: {
        extensions: {
          tasks: [{ name: 'digest' }],
        },
      },
    } as never;

    actions.onRefreshSchedules(plugin);
    const call = mockRefs.confirm.mock.calls.at(-1)?.[0];
    await call?.onOk();

    expect(mockRefs.refreshPluginSchedulesApi).toHaveBeenCalledWith(7);
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.plugin.messages.refreshSchedulesSuccess',
    );
    expect(afterMutation).toHaveBeenCalled();
  });

  it('runs enable through the withProcessing wrapper', async () => {
    const withProcessing = vi.fn(
      async (_id: number, run: () => Promise<void>) => {
        await run();
      },
    );
    const actions = usePluginAdminActions({ withProcessing });
    const plugin = {
      id: 11,
      display_name: 'Demo Plugin',
      manifest: {},
    } as never;

    actions.onEnable(plugin);
    const call = mockRefs.confirm.mock.calls.at(-1)?.[0];
    await call?.onOk();

    expect(withProcessing).toHaveBeenCalled();
    expect(mockRefs.enablePluginApi).toHaveBeenCalledWith(11, undefined);
    expect(mockRefs.progressStartOperation).toHaveBeenCalledWith(
      'Demo Plugin',
      'enable',
    );
  });

  it('shows warning instead of uninstalling dependencies for enabled plugins', () => {
    const actions = usePluginAdminActions();
    const plugin = {
      id: 5,
      display_name: 'Demo Plugin',
      status: 'enabled',
      manifest: {},
    } as never;

    actions.onUninstallDependencies(plugin);

    expect(mockRefs.confirm).not.toHaveBeenCalled();
    expect(mockRefs.messageWarning).toHaveBeenCalledWith(
      'admin.plugin.messages.disableBeforeUninstallDeps',
    );
  });

  it('runs install dependencies and force cleanup through confirmations', async () => {
    const afterMutation = vi.fn();
    const afterUninstall = vi.fn();
    const actions = usePluginAdminActions({ afterMutation, afterUninstall });
    const plugin = {
      id: 13,
      display_name: 'Demo Plugin',
      status: 'disabled',
      manifest: {},
    } as never;

    actions.onInstallDependencies(plugin);
    await mockRefs.confirm.mock.calls.at(-1)?.[0]?.onOk();
    expect(mockRefs.installPluginDependenciesApi).toHaveBeenCalledWith(13, {
      python: true,
    });
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.plugin.messages.installDepsSuccess',
    );
    expect(afterMutation).toHaveBeenCalled();

    actions.onForceCleanup(plugin);
    await mockRefs.confirm.mock.calls.at(-1)?.[0]?.onOk();
    expect(mockRefs.forceCleanupPluginApi).toHaveBeenCalledWith(13);
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.plugin.messages.forceCleanupSuccess',
    );
    expect(afterUninstall).toHaveBeenCalled();
  });
});

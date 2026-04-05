import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  confirm: vi.fn(),
  generateAccess: vi.fn(),
  refreshPluginSlots: vi.fn(),
  setAccessMenus: vi.fn(),
  setAccessRoutes: vi.fn(),
  setIsAccessChecked: vi.fn(),
  showRequestError: vi.fn(),
  userInfo: { roles: ['admin'] },
  warning: vi.fn(),
}));

vi.mock('@vben/stores', () => ({
  useAccessStore: () => ({
    setAccessMenus: mockRefs.setAccessMenus,
    setAccessRoutes: mockRefs.setAccessRoutes,
    setIsAccessChecked: mockRefs.setIsAccessChecked,
  }),
  useUserStore: () => ({
    userInfo: mockRefs.userInfo,
  }),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: mockRefs.confirm,
    warning: mockRefs.warning,
  },
}));

vi.mock('#/composables/use-plugin-frontend-init', () => ({
  refreshPluginSlots: mockRefs.refreshPluginSlots,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/router/access', () => ({
  generateAccess: mockRefs.generateAccess,
}));

vi.mock('#/router/routes', () => ({
  accessRoutes: [{ path: '/admin' }],
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: mockRefs.showRequestError,
}));

describe('plugin admin refresh helpers', () => {
  beforeEach(() => {
    mockRefs.confirm.mockReset();
    mockRefs.generateAccess.mockReset();
    mockRefs.refreshPluginSlots.mockReset();
    mockRefs.setAccessMenus.mockReset();
    mockRefs.setAccessRoutes.mockReset();
    mockRefs.setIsAccessChecked.mockReset();
    mockRefs.showRequestError.mockReset();
    mockRefs.warning.mockReset();
  });

  it('refreshes plugin slots and updates admin menus/routes', async () => {
    const { refreshAdminMenusAndPluginRoutes } =
      await import('../use-plugin-admin-refresh');

    mockRefs.generateAccess.mockResolvedValue({
      accessibleMenus: [{ name: 'Plugins' }],
      accessibleRoutes: [{ path: '/plugins' }],
    });

    await refreshAdminMenusAndPluginRoutes({} as never);

    expect(mockRefs.refreshPluginSlots).toHaveBeenCalledWith(
      '/admin',
      {},
      { reloadAssets: true },
    );
    expect(mockRefs.setAccessMenus).toHaveBeenCalledWith([{ name: 'Plugins' }]);
    expect(mockRefs.setAccessRoutes).toHaveBeenCalledWith([
      { path: '/plugins' },
    ]);
    expect(mockRefs.setIsAccessChecked).toHaveBeenCalledWith(true);
  });

  it('marks access as unchecked when menu regeneration fails', async () => {
    const { refreshAdminMenusAndPluginRoutes } =
      await import('../use-plugin-admin-refresh');

    mockRefs.generateAccess.mockRejectedValue(new Error('failed'));

    await refreshAdminMenusAndPluginRoutes({} as never);

    expect(mockRefs.setIsAccessChecked).toHaveBeenCalledWith(false);
  });

  it('shows dependency warning when disable fails because of dependent plugins', async () => {
    const { handleDisableError } = await import('../use-plugin-admin-refresh');

    handleDisableError(
      {
        response: {
          data: {
            message: 'plugins [alpha,beta] depend on it',
          },
        },
      },
      'Weather Plugin',
      vi.fn(),
    );

    expect(mockRefs.warning).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'admin.plugin.confirm.dependency_error_title',
        content: 'admin.plugin.confirm.dependency_error_content',
      }),
    );
  });

  it('shows force disable confirm for storage-driver usage errors', async () => {
    const { handleDisableError } = await import('../use-plugin-admin-refresh');
    const onForceDisable = vi.fn();

    handleDisableError(
      { message: 'storage driver used by tenant' },
      'Storage Plugin',
      onForceDisable,
    );

    expect(mockRefs.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        onOk: onForceDisable,
        okType: 'danger',
        title: 'admin.plugin.confirm.force_disable_title',
      }),
    );
  });

  it('falls back to shared request error handling for unknown disable errors', async () => {
    const { handleDisableError } = await import('../use-plugin-admin-refresh');

    handleDisableError(new Error('unknown'), 'Other Plugin', vi.fn());

    expect(mockRefs.showRequestError).toHaveBeenCalledWith(
      expect.any(Error),
      'admin.common.operationFailed',
    );
  });
});

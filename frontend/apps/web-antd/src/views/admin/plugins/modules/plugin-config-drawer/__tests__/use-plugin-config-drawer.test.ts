import type {
  PluginInfo,
  PluginLifecycleAuditReport,
} from '#/api/admin/plugin';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePluginConfigDrawer } from '../use-plugin-config-drawer';

const mockRefs = vi.hoisted(() => {
  const pluginActions = {
    onDisable: vi.fn(),
    onEnable: vi.fn().mockResolvedValue(undefined),
    onForceCleanup: vi.fn(),
    onInstallDependencies: vi.fn(),
    onRefreshSchedules: vi.fn(),
    onRepair: vi.fn(),
    onUninstall: vi.fn(),
    onUninstallDependencies: vi.fn(),
  };

  return {
    activatePluginLicenseApi: vi.fn(),
    activatePluginTrialApi: vi.fn(),
    assignPluginTenantsApi: vi.fn(),
    deletePluginBackupApi: vi.fn(),
    derivePluginType: vi.fn(() => 'bundled'),
    getPluginDetailApi: vi.fn(),
    getPluginLicenseApi: vi.fn(),
    getPluginLifecycleAuditApi: vi.fn(),
    getPluginRecoveryMeta: vi.fn(() => ({
      alertType: 'warning',
      descriptionKey: 'admin.plugin.recovery.description',
    })),
    getPluginRecoveryState: vi.fn(() => ({
      needs_attention: false,
    })),
    getPluginTenantsApi: vi.fn(),
    getPluginVersionsApi: vi.fn(),
    getTenantListApi: vi.fn(),
    handleDisableError: vi.fn(),
    hasPluginRecoveryAction: vi.fn(() => false),
    hasPluginScheduledTasks: vi.fn(() => false),
    listPluginBackupsApi: vi.fn(),
    messageError: vi.fn(),
    messageSuccess: vi.fn(),
    modalConfirm: vi.fn(),
    pluginActions,
    preferences: {
      app: {
        locale: 'zh-CN',
      },
    },
    refreshAdminMenusAndPluginRoutes: vi.fn(),
    resolvePluginMetadataIcon: vi.fn(() => ({
      icon: 'lucide:package',
      kind: 'icon',
    })),
    revokePluginLicenseApi: vi.fn(),
    rollbackPluginApi: vi.fn(),
    routerPush: vi.fn(),
    resolvePluginCompatibilityProfile: vi.fn(
      (source: {
        compatibility_profile?: null | {
          tenant_assignment_required?: boolean;
          tenant_exposure?: string;
        };
      }) => {
        const tenantExposure = source.compatibility_profile?.tenant_exposure;
        const tenantExposureMode =
          tenantExposure === 'all_tenants' ||
          tenantExposure === 'none' ||
          tenantExposure === 'scope_default' ||
          tenantExposure === 'selected_tenants'
            ? tenantExposure
            : 'scope_default';
        return {
          editions: ['saas'],
          saasCompatible: true,
          singleManagementCompatible: false,
          surfaces: [],
          tenantAssignmentRequired:
            source.compatibility_profile?.tenant_assignment_required === true ||
            tenantExposureMode === 'selected_tenants',
          tenantExposureMode,
        };
      },
    ),
    scopeNeedsAssignment: vi.fn(
      (scope: string) => scope === 'selected_tenants',
    ),
    t: vi.fn((key: string) => key),
    unassignPluginTenantApi: vi.fn(),
    updatePluginConfigApi: vi.fn(),
    upgradePluginApi: vi.fn(),
    usePluginAdminActions: vi.fn(() => pluginActions),
  };
});

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockRefs.routerPush,
  }),
}));

vi.mock('@vben/preferences', () => ({
  preferences: mockRefs.preferences,
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: mockRefs.modalConfirm,
  },
  message: {
    error: mockRefs.messageError,
    success: mockRefs.messageSuccess,
  },
}));

vi.mock('#/api/admin/plugin', () => ({
  activatePluginLicenseApi: mockRefs.activatePluginLicenseApi,
  activatePluginTrialApi: mockRefs.activatePluginTrialApi,
  assignPluginTenantsApi: mockRefs.assignPluginTenantsApi,
  deletePluginBackupApi: mockRefs.deletePluginBackupApi,
  getPluginDetailApi: mockRefs.getPluginDetailApi,
  getPluginLicenseApi: mockRefs.getPluginLicenseApi,
  getPluginLifecycleAuditApi: mockRefs.getPluginLifecycleAuditApi,
  getPluginTenantsApi: mockRefs.getPluginTenantsApi,
  getPluginVersionsApi: mockRefs.getPluginVersionsApi,
  listPluginBackupsApi: mockRefs.listPluginBackupsApi,
  resolvePluginCompatibilityProfile: mockRefs.resolvePluginCompatibilityProfile,
  revokePluginLicenseApi: mockRefs.revokePluginLicenseApi,
  rollbackPluginApi: mockRefs.rollbackPluginApi,
  unassignPluginTenantApi: mockRefs.unassignPluginTenantApi,
  updatePluginConfigApi: mockRefs.updatePluginConfigApi,
  upgradePluginApi: mockRefs.upgradePluginApi,
}));

vi.mock('#/api/admin/tenant', () => ({
  getTenantListApi: mockRefs.getTenantListApi,
}));

vi.mock('#/components/business/scope-select', () => ({
  scopeNeedsAssignment: mockRefs.scopeNeedsAssignment,
}));

vi.mock('#/composables/use-plugin-admin-refresh', () => ({
  handleDisableError: mockRefs.handleDisableError,
  refreshAdminMenusAndPluginRoutes: mockRefs.refreshAdminMenusAndPluginRoutes,
}));

vi.mock('#/locales', () => ({
  $t: mockRefs.t,
}));

vi.mock('#/utils/plugin-metadata-icon', () => ({
  resolvePluginMetadataIcon: mockRefs.resolvePluginMetadataIcon,
}));

vi.mock('../../../data', () => ({
  derivePluginType: mockRefs.derivePluginType,
}));

vi.mock('../../../plugin-recovery', () => ({
  getPluginRecoveryMeta: mockRefs.getPluginRecoveryMeta,
  getPluginRecoveryState: mockRefs.getPluginRecoveryState,
  hasPluginRecoveryAction: mockRefs.hasPluginRecoveryAction,
  hasPluginScheduledTasks: mockRefs.hasPluginScheduledTasks,
}));

vi.mock('../../../use-plugin-admin-actions', () => ({
  usePluginAdminActions: mockRefs.usePluginAdminActions,
}));

function createAuditReport(): PluginLifecycleAuditReport {
  return {
    exposed_capabilities: [],
    recent_failures: [],
    recovery_actions: [],
    runtime_kind: 'plugin',
    stage_results: [],
    target: {},
  };
}

function createPlugin(overrides: Partial<PluginInfo> = {}): PluginInfo {
  return {
    ai_requirements: null,
    author: 'NovusAI',
    config: {},
    created_at: '2026-04-11T00:00:00Z',
    description: 'Demo plugin',
    display_name: 'Demo Plugin',
    enabled_at: null,
    error_count: 0,
    error_message: null,
    granted_capabilities: [],
    homepage: null,
    icon: null,
    icon_color: null,
    id: 7,
    install_source: 'local',
    installed_at: '2026-04-11T00:00:00Z',
    installed_packages: [],
    license_text: null,
    manifest: {},
    marketplace_slug: null,
    name: 'demo-plugin',
    pricing_info: null,
    pricing_type: 'free',
    readme: null,
    repository_url: null,
    scope: 'platform',
    status: 'installed',
    tags: [],
    tier: 'free',
    updated_at: '2026-04-11T00:00:00Z',
    version: '1.0.0',
    ...overrides,
  };
}

describe('usePluginConfigDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockRefs.preferences.app.locale = 'zh-CN';
    mockRefs.getPluginDetailApi.mockImplementation(async (_id, _params) =>
      createPlugin(),
    );
    mockRefs.getPluginLicenseApi.mockResolvedValue({
      data: {
        is_valid: true,
        license_type: 'lifetime',
        status: 'active',
      },
    });
    mockRefs.getPluginLifecycleAuditApi.mockResolvedValue(createAuditReport());
    mockRefs.getPluginTenantsApi.mockResolvedValue({ data: [] });
    mockRefs.getPluginVersionsApi.mockResolvedValue({ data: [] });
    mockRefs.getTenantListApi.mockResolvedValue({ items: [] });
    mockRefs.listPluginBackupsApi.mockResolvedValue([]);
    mockRefs.resolvePluginCompatibilityProfile.mockImplementation(
      (source: {
        compatibility_profile?: null | {
          tenant_assignment_required?: boolean;
          tenant_exposure?: string;
        };
      }) => {
        const tenantExposure = source.compatibility_profile?.tenant_exposure;
        const tenantExposureMode =
          tenantExposure === 'all_tenants' ||
          tenantExposure === 'none' ||
          tenantExposure === 'scope_default' ||
          tenantExposure === 'selected_tenants'
            ? tenantExposure
            : 'scope_default';
        return {
          editions: ['saas'],
          saasCompatible: true,
          singleManagementCompatible: false,
          surfaces: [],
          tenantAssignmentRequired:
            source.compatibility_profile?.tenant_assignment_required === true ||
            tenantExposureMode === 'selected_tenants',
          tenantExposureMode,
        };
      },
    );
    mockRefs.scopeNeedsAssignment.mockImplementation(
      (scope: string) => scope === 'selected_tenants',
    );
  });

  it('hydrates localized schema fields and tenant options from normalized responses', async () => {
    const plugin = createPlugin({
      ai_requirements: { features: ['assist'] },
      config: { apiKey: 'row-token' },
      id: 12,
      manifest: {
        config_schema: {
          properties: {
            apiKey: {
              default: 'seed-token',
              description: {
                'zh-CN': '用于调用插件接口',
                en: 'Used for plugin requests',
              },
              type: 'string',
              title: {
                'zh-CN': '接口密钥',
                en: 'API Key',
              },
            },
          },
        },
      },
      scope: 'selected_tenants',
    });

    mockRefs.getPluginDetailApi.mockResolvedValue({
      data: {
        ...plugin,
        display_name: 'Detail Plugin',
      },
    });
    mockRefs.getPluginVersionsApi.mockResolvedValue({
      data: [
        {
          changelog: null,
          id: 1,
          installed_at: null,
          rolled_back_at: null,
          status: 'installed',
          version: '1.1.0',
        },
      ],
    });
    mockRefs.getPluginTenantsApi.mockResolvedValue({
      data: [
        {
          config: {},
          created_at: '2026-04-11T00:00:00Z',
          id: 1,
          is_active: true,
          plugin_id: 12,
          tenant_id: 1,
        },
      ],
    });
    mockRefs.getTenantListApi.mockResolvedValue({
      items: [
        { display_name: 'Acme', id: 1 },
        { id: 2, name: 'Beta' },
      ],
    });

    const drawer = usePluginConfigDrawer({ onSaved: vi.fn() });

    await drawer.open(plugin);

    expect(mockRefs.getPluginDetailApi).toHaveBeenCalledWith(12, {
      locale: 'zh-CN',
    });
    expect(mockRefs.getPluginTenantsApi).toHaveBeenCalledWith(12);
    expect(mockRefs.getTenantListApi).toHaveBeenCalledWith({
      'page[size]': 200,
    });
    expect(drawer.plugin.value?.display_name).toBe('Detail Plugin');
    expect(drawer.needsTenantAssignment.value).toBe(true);
    expect(drawer.pluginHasAiFeatures.value).toBe(true);
    expect(drawer.configSchemaFields.value).toContainEqual(
      expect.objectContaining({
        default: 'seed-token',
        description: '用于调用插件接口',
        key: 'apiKey',
        title: '接口密钥',
        type: 'string',
      }),
    );
    expect(drawer.availableTenants.value.map((tenant) => tenant.id)).toEqual([
      2,
    ]);
  });

  it('[behavioral] loads tenant assignments when compatibility profile requires explicit assignment', async () => {
    const plugin = createPlugin({
      compatibility_profile: {
        editions: ['saas', 'single_management'],
        tenant_assignment_required: true,
        tenant_exposure: 'selected_tenants',
      },
      id: 52,
      scope: 'platform',
    });

    mockRefs.getPluginDetailApi.mockResolvedValue({
      data: {
        ...plugin,
        display_name: 'Compatibility Detail Plugin',
      },
    });
    mockRefs.getPluginTenantsApi.mockResolvedValue({
      data: [
        {
          config: {},
          created_at: '2026-05-06T00:00:00Z',
          id: 9,
          is_active: true,
          plugin_id: 52,
          tenant_id: 3,
        },
      ],
    });
    mockRefs.getTenantListApi.mockResolvedValue({
      items: [
        { id: 3, name: 'Assigned Tenant' },
        { id: 4, name: 'Available Tenant' },
      ],
    });

    const drawer = usePluginConfigDrawer({ onSaved: vi.fn() });

    await drawer.open(plugin);

    expect(drawer.needsTenantAssignment.value).toBe(true);
    expect(mockRefs.getPluginTenantsApi).toHaveBeenCalledWith(52);
    expect(mockRefs.getTenantListApi).toHaveBeenCalledWith({
      'page[size]': 200,
    });
    expect(
      drawer.tenantAssignments.value.map((item) => item.tenant_id),
    ).toEqual([3]);
    expect(drawer.availableTenants.value.map((tenant) => tenant.id)).toEqual([
      4,
    ]);
  });

  it('saves structured config values when a schema is present', async () => {
    const onSaved = vi.fn();
    const plugin = createPlugin({
      config: { mode: 'auto' },
      id: 21,
      manifest: {
        config_schema: {
          properties: {
            mode: {
              default: 'auto',
              type: 'string',
            },
          },
        },
      },
    });

    mockRefs.getPluginDetailApi.mockResolvedValue({ data: plugin });

    const drawer = usePluginConfigDrawer({ onSaved });

    await drawer.open(plugin);
    drawer.setConfigValue('mode', 'manual');
    await drawer.onSaveConfig();

    expect(mockRefs.updatePluginConfigApi).toHaveBeenCalledWith(21, {
      mode: 'manual',
    });
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.plugin.config.saveSuccess',
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it('shows an invalid JSON message instead of saving malformed raw config', async () => {
    const plugin = createPlugin({
      config: { retries: 3 },
      id: 31,
      manifest: {},
    });

    mockRefs.getPluginDetailApi.mockResolvedValue({ data: plugin });

    const drawer = usePluginConfigDrawer({ onSaved: vi.fn() });

    await drawer.open(plugin);
    drawer.setConfigJson('{bad json');
    await drawer.onSaveConfig();

    expect(mockRefs.updatePluginConfigApi).not.toHaveBeenCalled();
    expect(mockRefs.messageError).toHaveBeenCalledWith(
      'admin.plugin.invalidJson',
    );
  });

  it('ignores malformed config schema properties instead of synthesizing bogus fields', async () => {
    const plugin = createPlugin({
      id: 41,
      manifest: {
        config_schema: {
          properties: {
            broken: 'oops',
            retries: {
              default: 3,
              enum: ['auto', 1],
              minimum: '1',
              title: {
                'zh-CN': '重试次数',
                en: 'Retries',
              },
              type: 'number',
            },
          },
        },
      },
    });

    mockRefs.getPluginDetailApi.mockResolvedValue({ data: plugin });

    const drawer = usePluginConfigDrawer({ onSaved: vi.fn() });

    await drawer.open(plugin);

    expect(drawer.configSchemaFields.value).toEqual([
      expect.objectContaining({
        default: 3,
        enum: ['auto'],
        key: 'retries',
        minimum: undefined,
        title: '重试次数',
        type: 'number',
      }),
    ]);
  });
});

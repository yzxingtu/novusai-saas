import { computed, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const adminApiMocks = vi.hoisted(() => ({
  getOverviewApi: vi.fn(),
  listBindingsApi: vi.fn(),
  listProviderProfilesApi: vi.fn(),
  listReconciliationRunsApi: vi.fn(),
  saveProviderProfilesApi: vi.fn(),
  validateProviderProfileApi: vi.fn(),
}));

const bindingsMocks = vi.hoisted(() => ({
  syncVisibleProviderSelection: vi.fn(),
}));

const runActionMocks = vi.hoisted(() => ({
  loadRunDetail: vi.fn(),
}));

vi.mock('@novus/plugin-shared', () => ({
  $t: (key: string) => key,
}));

vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue');
  return {
    ...actual,
    onMounted: () => undefined,
  };
});

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('../../../api/admin', () => ({
  getOverviewApi: adminApiMocks.getOverviewApi,
  listBindingsApi: adminApiMocks.listBindingsApi,
  listProviderProfilesApi: adminApiMocks.listProviderProfilesApi,
  listReconciliationRunsApi: adminApiMocks.listReconciliationRunsApi,
  saveProviderProfilesApi: adminApiMocks.saveProviderProfilesApi,
  validateProviderProfileApi: adminApiMocks.validateProviderProfileApi,
}));

vi.mock('../use-storage-billing-admin-bindings', () => ({
  useStorageBillingAdminBindings: () => ({
    bindingOpen: ref(false),
    syncVisibleProviderSelection: bindingsMocks.syncVisibleProviderSelection,
  }),
}));

vi.mock('../use-storage-billing-admin-presenters', () => ({
  useStorageBillingAdminPresenters: () => ({
    manualBillingDateError: computed(() => null),
    qiniuMonthValid: computed(() => true),
  }),
}));

vi.mock('../use-storage-billing-admin-run-actions', () => ({
  useStorageBillingAdminRunActions: () => ({
    applyRunChargeFilters: vi.fn(),
    exportCurrentRunCharges: vi.fn(),
    loadRunDetail: runActionMocks.loadRunDetail,
    resetRunChargeFilters: vi.fn(),
    triggerQiniuMonthlyRun: vi.fn(),
    triggerRun: vi.fn(),
  }),
}));

vi.mock('../use-reconciliation-run-detail', () => ({
  useReconciliationRunDetail: () => ({
    auditedSources: computed(() => []),
    currentRunChargeFilters: vi.fn(() => ({})),
    resetRunChargeFiltersState: vi.fn(),
    runChargeActiveFilters: computed(() => []),
    runChargeFilters: ref({}),
    runChargeProviderOptions: computed(() => []),
    runChargeSourceOptions: computed(() => []),
    selectedRun: computed(() => null),
    selectedRunProviderResults: computed(() => []),
    sourceLabelFromCharge: vi.fn(() => '-'),
  }),
}));

import { useStorageBillingAdminPage } from '../use-storage-billing-admin-page';

function installSharedAccess(shared?: unknown) {
  Object.assign(window, {
    NovusPluginShared: shared,
  });
}

describe('useStorageBillingAdminPage access guards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installSharedAccess(undefined);
    adminApiMocks.getOverviewApi.mockResolvedValue({
      host_snapshot: {},
      ledger_snapshot: { latest_runs: [] },
    });
    adminApiMocks.listProviderProfilesApi.mockResolvedValue({
      providers: {},
      validations: {},
    });
    adminApiMocks.listBindingsApi.mockResolvedValue({ items: [] });
    adminApiMocks.listReconciliationRunsApi.mockResolvedValue({ items: [] });
  });

  it('fails closed when shared access codes return a malformed value', async () => {
    installSharedAccess({
      getAccessCodes: () => ({ broken: true }),
    });

    const page = useStorageBillingAdminPage();
    await page.loadAll();

    expect(page.canViewAdmin.value).toBe(false);
    expect(adminApiMocks.getOverviewApi).not.toHaveBeenCalled();
    expect(page.bindings.value).toEqual([]);
    expect(page.runs.value).toEqual([]);
    expect(page.overview.value).toBeNull();
  });

  it('accepts wildcard access codes from the shared bridge', async () => {
    installSharedAccess({
      getAccessCodes: () => ['*'],
    });

    const page = useStorageBillingAdminPage();
    await page.loadAll();

    expect(page.canViewAdmin.value).toBe(true);
    expect(adminApiMocks.getOverviewApi).toHaveBeenCalledTimes(1);
    expect(adminApiMocks.listBindingsApi).toHaveBeenCalledTimes(1);
    expect(adminApiMocks.listProviderProfilesApi).toHaveBeenCalledTimes(1);
    expect(adminApiMocks.listReconciliationRunsApi).toHaveBeenCalledTimes(1);
  });
});

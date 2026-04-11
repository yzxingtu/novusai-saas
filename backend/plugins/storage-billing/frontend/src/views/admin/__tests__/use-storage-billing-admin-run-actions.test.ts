import type {
  ProviderCode,
  ReconciliationRun,
  ReconciliationRunChargeListResponse,
  ReconciliationRunDetailResponse,
} from '../../../types';

import { computed, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const adminApiMocks = vi.hoisted(() => ({
  exportReconciliationRunChargesCsvApi: vi.fn(),
  getReconciliationRunApi: vi.fn(),
  getReconciliationRunChargesApi: vi.fn(),
  runQiniuMonthlySettlementApi: vi.fn(),
  runReconciliationApi: vi.fn(),
}));

const uiMocks = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  modalConfirm: vi.fn(),
  t: vi.fn((key: string) => key),
}));

vi.mock('../../../api/admin', () => ({
  exportReconciliationRunChargesCsvApi:
    adminApiMocks.exportReconciliationRunChargesCsvApi,
  getReconciliationRunApi: adminApiMocks.getReconciliationRunApi,
  getReconciliationRunChargesApi: adminApiMocks.getReconciliationRunChargesApi,
  runQiniuMonthlySettlementApi: adminApiMocks.runQiniuMonthlySettlementApi,
  runReconciliationApi: adminApiMocks.runReconciliationApi,
}));

vi.mock('@novus/plugin-shared', () => ({
  $t: uiMocks.t,
  downloadBlob: uiMocks.downloadBlob,
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: uiMocks.modalConfirm,
  },
  message: {
    error: uiMocks.messageError,
    success: uiMocks.messageSuccess,
  },
}));

import { useStorageBillingAdminRunActions } from '../use-storage-billing-admin-run-actions';

function createRun(overrides: Partial<ReconciliationRun> = {}): ReconciliationRun {
  return {
    billing_date: '2026-04-10',
    completed_at: '2026-04-11T00:10:00Z',
    error_message: null,
    id: 5,
    provider_codes: ['qiniu-kodo'],
    requested_scope: {},
    run_key: 'run-5',
    started_at: '2026-04-11T00:00:00Z',
    status: 'completed',
    summary: {},
    trigger_type: 'manual',
    ...overrides,
  };
}

function createRunDetailResponse(): ReconciliationRunDetailResponse {
  return {
    run: createRun(),
    sources: [],
  };
}

function createRunChargeResponse(): ReconciliationRunChargeListResponse {
  return {
    items: [
      {
        amount_total: '12.30',
        billing_date: '2026-04-10',
        charge_basis: 'bucket',
        currency: 'CNY',
        driver_code: 'qiniu-kodo',
        id: 1,
        provider_code: 'qiniu-kodo',
        source_id: 2,
        tenant_id: 18,
        usage_bytes: 2048,
      },
    ],
    run_id: 5,
    total: 1,
  };
}

type StateOptions = {
  canReconcileAdmin?: boolean;
  canViewAdmin?: boolean;
};

function createState(options: StateOptions = {}) {
  const canViewAdmin = ref(options.canViewAdmin ?? true);
  const canReconcileAdmin = ref(options.canReconcileAdmin ?? true);
  const manualBillingDate = ref('');
  const manualBillingDateError = computed<null | string>(() => null);
  const manualProviderCodes = ref<ProviderCode[]>([]);
  const qiniuBillingMonth = ref('2026-03');
  const qiniuMonthValid = computed(() => true);
  const runChargeExporting = ref(false);
  const runChargeLoading = ref(false);
  const runDetailLoading = ref(false);
  const selectedRun = ref<null | ReconciliationRun>(createRun());
  const selectedRunChargeResponse = ref<null | ReconciliationRunChargeListResponse>(
    null,
  );
  const selectedRunCharges = ref(createRunChargeResponse().items);
  const selectedRunDetail = ref<null | ReconciliationRunDetailResponse>(null);
  const selectedRunId = ref<null | number>(5);
  const currentRunChargeFilters = vi.fn(() => ({
    provider_code: 'qiniu-kodo',
    tenant_id: 18,
  }));
  const loadAll = vi.fn(async () => undefined);
  const loadRunDetailAfterRefresh = vi.fn(async () => undefined);
  const providerLabel = vi.fn((code: ProviderCode) => `provider:${code}`);
  const resetRunChargeFiltersState = vi.fn(() => undefined);

  const actions = useStorageBillingAdminRunActions({
    canReconcileAdmin: computed(() => canReconcileAdmin.value),
    canViewAdmin: computed(() => canViewAdmin.value),
    currentRunChargeFilters,
    loadAll,
    loadRunDetailAfterRefresh,
    manualBillingDate,
    manualBillingDateError,
    manualProviderCodes,
    providerLabel,
    qiniuBillingMonth,
    qiniuMonthValid,
    resetRunChargeFiltersState,
    runChargeExporting,
    runChargeLoading,
    runDetailLoading,
    selectedRun: computed(() => selectedRun.value),
    selectedRunChargeResponse,
    selectedRunCharges,
    selectedRunDetail,
    selectedRunId,
  });

  return {
    actions,
    canReconcileAdmin,
    canViewAdmin,
    currentRunChargeFilters,
    loadAll,
    loadRunDetailAfterRefresh,
    manualBillingDate,
    manualProviderCodes,
    providerLabel,
    qiniuBillingMonth,
    resetRunChargeFiltersState,
    runChargeExporting,
    runChargeLoading,
    runDetailLoading,
    selectedRun,
    selectedRunChargeResponse,
    selectedRunCharges,
    selectedRunDetail,
    selectedRunId,
  };
}

describe('useStorageBillingAdminRunActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    adminApiMocks.getReconciliationRunApi.mockResolvedValue(
      createRunDetailResponse(),
    );
    adminApiMocks.getReconciliationRunChargesApi.mockResolvedValue(
      createRunChargeResponse(),
    );
    adminApiMocks.exportReconciliationRunChargesCsvApi.mockResolvedValue(
      new Blob(['csv']),
    );
    adminApiMocks.runReconciliationApi.mockResolvedValue({
      run: { id: 15 },
      status: 'queued',
    });
    adminApiMocks.runQiniuMonthlySettlementApi.mockResolvedValue({
      run: { id: 16 },
      status: 'queued',
    });
  });

  it('hydrates selected run detail and resets filters before loading charges', async () => {
    const state = createState();

    await state.actions.loadRunDetail(5);

    expect(state.selectedRunId.value).toBe(5);
    expect(state.resetRunChargeFiltersState).toHaveBeenCalledTimes(1);
    expect(adminApiMocks.getReconciliationRunApi).toHaveBeenCalledWith(5);
    expect(adminApiMocks.getReconciliationRunChargesApi).toHaveBeenCalledWith(5);
    expect(state.selectedRunDetail.value?.run.id).toBe(5);
    expect(state.selectedRunChargeResponse.value?.items).toHaveLength(1);
    expect(state.selectedRunCharges.value).toEqual(
      createRunChargeResponse().items,
    );
    expect(state.runDetailLoading.value).toBe(false);
  });

  it('applies charge filters through the current selected run context', async () => {
    const state = createState();
    state.selectedRunId.value = 9;

    await state.actions.applyRunChargeFilters();

    expect(adminApiMocks.getReconciliationRunChargesApi).toHaveBeenCalledWith(9, {
      provider_code: 'qiniu-kodo',
      tenant_id: 18,
    });
    expect(state.currentRunChargeFilters).toHaveBeenCalledTimes(1);
    expect(state.runChargeLoading.value).toBe(false);
  });

  it('exports current run charges with a stable csv filename', async () => {
    const state = createState();
    state.selectedRunId.value = 23;
    state.selectedRun.value = createRun({ billing_date: '2026-04-09', id: 23 });

    await state.actions.exportCurrentRunCharges();

    expect(adminApiMocks.exportReconciliationRunChargesCsvApi).toHaveBeenCalledWith(
      23,
      {
        provider_code: 'qiniu-kodo',
        tenant_id: 18,
      },
    );
    expect(uiMocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), {
      filename: 'storage-billing-run-23-2026-04-09.csv',
    });
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith(
      'plugin.storage-billing.admin.messages.exportSuccess',
    );
    expect(state.runChargeExporting.value).toBe(false);
  });

  it('stops manual reconciliation before opening confirm when the billing date is invalid', () => {
    const state = createState();
    const invalidActions = useStorageBillingAdminRunActions({
      canReconcileAdmin: computed(() => state.canReconcileAdmin.value),
      canViewAdmin: computed(() => state.canViewAdmin.value),
      currentRunChargeFilters: state.currentRunChargeFilters,
      loadAll: state.loadAll,
      loadRunDetailAfterRefresh: state.loadRunDetailAfterRefresh,
      manualBillingDate: state.manualBillingDate,
      manualBillingDateError: computed(() => 'invalid-date'),
      manualProviderCodes: state.manualProviderCodes,
      providerLabel: state.providerLabel,
      qiniuBillingMonth: state.qiniuBillingMonth,
      qiniuMonthValid: computed(() => true),
      resetRunChargeFiltersState: state.resetRunChargeFiltersState,
      runChargeExporting: state.runChargeExporting,
      runChargeLoading: state.runChargeLoading,
      runDetailLoading: state.runDetailLoading,
      selectedRun: computed(() => state.selectedRun.value),
      selectedRunChargeResponse: state.selectedRunChargeResponse,
      selectedRunCharges: state.selectedRunCharges,
      selectedRunDetail: state.selectedRunDetail,
      selectedRunId: state.selectedRunId,
    });

    invalidActions.triggerRun();

    expect(uiMocks.messageError).toHaveBeenCalledWith('invalid-date');
    expect(uiMocks.modalConfirm).not.toHaveBeenCalled();
    expect(adminApiMocks.runReconciliationApi).not.toHaveBeenCalled();
  });

  it('confirms manual reconciliation, sends normalized payload, and refreshes detail', async () => {
    const state = createState();
    state.manualBillingDate.value = '2026-04-10';
    state.manualProviderCodes.value = ['qiniu-kodo', 'tencent-cos'];

    state.actions.triggerRun();

    expect(uiMocks.modalConfirm).toHaveBeenCalledTimes(1);
    expect(uiMocks.modalConfirm.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        title: 'plugin.storage-billing.admin.actions.triggerRun',
      }),
    );

    const confirmConfig = uiMocks.modalConfirm.mock.calls[0]?.[0] as {
      onOk: () => Promise<void>;
    };
    await confirmConfig.onOk();

    expect(adminApiMocks.runReconciliationApi).toHaveBeenCalledWith({
      billing_date: '2026-04-10',
      provider_codes: ['qiniu-kodo', 'tencent-cos'],
    });
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith(
      'plugin.storage-billing.admin.messages.runTriggered',
    );
    expect(state.loadAll).toHaveBeenCalledTimes(1);
    expect(state.loadRunDetailAfterRefresh).toHaveBeenCalledWith(15);
  });

  it('blocks qiniu monthly reconciliation when the billing month is invalid', () => {
    const state = createState();
    const invalidMonthlyActions = useStorageBillingAdminRunActions({
      canReconcileAdmin: computed(() => state.canReconcileAdmin.value),
      canViewAdmin: computed(() => state.canViewAdmin.value),
      currentRunChargeFilters: state.currentRunChargeFilters,
      loadAll: state.loadAll,
      loadRunDetailAfterRefresh: state.loadRunDetailAfterRefresh,
      manualBillingDate: state.manualBillingDate,
      manualBillingDateError: computed(() => null),
      manualProviderCodes: state.manualProviderCodes,
      providerLabel: state.providerLabel,
      qiniuBillingMonth: state.qiniuBillingMonth,
      qiniuMonthValid: computed(() => false),
      resetRunChargeFiltersState: state.resetRunChargeFiltersState,
      runChargeExporting: state.runChargeExporting,
      runChargeLoading: state.runChargeLoading,
      runDetailLoading: state.runDetailLoading,
      selectedRun: computed(() => state.selectedRun.value),
      selectedRunChargeResponse: state.selectedRunChargeResponse,
      selectedRunCharges: state.selectedRunCharges,
      selectedRunDetail: state.selectedRunDetail,
      selectedRunId: state.selectedRunId,
    });

    invalidMonthlyActions.triggerQiniuMonthlyRun();

    expect(uiMocks.messageError).toHaveBeenCalledWith(
      'plugin.storage-billing.admin.actions.qiniuMonthlyInvalid',
    );
    expect(uiMocks.modalConfirm).not.toHaveBeenCalled();
    expect(adminApiMocks.runQiniuMonthlySettlementApi).not.toHaveBeenCalled();
  });
});

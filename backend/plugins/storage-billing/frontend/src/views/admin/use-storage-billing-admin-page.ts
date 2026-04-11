import type {
  BindingRecord,
  OverviewResponse,
  ProviderCode,
  ReconciliationChargeRow,
  ReconciliationRun,
  ReconciliationRunChargeListResponse,
  ReconciliationRunDetailResponse,
} from '../../types';

import { computed, onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { $t } from '@novus/plugin-shared';

import {
  getOverviewApi,
  listBindingsApi,
  listProviderProfilesApi,
  listReconciliationRunsApi,
  saveProviderProfilesApi,
  validateProviderProfileApi,
} from '../../api/admin';
import { useReconciliationRunDetail } from './use-reconciliation-run-detail';
import {
  buildMergedProviderState,
  buildProviderPayload,
  emptyProfiles,
  emptyValidations,
  PROVIDERS,
  RUN_HISTORY_LIMIT,
  type ProviderProfileEnvelope,
  type SharedAccessApi,
} from './storage-billing-admin-contracts';
import { useStorageBillingAdminBindings } from './use-storage-billing-admin-bindings';
import { useStorageBillingAdminPresenters } from './storage-billing-admin-presenters';
import { useStorageBillingAdminRunActions } from './use-storage-billing-admin-run-actions';

export function useStorageBillingAdminPage() {
  const overview = ref<null | OverviewResponse>(null);
  const loading = ref(false);
  const saving = ref(false);
  const bindings = ref<BindingRecord[]>([]);
  const runs = ref<ReconciliationRun[]>([]);
  const selectedRunId = ref<null | number>(null);
  const selectedRunDetail = ref<null | ReconciliationRunDetailResponse>(null);
  const selectedRunCharges = ref<ReconciliationChargeRow[]>([]);
  const selectedRunChargeResponse = ref<null | ReconciliationRunChargeListResponse>(null);
  const runDetailLoading = ref(false);
  const runChargeLoading = ref(false);
  const runChargeExporting = ref(false);
  const qiniuBillingMonth = ref(
    new Date(Date.now() - 32 * 24 * 60 * 60 * 1000).toISOString().slice(0, 7),
  );
  const manualBillingDate = ref('');
  const manualProviderCodes = ref<ProviderCode[]>([]);

  const profiles = reactive(emptyProfiles());
  const validations = reactive(emptyValidations());

  function getSharedAccess(): SharedAccessApi | undefined {
    return (window as unknown as { NovusPluginShared?: SharedAccessApi }).NovusPluginShared;
  }

  function hasAccess(codes: string[]): boolean {
    const shared = getSharedAccess();
    if (typeof shared?.hasAccessByCodes === 'function') {
      return shared.hasAccessByCodes(codes);
    }
    if (typeof shared?.getAccessCodes !== 'function') {
      return codes.length === 0;
    }
    const accessCodes = shared.getAccessCodes() ?? [];
    if (accessCodes.includes('*')) {
      return true;
    }
    return codes.some((code) => accessCodes.includes(code));
  }

  const canViewAdmin = computed(() =>
    hasAccess(['plugin.storage-billing.billing_admin:view']),
  );
  const canConfigureAdmin = computed(() =>
    hasAccess(['plugin.storage-billing.billing_admin:configure']),
  );
  const canReconcileAdmin = computed(() =>
    hasAccess(['plugin.storage-billing.billing_admin:reconcile']),
  );

  function providerLabel(code: ProviderCode): string {
    return $t(`plugin.storage-billing.common.provider.${code}`);
  }

  function providerLabelFromAny(code: string): string {
    return PROVIDERS.includes(code as ProviderCode)
      ? providerLabel(code as ProviderCode)
      : code || '-';
  }

  const activeConfiguredProviderCode = computed<null | ProviderCode>(() => {
    const rawDriver =
      overview.value?.host_snapshot.active_storage_driver
      ?? overview.value?.host_snapshot.platform_storage_context?.storage_config?.driver
      ?? '';
    const normalized = String(rawDriver || '').trim();
    return PROVIDERS.includes(normalized as ProviderCode)
      ? (normalized as ProviderCode)
      : null;
  });

  const visibleProviderCodes = computed<ProviderCode[]>(() =>
    activeConfiguredProviderCode.value ? [activeConfiguredProviderCode.value] : [],
  );

  async function loadAll(): Promise<void> {
    if (!canViewAdmin.value) {
      overview.value = null;
      bindings.value = [];
      runs.value = [];
      bindingsWorkflow.bindingOpen.value = false;
      selectedRunId.value = null;
      selectedRunDetail.value = null;
      selectedRunChargeResponse.value = null;
      selectedRunCharges.value = [];
      return;
    }

    loading.value = true;
    try {
      const [nextOverview, nextProfiles, nextBindings, nextRuns] = await Promise.all([
        getOverviewApi(),
        listProviderProfilesApi(),
        listBindingsApi(),
        listReconciliationRunsApi(RUN_HISTORY_LIMIT),
      ]);
      overview.value = nextOverview;
      bindings.value = nextBindings.items ?? [];
      runs.value = nextRuns.items ?? nextOverview.ledger_snapshot.latest_runs ?? [];
      syncProfiles(nextProfiles);
      bindingsWorkflow.syncVisibleProviderSelection();
      manualProviderCodes.value = manualProviderCodes.value.filter((code) =>
        visibleProviderCodes.value.includes(code),
      );
      await syncSelectedRun(runs.value);
    } finally {
      loading.value = false;
    }
  }

  const bindingsWorkflow = useStorageBillingAdminBindings({
    canConfigureAdmin,
    loadAll,
    providerLabel,
    visibleProviderCodes,
  });

  const presenters = useStorageBillingAdminPresenters({
    manualBillingDate,
    overview,
    profiles,
    providerLabel,
    providerLabelFromAny,
    qiniuBillingMonth,
    validations,
    visibleProviderCodes,
  });

  const {
    auditedSources,
    currentRunChargeFilters,
    resetRunChargeFiltersState,
    runChargeActiveFilters,
    runChargeFilters,
    runChargeProviderOptions,
    runChargeSourceOptions,
    selectedRun,
    selectedRunProviderResults,
    sourceLabelFromCharge,
  } = useReconciliationRunDetail({
    providerLabelFromAny,
    selectedRunChargeResponse,
    selectedRunDetail,
  });

  const {
    applyRunChargeFilters,
    exportCurrentRunCharges,
    loadRunDetail,
    resetRunChargeFilters,
    triggerQiniuMonthlyRun,
    triggerRun,
  } = useStorageBillingAdminRunActions({
    canReconcileAdmin,
    canViewAdmin,
    currentRunChargeFilters,
    loadAll,
    manualBillingDate,
    manualBillingDateError: presenters.manualBillingDateError,
    manualProviderCodes,
    providerLabel,
    qiniuBillingMonth,
    qiniuMonthValid: presenters.qiniuMonthValid,
    resetRunChargeFiltersState,
    runChargeExporting,
    runChargeLoading,
    runDetailLoading,
    selectedRun,
    selectedRunChargeResponse,
    selectedRunCharges,
    selectedRunDetail,
    selectedRunId,
  });

  function syncProfiles(payload: ProviderProfileEnvelope): void {
    for (const code of PROVIDERS) {
      const nextState = buildMergedProviderState(code, payload);
      Object.assign(profiles[code], nextState.profile);
      Object.assign(validations[code], nextState.validation);
    }
  }

  async function syncSelectedRun(nextRuns: ReconciliationRun[]): Promise<void> {
    const nextRun = nextRuns.find((item) => item.id === selectedRunId.value) ?? nextRuns[0] ?? null;
    if (!nextRun) {
      selectedRunId.value = null;
      selectedRunDetail.value = null;
      selectedRunCharges.value = [];
      selectedRunChargeResponse.value = null;
      resetRunChargeFiltersState();
      return;
    }
    if (
      selectedRunId.value === nextRun.id
      && selectedRunDetail.value?.run.id === nextRun.id
    ) {
      return;
    }
    await loadRunDetail(nextRun.id);
  }

  async function saveProfiles(): Promise<void> {
    if (!canConfigureAdmin.value) return;
    if (!visibleProviderCodes.value.length) {
      message.warning($t('plugin.storage-billing.admin.providers.noActiveDriver'));
      return;
    }

    saving.value = true;
    try {
      const payload = await saveProviderProfilesApi({
        providers: Object.fromEntries(
          visibleProviderCodes.value.map((code) => [
            code,
            buildProviderPayload(profiles, code),
          ]),
        ),
      });
      syncProfiles(payload);
      message.success($t('plugin.storage-billing.admin.messages.saved'));
    } finally {
      saving.value = false;
    }
  }

  async function validateProvider(code: ProviderCode): Promise<void> {
    if (!canConfigureAdmin.value) return;
    const result = await validateProviderProfileApi(
      code,
      buildProviderPayload(profiles, code),
    );
    Object.assign(profiles[code], { ...profiles[code], ...result.profile });
    Object.assign(validations[code], { ...validations[code], ...result });
    message[result.status === 'valid' ? 'success' : 'warning'](
      $t(
        result.status === 'valid'
          ? 'plugin.storage-billing.admin.messages.providerValid'
          : 'plugin.storage-billing.admin.messages.providerInvalid',
      ),
    );
  }

  onMounted(() => void loadAll());

  return {
    applyRunChargeFilters,
    auditedSources,
    bindings,
    bindingsWorkflow,
    canConfigureAdmin,
    canReconcileAdmin,
    canViewAdmin,
    exportCurrentRunCharges,
    loadAll,
    loadRunDetail,
    loading,
    manualBillingDate,
    manualProviderCodes,
    overview,
    presenters,
    providerLabel,
    providerLabelFromAny,
    profiles,
    qiniuBillingMonth,
    resetRunChargeFilters,
    runChargeActiveFilters,
    runChargeExporting,
    runChargeFilters,
    runChargeLoading,
    runChargeProviderOptions,
    runChargeSourceOptions,
    runDetailLoading,
    runs,
    saveProfiles,
    selectedRun,
    selectedRunChargeResponse,
    selectedRunCharges,
    selectedRunDetail,
    selectedRunProviderResults,
    saving,
    sourceLabelFromCharge,
    triggerQiniuMonthlyRun,
    triggerRun,
    validateProvider,
    validations,
    visibleProviderCodes,
  };
}

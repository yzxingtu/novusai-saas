import type { ComputedRef, Ref } from 'vue';
import { Modal, message } from 'ant-design-vue';
import { $t, downloadBlob } from '@novus/plugin-shared';

import type {
  ProviderCode,
  ReconciliationChargeRow,
  ReconciliationRun,
  ReconciliationRunChargeListResponse,
  ReconciliationRunDetailResponse,
} from '../../types';
import {
  exportReconciliationRunChargesCsvApi,
  getReconciliationRunApi,
  getReconciliationRunChargesApi,
  runQiniuMonthlySettlementApi,
  runReconciliationApi,
} from '../../api/admin';

type RunFilterPayload = Record<string, unknown>;

type UseStorageBillingAdminRunActionsParams = {
  canReconcileAdmin: ComputedRef<boolean>;
  canViewAdmin: ComputedRef<boolean>;
  currentRunChargeFilters: () => RunFilterPayload;
  loadAll: () => Promise<void>;
  loadRunDetailAfterRefresh?: (runId: number) => Promise<void>;
  manualBillingDate: Ref<string>;
  manualBillingDateError: ComputedRef<null | string>;
  manualProviderCodes: Ref<ProviderCode[]>;
  providerLabel: (code: ProviderCode) => string;
  qiniuBillingMonth: Ref<string>;
  qiniuMonthValid: ComputedRef<boolean>;
  resetRunChargeFiltersState: () => void;
  runChargeExporting: Ref<boolean>;
  runChargeLoading: Ref<boolean>;
  runDetailLoading: Ref<boolean>;
  selectedRun: ComputedRef<null | ReconciliationRun>;
  selectedRunChargeResponse: Ref<null | ReconciliationRunChargeListResponse>;
  selectedRunCharges: Ref<ReconciliationChargeRow[]>;
  selectedRunDetail: Ref<null | ReconciliationRunDetailResponse>;
  selectedRunId: Ref<null | number>;
};

export function useStorageBillingAdminRunActions(
  params: UseStorageBillingAdminRunActionsParams,
) {
  async function loadRunCharges(runId: number): Promise<void> {
    if (!params.canViewAdmin.value) {
      params.selectedRunChargeResponse.value = null;
      params.selectedRunCharges.value = [];
      return;
    }
    params.runChargeLoading.value = true;
    try {
      const runCharges = await getReconciliationRunChargesApi(
        runId,
        params.currentRunChargeFilters(),
      );
      params.selectedRunChargeResponse.value = runCharges;
      params.selectedRunCharges.value = runCharges.items ?? [];
    } finally {
      params.runChargeLoading.value = false;
    }
  }

  async function loadRunDetail(runId: number): Promise<void> {
    if (!params.canViewAdmin.value) return;
    params.runDetailLoading.value = true;
    params.selectedRunId.value = runId;
    params.resetRunChargeFiltersState();
    try {
      const [runDetail, runCharges] = await Promise.all([
        getReconciliationRunApi(runId),
        getReconciliationRunChargesApi(runId),
      ]);
      params.selectedRunDetail.value = runDetail;
      params.selectedRunChargeResponse.value = runCharges;
      params.selectedRunCharges.value = runCharges.items ?? [];
    } finally {
      params.runDetailLoading.value = false;
    }
  }

  async function applyRunChargeFilters(): Promise<void> {
    if (!params.selectedRunId.value || !params.canViewAdmin.value) return;
    await loadRunCharges(params.selectedRunId.value);
  }

  async function resetRunChargeFilters(): Promise<void> {
    if (!params.canViewAdmin.value || !params.selectedRunId.value) {
      params.resetRunChargeFiltersState();
      params.selectedRunChargeResponse.value = null;
      params.selectedRunCharges.value = [];
      return;
    }
    params.resetRunChargeFiltersState();
    await loadRunCharges(params.selectedRunId.value);
  }

  async function exportCurrentRunCharges(): Promise<void> {
    if (!params.selectedRunId.value || !params.canViewAdmin.value) return;
    params.runChargeExporting.value = true;
    try {
      const blob = await exportReconciliationRunChargesCsvApi(
        params.selectedRunId.value,
        params.currentRunChargeFilters(),
      );
      const datePart = params.selectedRun.value?.billing_date || 'unknown';
      downloadBlob(blob, {
        filename: `storage-billing-run-${params.selectedRunId.value}-${datePart}.csv`,
      });
      message.success($t('plugin.storage-billing.admin.messages.exportSuccess'));
    } catch {
      message.error($t('plugin.storage-billing.admin.messages.requestFailed'));
    } finally {
      params.runChargeExporting.value = false;
    }
  }

  function triggerRun(): void {
    if (!params.canReconcileAdmin.value) return;
    if (params.manualBillingDateError.value) {
      message.error(params.manualBillingDateError.value);
      return;
    }

    const payload: { billing_date?: string; provider_codes?: string[] } = {};
    if (params.manualBillingDate.value) {
      payload.billing_date = params.manualBillingDate.value;
    }
    if (params.manualProviderCodes.value.length) {
      payload.provider_codes = [...params.manualProviderCodes.value];
    }

    const providerSummary = params.manualProviderCodes.value.length
      ? params.manualProviderCodes.value
          .map((code) => params.providerLabel(code))
          .join(' / ')
      : $t('plugin.storage-billing.admin.actions.providerAll');
    const billingDateSummary =
      params.manualBillingDate.value || $t('plugin.storage-billing.admin.actions.dailyAuto');

    Modal.confirm({
      title: $t('plugin.storage-billing.admin.actions.triggerRun'),
      content: `${$t('plugin.storage-billing.admin.actions.triggerRunHint')} (${billingDateSummary} / ${providerSummary})`,
      onOk: async () => {
        const result = await runReconciliationApi(payload);
        message.success($t('plugin.storage-billing.admin.messages.runTriggered'));
        await params.loadAll();
        const runId = Number((result.run as Record<string, unknown>)?.id ?? 0);
        if (runId > 0) {
          await (params.loadRunDetailAfterRefresh?.(runId) ?? loadRunDetail(runId));
        }
      },
    });
  }

  function triggerQiniuMonthlyRun(): void {
    if (!params.canReconcileAdmin.value) return;
    if (!params.qiniuMonthValid.value) {
      message.error($t('plugin.storage-billing.admin.actions.qiniuMonthlyInvalid'));
      return;
    }

    Modal.confirm({
      title: $t('plugin.storage-billing.admin.actions.triggerQiniuMonthly'),
      content: `${$t('plugin.storage-billing.admin.actions.triggerQiniuMonthlyHint')} (${params.qiniuBillingMonth.value || '-'})`,
      onOk: async () => {
        const result = await runQiniuMonthlySettlementApi({
          billing_month: params.qiniuBillingMonth.value,
        });
        message.success($t('plugin.storage-billing.admin.messages.runTriggered'));
        await params.loadAll();
        const runId = Number((result.run as Record<string, unknown>)?.id ?? 0);
        if (runId > 0) {
          await (params.loadRunDetailAfterRefresh?.(runId) ?? loadRunDetail(runId));
        }
      },
    });
  }

  return {
    applyRunChargeFilters,
    exportCurrentRunCharges,
    loadRunDetail,
    resetRunChargeFilters,
    triggerQiniuMonthlyRun,
    triggerRun,
  };
}

import type {
  ReconciliationChargeRow,
  ReconciliationProviderSummary,
  ReconciliationRun,
  ReconciliationRunChargeFilters,
  ReconciliationRunChargeListResponse,
  ReconciliationRunDetailResponse,
} from '../../types';
import { computed, reactive, type Ref } from 'vue';
import { $t } from '@novus/plugin-shared';

import {
  hasAuditSamples,
  normalizeNumber,
} from './reconciliation-helpers';

type ChargeFilterBadge = {
  key: string;
  label: string;
  value: string;
};

type UseReconciliationRunDetailOptions = {
  providerLabelFromAny: (code: string) => string;
  selectedRunChargeResponse: Ref<null | ReconciliationRunChargeListResponse>;
  selectedRunDetail: Ref<null | ReconciliationRunDetailResponse>;
};

export function useReconciliationRunDetail(
  options: UseReconciliationRunDetailOptions,
) {
  const runChargeFilters = reactive<{
    provider_code: string;
    source_id: null | number;
    tenant_id: string;
  }>({
    provider_code: '',
    source_id: null,
    tenant_id: '',
  });

  const selectedRun = computed<null | ReconciliationRun>(
    () => options.selectedRunDetail.value?.run ?? null,
  );

  const selectedRunProviderResults = computed<ReconciliationProviderSummary[]>(
    () => {
      const providers = selectedRun.value?.summary?.providers;
      return Array.isArray(providers) ? providers : [];
    },
  );

  const auditedSources = computed(() =>
    (options.selectedRunDetail.value?.sources ?? []).filter((source) =>
      hasAuditSamples(source),
    ),
  );

  const sourceById = computed(() => {
    const lookup = new Map<number, NonNullable<
      ReconciliationRunDetailResponse['sources']
    >[number]>();
    for (const source of options.selectedRunDetail.value?.sources ?? []) {
      lookup.set(source.id, source);
    }
    return lookup;
  });

  const runChargeProviderOptions = computed(() =>
    Array.from(
      new Set(
        (options.selectedRunDetail.value?.sources ?? [])
          .map((source) => source.provider_code)
          .filter((code) => Boolean(code)),
      ),
    ).map((code) => ({
      label: options.providerLabelFromAny(code),
      value: code,
    })),
  );

  const runChargeSourceOptions = computed(() =>
    (options.selectedRunDetail.value?.sources ?? []).map((source) => ({
      label: `${options.providerLabelFromAny(source.provider_code)} · ${
        source.source_ref || source.source_key || `#${source.id}`
      }`,
      value: source.id,
    })),
  );

  const runChargeActiveFilters = computed<ChargeFilterBadge[]>(() => {
    const filters = options.selectedRunChargeResponse.value?.filters;
    if (!filters || typeof filters !== 'object') {
      return [];
    }

    return Object.entries(filters).flatMap(([key, rawValue]) => {
      if (rawValue === undefined || rawValue === null || rawValue === '') {
        return [];
      }
      if (key === 'provider_code' && typeof rawValue === 'string') {
        return [{
          key,
          label: $t('plugin.storage-billing.admin.runs.charges.filterProvider'),
          value: options.providerLabelFromAny(rawValue),
        }];
      }
      if (key === 'source_id') {
        const sourceId = normalizeNumber(rawValue);
        if (sourceId === null) {
          return [];
        }
        return [{
          key,
          label: $t('plugin.storage-billing.admin.runs.charges.filterSource'),
          value: sourceById.value.get(sourceId)?.source_ref || `#${sourceId}`,
        }];
      }
      if (key === 'tenant_id') {
        const tenantId = normalizeNumber(rawValue);
        return tenantId === null
          ? []
          : [{
              key,
              label: $t('plugin.storage-billing.admin.runs.charges.filterTenant'),
              value: `#${tenantId}`,
            }];
      }
      return [{
        key,
        label: key,
        value: String(rawValue),
      }];
    });
  });

  function currentRunChargeFilters(): ReconciliationRunChargeFilters {
    const tenantId = Number(runChargeFilters.tenant_id.trim());
    return {
      provider_code: runChargeFilters.provider_code || undefined,
      source_id: runChargeFilters.source_id ?? undefined,
      tenant_id: Number.isFinite(tenantId) && tenantId > 0 ? tenantId : undefined,
    };
  }

  function resetRunChargeFiltersState(): void {
    runChargeFilters.provider_code = '';
    runChargeFilters.source_id = null;
    runChargeFilters.tenant_id = '';
  }

  function sourceLabelFromCharge(charge: ReconciliationChargeRow): string {
    const sourceId = Number(charge.source_id ?? 0);
    if (!sourceId) return '-';
    const source = sourceById.value.get(sourceId);
    if (!source) return `#${sourceId}`;
    return source.source_ref || source.source_key || `#${sourceId}`;
  }

  return {
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
  };
}

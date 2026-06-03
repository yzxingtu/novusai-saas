import type { ComputedRef, Ref } from 'vue';
import type {
  BindingRecord,
  OverviewResponse,
  ProviderCode,
  ProviderProfile,
  ProviderRuntimeStorageSnapshot,
  ProviderValidation,
  ReconciliationProviderSummary,
  ReconciliationRun,
} from '../../types';

import { computed } from 'vue';
import { $t } from '@novus/plugin-shared';

import {
  formatBytes as formatBytesText,
  formatTimestamp as formatTimestampText,
  runRequestedScope as parseRunRequestedScope,
  scopeProviderCodes as listScopeProviderCodes,
  scopeProviderPlans as listScopeProviderPlans,
  selectedRunScopePayload as buildSelectedRunScopePayload,
  selectedRunScopeSummary as buildSelectedRunScopeSummary,
  sourceAllocationAudit as readSourceAllocationAudit,
  sourceAllocationSummary as summarizeSourceAllocation,
} from './reconciliation-helpers';
import {
  isValidBillingDate,
  isValidYearMonth,
  uniqueStrings,
  type CapabilitySummary,
  type ProviderField,
} from './storage-billing-admin-contracts';

type UseStorageBillingAdminPresentersOptions = {
  manualBillingDate: Ref<string>;
  overview: Ref<null | OverviewResponse>;
  profiles: Record<ProviderCode, ProviderProfile>;
  providerLabel: (code: ProviderCode) => string;
  providerLabelFromAny: (code: string) => string;
  qiniuBillingMonth: Ref<string>;
  validations: Record<ProviderCode, ProviderValidation>;
  visibleProviderCodes: ComputedRef<ProviderCode[]>;
};

export function useStorageBillingAdminPresenters(
  options: UseStorageBillingAdminPresentersOptions,
) {
  const bindingColumns = computed(() => [
    { key: 'tenant', title: $t('plugin.storage-billing.admin.bindings.table.tenant') },
    { key: 'provider', title: $t('plugin.storage-billing.admin.bindings.table.provider') },
    { key: 'mode', title: $t('plugin.storage-billing.admin.bindings.table.mode') },
    { key: 'scope', title: $t('plugin.storage-billing.admin.bindings.table.scope') },
    { key: 'status', title: $t('plugin.storage-billing.admin.bindings.table.status') },
    { key: 'message', title: $t('plugin.storage-billing.admin.bindings.table.message') },
    { key: 'actions', title: $t('plugin.storage-billing.admin.bindings.table.actions') },
  ]);

  const runColumns = computed(() => [
    { key: 'billing_date', title: $t('plugin.storage-billing.admin.runs.table.billingDate') },
    { key: 'status', title: $t('plugin.storage-billing.admin.runs.table.status') },
    { key: 'trigger_type', title: $t('plugin.storage-billing.admin.runs.table.trigger') },
    { key: 'providers', title: $t('plugin.storage-billing.admin.runs.table.providers') },
    { key: 'finished_at', title: $t('plugin.storage-billing.admin.runs.table.finishedAt') },
    { key: 'actions', title: $t('plugin.storage-billing.admin.runs.table.actions') },
  ]);

  const sourceColumns = computed(() => [
    { key: 'provider', title: $t('plugin.storage-billing.admin.runs.sources.table.provider') },
    { key: 'status', title: $t('plugin.storage-billing.admin.runs.sources.table.status') },
    { key: 'amount', title: $t('plugin.storage-billing.admin.runs.sources.table.amount') },
    { key: 'usage', title: $t('plugin.storage-billing.admin.runs.sources.table.usage') },
    { key: 'allocation', title: $t('plugin.storage-billing.admin.runs.sources.table.allocation') },
    { key: 'error', title: $t('plugin.storage-billing.admin.runs.sources.table.error') },
  ]);

  const chargeColumns = computed(() => [
    { key: 'billing_date', title: $t('plugin.storage-billing.admin.runs.charges.table.billingDate') },
    { key: 'tenant_id', title: $t('plugin.storage-billing.admin.runs.charges.table.tenant') },
    { key: 'provider', title: $t('plugin.storage-billing.admin.runs.charges.table.provider') },
    { key: 'source', title: $t('plugin.storage-billing.admin.runs.charges.table.source') },
    { key: 'charge_basis', title: $t('plugin.storage-billing.admin.runs.charges.table.chargeBasis') },
    { key: 'usage_bytes', title: $t('plugin.storage-billing.admin.runs.charges.table.usage') },
    { key: 'amount_total', title: $t('plugin.storage-billing.admin.runs.charges.table.amount') },
    { key: 'currency', title: $t('plugin.storage-billing.admin.runs.charges.table.currency') },
  ]);

  const qiniuMonthValid = computed(() =>
    isValidYearMonth(options.qiniuBillingMonth.value),
  );

  const qiniuMonthError = computed(() => {
    if (!options.qiniuBillingMonth.value) return null;
    return qiniuMonthValid.value
      ? null
      : $t('plugin.storage-billing.admin.actions.qiniuMonthlyInvalid');
  });

  const qiniuMonthStatus = computed(() => {
    if (!options.qiniuBillingMonth.value) return undefined;
    return qiniuMonthValid.value ? undefined : 'error';
  });

  const manualBillingDateValid = computed(
    () => !options.manualBillingDate.value || isValidBillingDate(options.manualBillingDate.value),
  );

  const manualBillingDateError = computed(() => {
    if (!options.manualBillingDate.value) return null;
    return manualBillingDateValid.value
      ? null
      : $t('plugin.storage-billing.admin.actions.dailyInvalid');
  });

  const manualBillingDateStatus = computed(() => {
    if (!options.manualBillingDate.value) return undefined;
    return manualBillingDateValid.value ? undefined : 'error';
  });

  const manualRunHelpText = computed(
    () =>
      manualBillingDateError.value
      || $t('plugin.storage-billing.admin.actions.triggerRunHint'),
  );

  const hasVisibleProviders = computed(
    () => options.visibleProviderCodes.value.length > 0,
  );

  const qiniuVisible = computed(() =>
    options.visibleProviderCodes.value.includes('qiniu-kodo'),
  );

  function fieldLabel(field: ProviderField): string {
    return $t(`plugin.storage-billing.admin.field.${field}`);
  }

  function prettyStatus(status: string): string {
    const normalized = (status || '').trim();
    const dictionary = new Set([
      'valid',
      'invalid',
      'pending',
      'completed',
      'completed_with_gaps',
      'failed',
      'running',
      'skipped',
      'fetched',
      'empty',
      'not_implemented',
    ]);
    if (dictionary.has(normalized)) {
      return $t(`plugin.storage-billing.common.status.${normalized}`);
    }
    return normalized || '-';
  }

  function statusColor(status: string): string {
    if (['valid', 'completed', 'fetched'].includes(status)) return 'success';
    if (['invalid', 'failed'].includes(status)) return 'error';
    if (['running', 'pending'].includes(status)) return 'processing';
    if (['completed_with_gaps', 'not_implemented'].includes(status)) return 'warning';
    return 'default';
  }

  function profileWarnings(code: ProviderCode): string {
    return [...options.validations[code].errors, ...options.validations[code].warnings].join(' | ');
  }

  function providerStorageContext(code: ProviderCode): ProviderRuntimeStorageSnapshot {
    const profileContext = options.profiles[code].storage_context;
    if (profileContext) {
      return profileContext;
    }

    const platformContext = options.overview.value?.host_snapshot.platform_storage_context;
    const storageConfig = platformContext?.storage_config;
    return {
      source: 'platform_storage',
      storage_mode: platformContext?.storage_mode,
      current_driver:
        options.overview.value?.host_snapshot.active_storage_driver
        ?? storageConfig?.driver
        ?? '',
      driver_match: false,
      bucket_name:
        String(storageConfig?.options?.bucket || storageConfig?.root_path || '').trim()
        || null,
      root_path: storageConfig?.root_path ?? null,
      base_url: storageConfig?.base_url ?? null,
      region: String(storageConfig?.options?.region || '').trim() || null,
      endpoint: String(storageConfig?.options?.endpoint || '').trim() || null,
      prefix: String(storageConfig?.options?.prefix || '').trim() || null,
    };
  }

  function providerStorageMatch(code: ProviderCode): boolean {
    return Boolean(
      options.validations[code].storage_driver_match
      ?? options.profiles[code].storage_driver_match
      ?? providerStorageContext(code).driver_match,
    );
  }

  function providerStorageReady(code: ProviderCode): boolean {
    return Boolean(
      options.validations[code].host_credentials_configured
      ?? options.profiles[code].host_credentials_configured,
    );
  }

  function providerRuntimeValue(value: null | string | undefined): string {
    const normalized = String(value || '').trim();
    return normalized || '-';
  }

  function buildCapabilitySummary(code: ProviderCode): CapabilitySummary {
    const overviewCaps = options.overview.value?.provider_capabilities?.[code];
    const profileCaps = options.profiles[code];
    const validationCaps = options.validations[code];
    const supportedPeriods =
      overviewCaps?.supported_period_types
      ?? profileCaps.supported_period_types
      ?? validationCaps.supported_period_types
      ?? [];
    const recommendedScopes = uniqueStrings([
      ...(profileCaps.recommended_scope_types ?? []),
      ...(validationCaps.recommended_scope_types ?? []),
    ]).filter((item): item is CapabilitySummary['recommended_scope_types'][number] =>
      ['bucket', 'domain', 'account', 'tag'].includes(item),
    );

    return {
      settlement_mode:
        overviewCaps?.settlement_mode
        ?? profileCaps.settlement_mode
        ?? validationCaps.settlement_mode,
      settlement_cycle:
        overviewCaps?.settlement_cycle
        ?? profileCaps.settlement_cycle
        ?? validationCaps.settlement_cycle,
      official_billing_lag_days:
        overviewCaps?.official_billing_lag_days
        ?? profileCaps.official_billing_lag_days
        ?? validationCaps.official_billing_lag_days,
      official_target_rule:
        overviewCaps?.official_target_rule
        ?? profileCaps.official_target_rule
        ?? validationCaps.official_target_rule,
      recommended_scope_types: recommendedScopes,
      supported_period_types: supportedPeriods,
      strict_reconciliation_supported:
        overviewCaps?.strict_reconciliation_supported
        ?? profileCaps.strict_reconciliation_supported
        ?? validationCaps.strict_reconciliation_supported,
      manual_pull_supported:
        overviewCaps?.manual_pull_supported
        ?? profileCaps.manual_pull_supported
        ?? validationCaps.manual_pull_supported,
      scheduled_daily_supported:
        overviewCaps?.scheduled_daily_supported
        ?? profileCaps.scheduled_daily_supported
        ?? validationCaps.scheduled_daily_supported,
    };
  }

  function capabilityModeLabel(value?: string): null | string {
    if (!value) return null;
    const map: Record<string, string> = {
      strict_daily_reconciliation: $t('plugin.storage-billing.common.capabilities.mode.strictDailyReconciliation'),
      monthly_settled: $t('plugin.storage-billing.common.capabilities.mode.monthlySettled'),
    };
    return map[value] ?? value;
  }

  function capabilityCycleLabel(value?: string): null | string {
    if (!value) return null;
    const map: Record<string, string> = {
      daily: $t('plugin.storage-billing.common.capabilities.cycle.daily'),
      monthly: $t('plugin.storage-billing.common.capabilities.cycle.monthly'),
    };
    return map[value] ?? value;
  }

  function capabilityPeriodLabel(value?: string): null | string {
    if (!value) return null;
    const map: Record<string, string> = {
      daily: $t('plugin.storage-billing.common.periodType.daily'),
      monthly: $t('plugin.storage-billing.common.periodType.monthly'),
    };
    return map[value] ?? value;
  }

  function capabilityTargetRuleLabel(value?: string): string {
    if (!value) return '-';
    if (value === 'per-provider') {
      return $t('plugin.storage-billing.common.capabilities.targetRule.perProvider');
    }
    return value;
  }

  function capabilityFlagLabel(key: 'manual' | 'scheduled' | 'strict'): string {
    if (key === 'strict') {
      return $t('plugin.storage-billing.common.capabilities.strictDailySupported');
    }
    if (key === 'manual') {
      return $t('plugin.storage-billing.common.capabilities.manualPullSupported');
    }
    return $t('plugin.storage-billing.common.capabilities.scheduledDailySupported');
  }

  function providerCapabilitySummary(code: ProviderCode): CapabilitySummary {
    return buildCapabilitySummary(code);
  }

  function providerCapabilityTags(code: ProviderCode): string[] {
    const summary = providerCapabilitySummary(code);
    const tags: string[] = [];
    if (summary.manual_pull_supported) {
      tags.push(capabilityFlagLabel('manual'));
    }
    if (summary.strict_reconciliation_supported) {
      tags.push(capabilityFlagLabel('strict'));
    }
    if (summary.scheduled_daily_supported) {
      tags.push(capabilityFlagLabel('scheduled'));
    }
    return tags;
  }

  const reconciliationScheduleSummary = computed(() => {
    const providerRules = options.overview.value?.reconciliation_schedule.provider_rules ?? {};
    const entries = Object.entries(providerRules);
    if (!entries.length) {
      return capabilityTargetRuleLabel(
        options.overview.value?.reconciliation_schedule.official_target_rule,
      );
    }
    return entries
      .map(
        ([providerCode, rule]) =>
          `${options.providerLabelFromAny(providerCode)} ${capabilityTargetRuleLabel(rule?.official_target_rule)}`,
      )
      .join(' / ');
  });

  const manualRunProviderOptions = computed(() =>
    options.visibleProviderCodes.value
      .filter((code) => providerCapabilitySummary(code).scheduled_daily_supported)
      .map((code) => ({
        label: options.providerLabel(code),
        value: code,
      })),
  );

  function billSourceOptions(code: ProviderCode): Array<{ label: string; value: string }> {
    return uniqueStrings([
      ...(options.profiles[code].supported_bill_sources ?? []),
      ...(options.validations[code].supported_bill_sources ?? []),
      options.profiles[code].bill_source,
    ]).map((item) => ({ label: item, value: item }));
  }

  function scopeValue(record: BindingRecord): string {
    if (record.scope_type === 'bucket') return record.bucket_name ?? record.scope_value;
    if (record.scope_type === 'domain') return record.domain_name ?? record.scope_value;
    if (record.scope_type === 'account') return record.account_identifier ?? record.scope_value;
    if (record.tag_key && record.tag_value) return `${record.tag_key}:${record.tag_value}`;
    return record.scope_value;
  }

  const formatTimestamp = formatTimestampText;
  const formatBytes = (value: null | number | undefined): string =>
    formatBytesText(value ?? 0);
  const sourceAllocationSummary = summarizeSourceAllocation;
  const sourceAllocationAudit = readSourceAllocationAudit;
  const runRequestedScope = parseRunRequestedScope;
  const scopeProviderCodes = listScopeProviderCodes;
  const scopeProviderPlans = listScopeProviderPlans;
  const selectedRunScopePayload = buildSelectedRunScopePayload;

  function chargeBasisLabel(basis: string): string {
    const key = `plugin.storage-billing.common.chargeBasis.${basis}`;
    const translated = $t(key);
    return translated === key ? basis : translated;
  }

  function runProviderSummaries(run: ReconciliationRun): ReconciliationProviderSummary[] {
    return Array.isArray(run.summary?.providers) ? run.summary.providers : [];
  }

  function selectedRunScopeSummary(run: ReconciliationRun): string {
    return buildSelectedRunScopeSummary(run, options.providerLabelFromAny);
  }

  return {
    billSourceOptions,
    bindingColumns,
    capabilityCycleLabel,
    capabilityModeLabel,
    capabilityPeriodLabel,
    capabilityTargetRuleLabel,
    chargeBasisLabel,
    chargeColumns,
    fieldLabel,
    formatBytes,
    formatTimestamp,
    hasVisibleProviders,
    manualBillingDateError,
    manualBillingDateStatus,
    manualRunHelpText,
    manualRunProviderOptions,
    prettyStatus,
    profileWarnings,
    providerCapabilitySummary,
    providerCapabilityTags,
    providerRuntimeValue,
    providerStorageContext,
    providerStorageMatch,
    providerStorageReady,
    qiniuMonthError,
    qiniuMonthStatus,
    qiniuMonthValid,
    qiniuVisible,
    reconciliationScheduleSummary,
    runColumns,
    runProviderSummaries,
    runRequestedScope,
    scopeProviderCodes,
    scopeProviderPlans,
    scopeValue,
    selectedRunScopePayload,
    selectedRunScopeSummary,
    sourceAllocationAudit,
    sourceAllocationSummary,
    sourceColumns,
    statusColor,
  };
}

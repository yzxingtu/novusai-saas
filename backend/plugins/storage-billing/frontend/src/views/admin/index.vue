<script lang="ts" setup>
import type {
  BillingMode,
  BindingPayload,
  BindingRecord,
  BindingScopeType,
  OverviewResponse,
  PeriodType,
  ProviderCode,
  ProviderProfile,
  ProviderRuntimeStorageSnapshot,
  ProviderValidation,
  ReconciliationChargeRow,
  ReconciliationProviderPlan,
  ReconciliationRequestedScope,
  ReconciliationRunChargeFilters,
  ReconciliationRunChargeListResponse,
  ReconciliationProviderSummary,
  ReconciliationRun,
  ReconciliationRunDetailResponse,
  ReconciliationSourceRecord,
  TenantSelectOption,
} from '../../types';
import { computed, onMounted, reactive, ref } from 'vue';
import { Page } from '@vben/common-ui';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  FormItem,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  message,
} from 'ant-design-vue';
import { $t, downloadBlob } from '@novus/plugin-shared';
import {
  createBindingApi,
  exportReconciliationRunChargesCsvApi,
  getOverviewApi,
  getReconciliationRunChargesApi,
  getReconciliationRunApi,
  getTenantSelectOptionsApi,
  listBindingsApi,
  listProviderProfilesApi,
  listReconciliationRunsApi,
  runReconciliationApi,
  runQiniuMonthlySettlementApi,
  saveProviderProfilesApi,
  updateBindingApi,
  validateBindingApi,
  validateProviderProfileApi,
} from '../../api/admin';

defineOptions({ name: 'StorageBillingAdminPage' });

type ProviderField =
  | 'account_identifier'
  | 'bill_source'
  | 'profile_code';

type BindingFormState = {
  account_identifier: string;
  billing_mode: BillingMode;
  bucket_name: string;
  domain_name: string;
  is_active: boolean;
  provider_code: ProviderCode;
  scope_type: BindingScopeType;
  tag_key: string;
  tag_value: string;
  tenant_id: null | number;
};

type AllocationSummary = {
  ambiguous_items: number;
  matched_items: number;
  unmatched_items: number;
  written_charge_rows: number;
};

type AllocationAudit = {
  ambiguous_item_samples: unknown[];
  unmatched_item_samples: unknown[];
};

type ChargeFilterBadge = {
  key: string;
  label: string;
  value: string;
};

const providers: ProviderCode[] = ['qiniu-kodo', 'aliyun-oss', 'tencent-cos'];
const profileCodeMap: Record<ProviderCode, string> = {
  'qiniu-kodo': 'qiniu-default',
  'aliyun-oss': 'aliyun-default',
  'tencent-cos': 'tencent-default',
};
const profileFields: Record<ProviderCode, readonly ProviderField[]> = {
  'qiniu-kodo': ['profile_code', 'bill_source', 'account_identifier'],
  'aliyun-oss': ['profile_code', 'bill_source', 'account_identifier'],
  'tencent-cos': ['profile_code', 'bill_source', 'account_identifier'],
};
const RUN_HISTORY_LIMIT = 10;

const overview = ref<null | OverviewResponse>(null);
const loading = ref(false);
const saving = ref(false);
const bindingOpen = ref(false);
const bindingLoading = ref(false);
const editingId = ref<null | number>(null);
const bindings = ref<BindingRecord[]>([]);
const tenants = ref<TenantSelectOption[]>([]);
const runs = ref<ReconciliationRun[]>([]);
const runDetailLoading = ref(false);
const selectedRunId = ref<null | number>(null);
const selectedRunDetail = ref<null | ReconciliationRunDetailResponse>(null);
const runChargeLoading = ref(false);
const runChargeExporting = ref(false);
const qiniuBillingMonth = ref(new Date(Date.now() - 32 * 24 * 60 * 60 * 1000).toISOString().slice(0, 7));
const qiniuMonthValid = computed(() => isValidYearMonth(qiniuBillingMonth.value));
const qiniuMonthError = computed(() => {
  if (!qiniuBillingMonth.value) return null;
  return qiniuMonthValid.value ? null : $t('plugin.storage-billing.admin.actions.qiniuMonthlyInvalid');
});
const qiniuMonthStatus = computed(() => {
  if (!qiniuBillingMonth.value) return undefined;
  return qiniuMonthValid.value ? undefined : 'error';
});
const selectedRunCharges = ref<ReconciliationChargeRow[]>([]);
const selectedRunChargeResponse = ref<null | ReconciliationRunChargeListResponse>(null);
const runChargeFilters = reactive<{
  provider_code: string;
  source_id: null | number;
  tenant_id: string;
}>({
  provider_code: '',
  source_id: null,
  tenant_id: '',
});

const profiles = reactive<Record<ProviderCode, ProviderProfile>>(emptyProfiles());
const validations = reactive<Record<ProviderCode, ProviderValidation>>(emptyValidations());
const form = reactive<BindingFormState>(emptyForm());

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
const activeConfiguredProviderCode = computed<null | ProviderCode>(() => {
  const rawDriver =
    overview.value?.host_snapshot.active_storage_driver ??
    overview.value?.host_snapshot.platform_storage_context?.storage_config?.driver ??
    '';
  const normalized = String(rawDriver || '').trim();
  return providers.includes(normalized as ProviderCode) ? (normalized as ProviderCode) : null;
});
const visibleProviderCodes = computed<ProviderCode[]>(() =>
  activeConfiguredProviderCode.value ? [activeConfiguredProviderCode.value] : [],
);
const providerOptions = computed(() =>
  visibleProviderCodes.value.map((code) => ({ label: providerLabel(code), value: code })),
);
const modeOptions = computed(() => [
  { label: $t('plugin.storage-billing.admin.bindings.mode.official_reconciled'), value: 'official_reconciled' },
  { label: $t('plugin.storage-billing.admin.bindings.mode.official_pass_through'), value: 'official_pass_through' },
]);
const scopeOptions = computed(() => [
  { label: $t('plugin.storage-billing.admin.bindings.scope.bucket'), value: 'bucket' },
  { label: $t('plugin.storage-billing.admin.bindings.scope.domain'), value: 'domain' },
  { label: $t('plugin.storage-billing.admin.bindings.scope.account'), value: 'account' },
  { label: $t('plugin.storage-billing.admin.bindings.scope.tag'), value: 'tag' },
]);
const currentModeOptions = computed(() =>
  form.provider_code === 'qiniu-kodo'
    ? modeOptions.value.filter((item) => item.value === 'official_reconciled')
    : modeOptions.value,
);
const currentScopeOptions = computed(() =>
  form.provider_code === 'qiniu-kodo'
    ? scopeOptions.value.filter((item) => item.value === 'account')
    : scopeOptions.value,
);
const modalTitle = computed(() => editingId.value === null ? $t('plugin.storage-billing.admin.bindingModal.createTitle') : $t('plugin.storage-billing.admin.bindingModal.editTitle'));
const modalOkText = computed(() => editingId.value === null ? $t('plugin.storage-billing.admin.bindingModal.submitCreate') : $t('plugin.storage-billing.admin.bindingModal.submitUpdate'));
const selectedRun = computed(() => selectedRunDetail.value?.run ?? null);
const selectedRunProviderResults = computed<ReconciliationProviderSummary[]>(() => {
  const providers = selectedRun.value?.summary?.providers;
  return Array.isArray(providers) ? providers : [];
});
const auditedSources = computed(() =>
  (selectedRunDetail.value?.sources ?? []).filter((source) => hasAuditSamples(source)),
);
const overviewRuns = computed(() => overview.value?.ledger_snapshot.latest_runs ?? []);
const sourceById = computed(() => {
  const lookup = new Map<number, ReconciliationSourceRecord>();
  for (const source of selectedRunDetail.value?.sources ?? []) {
    lookup.set(source.id, source);
  }
  return lookup;
});
const runChargeProviderOptions = computed(() =>
  Array.from(
    new Set(
      (selectedRunDetail.value?.sources ?? [])
        .map((source) => source.provider_code)
        .filter((code) => Boolean(code)),
    ),
  ).map((code) => ({
    label: providerLabelFromAny(code),
    value: code,
  })),
);
const runChargeSourceOptions = computed(() =>
  (selectedRunDetail.value?.sources ?? []).map((source) => ({
    label: `${providerLabelFromAny(source.provider_code)} · ${
      source.source_ref || source.source_key || `#${source.id}`
    }`,
    value: source.id,
  })),
);
const runChargeActiveFilters = computed<ChargeFilterBadge[]>(() => {
  const filters = selectedRunChargeResponse.value?.filters;
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
        value: providerLabelFromAny(rawValue),
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

function emptyProfile(code: ProviderCode): ProviderProfile {
  return { enabled: false, bill_source: '', profile_code: profileCodeMap[code], configured_fields: {}, configured_secret_fields: {}, required_fields: [], supported_bill_sources: [] };
}

function emptyValidation(): ProviderValidation {
  return { collector_ready: false, errors: [], profile_valid: false, required_fields: [], status: 'pending', supported_bill_sources: [], warnings: [] };
}

function emptyProfiles(): Record<ProviderCode, ProviderProfile> {
  return { 'qiniu-kodo': emptyProfile('qiniu-kodo'), 'aliyun-oss': emptyProfile('aliyun-oss'), 'tencent-cos': emptyProfile('tencent-cos') };
}

function emptyValidations(): Record<ProviderCode, ProviderValidation> {
  return { 'qiniu-kodo': emptyValidation(), 'aliyun-oss': emptyValidation(), 'tencent-cos': emptyValidation() };
}

function emptyForm(): BindingFormState {
  return { account_identifier: '', billing_mode: 'official_reconciled', bucket_name: '', domain_name: '', is_active: true, provider_code: 'tencent-cos', scope_type: 'bucket', tag_key: '', tag_value: '', tenant_id: null };
}

function unique(values: Array<null | string | undefined>): string[] {
  return Array.from(new Set(values.map((item) => (item ?? '').trim()).filter((item) => item)));
}

function syncProfiles(payload: { providers: Partial<Record<ProviderCode, ProviderProfile>>; validations: Partial<Record<ProviderCode, ProviderValidation>> }): void {
  for (const code of providers) {
    const nextProfile = { ...emptyProfile(code), ...(payload.providers[code] ?? {}) };
    const nextValidation = { ...emptyValidation(), ...(payload.validations[code] ?? {}) };
    nextProfile.required_fields = unique([...(nextProfile.required_fields ?? []), ...(nextValidation.required_fields ?? [])]);
    nextProfile.supported_bill_sources = unique([...(nextProfile.supported_bill_sources ?? []), ...(nextValidation.supported_bill_sources ?? []), nextProfile.bill_source]);
    nextValidation.required_fields = unique([...(nextValidation.required_fields ?? []), ...(nextProfile.required_fields ?? [])]);
    nextValidation.supported_bill_sources = unique([...(nextValidation.supported_bill_sources ?? []), ...(nextProfile.supported_bill_sources ?? []), nextProfile.bill_source]);
    Object.assign(profiles[code], nextProfile);
    Object.assign(validations[code], nextValidation);
  }
}

function providerLabel(code: ProviderCode): string {
  return $t(`plugin.storage-billing.common.provider.${code}`);
}

function providerLabelFromAny(code: string): string {
  return providers.includes(code as ProviderCode) ? providerLabel(code as ProviderCode) : code || '-';
}

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
  return [...validations[code].errors, ...validations[code].warnings].join(' | ');
}

function providerStorageContext(code: ProviderCode): ProviderRuntimeStorageSnapshot {
  const profileContext = profiles[code].storage_context;
  if (profileContext) {
    return profileContext;
  }
  const platformContext = overview.value?.host_snapshot.platform_storage_context;
  const storageConfig = platformContext?.storage_config;
  return {
    source: 'platform_storage',
    storage_mode: platformContext?.storage_mode,
    current_driver: overview.value?.host_snapshot.active_storage_driver ?? storageConfig?.driver ?? '',
    driver_match: false,
    bucket_name: String(storageConfig?.options?.bucket || storageConfig?.root_path || '').trim() || null,
    root_path: storageConfig?.root_path ?? null,
    base_url: storageConfig?.base_url ?? null,
    region: String(storageConfig?.options?.region || '').trim() || null,
    endpoint: String(storageConfig?.options?.endpoint || '').trim() || null,
    prefix: String(storageConfig?.options?.prefix || '').trim() || null,
  };
}

function providerStorageMatch(code: ProviderCode): boolean {
  return Boolean(
    validations[code].storage_driver_match ??
      profiles[code].storage_driver_match ??
      providerStorageContext(code).driver_match,
  );
}

function providerStorageReady(code: ProviderCode): boolean {
  return Boolean(
    validations[code].host_credentials_configured ??
      profiles[code].host_credentials_configured,
  );
}

function providerRuntimeValue(value: null | string | undefined): string {
  const normalized = String(value || '').trim();
  return normalized || '-';
}

const YEAR_MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;
const BILLING_DATE_PATTERN = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

type CapabilitySummary = {
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  recommended_scope_types: BindingScopeType[];
  settlement_mode?: string;
  settlement_cycle?: string;
  supported_period_types: PeriodType[];
  strict_reconciliation_supported?: boolean;
  manual_pull_supported?: boolean;
  scheduled_daily_supported?: boolean;
};

function isValidYearMonth(value: string): boolean {
  return YEAR_MONTH_PATTERN.test(value);
}

function isValidBillingDate(value: string): boolean {
  return BILLING_DATE_PATTERN.test(value);
}

function buildCapabilitySummary(code: ProviderCode): CapabilitySummary {
  const overviewCaps = overview.value?.provider_capabilities?.[code];
  const profileCaps = profiles[code];
  const validationCaps = validations[code];
  const supportedPeriods =
    overviewCaps?.supported_period_types ??
    profileCaps.supported_period_types ??
    validationCaps.supported_period_types ??
    [];
  const recommendedScopes = unique([
    ...((profileCaps.recommended_scope_types ?? []) as string[]),
    ...((validationCaps.recommended_scope_types ?? []) as string[]),
  ]).filter((item): item is BindingScopeType =>
    ['bucket', 'domain', 'account', 'tag'].includes(item),
  );

  return {
    settlement_mode:
      overviewCaps?.settlement_mode ?? profileCaps.settlement_mode ?? validationCaps.settlement_mode,
    settlement_cycle:
      overviewCaps?.settlement_cycle ?? profileCaps.settlement_cycle ?? validationCaps.settlement_cycle,
    official_billing_lag_days:
      overviewCaps?.official_billing_lag_days ??
      profileCaps.official_billing_lag_days ??
      validationCaps.official_billing_lag_days,
    official_target_rule:
      overviewCaps?.official_target_rule ??
      profileCaps.official_target_rule ??
      validationCaps.official_target_rule,
    recommended_scope_types: recommendedScopes,
    supported_period_types: supportedPeriods as PeriodType[],
    strict_reconciliation_supported:
      overviewCaps?.strict_reconciliation_supported ??
      profileCaps.strict_reconciliation_supported ??
      validationCaps.strict_reconciliation_supported,
    manual_pull_supported:
      overviewCaps?.manual_pull_supported ??
      profileCaps.manual_pull_supported ??
      validationCaps.manual_pull_supported,
    scheduled_daily_supported:
      overviewCaps?.scheduled_daily_supported ??
      profileCaps.scheduled_daily_supported ??
      validationCaps.scheduled_daily_supported,
  };
}

const providerCapabilitySummaries = computed<Record<ProviderCode, CapabilitySummary>>(() =>
  Object.fromEntries(providers.map((code) => [code, buildCapabilitySummary(code)])) as Record<ProviderCode, CapabilitySummary>,
);
const manualBillingDate = ref('');
const manualProviderCodes = ref<ProviderCode[]>([]);
const manualBillingDateValid = computed(() => !manualBillingDate.value || isValidBillingDate(manualBillingDate.value));
const manualBillingDateError = computed(() => {
  if (!manualBillingDate.value) return null;
  return manualBillingDateValid.value ? null : $t('plugin.storage-billing.admin.actions.dailyInvalid');
});
const manualBillingDateStatus = computed(() => {
  if (!manualBillingDate.value) return undefined;
  return manualBillingDateValid.value ? undefined : 'error';
});
const manualRunHelpText = computed(
  () => manualBillingDateError.value || $t('plugin.storage-billing.admin.actions.triggerRunHint'),
);

function capabilityModeLabel(value?: string): string | null {
  if (!value) return null;
  const map: Record<string, string> = {
    strict_daily_reconciliation: $t('plugin.storage-billing.common.capabilities.mode.strictDailyReconciliation'),
    monthly_settled: $t('plugin.storage-billing.common.capabilities.mode.monthlySettled'),
  };
  return map[value] ?? value;
}

function capabilityCycleLabel(value?: string): string | null {
  if (!value) return null;
  const map: Record<string, string> = {
    daily: $t('plugin.storage-billing.common.capabilities.cycle.daily'),
    monthly: $t('plugin.storage-billing.common.capabilities.cycle.monthly'),
  };
  return map[value] ?? value;
}

function capabilityPeriodLabel(value?: PeriodType | string): string | null {
  if (!value) return null;
  const map: Record<PeriodType, string> = {
    daily: $t('plugin.storage-billing.common.periodType.daily'),
    monthly: $t('plugin.storage-billing.common.periodType.monthly'),
  };
  return map[value as PeriodType] ?? value;
}

function capabilityTargetRuleLabel(value?: string): string {
  if (!value) return '-';
  if (value === 'per-provider') {
    return $t('plugin.storage-billing.common.capabilities.targetRule.perProvider');
  }
  return value;
}

function capabilityFlagLabel(key: 'strict' | 'manual' | 'scheduled'): string {
  if (key === 'strict') {
    return $t('plugin.storage-billing.common.capabilities.strictDailySupported');
  }
  if (key === 'manual') {
    return $t('plugin.storage-billing.common.capabilities.manualPullSupported');
  }
  return $t('plugin.storage-billing.common.capabilities.scheduledDailySupported');
}

function providerCapabilitySummary(code: ProviderCode): CapabilitySummary {
  return providerCapabilitySummaries.value[code];
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
  const providerRules = overview.value?.reconciliation_schedule.provider_rules ?? {};
  const entries = Object.entries(providerRules);
  if (!entries.length) {
    return capabilityTargetRuleLabel(
      overview.value?.reconciliation_schedule.official_target_rule,
    );
  }
  return entries
    .map(([providerCode, rule]) => `${providerLabelFromAny(providerCode)} ${capabilityTargetRuleLabel(rule?.official_target_rule)}`)
    .join(' / ');
});
const manualRunProviderOptions = computed(() =>
  visibleProviderCodes.value
    .filter((code) => providerCapabilitySummary(code).scheduled_daily_supported)
    .map((code) => ({
      label: providerLabel(code),
      value: code,
    })),
);
const hasVisibleProviders = computed(() => visibleProviderCodes.value.length > 0);
const qiniuVisible = computed(() => visibleProviderCodes.value.includes('qiniu-kodo'));

function billSourceOptions(code: ProviderCode): Array<{ label: string; value: string }> {
  return unique([...(profiles[code].supported_bill_sources ?? []), ...(validations[code].supported_bill_sources ?? []), profiles[code].bill_source]).map((item) => ({ label: item, value: item }));
}

function scopeValue(record: BindingRecord): string {
  if (record.scope_type === 'bucket') return record.bucket_name ?? record.scope_value;
  if (record.scope_type === 'domain') return record.domain_name ?? record.scope_value;
  if (record.scope_type === 'account') return record.account_identifier ?? record.scope_value;
  if (record.tag_key && record.tag_value) return `${record.tag_key}:${record.tag_value}`;
  return record.scope_value;
}

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

function formatTimestamp(value: null | string): string {
  if (!value) return '-';
  return value.replace('T', ' ').replace('Z', '');
}

function formatBytes(value: number): string {
  if (!value) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(2)} ${units[index]}`;
}

function chargeBasisLabel(basis: string): string {
  const key = `plugin.storage-billing.common.chargeBasis.${basis}`;
  const translated = $t(key);
  return translated === key ? basis : translated;
}

function runProviderSummaries(run: ReconciliationRun): ReconciliationProviderSummary[] {
  return Array.isArray(run.summary?.providers) ? run.summary.providers : [];
}

function sourceLabelFromCharge(charge: ReconciliationChargeRow): string {
  const sourceId = Number(charge.source_id ?? 0);
  if (!sourceId) return '-';
  const source = sourceById.value.get(sourceId);
  if (!source) return `#${sourceId}`;
  return source.source_ref || source.source_key || `#${sourceId}`;
}

function sourceAllocationSummary(source: ReconciliationSourceRecord): AllocationSummary {
  const raw = source.raw_payload_json?.allocation_summary;
  const payload = typeof raw === 'object' && raw !== null ? raw as Partial<AllocationSummary> : {};
  return {
    matched_items: Number(payload.matched_items ?? 0),
    unmatched_items: Number(payload.unmatched_items ?? 0),
    ambiguous_items: Number(payload.ambiguous_items ?? 0),
    written_charge_rows: Number(payload.written_charge_rows ?? 0),
  };
}

function sourceAllocationAudit(source: ReconciliationSourceRecord): AllocationAudit {
  const raw = source.raw_payload_json?.allocation_audit;
  const payload = typeof raw === 'object' && raw !== null ? raw as Partial<AllocationAudit> : {};
  return {
    unmatched_item_samples: Array.isArray(payload.unmatched_item_samples) ? payload.unmatched_item_samples : [],
    ambiguous_item_samples: Array.isArray(payload.ambiguous_item_samples) ? payload.ambiguous_item_samples : [],
  };
}

function hasAuditSamples(source: ReconciliationSourceRecord): boolean {
  const audit = sourceAllocationAudit(source);
  return audit.unmatched_item_samples.length > 0 || audit.ambiguous_item_samples.length > 0;
}

function normalizeNumber(value: unknown): null | number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function runRequestedScope(run: ReconciliationRun): ReconciliationRequestedScope {
  return typeof run.requested_scope === 'object' && run.requested_scope !== null
    ? run.requested_scope as ReconciliationRequestedScope
    : {};
}

function stringifyScopeValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return null;
}

function scopeProviderCodes(scope: ReconciliationRequestedScope): string[] {
  const raw = scope.provider_codes;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => stringifyScopeValue(item))
    .filter((item): item is string => Boolean(item));
}

function scopeProviderPlans(scope: ReconciliationRequestedScope): ReconciliationProviderPlan[] {
  const raw = scope.provider_plans;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (typeof item !== 'object' || item === null) return null;
      const payload = item as Record<string, unknown>;
      const providerCode = stringifyScopeValue(payload.provider_code);
      const billingDate = stringifyScopeValue(payload.billing_date);
      if (!providerCode || !billingDate) return null;
      return {
        billing_date: billingDate,
        cron: stringifyScopeValue(payload.cron) ?? undefined,
        local_time: stringifyScopeValue(payload.local_time) ?? undefined,
        official_billing_lag_days: normalizeNumber(payload.official_billing_lag_days),
        official_target_rule: stringifyScopeValue(payload.official_target_rule) ?? undefined,
        provider_code: providerCode,
      };
    })
    .filter((item): item is ReconciliationProviderPlan => Boolean(item));
}

function scopeProviderPlanSummary(scope: ReconciliationRequestedScope): string[] {
  return scopeProviderPlans(scope)
    .map((plan) => {
      const label = providerLabelFromAny(plan.provider_code);
      if (plan.official_target_rule) {
        return `${label} ${plan.official_target_rule} (${plan.billing_date})`;
      }
      return `${label} (${plan.billing_date})`;
    });
}

function selectedRunScopeSummary(run: ReconciliationRun): string {
  const scope = runRequestedScope(run);
  const parts: string[] = [];
  const job = stringifyScopeValue(scope.job);
  const billingDate = stringifyScopeValue(scope.billing_date);
  const billingMonth = stringifyScopeValue(scope.billing_month);
  const targetRule = stringifyScopeValue(scope.official_target_rule);
  const lagDays = stringifyScopeValue(scope.official_billing_lag_days);
  const scheduledProvider = stringifyScopeValue(scope.scheduled_provider_code);
  const providerCodes = scopeProviderCodes(scope);
  const providerPlans = scopeProviderPlanSummary(scope);

  if (job) {
    parts.push(`job=${job}`);
  }
  if (billingDate) {
    parts.push(`billing_date=${billingDate}`);
  }
  if (billingMonth) {
    parts.push(`billing_month=${billingMonth}`);
  }
  if (scheduledProvider) {
    parts.push(`scheduled_provider=${providerLabelFromAny(scheduledProvider)}`);
  }
  if (providerCodes.length) {
    parts.push(`providers=${providerCodes.map((code) => providerLabelFromAny(code)).join(', ')}`);
  }
  if (targetRule) {
    parts.push(`rule=${targetRule}`);
  }
  if (lagDays) {
    parts.push(`lag=${lagDays}`);
  }
  if (providerPlans.length) {
    parts.push(`plans=${providerPlans.join(' / ')}`);
  }
  return parts.join(' | ') || '-';
}

function selectedRunScopePayload(run: ReconciliationRun): string {
  return JSON.stringify(runRequestedScope(run), null, 2);
}

function resetForm(): void {
  Object.assign(form, emptyForm());
  const defaultProvider = visibleProviderCodes.value[0];
  if (defaultProvider) {
    form.provider_code = defaultProvider;
    handleProviderChange(defaultProvider);
  }
}

function clearScopeFields(scopeType: BindingScopeType): void {
  if (scopeType !== 'bucket') form.bucket_name = '';
  if (scopeType !== 'domain') form.domain_name = '';
  if (scopeType !== 'account') form.account_identifier = '';
  if (scopeType !== 'tag') {
    form.tag_key = '';
    form.tag_value = '';
  }
}

function handleProviderChange(code: ProviderCode): void {
  if (code === 'qiniu-kodo') {
    form.billing_mode = 'official_reconciled';
    if (form.scope_type !== 'account') {
      form.scope_type = 'account';
      clearScopeFields('account');
    }
  }
}

function providerPayload(code: ProviderCode): Partial<ProviderProfile> {
  const payload: Partial<ProviderProfile> = { enabled: Boolean(profiles[code].enabled) };
  for (const field of profileFields[code]) {
    const value = profiles[code][field];
    payload[field] = typeof value === 'string' ? value : '';
  }
  return payload;
}

function bindingPayload(): BindingPayload {
  const payload: BindingPayload = { tenant_id: Number(form.tenant_id), provider_code: form.provider_code, billing_mode: form.billing_mode, scope_type: form.scope_type, is_active: form.is_active };
  if (form.scope_type === 'bucket') payload.bucket_name = form.bucket_name.trim();
  if (form.scope_type === 'domain') payload.domain_name = form.domain_name.trim();
  if (form.scope_type === 'account') payload.account_identifier = form.account_identifier.trim();
  if (form.scope_type === 'tag') {
    payload.tag_key = form.tag_key.trim();
    payload.tag_value = form.tag_value.trim();
  }
  return payload;
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
  if (selectedRunId.value === nextRun.id && selectedRunDetail.value?.run.id === nextRun.id) {
    return;
  }
  await loadRunDetail(nextRun.id);
}

async function loadRunCharges(runId: number): Promise<void> {
  runChargeLoading.value = true;
  try {
    const runCharges = await getReconciliationRunChargesApi(
      runId,
      currentRunChargeFilters(),
    );
    selectedRunChargeResponse.value = runCharges;
    selectedRunCharges.value = runCharges.items ?? [];
  } finally {
    runChargeLoading.value = false;
  }
}

async function loadAll(): Promise<void> {
  loading.value = true;
  try {
    const [nextOverview, nextProfiles, nextBindings, nextTenants, nextRuns] = await Promise.all([
      getOverviewApi(),
      listProviderProfilesApi(),
      listBindingsApi(),
      getTenantSelectOptionsApi(),
      listReconciliationRunsApi(RUN_HISTORY_LIMIT),
    ]);
    overview.value = nextOverview;
    bindings.value = nextBindings.items ?? [];
    tenants.value = nextTenants;
    runs.value = nextRuns.items ?? nextOverview.ledger_snapshot.latest_runs ?? [];
    syncProfiles(nextProfiles);
    if (visibleProviderCodes.value.length) {
      if (!visibleProviderCodes.value.includes(form.provider_code)) {
        form.provider_code = visibleProviderCodes.value[0];
      }
      manualProviderCodes.value = manualProviderCodes.value.filter((code) =>
        visibleProviderCodes.value.includes(code),
      );
      handleProviderChange(form.provider_code);
    } else {
      manualProviderCodes.value = [];
    }
    await syncSelectedRun(runs.value);
  } finally {
    loading.value = false;
  }
}

async function loadRunDetail(runId: number): Promise<void> {
  runDetailLoading.value = true;
  selectedRunId.value = runId;
  resetRunChargeFiltersState();
  try {
    const [runDetail, runCharges] = await Promise.all([
      getReconciliationRunApi(runId),
      getReconciliationRunChargesApi(runId),
    ]);
    selectedRunDetail.value = runDetail;
    selectedRunChargeResponse.value = runCharges;
    selectedRunCharges.value = runCharges.items ?? [];
  } finally {
    runDetailLoading.value = false;
  }
}

async function applyRunChargeFilters(): Promise<void> {
  if (!selectedRunId.value) return;
  await loadRunCharges(selectedRunId.value);
}

async function resetRunChargeFilters(): Promise<void> {
  if (!selectedRunId.value) {
    resetRunChargeFiltersState();
    return;
  }
  resetRunChargeFiltersState();
  await loadRunCharges(selectedRunId.value);
}

async function exportCurrentRunCharges(): Promise<void> {
  if (!selectedRunId.value) return;
  runChargeExporting.value = true;
  try {
    const blob = await exportReconciliationRunChargesCsvApi(
      selectedRunId.value,
      currentRunChargeFilters(),
    );
    const datePart = selectedRun.value?.billing_date || 'unknown';
    downloadBlob(
      blob,
      { filename: `storage-billing-run-${selectedRunId.value}-${datePart}.csv` },
    );
    message.success($t('plugin.storage-billing.admin.messages.exportSuccess'));
  } catch {
    message.error($t('plugin.storage-billing.admin.messages.requestFailed'));
  } finally {
    runChargeExporting.value = false;
  }
}

async function saveProfiles(): Promise<void> {
  if (!visibleProviderCodes.value.length) {
    message.warning($t('plugin.storage-billing.admin.providers.noActiveDriver'));
    return;
  }
  saving.value = true;
  try {
    const payload = await saveProviderProfilesApi({
      providers: Object.fromEntries(
        visibleProviderCodes.value.map((code) => [code, providerPayload(code)]),
      ),
    });
    syncProfiles(payload);
    message.success($t('plugin.storage-billing.admin.messages.saved'));
  } finally {
    saving.value = false;
  }
}

async function validateProvider(code: ProviderCode): Promise<void> {
  const result = await validateProviderProfileApi(code, providerPayload(code));
  Object.assign(profiles[code], { ...profiles[code], ...result.profile });
  Object.assign(validations[code], { ...validations[code], ...result });
  message[result.status === 'valid' ? 'success' : 'warning']($t(result.status === 'valid' ? 'plugin.storage-billing.admin.messages.providerValid' : 'plugin.storage-billing.admin.messages.providerInvalid'));
}

async function searchTenants(keyword: string): Promise<void> {
  tenants.value = await getTenantSelectOptionsApi(keyword.trim());
}

function openCreate(): void {
  editingId.value = null;
  resetForm();
  bindingOpen.value = true;
}

function openEdit(record: BindingRecord): void {
  editingId.value = record.id;
  Object.assign(form, emptyForm(), { tenant_id: record.tenant_id, provider_code: record.provider_code, billing_mode: record.billing_mode, scope_type: record.scope_type, bucket_name: record.bucket_name ?? '', domain_name: record.domain_name ?? '', account_identifier: record.account_identifier ?? '', tag_key: record.tag_key ?? '', tag_value: record.tag_value ?? '', is_active: record.is_active });
  if (!tenants.value.some((item) => item.value === record.tenant_id)) tenants.value = [...tenants.value, { label: `#${record.tenant_id}`, value: record.tenant_id }];
  bindingOpen.value = true;
}

async function submitBinding(): Promise<void> {
  if (!form.tenant_id) {
    message.warning($t('plugin.storage-billing.admin.bindingForm.selectTenant'));
    return;
  }
  bindingLoading.value = true;
  try {
    const result = editingId.value === null ? await createBindingApi(bindingPayload()) : await updateBindingApi(editingId.value, bindingPayload());
    bindingOpen.value = false;
    await loadAll();
    message[result.validation.validation_status === 'valid' ? 'success' : 'warning']($t(result.validation.validation_status === 'valid' ? 'plugin.storage-billing.admin.messages.bindingSaved' : 'plugin.storage-billing.admin.messages.bindingInvalid'));
  } finally {
    bindingLoading.value = false;
  }
}

async function revalidateBinding(record: BindingRecord): Promise<void> {
  const result = await validateBindingApi(record.id);
  message[result.validation.validation_status === 'valid' ? 'success' : 'warning'](result.validation.validation_message || $t('plugin.storage-billing.admin.messages.bindingValidated'));
  await loadAll();
}

function triggerRun(): void {
  if (manualBillingDateError.value) {
    message.error(manualBillingDateError.value);
    return;
  }

  const payload: { billing_date?: string; provider_codes?: string[] } = {};
  if (manualBillingDate.value) {
    payload.billing_date = manualBillingDate.value;
  }
  if (manualProviderCodes.value.length) {
    payload.provider_codes = [...manualProviderCodes.value];
  }

  const providerSummary = manualProviderCodes.value.length
    ? manualProviderCodes.value.map((code) => providerLabel(code)).join(' / ')
    : $t('plugin.storage-billing.admin.actions.providerAll');
  const billingDateSummary = manualBillingDate.value || $t('plugin.storage-billing.admin.actions.dailyAuto');

  Modal.confirm({
    title: $t('plugin.storage-billing.admin.actions.triggerRun'),
    content: `${$t('plugin.storage-billing.admin.actions.triggerRunHint')} (${billingDateSummary} / ${providerSummary})`,
    onOk: async () => {
      const result = await runReconciliationApi(payload);
      message.success($t('plugin.storage-billing.admin.messages.runTriggered'));
      await loadAll();
      const runId = Number((result.run as Record<string, unknown>)?.id ?? 0);
      if (runId > 0) {
        await loadRunDetail(runId);
      }
    },
  });
}

function triggerQiniuMonthlyRun(): void {
  if (!qiniuMonthValid.value) {
    message.error($t('plugin.storage-billing.admin.actions.qiniuMonthlyInvalid'));
    return;
  }

  Modal.confirm({
    title: $t('plugin.storage-billing.admin.actions.triggerQiniuMonthly'),
    content: `${$t('plugin.storage-billing.admin.actions.triggerQiniuMonthlyHint')} (${qiniuBillingMonth.value || '-'})`,
    onOk: async () => {
      const result = await runQiniuMonthlySettlementApi({ billing_month: qiniuBillingMonth.value });
      message.success($t('plugin.storage-billing.admin.messages.runTriggered'));
      await loadAll();
      const runId = Number((result.run as Record<string, unknown>)?.id ?? 0);
      if (runId > 0) {
        await loadRunDetail(runId);
      }
    },
  });
}

onMounted(() => void loadAll());
</script>

<template>
  <Page class="storage-billing-admin">
    <Spin :spinning="loading || saving">
      <div class="hero">
        <div>
          <div class="badge">{{ $t('plugin.storage-billing.admin.hero.badge') }}</div>
          <h1>{{ $t('plugin.storage-billing.admin.page.title') }}</h1>
          <p>{{ $t('plugin.storage-billing.admin.page.subtitle') }}</p>
        </div>
        <div class="hero-actions">
          <Space wrap class="toolbar-group">
            <Button @click="loadAll">{{ $t('plugin.storage-billing.admin.actions.refresh') }}</Button>
            <Button :disabled="!hasVisibleProviders" type="primary" @click="saveProfiles">{{ $t('plugin.storage-billing.admin.providers.save') }}</Button>
          </Space>
          <div class="toolbar-stack">
            <Space wrap class="toolbar-group">
              <Input
                v-model:value="manualBillingDate"
                class="toolbar-field"
                :placeholder="$t('plugin.storage-billing.admin.actions.dailyPlaceholder')"
                :status="manualBillingDateStatus"
              />
              <Select
                v-model:value="manualProviderCodes"
                class="toolbar-field toolbar-field-wide"
                mode="multiple"
                :options="manualRunProviderOptions"
                :placeholder="$t('plugin.storage-billing.admin.actions.providerPlaceholder')"
              />
              <Button :disabled="!hasVisibleProviders" @click="triggerRun">{{ $t('plugin.storage-billing.admin.actions.triggerRun') }}</Button>
            </Space>
            <div class="toolbar-help" :class="{ 'toolbar-help-error': manualBillingDateError }">
              {{ manualRunHelpText }}
            </div>
          </div>
          <div v-if="qiniuVisible" class="toolbar-stack">
            <Space wrap class="toolbar-group">
              <Input
                v-model:value="qiniuBillingMonth"
                class="toolbar-field"
                :placeholder="$t('plugin.storage-billing.admin.actions.qiniuMonthlyPlaceholder')"
                :status="qiniuMonthStatus"
              />
              <Button @click="triggerQiniuMonthlyRun">{{ $t('plugin.storage-billing.admin.actions.triggerQiniuMonthly') }}</Button>
            </Space>
            <div class="toolbar-help" :class="{ 'toolbar-help-error': qiniuMonthError }">
              {{ qiniuMonthError || $t('plugin.storage-billing.admin.actions.triggerQiniuMonthlyHint') }}
            </div>
          </div>
          <div v-if="!hasVisibleProviders" class="toolbar-help toolbar-help-error">
            {{ $t('plugin.storage-billing.admin.providers.noActiveDriver') }}
          </div>
        </div>
      </div>

      <div class="stats">
        <Card><Statistic :title="$t('plugin.storage-billing.admin.overview.billableDrivers')" :value="overview?.billable_drivers.length ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storage-billing.admin.overview.enabledDrivers')" :value="overview?.host_snapshot.enabled_storage_drivers.length ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storage-billing.admin.overview.bindingTotal')" :value="overview?.ledger_snapshot.binding_total ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storage-billing.admin.overview.statementTotal')" :value="overview?.ledger_snapshot.statement_total ?? 0" /></Card>
      </div>

      <Alert
        class="block"
        :message="$t('plugin.storage-billing.admin.hero.lag')"
        :description="`${overview?.reconciliation_schedule.local_time ?? '03:00'} / ${reconciliationScheduleSummary} / ${overview?.mode ?? '-'}`"
        show-icon
        type="info"
      />

      <Card :title="$t('plugin.storage-billing.admin.providers.title')" class="block">
        <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.providers.subtitle') }}</div>
        <Alert
          v-if="!hasVisibleProviders"
          class="block"
          :message="$t('plugin.storage-billing.admin.providers.noActiveDriver')"
          type="warning"
          show-icon
        />
        <div v-else class="providers">
          <Card v-for="code in visibleProviderCodes" :key="code">
            <template #title>
              <Space wrap>
                <span>{{ providerLabel(code) }}</span>
                <Tag :color="statusColor(validations[code].status)">{{ prettyStatus(validations[code].status) }}</Tag>
                <Tag v-for="tag in providerCapabilityTags(code)" :key="`${code}-${tag}`" color="blue">{{ tag }}</Tag>
              </Space>
            </template>
            <Alert
              v-if="profiles[code].capability_message"
              class="block"
              :message="providerLabel(code)"
              :description="profiles[code].capability_message"
              type="info"
              show-icon
            />
            <Alert
              v-if="profileWarnings(code)"
              class="block"
              :message="providerLabel(code)"
              :description="profileWarnings(code)"
              :type="validations[code].errors.length ? 'error' : 'warning'"
              show-icon
            />
            <div class="capability-grid">
              <div class="capability-item">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.mode') }}</span>
                <strong>{{ capabilityModeLabel(providerCapabilitySummary(code).settlement_mode) || '-' }}</strong>
              </div>
              <div class="capability-item">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.cycle') }}</span>
                <strong>{{ capabilityCycleLabel(providerCapabilitySummary(code).settlement_cycle) || '-' }}</strong>
              </div>
              <div class="capability-item">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.targetRule') }}</span>
                <strong>{{ capabilityTargetRuleLabel(providerCapabilitySummary(code).official_target_rule) }}</strong>
              </div>
              <div class="capability-item">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.lagDays') }}</span>
                <strong>{{ providerCapabilitySummary(code).official_billing_lag_days ?? '-' }}</strong>
              </div>
              <div class="capability-item capability-item-wide">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.periodTypes') }}</span>
                <strong>
                  {{
                    providerCapabilitySummary(code).supported_period_types
                      .map((item) => capabilityPeriodLabel(item) || item)
                      .join(' / ') || '-'
                  }}
                </strong>
              </div>
              <div class="capability-item capability-item-wide">
                <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.recommendedScopes') }}</span>
                <strong>
                  {{
                    providerCapabilitySummary(code).recommended_scope_types
                      .map((item) => $t(`plugin.storage-billing.admin.bindings.scope.${item}`))
                      .join(' / ') || '-'
                  }}
                </strong>
              </div>
            </div>
            <Descriptions :column="2" class="provider-runtime" size="small">
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.configSource')">
                {{ $t('plugin.storage-billing.admin.providers.runtime.source.platform_storage') }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.currentDriver')">
                {{ providerLabelFromAny(providerStorageContext(code).current_driver || '-') }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.driverMatch')">
                <Tag :color="providerStorageMatch(code) ? 'success' : 'error'">
                  {{
                    $t(
                      providerStorageMatch(code)
                        ? 'plugin.storage-billing.admin.providers.runtime.match'
                        : 'plugin.storage-billing.admin.providers.runtime.mismatch',
                    )
                  }}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.credentialStatus')">
                <Tag :color="providerStorageReady(code) ? 'success' : 'warning'">
                  {{
                    $t(
                      providerStorageReady(code)
                        ? 'plugin.storage-billing.admin.providers.runtime.configured'
                        : 'plugin.storage-billing.admin.providers.runtime.missing',
                    )
                  }}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.bucket')">
                {{ providerRuntimeValue(providerStorageContext(code).bucket_name) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.baseUrl')">
                {{ providerRuntimeValue(providerStorageContext(code).base_url) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.region')">
                {{ providerRuntimeValue(providerStorageContext(code).region) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.endpoint')">
                {{ providerRuntimeValue(providerStorageContext(code).endpoint) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.prefix')">
                {{ providerRuntimeValue(providerStorageContext(code).prefix) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.rootPath')">
                {{ providerRuntimeValue(providerStorageContext(code).root_path) }}
              </Descriptions.Item>
            </Descriptions>
            <Form layout="vertical">
              <FormItem :label="$t('plugin.storage-billing.admin.field.enabled')"><Switch v-model:checked="profiles[code].enabled" /></FormItem>
              <FormItem v-for="field in profileFields[code]" :key="field" :label="fieldLabel(field)">
                <template #extra>
                  <Space wrap>
                    <Tag :color="(validations[code].required_fields ?? []).includes(field) ? 'error' : 'default'">
                      {{
                        (validations[code].required_fields ?? []).includes(field)
                          ? $t('plugin.storage-billing.admin.providers.required')
                          : $t('plugin.storage-billing.admin.providers.optional')
                      }}
                    </Tag>
                  </Space>
                </template>
                <Select v-if="field === 'bill_source'" v-model:value="profiles[code][field]" :options="billSourceOptions(code)" />
                <Input
                  v-else
                  v-model:value="profiles[code][field]"
                  type="text"
                />
              </FormItem>
            </Form>
            <div class="actions"><Button @click="validateProvider(code)">{{ $t('plugin.storage-billing.admin.providers.validate') }}</Button></div>
          </Card>
        </div>
      </Card>

      <Card :title="$t('plugin.storage-billing.admin.bindings.title')" class="block">
        <template #extra><Button :disabled="!hasVisibleProviders" type="primary" @click="openCreate">{{ $t('plugin.storage-billing.admin.bindings.add') }}</Button></template>
        <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.bindings.subtitle') }}</div>
        <Table :columns="bindingColumns" :data-source="bindings" :locale="{ emptyText: $t('plugin.storage-billing.admin.bindings.empty') }" :pagination="false" row-key="id">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'tenant'">#{{ record.tenant_id }}</template>
            <template v-else-if="column.key === 'provider'">{{ providerLabel(record.provider_code) }}</template>
            <template v-else-if="column.key === 'mode'">{{ $t(`plugin.storage-billing.admin.bindings.mode.${record.billing_mode}`) }}</template>
            <template v-else-if="column.key === 'scope'"><Space wrap><Tag color="blue">{{ $t(`plugin.storage-billing.admin.bindings.scope.${record.scope_type}`) }}</Tag><span>{{ scopeValue(record) }}</span></Space></template>
            <template v-else-if="column.key === 'status'"><Tag :color="statusColor(record.validation_status)">{{ prettyStatus(record.validation_status) }}</Tag></template>
            <template v-else-if="column.key === 'message'"><span class="muted">{{ record.validation_message || '-' }}</span></template>
            <template v-else-if="column.key === 'actions'"><Space wrap><Button size="small" @click="openEdit(record)">{{ $t('plugin.storage-billing.admin.bindings.edit') }}</Button><Button size="small" @click="revalidateBinding(record)">{{ $t('plugin.storage-billing.admin.bindings.revalidate') }}</Button></Space></template>
          </template>
        </Table>
        <div v-if="!bindings.length" class="empty"><Empty :description="$t('plugin.storage-billing.admin.bindings.empty')" /></div>
      </Card>

      <Card :title="$t('plugin.storage-billing.admin.runs.title')" class="block">
        <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.runs.subtitle') }}</div>
        <Table :columns="runColumns" :data-source="runs" :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.empty') }" :pagination="false" row-key="id">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'billing_date'">{{ record.period_label || record.billing_date }}</template>
            <template v-else-if="column.key === 'status'"><Tag :color="statusColor(record.status)">{{ prettyStatus(record.status) }}</Tag></template>
            <template v-else-if="column.key === 'trigger_type'">{{ record.trigger_type }}</template>
            <template v-else-if="column.key === 'providers'">
              <Space wrap>
                <Tag v-for="provider in runProviderSummaries(record)" :key="`${record.id}-${provider.provider_code}`" :color="statusColor(provider.source_status)">
                  {{ providerLabelFromAny(provider.provider_code) }} · {{ provider.matched_items ?? 0 }}/{{ provider.charge_item_count ?? 0 }}
                </Tag>
              </Space>
            </template>
            <template v-else-if="column.key === 'finished_at'">{{ formatTimestamp(record.completed_at) }}</template>
            <template v-else-if="column.key === 'actions'">
              <Button size="small" @click="loadRunDetail(record.id)">{{ $t('plugin.storage-billing.admin.runs.view') }}</Button>
            </template>
          </template>
        </Table>
        <div v-if="!runs.length" class="empty"><Empty :description="$t('plugin.storage-billing.admin.runs.empty')" /></div>

        <Card v-if="selectedRun" class="run-detail" size="small">
          <template #title>{{ $t('plugin.storage-billing.admin.runs.detailTitle') }} · {{ selectedRun.period_label || selectedRun.billing_date }}</template>
          <template #extra>
            <Button
              :loading="runChargeExporting"
              size="small"
              @click="exportCurrentRunCharges"
            >
              {{ $t('plugin.storage-billing.admin.runs.charges.export') }}
            </Button>
          </template>
          <Spin :spinning="runDetailLoading">
            <Descriptions :column="3" size="small">
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.status')">
                <Tag :color="statusColor(selectedRun.status)">{{ prettyStatus(selectedRun.status) }}</Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.trigger')">{{ selectedRun.trigger_type }}</Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.statementCount')">{{ selectedRun.summary.statement_count ?? 0 }}</Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.requestedScope')" :span="3">
                <div class="run-scope-summary">{{ selectedRunScopeSummary(selectedRun) }}</div>
                <Space v-if="scopeProviderCodes(runRequestedScope(selectedRun)).length" wrap class="run-scope-tags">
                  <Tag
                    v-for="providerCode in scopeProviderCodes(runRequestedScope(selectedRun))"
                    :key="`scope-provider-${providerCode}`"
                    color="blue"
                  >
                    {{ providerLabelFromAny(providerCode) }}
                  </Tag>
                </Space>
                <div v-if="scopeProviderPlans(runRequestedScope(selectedRun)).length" class="run-plan-list">
                  <div
                    v-for="plan in scopeProviderPlans(runRequestedScope(selectedRun))"
                    :key="`plan-${plan.provider_code}-${plan.billing_date}`"
                    class="run-plan-card"
                  >
                    <Space wrap>
                      <Tag color="blue">{{ providerLabelFromAny(plan.provider_code) }}</Tag>
                      <Tag color="processing">{{ plan.billing_date }}</Tag>
                      <Tag>{{ capabilityTargetRuleLabel(plan.official_target_rule) }}</Tag>
                      <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.lagDays') }} {{ plan.official_billing_lag_days ?? '-' }}</Tag>
                    </Space>
                  </div>
                </div>
                <details class="run-scope-details">
                  <summary>{{ $t('plugin.storage-billing.admin.runs.detail.scopeToggle') }}</summary>
                  <pre>{{ selectedRunScopePayload(selectedRun) }}</pre>
                </details>
              </Descriptions.Item>
            </Descriptions>

            <div v-if="selectedRunProviderResults.length" class="run-provider-results">
              <div
                v-for="provider in selectedRunProviderResults"
                :key="`provider-result-${provider.provider_code}`"
                class="run-provider-card"
              >
                <Space wrap>
                  <Tag :color="statusColor(provider.source_status)">
                    {{ providerLabelFromAny(provider.provider_code) }}
                  </Tag>
                  <Tag>{{ prettyStatus(provider.source_status) }}</Tag>
                  <Tag>{{ $t('plugin.storage-billing.admin.runs.audit.matched') }} {{ provider.matched_items ?? 0 }}</Tag>
                  <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.chargeItems') }} {{ provider.charge_item_count ?? 0 }}</Tag>
                  <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.writtenRows') }} {{ provider.written_charge_rows ?? 0 }}</Tag>
                </Space>
              </div>
            </div>

            <Table :columns="sourceColumns" :data-source="selectedRunDetail?.sources ?? []" :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.sources.empty') }" :pagination="false" row-key="id">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'provider'">
                  <Space direction="vertical" size="small">
                    <span>{{ providerLabelFromAny(record.provider_code) }}</span>
                    <span class="muted">{{ record.source_ref || record.source_key }}</span>
                  </Space>
                </template>
                <template v-else-if="column.key === 'status'">
                  <Tag :color="statusColor(record.source_status)">{{ prettyStatus(record.source_status) }}</Tag>
                </template>
                <template v-else-if="column.key === 'amount'">{{ record.amount_total }} {{ record.currency }}</template>
                <template v-else-if="column.key === 'usage'">{{ formatBytes(record.usage_bytes) }}</template>
                <template v-else-if="column.key === 'allocation'">
                  <Space wrap>
                    <Tag color="success">{{ $t('plugin.storage-billing.admin.runs.audit.matched') }} {{ sourceAllocationSummary(record).matched_items }}</Tag>
                    <Tag color="warning">{{ $t('plugin.storage-billing.admin.runs.audit.unmatched') }} {{ sourceAllocationSummary(record).unmatched_items }}</Tag>
                    <Tag color="error">{{ $t('plugin.storage-billing.admin.runs.audit.ambiguous') }} {{ sourceAllocationSummary(record).ambiguous_items }}</Tag>
                  </Space>
                </template>
                <template v-else-if="column.key === 'error'">
                  <span class="muted">{{ record.error_message || '-' }}</span>
                </template>
              </template>
            </Table>

            <Card class="run-charge-card" size="small">
              <template #title>{{ $t('plugin.storage-billing.admin.runs.charges.title') }}</template>
              <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.runs.charges.subtitle') }}</div>
              <Space wrap class="run-charge-summary">
                <Tag color="blue">{{ $t('plugin.storage-billing.admin.runs.charges.rowTotal') }} {{ selectedRunChargeResponse?.total ?? selectedRunCharges.length }}</Tag>
                <Tag color="cyan">{{ $t('plugin.storage-billing.admin.runs.charges.sourceTotal') }} {{ selectedRunChargeResponse?.source_total ?? (selectedRunDetail?.sources?.length ?? 0) }}</Tag>
                <Tag v-if="!runChargeActiveFilters.length" color="default">{{ $t('plugin.storage-billing.admin.runs.charges.filterNone') }}</Tag>
                <Tag v-for="filter in runChargeActiveFilters" :key="`charge-filter-${filter.key}`" color="processing">
                  {{ filter.label }}: {{ filter.value }}
                </Tag>
              </Space>
              <Space wrap class="run-charge-toolbar">
                <Select
                  v-model:value="runChargeFilters.provider_code"
                  allow-clear
                  class="toolbar-field"
                  :options="runChargeProviderOptions"
                  :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterProvider')"
                />
                <Select
                  v-model:value="runChargeFilters.source_id"
                  allow-clear
                  class="toolbar-field toolbar-source"
                  :options="runChargeSourceOptions"
                  :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterSource')"
                />
                <Input
                  v-model:value="runChargeFilters.tenant_id"
                  class="toolbar-field"
                  :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterTenant')"
                />
                <Button @click="applyRunChargeFilters">
                  {{ $t('plugin.storage-billing.admin.runs.charges.applyFilters') }}
                </Button>
                <Button @click="resetRunChargeFilters">
                  {{ $t('plugin.storage-billing.admin.runs.charges.resetFilters') }}
                </Button>
              </Space>
              <Spin :spinning="runChargeLoading">
                <Table
                  :columns="chargeColumns"
                  :data-source="selectedRunCharges"
                  :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.charges.empty') }"
                  :pagination="false"
                  row-key="id"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'billing_date'">{{ record.period_label || record.billing_date }}</template>
                    <template v-else-if="column.key === 'tenant_id'">#{{ record.tenant_id }}</template>
                    <template v-else-if="column.key === 'provider'">{{ providerLabelFromAny(record.provider_code) }}</template>
                    <template v-else-if="column.key === 'source'">{{ sourceLabelFromCharge(record) }}</template>
                    <template v-else-if="column.key === 'charge_basis'">{{ chargeBasisLabel(record.charge_basis) }}</template>
                    <template v-else-if="column.key === 'usage_bytes'">{{ formatBytes(record.usage_bytes) }}</template>
                    <template v-else-if="column.key === 'amount_total'">{{ record.amount_total }}</template>
                    <template v-else-if="column.key === 'currency'">{{ record.currency }}</template>
                  </template>
                </Table>
              </Spin>
            </Card>

            <div v-if="auditedSources.length" class="audit-list">
              <div v-for="source in auditedSources" :key="`audit-${source.id}`" class="audit-card">
                <div class="audit-head">
                  <Space wrap>
                    <Tag color="blue">{{ providerLabelFromAny(source.provider_code) }}</Tag>
                    <Tag :color="statusColor(source.source_status)">{{ prettyStatus(source.source_status) }}</Tag>
                  </Space>
                </div>
                <div class="audit-summary">
                  <Tag color="warning">{{ $t('plugin.storage-billing.admin.runs.audit.unmatchedSamples') }} {{ sourceAllocationAudit(source).unmatched_item_samples.length }}</Tag>
                  <Tag color="error">{{ $t('plugin.storage-billing.admin.runs.audit.ambiguousSamples') }} {{ sourceAllocationAudit(source).ambiguous_item_samples.length }}</Tag>
                </div>
                <details class="audit-details">
                  <summary>{{ $t('plugin.storage-billing.admin.runs.audit.toggle') }}</summary>
                  <pre>{{ JSON.stringify(source.raw_payload_json, null, 2) }}</pre>
                </details>
              </div>
            </div>
          </Spin>
        </Card>
      </Card>

      <Modal v-model:open="bindingOpen" :confirm-loading="bindingLoading" :title="modalTitle" :ok-text="modalOkText" @ok="submitBinding" @cancel="resetForm">
        <Form layout="vertical">
          <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tenant')"><Select v-model:value="form.tenant_id" :options="tenants" :filter-option="false" show-search @search="searchTenants" /></FormItem>
          <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.provider')"><Select v-model:value="form.provider_code" :disabled="providerOptions.length <= 1" :options="providerOptions" @change="handleProviderChange" /></FormItem>
          <Alert
            v-if="form.provider_code === 'qiniu-kodo'"
            class="block"
            :message="$t('plugin.storage-billing.admin.bindingForm.qiniuRestrictionTitle')"
            :description="$t('plugin.storage-billing.admin.bindingForm.qiniuRestrictionDesc')"
            show-icon
            type="info"
          />
          <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.mode')"><Select v-model:value="form.billing_mode" :options="currentModeOptions" /></FormItem>
          <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.scopeType')"><Select v-model:value="form.scope_type" :options="currentScopeOptions" @change="clearScopeFields" /></FormItem>
          <FormItem v-if="form.scope_type === 'bucket'" :label="$t('plugin.storage-billing.admin.bindingForm.bucketName')"><Input v-model:value="form.bucket_name" :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.bucket')" /></FormItem>
          <FormItem v-if="form.scope_type === 'domain'" :label="$t('plugin.storage-billing.admin.bindingForm.domainName')"><Input v-model:value="form.domain_name" :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.domain')" /></FormItem>
          <FormItem v-if="form.scope_type === 'account'" :label="$t('plugin.storage-billing.admin.bindingForm.accountIdentifier')"><Input v-model:value="form.account_identifier" :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.account')" /></FormItem>
          <template v-if="form.scope_type === 'tag'">
            <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tagKey')"><Input v-model:value="form.tag_key" :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.tagKey')" /></FormItem>
            <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tagValue')"><Input v-model:value="form.tag_value" :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.tagValue')" /></FormItem>
          </template>
          <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.isActive')"><Switch v-model:checked="form.is_active" /></FormItem>
        </Form>
      </Modal>
    </Spin>
  </Page>
</template>

<style>
.storage-billing-admin{--hero:linear-gradient(135deg,#fff7ed,#f8fafc 50%,#eff6ff)}
.storage-billing-admin .hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:20px;padding:24px;border-radius:24px;background:var(--hero);border:1px solid rgba(180,83,9,.14)}
.storage-billing-admin .badge{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#b45309;margin-bottom:8px}
.storage-billing-admin .hero h1{margin:0 0 8px;font-size:28px}
.storage-billing-admin .hero p{margin:0;color:#475569;max-width:760px}
.storage-billing-admin .hero-actions{display:flex;flex-direction:column;gap:12px;min-width:320px}
.storage-billing-admin .toolbar-group{justify-content:flex-end}
.storage-billing-admin .toolbar-stack{display:flex;flex-direction:column;gap:6px}
.storage-billing-admin .toolbar-field{min-width:180px}
.storage-billing-admin .toolbar-field-wide{min-width:240px}
.storage-billing-admin .toolbar-help{font-size:12px;color:#64748b;max-width:360px}
.storage-billing-admin .toolbar-help-error{color:#dc2626}
.storage-billing-admin .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}
.storage-billing-admin .block{margin-bottom:20px}
.storage-billing-admin .providers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.storage-billing-admin .section-subtitle,
.storage-billing-admin .muted{color:#64748b}
.storage-billing-admin .section-subtitle{margin-bottom:16px}
.storage-billing-admin .capability-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:16px}
.storage-billing-admin .capability-item{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .capability-item-wide{grid-column:1/-1}
.storage-billing-admin .provider-runtime{margin-bottom:16px;padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .capability-label{display:block;margin-bottom:6px;font-size:12px;color:#64748b}
.storage-billing-admin .actions{display:flex;justify-content:flex-end}
.storage-billing-admin .empty{margin-top:12px}
.storage-billing-admin .run-detail{margin-top:16px}
.storage-billing-admin .run-scope-summary{line-height:1.6;color:#0f172a}
.storage-billing-admin .run-scope-tags{margin-top:8px}
.storage-billing-admin .run-plan-list,
.storage-billing-admin .run-provider-results{display:grid;gap:12px;margin-top:16px}
.storage-billing-admin .run-plan-card,
.storage-billing-admin .run-provider-card{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .run-scope-details{margin-top:8px}
.storage-billing-admin .run-scope-details summary{cursor:pointer;color:#64748b}
.storage-billing-admin .run-scope-details pre{margin:8px 0 0;padding:12px;border-radius:12px;background:#0f172a;color:#e2e8f0;overflow:auto;max-height:320px}
.storage-billing-admin .run-charge-summary{display:flex;margin:12px 0}
.storage-billing-admin .run-charge-toolbar{display:flex;margin-bottom:12px}
.storage-billing-admin .toolbar-source{min-width:260px}
.storage-billing-admin .run-charge-card{margin-top:16px}
.storage-billing-admin .audit-list{display:grid;gap:12px;margin-top:16px}
.storage-billing-admin .audit-card{padding:16px;border-radius:16px;background:#f8fafc;border:1px solid rgba(148,163,184,.2)}
.storage-billing-admin .audit-head,
.storage-billing-admin .audit-summary{margin-bottom:12px}
.storage-billing-admin .audit-details summary{cursor:pointer;color:#0f172a;font-weight:600}
.storage-billing-admin .audit-details pre{margin-top:12px;padding:12px;border-radius:12px;background:#0f172a;color:#e2e8f0;overflow:auto;max-height:320px}
@media (max-width:1200px){
  .storage-billing-admin .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .storage-billing-admin .providers{grid-template-columns:1fr}
}
@media (max-width:768px){
  .storage-billing-admin .hero{flex-direction:column}
  .storage-billing-admin .hero-actions{min-width:0;width:100%}
  .storage-billing-admin .stats{grid-template-columns:1fr}
  .storage-billing-admin .capability-grid{grid-template-columns:1fr}
}
</style>

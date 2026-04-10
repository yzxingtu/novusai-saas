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
  ReconciliationRunChargeListResponse,
  ReconciliationRun,
  ReconciliationRunDetailResponse,
  TenantSelectOption,
} from '../../types';
import { computed, onMounted, reactive, ref } from 'vue';
import { Page } from '@vben/common-ui';
import { Spin, message } from 'ant-design-vue';
import { $t } from '@novus/plugin-shared';
import {
  createBindingApi,
  getOverviewApi,
  getTenantSelectOptionsApi,
  listBindingsApi,
  listProviderProfilesApi,
  listReconciliationRunsApi,
  saveProviderProfilesApi,
  updateBindingApi,
  validateBindingApi,
  validateProviderProfileApi,
} from '../../api/admin';
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
import { useStorageBillingAdminRunActions } from './use-storage-billing-admin-run-actions';
import { useReconciliationRunDetail } from './use-reconciliation-run-detail';
import AdminBindingModal from './components/AdminBindingModal.vue';
import AdminBindingsCard from './components/AdminBindingsCard.vue';
import AdminOverviewHero from './components/AdminOverviewHero.vue';
import AdminProvidersCard from './components/AdminProvidersCard.vue';
import AdminRunsCard from './components/AdminRunsCard.vue';
defineOptions({ name: 'StorageBillingAdminPage' });

type ProviderField = 'account_identifier' | 'bill_source' | 'profile_code';
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

type SharedAccessApi = {
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (codes: string[]) => boolean;
};

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
  return buildSelectedRunScopeSummary(run, providerLabelFromAny);
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

async function loadAll(): Promise<void> {
  if (!canViewAdmin.value) {
    overview.value = null;
    bindings.value = [];
    tenants.value = [];
    runs.value = [];
    bindingOpen.value = false;
    selectedRunId.value = null;
    selectedRunDetail.value = null;
    selectedRunChargeResponse.value = null;
    selectedRunCharges.value = [];
    return;
  }
  loading.value = true;
  try {
    const [nextOverview, nextProfiles, nextBindings, nextTenants, nextRuns] = await Promise.all([
      getOverviewApi(),
      listProviderProfilesApi(),
      listBindingsApi(),
      Promise.resolve([] as TenantSelectOption[]),
      listReconciliationRunsApi(RUN_HISTORY_LIMIT),
    ]);
    overview.value = nextOverview;
    bindings.value = nextBindings.items ?? [];
    tenants.value = canConfigureAdmin.value ? nextTenants : [];
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
  manualBillingDateError,
  manualProviderCodes,
  providerLabel,
  qiniuBillingMonth,
  qiniuMonthValid,
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
  if (!canConfigureAdmin.value) return;
  const result = await validateProviderProfileApi(code, providerPayload(code));
  Object.assign(profiles[code], { ...profiles[code], ...result.profile });
  Object.assign(validations[code], { ...validations[code], ...result });
  message[result.status === 'valid' ? 'success' : 'warning']($t(result.status === 'valid' ? 'plugin.storage-billing.admin.messages.providerValid' : 'plugin.storage-billing.admin.messages.providerInvalid'));
}

async function searchTenants(keyword: string): Promise<void> {
  if (!canConfigureAdmin.value) {
    tenants.value = [];
    return;
  }
  tenants.value = await getTenantSelectOptionsApi(keyword.trim());
}

async function openCreate(): Promise<void> {
  if (!canConfigureAdmin.value) return;
  editingId.value = null;
  resetForm();
  tenants.value = await getTenantSelectOptionsApi();
  bindingOpen.value = true;
}

function openEdit(record: BindingRecord): void {
  if (!canConfigureAdmin.value) return;
  editingId.value = record.id;
  Object.assign(form, emptyForm(), { tenant_id: record.tenant_id, provider_code: record.provider_code, billing_mode: record.billing_mode, scope_type: record.scope_type, bucket_name: record.bucket_name ?? '', domain_name: record.domain_name ?? '', account_identifier: record.account_identifier ?? '', tag_key: record.tag_key ?? '', tag_value: record.tag_value ?? '', is_active: record.is_active });
  if (!tenants.value.some((item) => item.value === record.tenant_id)) tenants.value = [...tenants.value, { label: `#${record.tenant_id}`, value: record.tenant_id }];
  bindingOpen.value = true;
}

async function submitBinding(): Promise<void> {
  if (!canConfigureAdmin.value) return;
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
  if (!canConfigureAdmin.value) return;
  const result = await validateBindingApi(record.id);
  message[result.validation.validation_status === 'valid' ? 'success' : 'warning'](result.validation.validation_message || $t('plugin.storage-billing.admin.messages.bindingValidated'));
  await loadAll();
}

onMounted(() => void loadAll());
</script>

<template>
  <Page class="storage-billing-admin">
    <Spin :spinning="loading || saving">
      <AdminOverviewHero
        :can-configure-admin="canConfigureAdmin"
        :can-reconcile-admin="canReconcileAdmin"
        :has-visible-providers="hasVisibleProviders"
        :load-all="loadAll"
        :manual-billing-date="manualBillingDate"
        :manual-billing-date-error="manualBillingDateError"
        :manual-billing-date-status="manualBillingDateStatus"
        :manual-provider-codes="manualProviderCodes"
        :manual-run-help-text="manualRunHelpText"
        :manual-run-provider-options="manualRunProviderOptions"
        :overview="overview"
        :qiniu-billing-month="qiniuBillingMonth"
        :qiniu-month-error="qiniuMonthError"
        :qiniu-month-status="qiniuMonthStatus"
        :qiniu-visible="qiniuVisible"
        :reconciliation-schedule-summary="reconciliationScheduleSummary"
        :save-profiles="saveProfiles"
        :trigger-qiniu-monthly-run="triggerQiniuMonthlyRun"
        :trigger-run="triggerRun"
        @update:manual-billing-date="manualBillingDate = $event"
        @update:manual-provider-codes="manualProviderCodes = $event"
        @update:qiniu-billing-month="qiniuBillingMonth = $event"
      />

      <AdminProvidersCard
        :bill-source-options="billSourceOptions"
        :can-configure-admin="canConfigureAdmin"
        :capability-cycle-label="capabilityCycleLabel"
        :capability-mode-label="capabilityModeLabel"
        :capability-period-label="capabilityPeriodLabel"
        :capability-target-rule-label="capabilityTargetRuleLabel"
        :field-label="fieldLabel"
        :has-visible-providers="hasVisibleProviders"
        :pretty-status="prettyStatus"
        :profile-fields="profileFields"
        :profile-warnings="profileWarnings"
        :profiles="profiles"
        :provider-capability-summary="providerCapabilitySummary"
        :provider-capability-tags="providerCapabilityTags"
        :provider-label="providerLabel"
        :provider-label-from-any="providerLabelFromAny"
        :provider-runtime-value="providerRuntimeValue"
        :provider-storage-context="providerStorageContext"
        :provider-storage-match="providerStorageMatch"
        :provider-storage-ready="providerStorageReady"
        :status-color="statusColor"
        :validate-provider="validateProvider"
        :validations="validations"
        :visible-provider-codes="visibleProviderCodes"
      />

      <AdminBindingsCard
        :binding-columns="bindingColumns"
        :bindings="bindings"
        :can-configure-admin="canConfigureAdmin"
        :has-visible-providers="hasVisibleProviders"
        :open-create="openCreate"
        :open-edit="openEdit"
        :pretty-status="prettyStatus"
        :provider-label="providerLabel"
        :revalidate-binding="revalidateBinding"
        :scope-value="scopeValue"
        :status-color="statusColor"
      />

      <AdminRunsCard
        :apply-run-charge-filters="applyRunChargeFilters"
        :audited-sources="auditedSources"
        :can-view-admin="canViewAdmin"
        :capability-target-rule-label="capabilityTargetRuleLabel"
        :charge-basis-label="chargeBasisLabel"
        :charge-columns="chargeColumns"
        :export-current-run-charges="exportCurrentRunCharges"
        :format-bytes="formatBytes"
        :format-timestamp="formatTimestamp"
        :load-run-detail="loadRunDetail"
        :pretty-status="prettyStatus"
        :provider-label-from-any="providerLabelFromAny"
        :reset-run-charge-filters="resetRunChargeFilters"
        :run-charge-active-filters="runChargeActiveFilters"
        :run-charge-exporting="runChargeExporting"
        :run-charge-filters="runChargeFilters"
        :run-charge-loading="runChargeLoading"
        :run-charge-provider-options="runChargeProviderOptions"
        :run-charge-source-options="runChargeSourceOptions"
        :run-columns="runColumns"
        :run-detail-loading="runDetailLoading"
        :run-provider-summaries="runProviderSummaries"
        :run-requested-scope="runRequestedScope"
        :runs="runs"
        :scope-provider-codes="scopeProviderCodes"
        :scope-provider-plans="scopeProviderPlans"
        :selected-run="selectedRun"
        :selected-run-charge-response="selectedRunChargeResponse"
        :selected-run-charges="selectedRunCharges"
        :selected-run-detail="selectedRunDetail"
        :selected-run-provider-results="selectedRunProviderResults"
        :selected-run-scope-payload="selectedRunScopePayload"
        :selected-run-scope-summary="selectedRunScopeSummary"
        :source-allocation-audit="sourceAllocationAudit"
        :source-allocation-summary="sourceAllocationSummary"
        :source-columns="sourceColumns"
        :source-label-from-charge="sourceLabelFromCharge"
        :status-color="statusColor"
      />

      <AdminBindingModal
        :binding-loading="bindingLoading"
        :clear-scope-fields="clearScopeFields"
        :current-mode-options="currentModeOptions"
        :current-scope-options="currentScopeOptions"
        :form="form"
        :handle-provider-change="handleProviderChange"
        :modal-ok-text="modalOkText"
        :modal-title="modalTitle"
        :open="bindingOpen"
        :provider-options="providerOptions"
        :reset-form="resetForm"
        :search-tenants="searchTenants"
        :submit-binding="submitBinding"
        :tenants="tenants"
        @update:open="bindingOpen = $event"
      />
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

<script lang="ts" setup>
import type {
  BillingMode,
  BindingPayload,
  BindingRecord,
  BindingScopeType,
  OverviewResponse,
  ProviderCode,
  ProviderProfile,
  ProviderValidation,
  ReconciliationChargeRow,
  ReconciliationRunChargeFilters,
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
  | 'access_key'
  | 'access_key_id'
  | 'access_key_secret'
  | 'account_identifier'
  | 'bill_bucket'
  | 'bill_prefix'
  | 'bill_source'
  | 'profile_code'
  | 'region'
  | 'secret_id'
  | 'secret_key';

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

const providers: ProviderCode[] = ['qiniu-kodo', 'aliyun-oss', 'tencent-cos'];
const profileCodeMap: Record<ProviderCode, string> = {
  'qiniu-kodo': 'qiniu-default',
  'aliyun-oss': 'aliyun-default',
  'tencent-cos': 'tencent-default',
};
const profileFields: Record<ProviderCode, readonly ProviderField[]> = {
  'qiniu-kodo': ['profile_code', 'bill_source', 'access_key', 'secret_key', 'account_identifier'],
  'aliyun-oss': ['profile_code', 'bill_source', 'region', 'access_key_id', 'access_key_secret', 'bill_bucket', 'bill_prefix', 'account_identifier'],
  'tencent-cos': ['profile_code', 'bill_source', 'region', 'secret_id', 'secret_key', 'bill_bucket', 'bill_prefix', 'account_identifier'],
};
const secretFields = new Set<ProviderField>(['access_key', 'secret_key', 'access_key_id', 'access_key_secret', 'secret_id']);
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
const selectedRunCharges = ref<ReconciliationChargeRow[]>([]);
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
  { key: 'tenant', title: $t('plugin.storageBilling.admin.bindings.table.tenant') },
  { key: 'provider', title: $t('plugin.storageBilling.admin.bindings.table.provider') },
  { key: 'mode', title: $t('plugin.storageBilling.admin.bindings.table.mode') },
  { key: 'scope', title: $t('plugin.storageBilling.admin.bindings.table.scope') },
  { key: 'status', title: $t('plugin.storageBilling.admin.bindings.table.status') },
  { key: 'message', title: $t('plugin.storageBilling.admin.bindings.table.message') },
  { key: 'actions', title: $t('plugin.storageBilling.admin.bindings.table.actions') },
]);
const runColumns = computed(() => [
  { key: 'billing_date', title: $t('plugin.storageBilling.admin.runs.table.billingDate') },
  { key: 'status', title: $t('plugin.storageBilling.admin.runs.table.status') },
  { key: 'trigger_type', title: $t('plugin.storageBilling.admin.runs.table.trigger') },
  { key: 'providers', title: $t('plugin.storageBilling.admin.runs.table.providers') },
  { key: 'finished_at', title: $t('plugin.storageBilling.admin.runs.table.finishedAt') },
  { key: 'actions', title: $t('plugin.storageBilling.admin.runs.table.actions') },
]);
const sourceColumns = computed(() => [
  { key: 'provider', title: $t('plugin.storageBilling.admin.runs.sources.table.provider') },
  { key: 'status', title: $t('plugin.storageBilling.admin.runs.sources.table.status') },
  { key: 'amount', title: $t('plugin.storageBilling.admin.runs.sources.table.amount') },
  { key: 'usage', title: $t('plugin.storageBilling.admin.runs.sources.table.usage') },
  { key: 'allocation', title: $t('plugin.storageBilling.admin.runs.sources.table.allocation') },
  { key: 'error', title: $t('plugin.storageBilling.admin.runs.sources.table.error') },
]);
const chargeColumns = computed(() => [
  { key: 'billing_date', title: $t('plugin.storageBilling.admin.runs.charges.table.billingDate') },
  { key: 'tenant_id', title: $t('plugin.storageBilling.admin.runs.charges.table.tenant') },
  { key: 'provider', title: $t('plugin.storageBilling.admin.runs.charges.table.provider') },
  { key: 'source', title: $t('plugin.storageBilling.admin.runs.charges.table.source') },
  { key: 'charge_basis', title: $t('plugin.storageBilling.admin.runs.charges.table.chargeBasis') },
  { key: 'usage_bytes', title: $t('plugin.storageBilling.admin.runs.charges.table.usage') },
  { key: 'amount_total', title: $t('plugin.storageBilling.admin.runs.charges.table.amount') },
  { key: 'currency', title: $t('plugin.storageBilling.admin.runs.charges.table.currency') },
]);
const providerOptions = computed(() => providers.map((code) => ({ label: providerLabel(code), value: code })));
const modeOptions = computed(() => [
  { label: $t('plugin.storageBilling.admin.bindings.mode.official_reconciled'), value: 'official_reconciled' },
  { label: $t('plugin.storageBilling.admin.bindings.mode.official_pass_through'), value: 'official_pass_through' },
]);
const scopeOptions = computed(() => [
  { label: $t('plugin.storageBilling.admin.bindings.scope.bucket'), value: 'bucket' },
  { label: $t('plugin.storageBilling.admin.bindings.scope.domain'), value: 'domain' },
  { label: $t('plugin.storageBilling.admin.bindings.scope.account'), value: 'account' },
  { label: $t('plugin.storageBilling.admin.bindings.scope.tag'), value: 'tag' },
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
const modalTitle = computed(() => editingId.value === null ? $t('plugin.storageBilling.admin.bindingModal.createTitle') : $t('plugin.storageBilling.admin.bindingModal.editTitle'));
const modalOkText = computed(() => editingId.value === null ? $t('plugin.storageBilling.admin.bindingModal.submitCreate') : $t('plugin.storageBilling.admin.bindingModal.submitUpdate'));
const selectedRun = computed(() => selectedRunDetail.value?.run ?? null);
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
  return $t(`plugin.storageBilling.common.provider.${code}`);
}

function providerLabelFromAny(code: string): string {
  return providers.includes(code as ProviderCode) ? providerLabel(code as ProviderCode) : code || '-';
}

function fieldLabel(field: ProviderField): string {
  return $t(`plugin.storageBilling.admin.field.${field}`);
}

function fieldRequired(code: ProviderCode, field: ProviderField): boolean {
  return (validations[code].required_fields ?? []).includes(field);
}

function fieldConfigured(code: ProviderCode, field: ProviderField): boolean {
  return Boolean(profiles[code].configured_fields?.[field] || profiles[code].configured_secret_fields?.[field]);
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
    return $t(`plugin.storageBilling.common.status.${normalized}`);
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

function providerCapabilityTags(code: ProviderCode): string[] {
  return [
    profiles[code].settlement_cycle ? `${profiles[code].settlement_cycle}` : '',
    profiles[code].settlement_mode ? `${profiles[code].settlement_mode}` : '',
    profiles[code].strict_reconciliation_supported ? 'strict_daily' : '',
    profiles[code].manual_pull_supported ? 'manual_pull' : '',
  ].filter(Boolean);
}

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
  const key = `plugin.storageBilling.common.chargeBasis.${basis}`;
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

function resetForm(): void {
  Object.assign(form, emptyForm());
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
    message.success($t('plugin.storageBilling.admin.messages.exportSuccess'));
  } catch {
    message.error($t('plugin.storageBilling.admin.messages.requestFailed'));
  } finally {
    runChargeExporting.value = false;
  }
}

async function saveProfiles(): Promise<void> {
  saving.value = true;
  try {
    const payload = await saveProviderProfilesApi({ providers: { 'qiniu-kodo': providerPayload('qiniu-kodo'), 'aliyun-oss': providerPayload('aliyun-oss'), 'tencent-cos': providerPayload('tencent-cos') } });
    syncProfiles(payload);
    message.success($t('plugin.storageBilling.admin.messages.saved'));
  } finally {
    saving.value = false;
  }
}

async function validateProvider(code: ProviderCode): Promise<void> {
  const result = await validateProviderProfileApi(code, providerPayload(code));
  Object.assign(profiles[code], { ...profiles[code], ...result.profile });
  Object.assign(validations[code], { ...validations[code], ...result });
  message[result.status === 'valid' ? 'success' : 'warning']($t(result.status === 'valid' ? 'plugin.storageBilling.admin.messages.providerValid' : 'plugin.storageBilling.admin.messages.providerInvalid'));
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
    message.warning($t('plugin.storageBilling.admin.bindingForm.selectTenant'));
    return;
  }
  bindingLoading.value = true;
  try {
    const result = editingId.value === null ? await createBindingApi(bindingPayload()) : await updateBindingApi(editingId.value, bindingPayload());
    bindingOpen.value = false;
    await loadAll();
    message[result.validation.validation_status === 'valid' ? 'success' : 'warning']($t(result.validation.validation_status === 'valid' ? 'plugin.storageBilling.admin.messages.bindingSaved' : 'plugin.storageBilling.admin.messages.bindingInvalid'));
  } finally {
    bindingLoading.value = false;
  }
}

async function revalidateBinding(record: BindingRecord): Promise<void> {
  const result = await validateBindingApi(record.id);
  message[result.validation.validation_status === 'valid' ? 'success' : 'warning'](result.validation.validation_message || $t('plugin.storageBilling.admin.messages.bindingValidated'));
  await loadAll();
}

function triggerRun(): void {
  Modal.confirm({
    title: $t('plugin.storageBilling.admin.actions.triggerRun'),
    content: $t('plugin.storageBilling.admin.actions.triggerRunHint'),
    onOk: async () => {
      const result = await runReconciliationApi();
      message.success($t('plugin.storageBilling.admin.messages.runTriggered'));
      await loadAll();
      const runId = Number((result.run as Record<string, unknown>)?.id ?? 0);
      if (runId > 0) {
        await loadRunDetail(runId);
      }
    },
  });
}

function triggerQiniuMonthlyRun(): void {
  Modal.confirm({
    title: $t('plugin.storageBilling.admin.actions.triggerQiniuMonthly'),
    content: `${$t('plugin.storageBilling.admin.actions.triggerQiniuMonthlyHint')} (${qiniuBillingMonth.value || '-'})`,
    onOk: async () => {
      const result = await runQiniuMonthlySettlementApi({ billing_month: qiniuBillingMonth.value });
      message.success($t('plugin.storageBilling.admin.messages.runTriggered'));
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
          <div class="badge">{{ $t('plugin.storageBilling.admin.hero.badge') }}</div>
          <h1>{{ $t('plugin.storageBilling.admin.page.title') }}</h1>
          <p>{{ $t('plugin.storageBilling.admin.page.subtitle') }}</p>
        </div>
        <Space wrap>
          <Button @click="loadAll">{{ $t('plugin.storageBilling.admin.actions.refresh') }}</Button>
          <Button type="primary" @click="saveProfiles">{{ $t('plugin.storageBilling.admin.providers.save') }}</Button>
          <Button @click="triggerRun">{{ $t('plugin.storageBilling.admin.actions.triggerRun') }}</Button>
          <Input v-model:value="qiniuBillingMonth" class="toolbar-field" placeholder="YYYY-MM" />
          <Button @click="triggerQiniuMonthlyRun">{{ $t('plugin.storageBilling.admin.actions.triggerQiniuMonthly') }}</Button>
        </Space>
      </div>

      <div class="stats">
        <Card><Statistic :title="$t('plugin.storageBilling.admin.overview.billableDrivers')" :value="overview?.billable_drivers.length ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.admin.overview.enabledDrivers')" :value="overview?.host_snapshot.enabled_storage_drivers.length ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.admin.overview.bindingTotal')" :value="overview?.ledger_snapshot.binding_total ?? 0" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.admin.overview.statementTotal')" :value="overview?.ledger_snapshot.statement_total ?? 0" /></Card>
      </div>

      <Alert
        class="block"
        :message="$t('plugin.storageBilling.admin.hero.lag')"
        :description="`${overview?.reconciliation_schedule.local_time ?? '03:00'} / ${overview?.reconciliation_schedule.official_target_rule ?? 'D-2'} / ${overview?.mode ?? '-'}`"
        show-icon
        type="info"
      />

      <Card :title="$t('plugin.storageBilling.admin.providers.title')" class="block">
        <div class="section-subtitle">{{ $t('plugin.storageBilling.admin.providers.subtitle') }}</div>
        <div class="providers">
          <Card v-for="code in providers" :key="code">
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
            <Form layout="vertical">
              <FormItem :label="$t('plugin.storageBilling.admin.field.enabled')"><Switch v-model:checked="profiles[code].enabled" /></FormItem>
              <FormItem v-for="field in profileFields[code]" :key="field" :label="fieldLabel(field)">
                <template #extra>
                  <Space wrap>
                    <Tag :color="fieldRequired(code, field) ? 'error' : 'default'">
                      {{ fieldRequired(code, field) ? $t('plugin.storageBilling.admin.providers.required') : $t('plugin.storageBilling.admin.providers.optional') }}
                    </Tag>
                    <Tag v-if="secretFields.has(field) && fieldConfigured(code, field)" color="blue">{{ $t('plugin.storageBilling.admin.providers.secretConfigured') }}</Tag>
                  </Space>
                </template>
                <Select v-if="field === 'bill_source'" v-model:value="profiles[code][field]" :options="billSourceOptions(code)" />
                <Input
                  v-else
                  v-model:value="profiles[code][field]"
                  :placeholder="secretFields.has(field) && fieldConfigured(code, field) ? $t('plugin.storageBilling.admin.providers.secretKeep') : ''"
                  :type="secretFields.has(field) ? 'password' : 'text'"
                />
              </FormItem>
            </Form>
            <div class="actions"><Button @click="validateProvider(code)">{{ $t('plugin.storageBilling.admin.providers.validate') }}</Button></div>
          </Card>
        </div>
      </Card>

      <Card :title="$t('plugin.storageBilling.admin.bindings.title')" class="block">
        <template #extra><Button type="primary" @click="openCreate">{{ $t('plugin.storageBilling.admin.bindings.add') }}</Button></template>
        <div class="section-subtitle">{{ $t('plugin.storageBilling.admin.bindings.subtitle') }}</div>
        <Table :columns="bindingColumns" :data-source="bindings" :locale="{ emptyText: $t('plugin.storageBilling.admin.bindings.empty') }" :pagination="false" row-key="id">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'tenant'">#{{ record.tenant_id }}</template>
            <template v-else-if="column.key === 'provider'">{{ providerLabel(record.provider_code) }}</template>
            <template v-else-if="column.key === 'mode'">{{ $t(`plugin.storageBilling.admin.bindings.mode.${record.billing_mode}`) }}</template>
            <template v-else-if="column.key === 'scope'"><Space wrap><Tag color="blue">{{ $t(`plugin.storageBilling.admin.bindings.scope.${record.scope_type}`) }}</Tag><span>{{ scopeValue(record) }}</span></Space></template>
            <template v-else-if="column.key === 'status'"><Tag :color="statusColor(record.validation_status)">{{ prettyStatus(record.validation_status) }}</Tag></template>
            <template v-else-if="column.key === 'message'"><span class="muted">{{ record.validation_message || '-' }}</span></template>
            <template v-else-if="column.key === 'actions'"><Space wrap><Button size="small" @click="openEdit(record)">{{ $t('plugin.storageBilling.admin.bindings.edit') }}</Button><Button size="small" @click="revalidateBinding(record)">{{ $t('plugin.storageBilling.admin.bindings.revalidate') }}</Button></Space></template>
          </template>
        </Table>
        <div v-if="!bindings.length" class="empty"><Empty :description="$t('plugin.storageBilling.admin.bindings.empty')" /></div>
      </Card>

      <Card :title="$t('plugin.storageBilling.admin.runs.title')" class="block">
        <div class="section-subtitle">{{ $t('plugin.storageBilling.admin.runs.subtitle') }}</div>
        <Table :columns="runColumns" :data-source="runs" :locale="{ emptyText: $t('plugin.storageBilling.admin.runs.empty') }" :pagination="false" row-key="id">
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
              <Button size="small" @click="loadRunDetail(record.id)">{{ $t('plugin.storageBilling.admin.runs.view') }}</Button>
            </template>
          </template>
        </Table>
        <div v-if="!runs.length" class="empty"><Empty :description="$t('plugin.storageBilling.admin.runs.empty')" /></div>

        <Card v-if="selectedRun" class="run-detail" size="small">
          <template #title>{{ $t('plugin.storageBilling.admin.runs.detailTitle') }} · {{ selectedRun.period_label || selectedRun.billing_date }}</template>
          <template #extra>
            <Button
              :loading="runChargeExporting"
              size="small"
              @click="exportCurrentRunCharges"
            >
              {{ $t('plugin.storageBilling.admin.runs.charges.export') }}
            </Button>
          </template>
          <Spin :spinning="runDetailLoading">
            <Descriptions :column="3" size="small">
              <Descriptions.Item :label="$t('plugin.storageBilling.admin.runs.detail.status')">
                <Tag :color="statusColor(selectedRun.status)">{{ prettyStatus(selectedRun.status) }}</Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storageBilling.admin.runs.detail.trigger')">{{ selectedRun.trigger_type }}</Descriptions.Item>
              <Descriptions.Item :label="$t('plugin.storageBilling.admin.runs.detail.statementCount')">{{ selectedRun.summary.statement_count ?? 0 }}</Descriptions.Item>
            </Descriptions>

            <Table :columns="sourceColumns" :data-source="selectedRunDetail?.sources ?? []" :locale="{ emptyText: $t('plugin.storageBilling.admin.runs.sources.empty') }" :pagination="false" row-key="id">
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
                    <Tag color="success">{{ $t('plugin.storageBilling.admin.runs.audit.matched') }} {{ sourceAllocationSummary(record).matched_items }}</Tag>
                    <Tag color="warning">{{ $t('plugin.storageBilling.admin.runs.audit.unmatched') }} {{ sourceAllocationSummary(record).unmatched_items }}</Tag>
                    <Tag color="error">{{ $t('plugin.storageBilling.admin.runs.audit.ambiguous') }} {{ sourceAllocationSummary(record).ambiguous_items }}</Tag>
                  </Space>
                </template>
                <template v-else-if="column.key === 'error'">
                  <span class="muted">{{ record.error_message || '-' }}</span>
                </template>
              </template>
            </Table>

            <Card class="run-charge-card" size="small">
              <template #title>{{ $t('plugin.storageBilling.admin.runs.charges.title') }}</template>
              <div class="section-subtitle">{{ $t('plugin.storageBilling.admin.runs.charges.subtitle') }}</div>
              <Space wrap class="run-charge-toolbar">
                <Select
                  v-model:value="runChargeFilters.provider_code"
                  allow-clear
                  class="toolbar-field"
                  :options="runChargeProviderOptions"
                  :placeholder="$t('plugin.storageBilling.admin.runs.charges.filterProvider')"
                />
                <Select
                  v-model:value="runChargeFilters.source_id"
                  allow-clear
                  class="toolbar-field toolbar-source"
                  :options="runChargeSourceOptions"
                  :placeholder="$t('plugin.storageBilling.admin.runs.charges.filterSource')"
                />
                <Input
                  v-model:value="runChargeFilters.tenant_id"
                  class="toolbar-field"
                  :placeholder="$t('plugin.storageBilling.admin.runs.charges.filterTenant')"
                />
                <Button @click="applyRunChargeFilters">
                  {{ $t('plugin.storageBilling.admin.runs.charges.applyFilters') }}
                </Button>
                <Button @click="resetRunChargeFilters">
                  {{ $t('plugin.storageBilling.admin.runs.charges.resetFilters') }}
                </Button>
              </Space>
              <Spin :spinning="runChargeLoading">
                <Table
                  :columns="chargeColumns"
                  :data-source="selectedRunCharges"
                  :locale="{ emptyText: $t('plugin.storageBilling.admin.runs.charges.empty') }"
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
                  <Tag color="warning">{{ $t('plugin.storageBilling.admin.runs.audit.unmatchedSamples') }} {{ sourceAllocationAudit(source).unmatched_item_samples.length }}</Tag>
                  <Tag color="error">{{ $t('plugin.storageBilling.admin.runs.audit.ambiguousSamples') }} {{ sourceAllocationAudit(source).ambiguous_item_samples.length }}</Tag>
                </div>
                <details class="audit-details">
                  <summary>{{ $t('plugin.storageBilling.admin.runs.audit.toggle') }}</summary>
                  <pre>{{ JSON.stringify(source.raw_payload_json, null, 2) }}</pre>
                </details>
              </div>
            </div>
          </Spin>
        </Card>
      </Card>

      <Modal v-model:open="bindingOpen" :confirm-loading="bindingLoading" :title="modalTitle" :ok-text="modalOkText" @ok="submitBinding" @cancel="resetForm">
        <Form layout="vertical">
          <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.tenant')"><Select v-model:value="form.tenant_id" :options="tenants" :filter-option="false" show-search @search="searchTenants" /></FormItem>
          <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.provider')"><Select v-model:value="form.provider_code" :options="providerOptions" @change="handleProviderChange" /></FormItem>
          <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.mode')"><Select v-model:value="form.billing_mode" :options="currentModeOptions" /></FormItem>
          <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.scopeType')"><Select v-model:value="form.scope_type" :options="currentScopeOptions" @change="clearScopeFields" /></FormItem>
          <FormItem v-if="form.scope_type === 'bucket'" :label="$t('plugin.storageBilling.admin.bindingForm.bucketName')"><Input v-model:value="form.bucket_name" :placeholder="$t('plugin.storageBilling.admin.bindingForm.scopePlaceholder.bucket')" /></FormItem>
          <FormItem v-if="form.scope_type === 'domain'" :label="$t('plugin.storageBilling.admin.bindingForm.domainName')"><Input v-model:value="form.domain_name" :placeholder="$t('plugin.storageBilling.admin.bindingForm.scopePlaceholder.domain')" /></FormItem>
          <FormItem v-if="form.scope_type === 'account'" :label="$t('plugin.storageBilling.admin.bindingForm.accountIdentifier')"><Input v-model:value="form.account_identifier" :placeholder="$t('plugin.storageBilling.admin.bindingForm.scopePlaceholder.account')" /></FormItem>
          <template v-if="form.scope_type === 'tag'">
            <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.tagKey')"><Input v-model:value="form.tag_key" :placeholder="$t('plugin.storageBilling.admin.bindingForm.scopePlaceholder.tagKey')" /></FormItem>
            <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.tagValue')"><Input v-model:value="form.tag_value" :placeholder="$t('plugin.storageBilling.admin.bindingForm.scopePlaceholder.tagValue')" /></FormItem>
          </template>
          <FormItem :label="$t('plugin.storageBilling.admin.bindingForm.isActive')"><Switch v-model:checked="form.is_active" /></FormItem>
        </Form>
      </Modal>
    </Spin>
  </Page>
</template>

<style scoped>
.storage-billing-admin{--hero:linear-gradient(135deg,#fff7ed,#f8fafc 50%,#eff6ff)}
.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:20px;padding:24px;border-radius:24px;background:var(--hero);border:1px solid rgba(180,83,9,.14)}
.badge{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#b45309;margin-bottom:8px}
.hero h1{margin:0 0 8px;font-size:28px}
.hero p{margin:0;color:#475569;max-width:760px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}
.block{margin-bottom:20px}
.providers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.section-subtitle,.muted{color:#64748b}
.section-subtitle{margin-bottom:16px}
.actions{display:flex;justify-content:flex-end}
.empty{margin-top:12px}
.run-detail{margin-top:16px}
.run-charge-toolbar{display:flex;margin-bottom:12px}
.toolbar-field{min-width:180px}
.toolbar-source{min-width:260px}
.run-charge-card{margin-top:16px}
.audit-list{display:grid;gap:12px;margin-top:16px}
.audit-card{padding:16px;border-radius:16px;background:#f8fafc;border:1px solid rgba(148,163,184,.2)}
.audit-head,.audit-summary{margin-bottom:12px}
.audit-details summary{cursor:pointer;color:#0f172a;font-weight:600}
.audit-details pre{margin-top:12px;padding:12px;border-radius:12px;background:#0f172a;color:#e2e8f0;overflow:auto;max-height:320px}
@media (max-width:1200px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.providers{grid-template-columns:1fr}}
@media (max-width:768px){.hero{flex-direction:column}.stats{grid-template-columns:1fr}}
</style>

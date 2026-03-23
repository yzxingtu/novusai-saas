export type ProviderCode = 'aliyun-oss' | 'qiniu-kodo' | 'tencent-cos';
export type BindingScopeType = 'account' | 'bucket' | 'domain' | 'tag';
export type BillingMode = 'official_pass_through' | 'official_reconciled';
export type PeriodType = 'daily' | 'monthly';
export type SettlementMode = 'monthly_settled' | 'strict_daily_reconciliation' | 'unsupported';

export interface ProviderCapabilitySnapshot {
  capability_message?: string;
  manual_pull_supported?: boolean;
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  recommended_scope_types?: string[];
  scheduled_daily_supported?: boolean;
  settlement_cycle?: PeriodType;
  settlement_mode?: SettlementMode;
  strict_reconciliation_supported?: boolean;
  supported_period_types?: PeriodType[];
}

export interface PluginStatusSnapshot {
  enabled: boolean;
  name: string;
  status?: string;
}

export interface StorageContextSnapshot {
  apply_quota?: boolean;
  storage_mode?: string;
  storage_config?: {
    base_url?: string | null;
    driver?: string;
    options?: Record<string, unknown>;
    root_path?: string | null;
  };
}

export interface ProviderRuntimeStorageSnapshot {
  base_url?: string | null;
  bucket_name?: null | string;
  current_driver?: string;
  driver_match?: boolean;
  endpoint?: string | null;
  prefix?: string | null;
  region?: string | null;
  root_path?: string | null;
  source?: string;
  storage_mode?: string;
}

export interface ReconciliationScheduleRule {
  cron?: string;
  local_time?: string;
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
}

export interface ReconciliationProviderPlan extends ReconciliationScheduleRule {
  billing_date: string;
  provider_code: string;
}

export interface ReconciliationRequestedScope extends Record<string, unknown> {
  billing_date?: string;
  billing_month?: string;
  job?: string;
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  provider_codes?: string[];
  provider_plans?: ReconciliationProviderPlan[];
  resolved_provider_code?: string;
  scheduled_provider_code?: string;
}

export interface OverviewResponse {
  billable_drivers: string[];
  excluded_drivers: string[];
  host_snapshot: {
    active_storage_driver?: null | string;
    enabled_storage_drivers: Array<{
      code: string;
      display_name?: string;
      is_available?: boolean;
      plugin_name?: string | null;
      plugin_status?: string | null;
    }>;
    platform_storage_context?: StorageContextSnapshot;
    related_plugins: PluginStatusSnapshot[];
  };
  ledger_snapshot: {
    binding_total: number;
    daily_charge_total: number;
    latest_runs: ReconciliationRun[];
    statement_total: number;
  };
  mode: string;
  provider_capabilities?: Record<string, ProviderCapabilitySnapshot>;
  provider_schedules?: Record<string, {
    cron?: string;
    local_time?: string;
    provider_rules?: Record<string, ReconciliationScheduleRule>;
    provider_codes?: string[];
  }>;
  reconciliation_schedule: {
    cron: string;
    local_time: string;
    official_billing_lag_days?: null | number;
    official_target_rule?: string;
    provider_rules?: Record<string, ReconciliationScheduleRule>;
  };
  status: string;
}

export interface ReconciliationRun {
  billing_date: string;
  completed_at: null | string;
  error_message: null | string;
  id: number;
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  provider_codes: string[];
  requested_scope: ReconciliationRequestedScope;
  run_key: string;
  started_at: null | string;
  status: string;
  summary: {
    driver_count?: number;
    excluded_drivers?: string[];
    providers?: ReconciliationProviderSummary[];
    source_status_counts?: Record<string, number>;
    statement_count?: number;
  } & Record<string, unknown>;
  trigger_type: string;
}

export interface ReconciliationProviderSummary {
  ambiguous_items?: number;
  charge_item_count?: number;
  matched_items?: number;
  provider_code: string;
  source_status: string;
  unmatched_items?: number;
  written_charge_rows?: number;
}

export interface ReconciliationSourceRecord {
  amount_total: string;
  billing_date: string;
  currency: string;
  driver_code: string;
  error_message: null | string;
  fetched_at: null | string;
  id: number;
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  provider_code: ProviderCode | string;
  raw_payload_json: Record<string, unknown>;
  run_id: number;
  source_key: string;
  source_ref: string;
  source_status: string;
  usage_bytes: number;
}

export interface ReconciliationRunListResponse {
  items: ReconciliationRun[];
  limit: number;
  total: number;
}

export interface ReconciliationRunDetailResponse {
  run: ReconciliationRun;
  sources: ReconciliationSourceRecord[];
}

export interface ReconciliationRunChargeFilters {
  provider_code?: string;
  source_id?: number;
  tenant_id?: number;
}

export interface ReconciliationChargeRow {
  amount_total: string;
  billing_date: string;
  charge_basis: string;
  currency: string;
  details?: Record<string, unknown>;
  driver_code: string;
  id: number;
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  provider_code: ProviderCode | string;
  run_id?: number;
  source_key?: null | string;
  source_ref?: null | string;
  source_status?: string;
  source_id?: null | number;
  statement_id?: null | number;
  tenant_id: number;
  usage_bytes: number;
}

export interface ReconciliationRunChargeListResponse {
  billing_date?: string;
  filters?: Record<string, unknown>;
  items: ReconciliationChargeRow[];
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  run?: ReconciliationRun;
  run_id: number;
  source_total?: number;
  summary?: Record<string, unknown>;
  total: number;
}

export interface ProviderProfile {
  account_identifier?: string;
  bill_source: string;
  active_storage_driver?: string;
  collector_ready?: boolean;
  configured_fields?: Record<string, boolean>;
  configured_secret_fields?: Record<string, boolean>;
  capability_message?: string;
  driver_enabled?: boolean | null;
  enabled: boolean;
  host_credentials_configured?: boolean;
  implemented?: boolean;
  manual_pull_supported?: boolean;
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  profile_code: string;
  profile_valid?: boolean;
  recommended_scope_types?: string[];
  region?: string;
  required_fields?: string[];
  scheduled_daily_supported?: boolean;
  settlement_cycle?: PeriodType;
  settlement_mode?: SettlementMode;
  status?: string;
  storage_context?: ProviderRuntimeStorageSnapshot;
  storage_driver_match?: boolean;
  strict_reconciliation_supported?: boolean;
  supported_bill_sources?: string[];
  supported_period_types?: PeriodType[];
}

export interface ProviderValidation {
  active_storage_driver?: string;
  capability_message?: string;
  collector_ready: boolean;
  driver_enabled?: boolean | null;
  errors: string[];
  host_credentials_configured?: boolean;
  manual_pull_supported?: boolean;
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  profile_valid: boolean;
  required_fields: string[];
  recommended_scope_types?: string[];
  scheduled_daily_supported?: boolean;
  settlement_cycle?: PeriodType;
  settlement_mode?: SettlementMode;
  status: string;
  storage_context?: ProviderRuntimeStorageSnapshot;
  storage_driver_match?: boolean;
  strict_reconciliation_supported?: boolean;
  supported_bill_sources: string[];
  supported_period_types?: PeriodType[];
  warnings: string[];
}

export interface ProviderProfilesResponse {
  providers: Record<ProviderCode, ProviderProfile>;
  supported_providers: string[];
  validations: Record<ProviderCode, ProviderValidation>;
}

export interface BindingRecord {
  account_identifier?: null | string;
  binding_key: string;
  billing_mode: BillingMode;
  bucket_name?: null | string;
  created_at: null | string;
  domain_name?: null | string;
  driver_code: string;
  entitlement_snapshot: Record<string, unknown>;
  id: number;
  is_active: boolean;
  metadata: Record<string, unknown>;
  provider_code: ProviderCode;
  provider_profile_code: string;
  scope_type: BindingScopeType;
  scope_value: string;
  tag_key?: null | string;
  tag_value?: null | string;
  tenant_id: number;
  updated_at: null | string;
  validated_at: null | string;
  validation_message: null | string;
  validation_status: string;
}

export interface BindingListResponse {
  items: BindingRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface BindingPayload {
  account_identifier?: string;
  billing_mode: BillingMode;
  bucket_name?: string;
  domain_name?: string;
  is_active?: boolean;
  metadata_json?: Record<string, unknown>;
  provider_code: ProviderCode;
  scope_type: BindingScopeType;
  scope_value?: string;
  tag_key?: string;
  tag_value?: string;
  tenant_id: number;
}

export interface BindingMutationResponse {
  binding: BindingRecord;
  ok: boolean;
  validation: {
    errors: string[];
    message: string;
    status: string;
    validated_at: string;
    validation_message: string;
    validation_status: string;
    warnings: string[];
  };
}

export interface TenantSelectOption {
  extra?: {
    code?: string;
    isActive?: boolean;
  };
  label: string;
  value: number;
}

export interface TenantStatementSummary {
  amount_total: string;
  billing_date: string;
  charge_count: number;
  currency: string;
  generated_at: null | string;
  id: number;
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  published_at: null | string;
  status: string;
  summary: Record<string, unknown>;
  tenant_id: number;
}

export interface TenantStatementResponse {
  billable_drivers: string[];
  charge_local_storage: boolean;
  excluded_drivers: string[];
  message: string;
  request_id: string;
  statement: null | TenantStatementSummary;
  statement_status: string;
  tenant_id: null | number;
}

export interface TenantStatementsResponse {
  items: TenantStatementSummary[];
  limit: number;
  total: number;
}

export interface TenantStatementChargeRow {
  amount_total: string;
  billing_date: string;
  charge_basis: string;
  currency: string;
  details?: Record<string, unknown>;
  driver_code?: string;
  id?: number;
  period_end?: string;
  period_label?: string;
  period_start?: string;
  period_type?: PeriodType;
  provider_code: string;
  usage_bytes: number;
}

export interface TenantStatementChargeSummaryRow {
  amount_total: string;
  charge_count: number;
  currency: string;
  usage_bytes: number;
}

export interface TenantStatementChargeProviderSummaryRow extends TenantStatementChargeSummaryRow {
  provider_code: string;
}

export interface TenantStatementChargeBasisSummaryRow extends TenantStatementChargeSummaryRow {
  charge_basis: string;
}

export interface TenantStatementChargeSummary {
  amount_total: string;
  charge_basis_totals: TenantStatementChargeBasisSummaryRow[];
  provider_totals: TenantStatementChargeProviderSummaryRow[];
  total_usage_bytes: number;
}

export interface TenantStatementChargesResponse {
  billing_date: null | string;
  items: TenantStatementChargeRow[];
  message: string;
  period_type?: PeriodType | string;
  statement: null | TenantStatementSummary;
  summary: TenantStatementChargeSummary;
  tenant_id: null | number;
  total: number;
}

export interface TenantPrerequisitesResponse {
  bindings: {
    active_total: number;
    items: BindingRecord[];
    matching_active_total?: number;
    ready_total?: number;
    total: number;
    valid_active_total?: number;
  };
  ok: boolean;
  plan: {
    code?: string;
    name?: string;
    plan_id?: number;
    storage_billing_enabled: boolean;
  };
  prerequisites: {
    charge_local_storage: boolean;
    current_driver: string;
    current_driver_billable: boolean;
    feature_enabled: boolean;
    missing_reasons: string[];
    ready: boolean;
  };
  provider_profiles: ProviderProfilesResponse;
  provider_capabilities?: Record<string, ProviderCapabilitySnapshot>;
  storage_context: {
    tenant_id?: number;
  } & StorageContextSnapshot;
  tenant_id: number;
}

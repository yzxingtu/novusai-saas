import type {
  BillingMode,
  BindingPayload,
  BindingScopeType,
  PeriodType,
  ProviderCode,
  ProviderProfile,
  ProviderValidation,
} from '../../types';

export type ProviderField = 'account_identifier' | 'bill_source' | 'profile_code';

export type BindingFormState = {
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

export type CapabilitySummary = {
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  recommended_scope_types: BindingScopeType[];
  settlement_cycle?: string;
  settlement_mode?: string;
  supported_period_types: PeriodType[];
  strict_reconciliation_supported?: boolean;
  manual_pull_supported?: boolean;
  scheduled_daily_supported?: boolean;
};

export type ProviderProfileEnvelope = {
  providers: Partial<Record<ProviderCode, ProviderProfile>>;
  validations: Partial<Record<ProviderCode, ProviderValidation>>;
};

export type SharedAccessApi = {
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (codes: string[]) => boolean;
};

export const PROVIDERS: ProviderCode[] = ['qiniu-kodo', 'aliyun-oss', 'tencent-cos'];
export const RUN_HISTORY_LIMIT = 10;

export const PROFILE_CODE_MAP: Record<ProviderCode, string> = {
  'qiniu-kodo': 'qiniu-default',
  'aliyun-oss': 'aliyun-default',
  'tencent-cos': 'tencent-default',
};

export const PROFILE_FIELDS: Record<ProviderCode, readonly ProviderField[]> = {
  'qiniu-kodo': ['profile_code', 'bill_source', 'account_identifier'],
  'aliyun-oss': ['profile_code', 'bill_source', 'account_identifier'],
  'tencent-cos': ['profile_code', 'bill_source', 'account_identifier'],
};

const YEAR_MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;
const BILLING_DATE_PATTERN = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

export function emptyProfile(code: ProviderCode): ProviderProfile {
  return {
    enabled: false,
    bill_source: '',
    profile_code: PROFILE_CODE_MAP[code],
    configured_fields: {},
    configured_secret_fields: {},
    required_fields: [],
    supported_bill_sources: [],
  };
}

export function emptyValidation(): ProviderValidation {
  return {
    collector_ready: false,
    errors: [],
    profile_valid: false,
    required_fields: [],
    status: 'pending',
    supported_bill_sources: [],
    warnings: [],
  };
}

export function emptyProfiles(): Record<ProviderCode, ProviderProfile> {
  return {
    'qiniu-kodo': emptyProfile('qiniu-kodo'),
    'aliyun-oss': emptyProfile('aliyun-oss'),
    'tencent-cos': emptyProfile('tencent-cos'),
  };
}

export function emptyValidations(): Record<ProviderCode, ProviderValidation> {
  return {
    'qiniu-kodo': emptyValidation(),
    'aliyun-oss': emptyValidation(),
    'tencent-cos': emptyValidation(),
  };
}

export function emptyForm(): BindingFormState {
  return {
    account_identifier: '',
    billing_mode: 'official_reconciled',
    bucket_name: '',
    domain_name: '',
    is_active: true,
    provider_code: 'tencent-cos',
    scope_type: 'bucket',
    tag_key: '',
    tag_value: '',
    tenant_id: null,
  };
}

export function uniqueStrings(
  values: Array<null | string | undefined>,
): string[] {
  return Array.from(
    new Set(values.map((item) => (item ?? '').trim()).filter((item) => item)),
  );
}

export function buildMergedProviderState(
  code: ProviderCode,
  payload: ProviderProfileEnvelope,
): {
  profile: ProviderProfile;
  validation: ProviderValidation;
} {
  const nextProfile = {
    ...emptyProfile(code),
    ...(payload.providers[code] ?? {}),
  };
  const nextValidation = {
    ...emptyValidation(),
    ...(payload.validations[code] ?? {}),
  };

  nextProfile.required_fields = uniqueStrings([
    ...(nextProfile.required_fields ?? []),
    ...(nextValidation.required_fields ?? []),
  ]);
  nextProfile.supported_bill_sources = uniqueStrings([
    ...(nextProfile.supported_bill_sources ?? []),
    ...(nextValidation.supported_bill_sources ?? []),
    nextProfile.bill_source,
  ]);
  nextValidation.required_fields = uniqueStrings([
    ...(nextValidation.required_fields ?? []),
    ...(nextProfile.required_fields ?? []),
  ]);
  nextValidation.supported_bill_sources = uniqueStrings([
    ...(nextValidation.supported_bill_sources ?? []),
    ...(nextProfile.supported_bill_sources ?? []),
    nextProfile.bill_source,
  ]);

  return {
    profile: nextProfile,
    validation: nextValidation,
  };
}

export function buildProviderPayload(
  profiles: Record<ProviderCode, ProviderProfile>,
  code: ProviderCode,
): Partial<ProviderProfile> {
  const payload: Partial<ProviderProfile> = {
    enabled: Boolean(profiles[code].enabled),
  };

  for (const field of PROFILE_FIELDS[code]) {
    const value = profiles[code][field];
    payload[field] = typeof value === 'string' ? value : '';
  }

  return payload;
}

export function buildBindingPayload(form: BindingFormState): BindingPayload {
  const payload: BindingPayload = {
    tenant_id: Number(form.tenant_id),
    provider_code: form.provider_code,
    billing_mode: form.billing_mode,
    scope_type: form.scope_type,
    is_active: form.is_active,
  };

  if (form.scope_type === 'bucket') payload.bucket_name = form.bucket_name.trim();
  if (form.scope_type === 'domain') payload.domain_name = form.domain_name.trim();
  if (form.scope_type === 'account') {
    payload.account_identifier = form.account_identifier.trim();
  }
  if (form.scope_type === 'tag') {
    payload.tag_key = form.tag_key.trim();
    payload.tag_value = form.tag_value.trim();
  }

  return payload;
}

export function isValidYearMonth(value: string): boolean {
  return YEAR_MONTH_PATTERN.test(value);
}

export function isValidBillingDate(value: string): boolean {
  return BILLING_DATE_PATTERN.test(value);
}

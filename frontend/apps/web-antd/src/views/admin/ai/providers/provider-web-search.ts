import type {
  ProviderWebSearchConfig,
  ProviderWebSearchRuntime,
  ProviderWebSearchVerifiedTarget,
} from '#/api/admin/ai';

import { $t } from '#/locales';

export type ProviderWebSearchStrategy = 'native_first_fallback_public';
export type PublicWebSearchProvider = 'baidu' | 'so360';

export interface ProviderWebSearchConfigWithAdvancedFields extends ProviderWebSearchConfig {
  allow_unverified_runtime_target?: boolean;
  verified_native_target?: null | ProviderWebSearchVerifiedTarget;
}

export const WEB_SEARCH_DEFAULTS: ProviderWebSearchConfig = {
  enabled: true,
  strategy: 'native_first_fallback_public',
  max_results_cap: 8,
  native_timeout_seconds: 20,
  public_timeout_seconds: 15,
  public_providers: ['baidu', 'so360'],
};

const WEB_SEARCH_PUBLIC_PROVIDER_OPTIONS: PublicWebSearchProvider[] = [
  'baidu',
  'so360',
];

function toIntInRange(
  value: unknown,
  fallback: number,
  min: number,
  max: number,
): number {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return fallback;
  const rounded = Math.trunc(raw);
  if (rounded < min) return min;
  if (rounded > max) return max;
  return rounded;
}

function normalizePublicProviders(value: unknown): PublicWebSearchProvider[] {
  const rawList = Array.isArray(value) ? value : [];
  const providers = rawList
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(
      (item): item is PublicWebSearchProvider =>
        item === 'baidu' || item === 'so360',
    );
  return providers.length > 0 ? [...new Set(providers)] : ['baidu', 'so360'];
}

function readOptionalBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function readOptionalString(
  value: unknown,
  maxLength: number,
): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) return undefined;
  return normalized;
}

function readOptionalPositiveInt(value: unknown): number | undefined {
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    return undefined;
  }
  return value;
}

function hasOwnField(
  values: Record<string, unknown>,
  fieldName: string,
): boolean {
  return Object.prototype.hasOwnProperty.call(values, fieldName);
}

function normalizeVerifiedNativeTarget(
  value: unknown,
): null | ProviderWebSearchVerifiedTarget | undefined {
  if (value === null) return null;
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  const normalized: ProviderWebSearchVerifiedTarget = {};
  const providerId = readOptionalPositiveInt(record.provider_id);
  const providerCode = readOptionalString(record.provider_code, 50);
  const modelId = readOptionalPositiveInt(record.model_id);
  const modelCode = readOptionalString(record.model_code, 100);

  if (providerId !== undefined) normalized.provider_id = providerId;
  if (providerCode !== undefined) normalized.provider_code = providerCode;
  if (modelId !== undefined) normalized.model_id = modelId;
  if (modelCode !== undefined) normalized.model_code = modelCode;

  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function buildVerifiedNativeTargetFromFormValues(
  values: Record<string, unknown>,
): null | ProviderWebSearchVerifiedTarget | undefined {
  const hasFlatFields =
    hasOwnField(values, 'web_search_verified_provider_code') ||
    hasOwnField(values, 'web_search_verified_model_code') ||
    hasOwnField(values, 'web_search_verified_provider_id') ||
    hasOwnField(values, 'web_search_verified_model_id');
  if (!hasFlatFields) {
    return normalizeVerifiedNativeTarget(
      values.web_search_verified_native_target,
    );
  }

  const target: ProviderWebSearchVerifiedTarget = {};
  const providerId = readOptionalPositiveInt(
    values.web_search_verified_provider_id,
  );
  const providerCode = readOptionalString(
    values.web_search_verified_provider_code,
    50,
  );
  const modelId = readOptionalPositiveInt(values.web_search_verified_model_id);
  const modelCode = readOptionalString(
    values.web_search_verified_model_code,
    100,
  );

  if (providerId !== undefined) target.provider_id = providerId;
  if (providerCode !== undefined) target.provider_code = providerCode;
  if (modelId !== undefined) target.model_id = modelId;
  if (modelCode !== undefined) target.model_code = modelCode;

  return Object.keys(target).length > 0 ? target : null;
}

function mergeProviderWebSearchAdvancedFields(
  nextConfig: ProviderWebSearchConfig,
  source?:
    | null
    | ProviderWebSearchConfigWithAdvancedFields
    | Record<string, unknown>,
): ProviderWebSearchConfigWithAdvancedFields {
  const merged: ProviderWebSearchConfigWithAdvancedFields = { ...nextConfig };
  if (!source) return merged;

  const allowUnverified = readOptionalBoolean(
    (source as Record<string, unknown>).allow_unverified_runtime_target,
  );
  if (allowUnverified !== undefined) {
    merged.allow_unverified_runtime_target = allowUnverified;
  }

  const verifiedTarget = normalizeVerifiedNativeTarget(
    (source as Record<string, unknown>).verified_native_target,
  );
  if (verifiedTarget !== undefined) {
    merged.verified_native_target = verifiedTarget;
  }

  return merged;
}

export function resolveProviderWebSearchConfig(
  config: null | Record<string, unknown> | undefined,
): ProviderWebSearchConfigWithAdvancedFields {
  const raw = config?.web_search;
  if (!raw || typeof raw !== 'object') {
    return { ...WEB_SEARCH_DEFAULTS };
  }
  const webSearch = raw as Record<string, unknown>;
  return mergeProviderWebSearchAdvancedFields(
    {
      enabled:
        typeof webSearch.enabled === 'boolean'
          ? webSearch.enabled
          : WEB_SEARCH_DEFAULTS.enabled,
      strategy:
        webSearch.strategy === 'native_first_fallback_public'
          ? 'native_first_fallback_public'
          : WEB_SEARCH_DEFAULTS.strategy,
      max_results_cap: toIntInRange(
        webSearch.max_results_cap,
        WEB_SEARCH_DEFAULTS.max_results_cap,
        1,
        10,
      ),
      native_timeout_seconds: toIntInRange(
        webSearch.native_timeout_seconds,
        WEB_SEARCH_DEFAULTS.native_timeout_seconds,
        1,
        120,
      ),
      public_timeout_seconds: toIntInRange(
        webSearch.public_timeout_seconds,
        WEB_SEARCH_DEFAULTS.public_timeout_seconds,
        1,
        120,
      ),
      public_providers: normalizePublicProviders(webSearch.public_providers),
    },
    webSearch,
  );
}

export function buildProviderWebSearchConfigFromForm(
  values: Record<string, unknown>,
  existingConfig?: null | ProviderWebSearchConfigWithAdvancedFields,
): ProviderWebSearchConfigWithAdvancedFields {
  const hasExplicitAdvancedFields =
    hasOwnField(values, 'web_search_allow_unverified_runtime_target') ||
    hasOwnField(values, 'web_search_verified_provider_code') ||
    hasOwnField(values, 'web_search_verified_model_code') ||
    hasOwnField(values, 'web_search_verified_provider_id') ||
    hasOwnField(values, 'web_search_verified_model_id') ||
    normalizeVerifiedNativeTarget(values.web_search_verified_native_target) !==
      undefined;
  const verifiedTargetFromForm =
    buildVerifiedNativeTargetFromFormValues(values);
  const allowUnverifiedFromForm = readOptionalBoolean(
    values.web_search_allow_unverified_runtime_target,
  );

  return mergeProviderWebSearchAdvancedFields(
    {
      enabled: values.web_search_enabled !== false,
      strategy:
        values.web_search_strategy === 'native_first_fallback_public'
          ? 'native_first_fallback_public'
          : WEB_SEARCH_DEFAULTS.strategy,
      max_results_cap: toIntInRange(
        values.web_search_max_results_cap,
        WEB_SEARCH_DEFAULTS.max_results_cap,
        1,
        10,
      ),
      native_timeout_seconds: toIntInRange(
        values.web_search_native_timeout_seconds,
        WEB_SEARCH_DEFAULTS.native_timeout_seconds,
        1,
        120,
      ),
      public_timeout_seconds: toIntInRange(
        values.web_search_public_timeout_seconds,
        WEB_SEARCH_DEFAULTS.public_timeout_seconds,
        1,
        120,
      ),
      public_providers: normalizePublicProviders(
        values.web_search_public_providers,
      ),
    },
    hasExplicitAdvancedFields
      ? {
          allow_unverified_runtime_target: allowUnverifiedFromForm ?? false,
          verified_native_target: verifiedTargetFromForm,
        }
      : existingConfig,
  );
}

export function getProviderWebSearchStrategyOptions() {
  return [
    {
      label: $t(
        'admin.ai.provider.webSearch.strategyOptions.native_first_fallback_public',
      ),
      value: 'native_first_fallback_public',
    },
  ];
}

export function getProviderWebSearchPublicProviderOptions() {
  return WEB_SEARCH_PUBLIC_PROVIDER_OPTIONS.map((provider) => ({
    label: $t(`admin.ai.provider.webSearch.publicProviderOptions.${provider}`),
    value: provider,
  }));
}

export function getProviderWebSearchStrategyText(
  strategy: null | string | undefined,
): string {
  if (strategy === 'native_first_fallback_public') {
    return $t(
      'admin.ai.provider.webSearch.strategyOptions.native_first_fallback_public',
    );
  }
  return $t(
    'admin.ai.provider.webSearch.strategyOptions.native_first_fallback_public',
  );
}

export function getProviderWebSearchRuntimeSummary(
  runtime: null | ProviderWebSearchRuntime | undefined,
): string {
  if (!runtime) return $t('admin.ai.provider.webSearch.runtime.unknown');
  if (runtime.native_supported) {
    const provider = runtime.native_provider || '-';
    return $t('admin.ai.provider.webSearch.runtime.nativeSupported', {
      provider,
    });
  }
  if (runtime.reason) {
    return $t('admin.ai.provider.webSearch.runtime.fallbackReason', {
      reason: runtime.reason,
    });
  }
  return $t('admin.ai.provider.webSearch.runtime.fallbackDefault');
}

export function shouldWarnProviderWebSearchAutoFallback(
  runtime: null | ProviderWebSearchRuntime | undefined,
): boolean {
  return Boolean(runtime && runtime.native_supported === false);
}

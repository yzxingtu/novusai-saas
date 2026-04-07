/**
 * AI 供应商管理 - 表格列、搜索和表单配置
 * AI provider admin — columns, search and form config
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  AdapterTypeInfo,
  AIProviderInfo,
  ProviderWebSearchConfig,
  ProviderWebSearchRuntime,
  ProviderWebSearchVerifiedTarget,
} from '#/api/admin/ai';

import { ref } from 'vue';

import {
  inputField,
  searchInput,
  select,
  switchField,
  textareaField,
  z,
} from '#/adapter/form';
import { dragColumn } from '#/adapter/vxe-table';
import { getAdapterTypesApi } from '#/api/admin/ai';
import { $t } from '#/locales';

/** 缓存适配器类型列表 / Cached adapter type list */
const adapterTypesCache = ref<AdapterTypeInfo[]>([]);

export type OpenAICompatibleWireApi = 'chat_completions' | 'responses';
export type ResponsesToolHistoryMode = 'structured' | 'text';
export type ProviderWebSearchStrategy = 'native_first_fallback_public';
export type PublicWebSearchProvider = 'baidu' | 'so360';

export interface ProviderWebSearchConfigWithAdvancedFields extends ProviderWebSearchConfig {
  allow_unverified_runtime_target?: boolean;
  verified_native_target?: null | ProviderWebSearchVerifiedTarget;
}

const WEB_SEARCH_DEFAULTS: ProviderWebSearchConfig = {
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

const OPENAI_COMPATIBLE_FORBIDDEN_BASE_URL_SUFFIXES = [
  '/responses',
  '/chat/completions',
] as const;

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
  return providers.length > 0
    ? Array.from(new Set(providers))
    : ['baidu', 'so360'];
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

function hasOwnField(values: Record<string, unknown>, fieldName: string): boolean {
  return Object.prototype.hasOwnProperty.call(values, fieldName);
}

function normalizeVerifiedNativeTarget(
  value: unknown,
): null | ProviderWebSearchVerifiedTarget | undefined {
  if (value === null) return null;
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return undefined;

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
    return normalizeVerifiedNativeTarget(values.web_search_verified_native_target);
  }

  const target: ProviderWebSearchVerifiedTarget = {};
  const providerId = readOptionalPositiveInt(values.web_search_verified_provider_id);
  const providerCode = readOptionalString(
    values.web_search_verified_provider_code,
    50,
  );
  const modelId = readOptionalPositiveInt(values.web_search_verified_model_id);
  const modelCode = readOptionalString(values.web_search_verified_model_code, 100);

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
    | Record<string, unknown>
    | ProviderWebSearchConfigWithAdvancedFields,
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
  const verifiedTargetFromForm = buildVerifiedNativeTargetFromFormValues(values);
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

function normalizeWireApi(
  wireApi: null | string | undefined,
): null | OpenAICompatibleWireApi {
  const normalizedValue = String(wireApi || '')
    .trim()
    .toLowerCase()
    .replaceAll('-', '_');
  if (
    normalizedValue === 'responses' ||
    normalizedValue === 'chat_completions'
  ) {
    return normalizedValue;
  }
  return null;
}

export function normalizeProviderBaseUrlInput(
  baseUrl: null | string | undefined,
): null | string {
  const trimmedBaseUrl = typeof baseUrl === 'string' ? baseUrl.trim() : '';
  return trimmedBaseUrl || null;
}

export function hasForbiddenProviderEndpointSuffix(
  baseUrl: null | string | undefined,
  providerType: null | string | undefined,
): boolean {
  if (providerType !== 'openai_compatible') {
    return false;
  }
  const normalizedBaseUrl = normalizeProviderBaseUrlInput(baseUrl);
  if (!normalizedBaseUrl) {
    return false;
  }
  const normalizedForSuffixCheck = stripTrailingSlashes(
    normalizedBaseUrl.toLowerCase(),
  );
  return OPENAI_COMPATIBLE_FORBIDDEN_BASE_URL_SUFFIXES.some((suffix) =>
    normalizedForSuffixCheck.endsWith(suffix),
  );
}

export function hasLikelyMissingProviderApiVersion(
  baseUrl: null | string | undefined,
  providerType: null | string | undefined,
): boolean {
  if (providerType !== 'openai_compatible') {
    return false;
  }
  const normalizedBaseUrl = normalizeProviderBaseUrlInput(baseUrl);
  if (!normalizedBaseUrl) {
    return false;
  }
  try {
    const url = new URL(normalizedBaseUrl);
    const normalizedPath = stripTrailingSlashes(url.pathname);
    if (!normalizedPath) {
      return true;
    }
    return !hasVersionSegment(normalizedPath);
  } catch {
    return false;
  }
}

function stripTrailingSlashes(value: string): string {
  let result = value;
  while (result.endsWith('/')) {
    result = result.slice(0, -1);
  }
  return result;
}

function hasVersionSegment(pathname: string): boolean {
  const segments = pathname.split('/').filter(Boolean);
  const tail = segments.at(-1) || '';
  if (tail.length < 2 || !tail.startsWith('v')) {
    return false;
  }
  return /^\d+$/.test(tail.slice(1));
}

export function resolveProviderWireApi(
  providerType: null | string | undefined,
  wireApi?: null | string,
): null | OpenAICompatibleWireApi {
  const normalizedWireApi = normalizeWireApi(wireApi);
  if (providerType !== 'openai_compatible') {
    return null;
  }
  return normalizedWireApi || 'chat_completions';
}

export function getProviderWireApiOptions() {
  return [
    {
      label: $t('admin.ai.provider.wireApiOptions.chat_completions'),
      value: 'chat_completions',
    },
    {
      label: $t('admin.ai.provider.wireApiOptions.responses'),
      value: 'responses',
    },
  ];
}

export function getProviderWireApiText(
  wireApi: null | string | undefined,
): string {
  const normalizedWireApi = normalizeWireApi(wireApi) || 'chat_completions';
  return $t(`admin.ai.provider.wireApiOptions.${normalizedWireApi}`);
}

export function isResponsesToolHistoryCompatEnabled(
  config: null | Record<string, unknown> | undefined,
): boolean {
  return config?.responses_tool_history_mode === 'text';
}

function isValidProviderBaseUrl(value: string): boolean {
  const trimmedValue = value.trim();
  if (!trimmedValue) return true;

  try {
    const url = new URL(trimmedValue);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

/** 加载适配器类型（含插件注册的） / Load adapter types (including plugin-registered) */
export async function loadAdapterTypes(): Promise<AdapterTypeInfo[]> {
  if (adapterTypesCache.value.length > 0) return adapterTypesCache.value;
  try {
    const data = await getAdapterTypesApi();
    adapterTypesCache.value = data;
    return data;
  } catch {
    return [
      {
        type: 'openai_compatible',
        source: 'builtin',
        display_name: 'OpenAI Compatible',
      },
    ];
  }
}

function getProviderTypeOptions() {
  const types = adapterTypesCache.value;
  if (types.length > 0) {
    return types.map((t) => ({
      label:
        t.source === 'plugin' ? `${t.display_name} (Plugin)` : t.display_name,
      value: t.type,
    }));
  }
  return [
    {
      label: $t('admin.ai.provider.type_options.openai_compatible'),
      value: 'openai_compatible',
    },
  ];
}

/**
 * 获取供应商类型文本
 */
export function getProviderTypeText(type: string | undefined): string {
  if (!type) return '-';
  const cached = adapterTypesCache.value.find((t) => t.type === type);
  if (cached) return cached.display_name;
  switch (type) {
    case 'openai_compatible': {
      return $t('admin.ai.provider.type_options.openai_compatible');
    }
    default: {
      return type;
    }
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = AIProviderInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    dragColumn,
    {
      field: 'name',
      title: $t('admin.ai.provider.name'),
      minWidth: 280,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('admin.ai.provider.type'),
      width: 160,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'wire_api',
      title: $t('admin.ai.provider.wireApi'),
      width: 180,
      align: 'center',
      slots: { default: 'wireApi_cell' },
    },
    {
      field: 'web_search',
      title: $t('admin.ai.provider.webSearch.title'),
      minWidth: 260,
      slots: { default: 'webSearch_cell' },
    },
    {
      field: 'model_count',
      title: $t('admin.ai.provider.modelCount'),
      width: 100,
      align: 'center',
      slots: { default: 'modelCount_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.provider.isActive'),
      width: 130,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_provider',
          nameField: 'name',
          nameTitle: $t('admin.ai.provider.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', 'delete'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.ai.provider.name'), {
      placeholder: $t('admin.ai.provider.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('admin.ai.provider.type'), {
      options: getProviderTypeOptions(),
      placeholder: $t('admin.ai.provider.type'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit = false): VbenFormSchema[] {
  return [
    inputField('name', $t('admin.ai.provider.name'), {
      required: true,
      placeholder: $t('admin.ai.provider.placeholder.inputName'),
    }),
    ...(isEdit
      ? [
          inputField('code', $t('admin.ai.provider.code'), {
            disabled: true,
          }),
        ]
      : []),
    {
      ...select('type', $t('admin.ai.provider.type'), {
        options: getProviderTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.provider.placeholder.selectType'),
      }),
      help: $t('admin.ai.provider.help.type'),
    },
    {
      component: 'Input',
      componentProps: {
        maxLength: 500,
        placeholder: $t('admin.ai.provider.placeholder.inputBaseUrl'),
      },
      fieldName: 'base_url',
      label: $t('admin.ai.provider.baseUrl'),
      rules: z
        .union([z.string(), z.undefined()])
        .refine(
          (value: string | undefined) =>
            value === undefined ||
            value === '' ||
            isValidProviderBaseUrl(value),
          { message: $t('admin.ai.provider.validation.baseUrlInvalid') },
        ),
      help: $t('admin.ai.provider.help.baseUrl'),
    } as VbenFormSchema,
    {
      ...select('wire_api', $t('admin.ai.provider.wireApi'), {
        options: getProviderWireApiOptions(),
        placeholder: $t('admin.ai.provider.placeholder.selectWireApi'),
        required: true,
      }),
      dependencies: {
        triggerFields: ['type'],
        show: (values: Record<string, unknown>) =>
          values.type === 'openai_compatible',
      },
      help: $t('admin.ai.provider.help.wireApi'),
    },
    {
      ...switchField(
        'responses_tool_history_compat',
        $t('admin.ai.provider.responsesToolHistoryCompat'),
        {
          defaultValue: false,
        },
      ),
      dependencies: {
        triggerFields: ['type', 'wire_api'],
        show: (values: Record<string, unknown>) =>
          values.type === 'openai_compatible' &&
          values.wire_api === 'responses',
      },
      help: $t('admin.ai.provider.help.responsesToolHistoryCompat'),
    },
    {
      ...switchField(
        'web_search_enabled',
        $t('admin.ai.provider.webSearch.enabled'),
        {
          defaultValue: WEB_SEARCH_DEFAULTS.enabled,
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.enabled'),
    },
    {
      ...select(
        'web_search_strategy',
        $t('admin.ai.provider.webSearch.strategy'),
        {
          options: getProviderWebSearchStrategyOptions(),
          required: true,
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.strategy'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 10,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_max_results_cap',
      label: $t('admin.ai.provider.webSearch.maxResultsCap'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: number | null | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 10),
          {
            message: $t('admin.ai.provider.webSearch.validation.maxResultsCap'),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.maxResultsCap'),
    } as VbenFormSchema,
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 120,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_native_timeout_seconds',
      label: $t('admin.ai.provider.webSearch.nativeTimeoutSeconds'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: number | null | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 120),
          {
            message: $t(
              'admin.ai.provider.webSearch.validation.nativeTimeoutSeconds',
            ),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.nativeTimeoutSeconds'),
    } as VbenFormSchema,
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 120,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_public_timeout_seconds',
      label: $t('admin.ai.provider.webSearch.publicTimeoutSeconds'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: number | null | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 120),
          {
            message: $t(
              'admin.ai.provider.webSearch.validation.publicTimeoutSeconds',
            ),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.publicTimeoutSeconds'),
    } as VbenFormSchema,
    {
      ...select(
        'web_search_public_providers',
        $t('admin.ai.provider.webSearch.publicProviders'),
        {
          options: getProviderWebSearchPublicProviderOptions(),
          componentProps: {
            mode: 'multiple',
            maxTagCount: 'responsive',
          },
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.publicProviders'),
    },
    {
      ...switchField(
        'web_search_allow_unverified_runtime_target',
        $t('admin.ai.provider.webSearch.allowUnverifiedRuntimeTarget'),
        {
          defaultValue: false,
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          values.type === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.allowUnverifiedRuntimeTarget'),
    },
    {
      ...inputField(
        'web_search_verified_provider_code',
        $t('admin.ai.provider.webSearch.verifiedProviderCode'),
        {
          placeholder: $t(
            'admin.ai.provider.webSearch.placeholder.verifiedProviderCode',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          values.type === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.verifiedProviderCode'),
    },
    {
      ...inputField(
        'web_search_verified_model_code',
        $t('admin.ai.provider.webSearch.verifiedModelCode'),
        {
          placeholder: $t(
            'admin.ai.provider.webSearch.placeholder.verifiedModelCode',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          values.type === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.verifiedModelCode'),
    },
    textareaField('description', $t('admin.ai.provider.description'), {
      placeholder: $t('admin.ai.provider.placeholder.inputDescription'),
    }),
    {
      component: 'ImageUpload' as const,
      fieldName: 'icon',
      label: $t('admin.ai.provider.icon'),
    },
    {
      ...switchField('is_active', $t('admin.ai.provider.isActive'), {
        defaultValue: true,
      }),
      help: $t('admin.ai.provider.help.isActive'),
    },
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'openai_compatible',
    wire_api: 'chat_completions',
    responses_tool_history_compat: false,
    web_search_enabled: WEB_SEARCH_DEFAULTS.enabled,
    web_search_strategy: WEB_SEARCH_DEFAULTS.strategy,
    web_search_max_results_cap: WEB_SEARCH_DEFAULTS.max_results_cap,
    web_search_native_timeout_seconds:
      WEB_SEARCH_DEFAULTS.native_timeout_seconds,
    web_search_public_timeout_seconds:
      WEB_SEARCH_DEFAULTS.public_timeout_seconds,
    web_search_public_providers: [...WEB_SEARCH_DEFAULTS.public_providers],
    web_search_allow_unverified_runtime_target: false,
    web_search_verified_provider_code: '',
    web_search_verified_model_code: '',
    is_active: true,
    sort_order: 0,
  };
}

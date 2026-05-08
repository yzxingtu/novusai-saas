import type {
  AIProviderConfig,
  AIProviderProtocolCapabilities,
  ProviderWireApi,
} from '#/api/admin/ai-providers';

import { $t } from '#/locales';

export type OpenAICompatibleWireApi = ProviderWireApi;

const OPENAI_COMPATIBLE_FORBIDDEN_BASE_URL_SUFFIXES = [
  '/responses',
  '/chat/completions',
] as const;
const RETIRED_PROVIDER_CONFIG_KEY_TOKENS = new Set([
  'allow_adapter_cross_protocol_fallback',
  'allowed_cross_protocol_fallbacks',
  'responses_tool_history_compat',
  'responses_tool_history_mode',
  'wire_api',
]);

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

function getProviderProtocolCapabilities(
  config: AIProviderConfig | null | undefined,
): AIProviderProtocolCapabilities | null {
  const protocolCapabilities = config?.protocol_capabilities;
  return protocolCapabilities && typeof protocolCapabilities === 'object'
    ? protocolCapabilities
    : null;
}

function isProviderConfigRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeProviderConfigKey(key: string): string {
  return key
    .trim()
    .toLowerCase()
    .replaceAll(/[\s.\-:/\\]+/g, '_')
    .replaceAll(/^_+|_+$/g, '');
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

function stripRetiredProviderConfigValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stripRetiredProviderConfigValue(item));
  }
  if (!isProviderConfigRecord(value)) {
    return value;
  }

  const cleanedConfig: Record<string, unknown> = {};
  for (const [key, nestedValue] of Object.entries(value)) {
    if (RETIRED_PROVIDER_CONFIG_KEY_TOKENS.has(normalizeProviderConfigKey(key))) {
      continue;
    }
    cleanedConfig[key] = stripRetiredProviderConfigValue(nestedValue);
  }
  return cleanedConfig;
}

function sanitizeProviderConfig(
  config: AIProviderConfig | null | undefined,
): AIProviderConfig {
  const cleanedConfig = stripRetiredProviderConfigValue(config ?? {});
  return isProviderConfigRecord(cleanedConfig)
    ? (cleanedConfig as AIProviderConfig)
    : {};
}

export function buildProviderConfigWithPrimaryWireApi(
  currentConfig: AIProviderConfig | null | undefined,
  providerType: null | string | undefined,
  primaryWireApi: null | string | undefined,
): AIProviderConfig | null {
  const nextConfig = sanitizeProviderConfig(currentConfig);

  if (providerType === 'openai_compatible') {
    const currentPrimaryWireApi = normalizeWireApi(
      getProviderProtocolCapabilities(nextConfig)?.primary_wire_api,
    );
    const effectivePrimaryWireApi =
      normalizeWireApi(primaryWireApi) || currentPrimaryWireApi;
    const nextProtocolCapabilities: AIProviderProtocolCapabilities = {
      ...(getProviderProtocolCapabilities(nextConfig) ?? {}),
    };

    if (effectivePrimaryWireApi) {
      nextProtocolCapabilities.primary_wire_api = effectivePrimaryWireApi;
      nextProtocolCapabilities.allowed_wire_apis = [effectivePrimaryWireApi];
      nextConfig.protocol_capabilities = nextProtocolCapabilities;
    } else {
      delete nextConfig.protocol_capabilities;
    }
  } else {
    delete nextConfig.protocol_capabilities;
  }

  return Object.keys(nextConfig).length > 0 ? nextConfig : null;
}

export function resolveProviderPrimaryWireApi(
  providerType: null | string | undefined,
  config?: AIProviderConfig | null,
): null | OpenAICompatibleWireApi {
  if (providerType !== 'openai_compatible') {
    return null;
  }
  return normalizeWireApi(
    getProviderProtocolCapabilities(config)?.primary_wire_api,
  );
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
  const normalizedWireApi = normalizeWireApi(wireApi);
  if (!normalizedWireApi) {
    return '-';
  }
  return $t(`admin.ai.provider.wireApiOptions.${normalizedWireApi}`);
}

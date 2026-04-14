import { $t } from '#/locales';

export type OpenAICompatibleWireApi = 'chat_completions' | 'responses';
export type ResponsesToolHistoryMode = 'structured' | 'text';

const OPENAI_COMPATIBLE_FORBIDDEN_BASE_URL_SUFFIXES = [
  '/responses',
  '/chat/completions',
] as const;

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

import type {
  AIModelConfig,
  ModelProviderType,
  ReasoningEffort,
} from '#/api/admin/ai-models';

import { OPENAI_COMPATIBLE_PROVIDER_TYPE } from './model-options';

const REASONING_MODEL_PREFIXES = ['gpt-5', 'o1', 'o3', 'o4'] as const;

export function supportsReasoningEffort(
  modelCode: null | string | undefined,
): boolean {
  const normalizedModelCode = String(modelCode || '')
    .trim()
    .toLowerCase();
  if (!normalizedModelCode) return false;
  return REASONING_MODEL_PREFIXES.some((prefix) =>
    normalizedModelCode.startsWith(prefix),
  );
}

export function supportsAdvancedRuntimeParams(options: {
  modelCode?: null | string;
  modelType?: null | string;
  providerType?: ModelProviderType | null;
}): boolean {
  return (
    options.providerType === OPENAI_COMPATIBLE_PROVIDER_TYPE &&
    options.modelType === 'chat' &&
    supportsReasoningEffort(options.modelCode)
  );
}

export function normalizeReasoningEffort(
  value: null | string | undefined,
): null | ReasoningEffort {
  switch (
    String(value || '')
      .trim()
      .toLowerCase()
  ) {
    case 'high':
    case 'low':
    case 'medium':
    case 'none':
    case 'xhigh': {
      return String(value).trim().toLowerCase() as ReasoningEffort;
    }
    default: {
      return null;
    }
  }
}

export function getOpenAICompatibleRuntimeOverrides(
  config: AIModelConfig | null | undefined,
): NonNullable<AIModelConfig['runtime_overrides']>['openai_compatible'] | null {
  const runtimeOverrides = config?.runtime_overrides;
  if (!runtimeOverrides || typeof runtimeOverrides !== 'object') {
    return null;
  }

  const openaiOverrides = runtimeOverrides.openai_compatible;
  if (!openaiOverrides || typeof openaiOverrides !== 'object') {
    return null;
  }

  return openaiOverrides;
}

export function readConfiguredReasoningEffort(
  config: AIModelConfig | null | undefined,
): null | ReasoningEffort {
  const openaiOverrides = getOpenAICompatibleRuntimeOverrides(config);
  const responsesEffort = normalizeReasoningEffort(
    openaiOverrides?.responses?.reasoning?.effort,
  );
  if (responsesEffort) return responsesEffort;

  return null;
}

export function resolveReasoningEffort(
  config: AIModelConfig | null | undefined,
  modelCode?: null | string,
  providerType?: ModelProviderType | null,
  modelType?: null | string,
): null | ReasoningEffort {
  const normalizedModelCode = resolveModelCodeForForm(config, modelCode);
  const configEffort = supportsAdvancedRuntimeParams({
    providerType,
    modelCode: normalizedModelCode,
    modelType,
  })
    ? readConfiguredReasoningEffort(config)
    : null;
  if (configEffort) return configEffort;
  return null;
}

export function resolveModelCodeForForm(
  _config: AIModelConfig | null | undefined,
  modelCode?: null | string,
): string {
  return String(modelCode || '');
}

export function buildModelConfig(
  reasoningEffort: null | string | undefined,
  modelCode?: null | string,
  providerType?: ModelProviderType | null,
  modelType?: null | string,
  configSnapshot?: AIModelConfig | null,
): AIModelConfig | null {
  const normalizedEffort = normalizeReasoningEffort(reasoningEffort);
  const nextConfig: AIModelConfig = { ...configSnapshot };
  const nextRuntimeOverrides =
    nextConfig.runtime_overrides &&
    typeof nextConfig.runtime_overrides === 'object'
      ? { ...nextConfig.runtime_overrides }
      : {};
  const nextOpenAIOverrides =
    nextRuntimeOverrides.openai_compatible &&
    typeof nextRuntimeOverrides.openai_compatible === 'object'
      ? { ...nextRuntimeOverrides.openai_compatible }
      : {};
  const nextResponsesOverrides =
    nextOpenAIOverrides.responses &&
    typeof nextOpenAIOverrides.responses === 'object'
      ? { ...nextOpenAIOverrides.responses }
      : {};
  const nextReasoning =
    nextResponsesOverrides.reasoning &&
    typeof nextResponsesOverrides.reasoning === 'object'
      ? { ...nextResponsesOverrides.reasoning }
      : {};
  delete nextOpenAIOverrides.chat_completions;

  if (
    normalizedEffort &&
    supportsAdvancedRuntimeParams({
      providerType,
      modelCode,
      modelType,
    })
  ) {
    nextReasoning.effort = normalizedEffort;
    nextResponsesOverrides.reasoning = nextReasoning;
    nextOpenAIOverrides.responses = nextResponsesOverrides;
    nextRuntimeOverrides.openai_compatible = nextOpenAIOverrides;
    nextConfig.runtime_overrides = nextRuntimeOverrides;
  } else {
    delete nextReasoning.effort;
    if (Object.keys(nextReasoning).length > 0) {
      nextResponsesOverrides.reasoning = nextReasoning;
    } else {
      delete nextResponsesOverrides.reasoning;
    }

    if (Object.keys(nextResponsesOverrides).length > 0) {
      nextOpenAIOverrides.responses = nextResponsesOverrides;
    } else {
      delete nextOpenAIOverrides.responses;
    }
    if (Object.keys(nextOpenAIOverrides).length > 0) {
      nextRuntimeOverrides.openai_compatible = nextOpenAIOverrides;
    } else {
      delete nextRuntimeOverrides.openai_compatible;
    }
    if (Object.keys(nextRuntimeOverrides).length > 0) {
      nextConfig.runtime_overrides = nextRuntimeOverrides;
    } else {
      delete nextConfig.runtime_overrides;
    }
  }

  delete nextConfig.reasoning;
  delete nextConfig.reasoning_effort;
  delete nextConfig.reasoningEffort;
  delete nextConfig.runtimeOverrides;

  return Object.keys(nextConfig).length > 0 ? nextConfig : null;
}

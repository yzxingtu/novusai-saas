/**
 * AI 模型管理 - 表格列、搜索和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  AIModelConfig,
  AIModelInfo,
  ModelProviderType,
  ReasoningEffort,
  RemoteModelCapabilities,
} from '#/api/admin/ai';

import {
  dividerField,
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
} from '#/adapter/form';
import { getAIModelSelectApi, getAIProviderSelectApi } from '#/api/admin/ai';
import { $t } from '#/locales';

const LEGACY_REASONING_MODEL_PREFIXES = ['gpt-5', 'o1', 'o3', 'o4'] as const;
const OPENAI_COMPATIBLE_PROVIDER_TYPE = 'openai_compatible' as const;

export function supportsReasoningEffort(
  modelCode: null | string | undefined,
): boolean {
  const normalizedModelCode = String(modelCode || '').trim().toLowerCase();
  if (!normalizedModelCode) return false;
  return LEGACY_REASONING_MODEL_PREFIXES.some((prefix) =>
    normalizedModelCode.startsWith(prefix),
  );
}

export function supportsAdvancedRuntimeParams(options: {
  providerType?: null | ModelProviderType;
  modelCode?: null | string;
  modelType?: null | string;
}): boolean {
  return (
    options.providerType === OPENAI_COMPATIBLE_PROVIDER_TYPE &&
    options.modelType === 'chat' &&
    supportsReasoningEffort(options.modelCode)
  );
}

export function getReasoningEffortOptions() {
  return [
    { label: $t('admin.ai.model.reasoningEffortOptions.none'), value: 'none' },
    { label: $t('admin.ai.model.reasoningEffortOptions.low'), value: 'low' },
    {
      label: $t('admin.ai.model.reasoningEffortOptions.medium'),
      value: 'medium',
    },
    { label: $t('admin.ai.model.reasoningEffortOptions.high'), value: 'high' },
    {
      label: $t('admin.ai.model.reasoningEffortOptions.xhigh'),
      value: 'xhigh',
    },
  ];
}

export function normalizeReasoningEffort(
  value: null | string | undefined,
): null | ReasoningEffort {
  switch (String(value || '').trim().toLowerCase()) {
    case 'none':
    case 'low':
    case 'medium':
    case 'high':
    case 'xhigh': {
      return String(value).trim().toLowerCase() as ReasoningEffort;
    }
    default: {
      return null;
    }
  }
}

export function extractLegacyReasoningAlias(modelCode: null | string | undefined): {
  reasoningEffort: null | ReasoningEffort;
  upstreamModel: string;
} | null {
  const normalizedModelCode = String(modelCode || '').trim();
  if (!normalizedModelCode) return null;

  const segments = normalizedModelCode.split('-');
  if (segments.length < 2) return null;
  const effortSegment = segments.at(-1);
  const baseModel = segments.slice(0, -1).join('-');
  if (
    !LEGACY_REASONING_MODEL_PREFIXES.some((prefix) => baseModel.startsWith(prefix))
  ) {
    return null;
  }

  const reasoningEffort = normalizeReasoningEffort(effortSegment);
  if (!reasoningEffort) return null;

  return {
    upstreamModel: baseModel,
    reasoningEffort,
  };
}

export function getOpenAICompatibleRuntimeOverrides(
  config: AIModelConfig | null | undefined,
): null | NonNullable<AIModelConfig['runtime_overrides']>['openai_compatible'] {
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

  const chatEffort = normalizeReasoningEffort(
    openaiOverrides?.chat_completions?.reasoning_effort,
  );
  if (chatEffort) return chatEffort;

  const legacyReasoningEffort = normalizeReasoningEffort(config?.reasoning?.effort);
  if (legacyReasoningEffort) return legacyReasoningEffort;

  return normalizeReasoningEffort(
    config?.reasoning_effort || config?.reasoningEffort,
  );
}

export function resolveReasoningEffort(
  config: AIModelConfig | null | undefined,
  modelCode?: null | string,
  providerType?: null | ModelProviderType,
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
  return extractLegacyReasoningAlias(modelCode)?.reasoningEffort || null;
}

export function resolveModelCodeForForm(
  config: AIModelConfig | null | undefined,
  modelCode?: null | string,
): string {
  const configEffort = readConfiguredReasoningEffort(config);
  if (configEffort) return String(modelCode || '');
  return (
    extractLegacyReasoningAlias(modelCode)?.upstreamModel || String(modelCode || '')
  );
}

export function buildModelConfig(
  reasoningEffort: null | string | undefined,
  modelCode?: null | string,
  providerType?: null | ModelProviderType,
  modelType?: null | string,
  configSnapshot?: AIModelConfig | null,
): AIModelConfig | null {
  const normalizedEffort = normalizeReasoningEffort(reasoningEffort);
  const nextConfig: AIModelConfig = { ...(configSnapshot || {}) };
  const nextRuntimeOverrides =
    nextConfig.runtime_overrides && typeof nextConfig.runtime_overrides === 'object'
      ? { ...nextConfig.runtime_overrides }
      : {};
  const nextOpenAIOverrides =
    nextRuntimeOverrides.openai_compatible &&
    typeof nextRuntimeOverrides.openai_compatible === 'object'
      ? { ...nextRuntimeOverrides.openai_compatible }
      : {};
  const nextResponsesOverrides =
    nextOpenAIOverrides.responses && typeof nextOpenAIOverrides.responses === 'object'
      ? { ...nextOpenAIOverrides.responses }
      : {};
  const nextChatOverrides =
    nextOpenAIOverrides.chat_completions &&
    typeof nextOpenAIOverrides.chat_completions === 'object'
      ? { ...nextOpenAIOverrides.chat_completions }
      : {};
  const nextReasoning =
    nextResponsesOverrides.reasoning &&
    typeof nextResponsesOverrides.reasoning === 'object'
      ? { ...nextResponsesOverrides.reasoning }
      : {};

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
    nextChatOverrides.reasoning_effort = normalizedEffort;
    nextOpenAIOverrides.responses = nextResponsesOverrides;
    nextOpenAIOverrides.chat_completions = nextChatOverrides;
    nextRuntimeOverrides.openai_compatible = nextOpenAIOverrides;
    nextConfig.runtime_overrides = nextRuntimeOverrides;
  } else {
    delete nextReasoning.effort;
    if (Object.keys(nextReasoning).length > 0) {
      nextResponsesOverrides.reasoning = nextReasoning;
    } else {
      delete nextResponsesOverrides.reasoning;
    }
    delete nextChatOverrides.reasoning_effort;

    if (Object.keys(nextResponsesOverrides).length > 0) {
      nextOpenAIOverrides.responses = nextResponsesOverrides;
    } else {
      delete nextOpenAIOverrides.responses;
    }
    if (Object.keys(nextChatOverrides).length > 0) {
      nextOpenAIOverrides.chat_completions = nextChatOverrides;
    } else {
      delete nextOpenAIOverrides.chat_completions;
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

  // Normalize away the earlier GPT-specific flat config shape on save.
  delete nextConfig.reasoning;
  delete nextConfig.reasoning_effort;
  delete nextConfig.reasoningEffort;

  return Object.keys(nextConfig).length > 0 ? nextConfig : null;
}

export function buildModelPayload(
  values: Record<string, unknown>,
  configSnapshot?: AIModelConfig | null,
): Record<string, unknown> {
  return {
    name: values.name,
    code: typeof values.code === 'string' ? values.code.trim() : values.code,
    type: values.type,
    provider_id: values.provider_id,
    context_window: values.context_window || null,
    max_output_tokens: values.max_output_tokens || null,
    input_price_per_1k: values.input_price_per_1k || null,
    output_price_per_1k: values.output_price_per_1k || null,
    rpm_limit: values.rpm_limit || null,
    tpm_limit: values.tpm_limit || null,
    supports_function_calling: values.supports_function_calling ?? false,
    supports_vision: values.supports_vision ?? false,
    supports_audio: values.supports_audio ?? false,
    supports_video: values.supports_video ?? false,
    supports_streaming: values.supports_streaming ?? true,
    max_image_count: values.supports_vision ? values.max_image_count || 5 : null,
    max_image_size_mb: values.supports_vision
      ? values.max_image_size_mb || 10
      : null,
    is_active: values.is_active ?? true,
    config: buildModelConfig(
      typeof values.reasoning_effort === 'string'
        ? values.reasoning_effort
        : null,
      typeof values.code === 'string' ? values.code : null,
      typeof values.provider_type === 'string' ? values.provider_type : null,
      typeof values.type === 'string' ? values.type : null,
      configSnapshot,
    ),
    fallback_model_id: values.fallback_model_id || null,
    tier: values.tier || null,
  };
}

export function buildModelFormValues(data: AIModelInfo): Record<string, unknown> {
  return {
    name: data.name,
    code: resolveModelCodeForForm(data.config, data.code),
    type: data.type,
    provider_id: data.provider_id,
    provider_type: data.provider_type,
    context_window: data.context_window,
    max_output_tokens: data.max_output_tokens,
    input_price_per_1k: data.input_price_per_1k,
    output_price_per_1k: data.output_price_per_1k,
    rpm_limit: data.rpm_limit,
    tpm_limit: data.tpm_limit,
    supports_function_calling: data.supports_function_calling,
    supports_vision: data.supports_vision,
    supports_audio: data.supports_audio,
    supports_video: data.supports_video,
    supports_streaming: data.supports_streaming,
    max_image_count: data.max_image_count ?? 5,
    max_image_size_mb: data.max_image_size_mb ?? 10,
    is_active: data.is_active,
    reasoning_effort: resolveReasoningEffort(
      data.config,
      data.code,
      data.provider_type,
      data.type,
    ),
    fallback_model_id: data.fallback_model_id,
    tier: data.tier,
  };
}

export function buildRemoteModelFormValues(
  modelId: string,
  providerId?: number,
  providerType?: null | ModelProviderType,
  caps?: null | RemoteModelCapabilities,
): Record<string, unknown> {
  const defaults = getFormDefaults();
  const values: Record<string, unknown> = {
    ...defaults,
    provider_id: providerId,
    provider_type: providerType || OPENAI_COMPATIBLE_PROVIDER_TYPE,
    code: modelId,
    name: modelId,
    reasoning_effort: null,
    context_window: null,
    max_output_tokens: null,
    input_price_per_1k: null,
    output_price_per_1k: null,
    rpm_limit: null,
    tpm_limit: null,
    fallback_model_id: null,
  };

  if (caps) {
    if (caps.model_type) values.type = caps.model_type;
    if (caps.supports_vision !== null && caps.supports_vision !== undefined)
      values.supports_vision = caps.supports_vision;
    if (caps.supports_audio !== null && caps.supports_audio !== undefined)
      values.supports_audio = caps.supports_audio;
    if (caps.supports_video !== null && caps.supports_video !== undefined)
      values.supports_video = caps.supports_video;
    if (
      caps.supports_function_calling !== null &&
      caps.supports_function_calling !== undefined
    )
      values.supports_function_calling = caps.supports_function_calling;
    if (
      caps.supports_streaming !== null &&
      caps.supports_streaming !== undefined
    )
      values.supports_streaming = caps.supports_streaming;
    if (caps.context_window !== null && caps.context_window !== undefined)
      values.context_window = caps.context_window;
    if (caps.max_output_tokens !== null && caps.max_output_tokens !== undefined)
      values.max_output_tokens = caps.max_output_tokens;
    if (
      caps.input_price_per_1k !== null &&
      caps.input_price_per_1k !== undefined
    )
      values.input_price_per_1k = caps.input_price_per_1k;
    if (
      caps.output_price_per_1k !== null &&
      caps.output_price_per_1k !== undefined
    )
      values.output_price_per_1k = caps.output_price_per_1k;
    if (caps.rpm_limit !== null && caps.rpm_limit !== undefined)
      values.rpm_limit = caps.rpm_limit;
    if (caps.tpm_limit !== null && caps.tpm_limit !== undefined)
      values.tpm_limit = caps.tpm_limit;
  }

  return values;
}

function getModelTypeOptions() {
  return [
    { label: $t('admin.ai.model.type_options.chat'), value: 'chat' },
    { label: $t('admin.ai.model.type_options.embedding'), value: 'embedding' },
    { label: $t('admin.ai.model.type_options.image'), value: 'image' },
  ];
}

function getModelTierOptions() {
  return [
    { label: $t('admin.ai.model.tier_options.fast'), value: 'fast' },
    { label: $t('admin.ai.model.tier_options.standard'), value: 'standard' },
    { label: $t('admin.ai.model.tier_options.premium'), value: 'premium' },
  ];
}

export function getModelTierText(tier: null | string | undefined): string {
  if (!tier) return '-';
  return $t(`admin.ai.model.tier_options.${tier}` as never, tier);
}

/**
 * 获取模型类型文本
 */
export function getModelTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'chat': {
      return $t('admin.ai.model.type_options.chat');
    }
    case 'embedding': {
      return $t('admin.ai.model.type_options.embedding');
    }
    case 'image': {
      return $t('admin.ai.model.type_options.image');
    }
    default: {
      return type;
    }
  }
}

/**
 * 备用模型下拉 — 用闭包排除自身 ID 后透传 ApiSelect 分页参数
 */
function getFallbackModelSelectApi(excludeId?: number) {
  return async (params?: Record<string, unknown>) => {
    const res = await getAIModelSelectApi({ ...params, type: 'chat' });
    if (excludeId && res?.items) {
      res.items = res.items.filter(
        (i: { value: number }) => i.value !== excludeId,
      );
    }
    return res;
  };
}

/**
 * 表格列定义
 */
export function useColumns<T = AIModelInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.model.name'),
      minWidth: 240,
      slots: { default: 'name_cell' },
    },
    {
      field: 'code',
      title: $t('admin.ai.model.code'),
      width: 180,
      slots: { default: 'code_cell' },
    },
    {
      field: 'type',
      title: $t('admin.ai.model.type'),
      width: 100,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'provider_name',
      title: $t('admin.ai.model.providerName'),
      width: 160,
      align: 'center',
      slots: { default: 'providerName_cell' },
    },
    {
      field: 'context_window',
      title: $t('admin.ai.model.contextWindow'),
      width: 110,
      align: 'center',
      slots: { default: 'contextWindow_cell' },
    },
    {
      field: 'input_price_per_1k',
      title: `${$t('admin.ai.model.inputPrice')} / ${$t(
        'admin.ai.model.outputPrice',
      )}`,
      width: 160,
      align: 'center',
      slots: { default: 'price_cell' },
    },
    {
      field: 'tier',
      title: $t('admin.ai.model.tier'),
      width: 110,
      align: 'center',
      slots: { default: 'tier_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.model.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_model',
          nameField: 'name',
          nameTitle: $t('admin.ai.model.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'test',
            accessCodes: ['ai_gateway:test'],
            text: $t('admin.ai.model.test'),
            icon: 'lucide:activity',
          },
          'edit',
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 200,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.ai.model.name'), {
      placeholder: $t('admin.ai.model.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('admin.ai.model.type'), {
      options: getModelTypeOptions(),
      placeholder: $t('admin.ai.model.placeholder.allTypes'),
    }),
    select('filter[provider_id]', $t('admin.ai.model.providerName'), {
      api: getAIProviderSelectApi,
      placeholder: $t('admin.ai.model.placeholder.allProviders'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(
  _isEdit?: boolean,
  currentModelId?: number,
  onProviderChange?: (providerId: number) => void,
): VbenFormSchema[] {
  const providerField = select('provider_id', $t('admin.ai.model.providerId'), {
    api: getAIProviderSelectApi,
    required: true,
    placeholder: $t('admin.ai.model.placeholder.selectProvider'),
  });

  if (onProviderChange) {
    providerField.componentProps = {
      ...(providerField.componentProps as Record<string, unknown>),
      onChange: (val: number) => onProviderChange(val),
    };
  }

  return [
    dividerField('basic_divider', $t('admin.ai.model.section.basic')),
    {
      ...inputField('provider_type', '', {
        componentProps: {
          type: 'hidden',
        },
      }),
      formItemClass: 'hidden',
    },
    providerField,
    inputField('name', $t('admin.ai.model.name'), {
      required: true,
      placeholder: $t('admin.ai.model.placeholder.inputName'),
    }),
    {
      ...inputField('code', $t('admin.ai.model.code'), {
        required: true,
        placeholder: $t('admin.ai.model.placeholder.inputCode'),
      }),
      help: $t('admin.ai.model.help.code'),
    },
    {
      ...dividerField(
        'runtime_divider',
        $t('admin.ai.model.section.runtimeOverrides'),
      ),
      dependencies: {
        triggerFields: ['provider_type', 'type', 'code'],
        show: (values: Record<string, unknown>) =>
          supportsAdvancedRuntimeParams({
            providerType:
              typeof values.provider_type === 'string'
                ? values.provider_type
                : null,
            modelCode: typeof values.code === 'string' ? values.code : null,
            modelType: typeof values.type === 'string' ? values.type : null,
          }),
      },
    },
    {
      ...select('reasoning_effort', $t('admin.ai.model.reasoningEffort'), {
        options: getReasoningEffortOptions(),
        placeholder: $t('admin.ai.model.placeholder.selectReasoningEffort'),
      }),
      dependencies: {
        triggerFields: ['provider_type', 'type', 'code'],
        show: (values: Record<string, unknown>) =>
          supportsAdvancedRuntimeParams({
            providerType:
              typeof values.provider_type === 'string'
                ? values.provider_type
                : null,
            modelCode: typeof values.code === 'string' ? values.code : null,
            modelType: typeof values.type === 'string' ? values.type : null,
          }),
      },
      help: $t('admin.ai.model.help.reasoningEffort'),
    },
    {
      ...select('type', $t('admin.ai.model.type'), {
        options: getModelTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.model.placeholder.selectType'),
      }),
      help: $t('admin.ai.model.help.type'),
    },
    {
      ...numberField('context_window', $t('admin.ai.model.contextWindow'), {
        min: 0,
        placeholder: $t('admin.ai.model.placeholder.inputContextWindow'),
      }),
      help: $t('admin.ai.model.help.contextWindow'),
    },
    {
      ...numberField(
        'max_output_tokens',
        $t('admin.ai.model.maxOutputTokens'),
        {
          min: 0,
          placeholder: $t('admin.ai.model.placeholder.inputMaxOutput'),
        },
      ),
      help: $t('admin.ai.model.help.maxOutputTokens'),
    },
    switchField('is_active', $t('admin.ai.model.isActive'), {
      defaultValue: true,
    }),

    dividerField('pricing_divider', $t('admin.ai.model.section.pricing')),
    numberField('input_price_per_1k', $t('admin.ai.model.inputPrice'), {
      min: 0,
      placeholder: $t('admin.ai.model.placeholder.inputPrice'),
    }),
    numberField('output_price_per_1k', $t('admin.ai.model.outputPrice'), {
      min: 0,
      placeholder: $t('admin.ai.model.placeholder.outputPrice'),
    }),

    dividerField('rate_limit_divider', $t('admin.ai.model.section.rateLimit')),
    {
      ...numberField('rpm_limit', $t('admin.ai.model.rpmLimit'), {
        min: 0,
        placeholder: $t('admin.ai.model.placeholder.inputRpmLimit'),
      }),
      help: $t('admin.ai.model.help.rpmLimit'),
    },
    {
      ...numberField('tpm_limit', $t('admin.ai.model.tpmLimit'), {
        min: 0,
        placeholder: $t('admin.ai.model.placeholder.inputTpmLimit'),
      }),
      help: $t('admin.ai.model.help.tpmLimit'),
    },

    dividerField('capability_divider', $t('admin.ai.model.section.capability')),
    {
      ...switchField(
        'supports_function_calling',
        $t('admin.ai.model.functionCalling'),
        {
          defaultValue: false,
        },
      ),
      help: $t('admin.ai.model.help.functionCalling'),
    },
    switchField('supports_vision', $t('admin.ai.model.vision'), {
      defaultValue: false,
    }),
    switchField('supports_audio', $t('admin.ai.model.supportsAudio'), {
      defaultValue: false,
    }),
    switchField('supports_video', $t('admin.ai.model.supportsVideo'), {
      defaultValue: false,
    }),
    {
      ...numberField('max_image_count', $t('admin.ai.model.maxImageCount'), {
        min: 1,
        max: 20,
        placeholder: $t('admin.ai.model.placeholder.inputMaxImageCount'),
      }),
      dependencies: {
        triggerFields: ['supports_vision'],
        show: (values: Record<string, unknown>) => !!values.supports_vision,
      },
      help: $t('admin.ai.model.help.maxImageCount'),
    },
    {
      ...numberField('max_image_size_mb', $t('admin.ai.model.maxImageSizeMb'), {
        min: 1,
        max: 50,
        placeholder: $t('admin.ai.model.placeholder.inputMaxImageSizeMb'),
      }),
      dependencies: {
        triggerFields: ['supports_vision'],
        show: (values: Record<string, unknown>) => !!values.supports_vision,
      },
      help: $t('admin.ai.model.help.maxImageSizeMb'),
    },
    switchField('supports_streaming', $t('admin.ai.model.streaming'), {
      defaultValue: true,
    }),

    dividerField('failover_divider', $t('admin.ai.model.section.failover')),
    {
      ...select('fallback_model_id', $t('admin.ai.model.fallbackModel'), {
        api: getFallbackModelSelectApi(currentModelId),
        placeholder: $t('admin.ai.model.placeholder.selectFallback'),
      }),
      help: $t('admin.ai.model.help.fallbackModel'),
    },

    dividerField('routing_divider', $t('admin.ai.model.section.routing')),
    {
      ...select('tier', $t('admin.ai.model.tier'), {
        options: getModelTierOptions(),
        placeholder: $t('admin.ai.model.placeholder.selectTier'),
        required: false,
      }),
      help: $t('admin.ai.model.help.tier'),
    },
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'chat',
    reasoning_effort: null,
    is_active: true,
    supports_function_calling: false,
    supports_vision: false,
    supports_audio: false,
    supports_video: false,
    supports_streaming: true,
    max_image_count: 5,
    max_image_size_mb: 10,
    tier: null,
  };
}

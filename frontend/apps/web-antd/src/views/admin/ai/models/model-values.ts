import type {
  AIModelConfig,
  AIModelInfo,
  ModelProviderType,
  RemoteModelCapabilities,
} from '#/api/admin/ai-models';

import {
  getFormDefaults,
  OPENAI_COMPATIBLE_PROVIDER_TYPE,
} from './model-options';
import {
  buildModelConfig,
  resolveModelCodeForForm,
  resolveReasoningEffort,
} from './model-runtime';

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
    max_image_count: values.supports_vision
      ? values.max_image_count || 5
      : null,
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

export function buildModelFormValues(
  data: AIModelInfo,
): Record<string, unknown> {
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
  providerType?: ModelProviderType | null,
  caps?: null | RemoteModelCapabilities,
): Record<string, unknown> {
  const values: Record<string, unknown> = {
    ...getFormDefaults(),
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
    if (caps.supports_vision !== null && caps.supports_vision !== undefined) {
      values.supports_vision = caps.supports_vision;
    }
    if (caps.supports_audio !== null && caps.supports_audio !== undefined) {
      values.supports_audio = caps.supports_audio;
    }
    if (caps.supports_video !== null && caps.supports_video !== undefined) {
      values.supports_video = caps.supports_video;
    }
    if (
      caps.supports_function_calling !== null &&
      caps.supports_function_calling !== undefined
    ) {
      values.supports_function_calling = caps.supports_function_calling;
    }
    if (
      caps.supports_streaming !== null &&
      caps.supports_streaming !== undefined
    ) {
      values.supports_streaming = caps.supports_streaming;
    }
    if (caps.context_window !== null && caps.context_window !== undefined) {
      values.context_window = caps.context_window;
    }
    if (
      caps.max_output_tokens !== null &&
      caps.max_output_tokens !== undefined
    ) {
      values.max_output_tokens = caps.max_output_tokens;
    }
    if (
      caps.input_price_per_1k !== null &&
      caps.input_price_per_1k !== undefined
    ) {
      values.input_price_per_1k = caps.input_price_per_1k;
    }
    if (
      caps.output_price_per_1k !== null &&
      caps.output_price_per_1k !== undefined
    ) {
      values.output_price_per_1k = caps.output_price_per_1k;
    }
    if (caps.rpm_limit !== null && caps.rpm_limit !== undefined) {
      values.rpm_limit = caps.rpm_limit;
    }
    if (caps.tpm_limit !== null && caps.tpm_limit !== undefined) {
      values.tpm_limit = caps.tpm_limit;
    }
  }

  return values;
}

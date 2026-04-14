import { $t } from '#/locales';

export const OPENAI_COMPATIBLE_PROVIDER_TYPE = 'openai_compatible' as const;

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

export function getModelTypeOptions() {
  return [
    { label: $t('admin.ai.model.type_options.chat'), value: 'chat' },
    { label: $t('admin.ai.model.type_options.embedding'), value: 'embedding' },
    { label: $t('admin.ai.model.type_options.image'), value: 'image' },
  ];
}

export function getModelTierOptions() {
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

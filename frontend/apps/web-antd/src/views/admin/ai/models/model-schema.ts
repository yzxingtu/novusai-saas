import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIModelInfo } from '#/api/admin/ai-models';

import {
  dividerField,
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
} from '#/adapter/form';
import { getAIModelSelectApi } from '#/api/admin/ai-models';
import { getAIProviderSelectApi } from '#/api/admin/ai-providers';
import { $t } from '#/locales';

import {
  getModelTierOptions,
  getModelTypeOptions,
  getEmbeddingDimensionsOptions,
  getReasoningEffortOptions,
} from './model-options';
import { supportsAdvancedRuntimeParams } from './model-runtime';

function getFallbackModelSelectApi(excludeId?: number) {
  return async (params?: Record<string, unknown>) => {
    const res = await getAIModelSelectApi({ ...params, type: 'chat' });
    if (excludeId && res?.items) {
      res.items = res.items.filter(
        (item: { value: number }) => item.value !== excludeId,
      );
    }
    return res;
  };
}

function shouldShowAdvancedRuntimeParams(values: Record<string, unknown>) {
  return supportsAdvancedRuntimeParams({
    providerType:
      typeof values.provider_type === 'string' ? values.provider_type : null,
    modelCode: typeof values.code === 'string' ? values.code : null,
    modelType: typeof values.type === 'string' ? values.type : null,
  });
}

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
      onChange: (value: number) => onProviderChange(value),
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
        show: shouldShowAdvancedRuntimeParams,
      },
    },
    {
      ...select('reasoning_effort', $t('admin.ai.model.reasoningEffort'), {
        options: getReasoningEffortOptions(),
        placeholder: $t('admin.ai.model.placeholder.selectReasoningEffort'),
      }),
      dependencies: {
        triggerFields: ['provider_type', 'type', 'code'],
        show: shouldShowAdvancedRuntimeParams,
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
      ...select(
        'embedding_dimensions',
        $t('admin.ai.model.embeddingDimensions'),
        {
          options: getEmbeddingDimensionsOptions(),
          required: true,
          placeholder: $t(
            'admin.ai.model.placeholder.selectEmbeddingDimensions',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['type'],
        show: (values: Record<string, unknown>) =>
          values.type === 'embedding',
      },
      help: $t('admin.ai.model.help.embeddingDimensions'),
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

/**
 * AI 供应商管理 - 表格列、搜索和表单配置
 * AI provider admin — columns, search and form config
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdapterTypeInfo, AIProviderInfo } from '#/api/admin/ai';

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
  const normalizedForSuffixCheck = normalizedBaseUrl
    .toLowerCase()
    .replace(/\/+$/, '');
  return OPENAI_COMPATIBLE_FORBIDDEN_BASE_URL_SUFFIXES.some((suffix) =>
    normalizedForSuffixCheck.endsWith(suffix),
  );
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
    is_active: true,
    sort_order: 0,
  };
}

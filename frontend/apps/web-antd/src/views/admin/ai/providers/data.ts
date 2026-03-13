/**
 * AI 供应商管理 - 表格列、搜索和表单配置
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
} from '#/adapter/form';
import { dragColumn } from '#/adapter/vxe-table';
import { getAdapterTypesApi } from '#/api/admin/ai';
import { $t } from '#/locales';

/** 缓存适配器类型列表 */
const adapterTypesCache = ref<AdapterTypeInfo[]>([]);

/** 加载适配器类型（含插件注册的） */
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
 * 获取适配器来源文本
 */
export function getAdapterSource(
  type: string | undefined,
): 'builtin' | 'plugin' {
  if (!type) return 'builtin';
  const cached = adapterTypesCache.value.find((t) => t.type === type);
  return cached?.source ?? 'builtin';
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
      ...inputField('base_url', $t('admin.ai.provider.baseUrl'), {
        placeholder: $t('admin.ai.provider.placeholder.inputBaseUrl'),
      }),
      help: $t('admin.ai.provider.help.baseUrl'),
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
    is_active: true,
    sort_order: 0,
  };
}

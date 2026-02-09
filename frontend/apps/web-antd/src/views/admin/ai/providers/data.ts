/**
 * AI 供应商管理 - 表格列、搜索和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIProviderInfo } from '#/api/admin/ai';

import {
  iconField,
  inputField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { dragColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';

function getProviderTypeOptions() {
  return [
    { label: $t('admin.ai.provider.type_options.openai_compatible'), value: 'openai_compatible' },
  ];
}

/**
 * 获取供应商类型文本
 */
export function getProviderTypeText(type: string | undefined): string {
  if (!type) return '-';
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
      minWidth: 200,
      slots: { default: 'name_cell' },
    },
    {
      field: 'code',
      title: $t('admin.ai.provider.code'),
      width: 150,
      slots: { default: 'code_cell' },
    },
    {
      field: 'type',
      title: $t('admin.ai.provider.type'),
      width: 150,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'model_count',
      title: $t('admin.ai.provider.modelCount'),
      width: 100,
      align: 'center',
    },
    {
      field: 'is_active',
      title: $t('admin.ai.provider.isActive'),
      width: 100,
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
    select('type', $t('admin.ai.provider.type'), {
      options: getProviderTypeOptions(),
      required: true,
      placeholder: $t('admin.ai.provider.placeholder.selectType'),
    }),
    inputField('base_url', $t('admin.ai.provider.baseUrl'), {
      placeholder: $t('admin.ai.provider.placeholder.inputBaseUrl'),
    }),
    textareaField('description', $t('admin.ai.provider.description'), {
      placeholder: $t('admin.ai.provider.placeholder.inputDescription'),
    }),
    iconField('icon', $t('admin.ai.provider.icon'), {
      placeholder: 'lucide:cpu',
    }),
    switchField('is_active', $t('admin.ai.provider.isActive'), {
      defaultValue: true,
    }),
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

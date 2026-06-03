import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIProviderInfo } from '#/api/admin/ai-providers';

import {
  inputField,
  searchInput,
  select,
  switchField,
  textareaField,
  z,
} from '#/adapter/form';
import { dragColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';

import {
  getDefaultProviderType,
  getProviderTypeOptions,
  hasMultipleAdapterTypeOptions,
} from './provider-adapter-types';
import { getProviderWireApiOptions } from './provider-connection';

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

function resolveSchemaProviderType(values: Record<string, unknown>): string {
  return typeof values.type === 'string' && values.type.trim()
    ? values.type
    : getDefaultProviderType();
}

/**
 * 表格列定义
 */
export function useColumns<T = AIProviderInfo>(
  onActionClick: OnActionClickFn<T>,
  _onToggleStatus?: unknown,
  options?: {
    showProviderTypeColumn?: boolean;
  },
): VxeTableGridOptions['columns'] {
  const showProviderTypeColumn =
    options?.showProviderTypeColumn ?? hasMultipleAdapterTypeOptions();

  return [
    dragColumn,
    {
      field: 'name',
      title: $t('admin.ai.provider.name'),
      minWidth: 280,
      slots: { default: 'name_cell' },
    },
    ...(showProviderTypeColumn
      ? [
          {
            field: 'type',
            title: $t('admin.ai.provider.type'),
            width: 160,
            align: 'center' as const,
            slots: { default: 'type_cell' },
          },
          {
            field: 'primary_wire_api',
            title: $t('admin.ai.provider.wireApi'),
            width: 180,
            align: 'center' as const,
            slots: { default: 'wireApi_cell' },
          },
        ]
      : [
          {
            field: 'connection_mode',
            title: $t('admin.ai.provider.connectionMode'),
            minWidth: 220,
            align: 'center' as const,
            slots: { default: 'connection_cell' },
          },
        ]),
    {
      field: 'model_count',
      title: $t('admin.ai.provider.modelCount'),
      width: 100,
      align: 'center' as const,
      slots: { default: 'modelCount_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.provider.isActive'),
      width: 130,
      align: 'center' as const,
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'center' as const,
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
  const schema: VbenFormSchema[] = [
    searchInput('name', $t('admin.ai.provider.name'), {
      placeholder: $t('admin.ai.provider.placeholder.searchName'),
    }),
  ];
  if (hasMultipleAdapterTypeOptions()) {
    schema.push(
      select('filter[type][eq]', $t('admin.ai.provider.type'), {
        options: getProviderTypeOptions(),
        placeholder: $t('admin.ai.provider.type'),
      }),
    );
  }
  return schema;
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit = false): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [
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
  ];
  if (hasMultipleAdapterTypeOptions()) {
    schema.push({
      ...select('type', $t('admin.ai.provider.type'), {
        options: getProviderTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.provider.placeholder.selectType'),
      }),
      help: $t('admin.ai.provider.help.type'),
    });
  }
  schema.push(
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
      ...select('primary_wire_api', $t('admin.ai.provider.wireApi'), {
        options: getProviderWireApiOptions(),
        placeholder: $t('admin.ai.provider.placeholder.selectWireApi'),
        required: true,
      }),
      dependencies: {
        triggerFields: ['type'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible',
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
  );
  return schema;
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: getDefaultProviderType(),
    primary_wire_api: 'chat_completions',
    is_active: true,
    sort_order: 0,
  };
}

/**
 * AI API Key 管理 - 表格列、搜索和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIApiKeyInfo } from '#/api/admin/ai';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
} from '#/adapter/form';
import { getAIProviderListApi } from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

/**
 * 获取供应商下拉选项
 */
async function getProviderSelectOptions() {
  const response = await getAIProviderListApi({
    'page[size]': 100,
    sort: 'sort_order',
  });
  return response.items.map((item) => ({
    label: item.name,
    value: item.id,
  }));
}

/**
 * 表格列定义
 */
export function useColumns<T = AIApiKeyInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.apiKey.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'key_preview',
      title: $t('admin.ai.apiKey.keyPreview'),
      width: 200,
      slots: { default: 'keyPreview_cell' },
    },
    {
      field: 'provider_name',
      title: $t('admin.ai.apiKey.providerName'),
      width: 140,
      align: 'center',
    },
    {
      field: 'tenant_name',
      title: $t('admin.ai.apiKey.tenantName'),
      width: 140,
      align: 'center',
      slots: { default: 'tenantName_cell' },
    },
    {
      field: 'usage_count',
      title: $t('admin.ai.apiKey.usageCount'),
      width: 120,
      align: 'right',
      slots: { default: 'usageCount_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.apiKey.isActive'),
      width: 120,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'is_available',
      title: $t('admin.ai.apiKey.isAvailable'),
      width: 140,
      align: 'center',
      slots: { default: 'isAvailable_cell' },
    },
    {
      field: 'expires_at',
      title: $t('admin.ai.apiKey.expiresAt'),
      width: 140,
      align: 'center',
      slots: { default: 'expiresAt_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 140,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_api_key',
          nameField: 'name',
          nameTitle: $t('admin.ai.apiKey.name'),
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
    searchInput('name', $t('admin.ai.apiKey.name'), {
      placeholder: $t('admin.ai.apiKey.placeholder.searchName'),
    }),
    select('filter[provider_id]', $t('admin.ai.apiKey.providerName'), {
      api: getProviderSelectOptions,
      placeholder: $t('admin.ai.apiKey.placeholder.allProviders'),
    }),
    select('filter[tenant_id]', $t('admin.ai.apiKey.tenantName'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.apiKey.tenantName'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit: boolean): VbenFormSchema[] {
  const providerField = select(
    'provider_id',
    $t('admin.ai.apiKey.providerId'),
    {
      api: getProviderSelectOptions,
      required: true,
      placeholder: $t('admin.ai.apiKey.placeholder.selectProvider'),
    },
  );

  if (isEdit) {
    providerField.componentProps = {
      ...(providerField.componentProps as Record<string, unknown>),
      disabled: true,
    };
  }

  const fields: VbenFormSchema[] = [
    inputField('name', $t('admin.ai.apiKey.name'), {
      required: true,
      placeholder: $t('admin.ai.apiKey.placeholder.inputName'),
    }),
    providerField,
  ];

  // 仅新建模式显示 api_key 字段
  if (!isEdit) {
    fields.push({
      ...inputField('api_key', $t('admin.ai.apiKey.apiKey'), {
        required: true,
        placeholder: $t('admin.ai.apiKey.placeholder.inputApiKey'),
      }),
      help: $t('admin.ai.apiKey.help.apiKey'),
    });
  }

  const tenantField = select('tenant_id', $t('admin.ai.apiKey.tenantId'), {
    api: getTenantSelectApi,
    params: { is_active: 'true' },
    placeholder: $t('admin.ai.apiKey.placeholder.selectTenant'),
  });

  if (isEdit) {
    tenantField.componentProps = {
      ...(tenantField.componentProps as Record<string, unknown>),
      disabled: true,
    };
  }

  fields.push(
    {
      ...tenantField,
      help: $t('admin.ai.apiKey.help.tenantId'),
    },
    {
      ...numberField('usage_limit', $t('admin.ai.apiKey.usageLimit'), {
        min: 0,
        placeholder: $t('admin.ai.apiKey.placeholder.inputUsageLimit'),
      }),
      help: $t('admin.ai.apiKey.help.usageLimit'),
    },
    {
      ...switchField('is_active', $t('admin.ai.apiKey.isActive'), {
        defaultValue: true,
      }),
      help: $t('admin.ai.apiKey.help.isActive'),
    },
  );

  return fields;
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    is_active: true,
  };
}

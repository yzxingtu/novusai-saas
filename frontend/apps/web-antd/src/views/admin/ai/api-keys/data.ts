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
import { getAIProviderSelectApi } from '#/api/admin/ai';
import { useScopeFields } from '#/components/business/scope-select';
import { $t } from '#/locales';
import { getScopeOptions } from '#/utils/scope-helpers';

function getApiKeyScopeOptions() {
  return getScopeOptions(['admin_only', 'global_shared', 'selected_tenants']);
}

export function useColumns<T = AIApiKeyInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.apiKey.name'),
      minWidth: 220,
      align: 'left',
      headerAlign: 'left',
      slots: { default: 'name_cell' },
    },
    {
      field: 'key_preview',
      title: $t('admin.ai.apiKey.keyPreview'),
      minWidth: 168,
      width: 200,
      slots: { default: 'keyPreview_cell' },
    },
    {
      field: 'provider_name',
      title: $t('admin.ai.apiKey.providerName'),
      minWidth: 160,
      width: 200,
      align: 'left',
      slots: { default: 'providerName_cell' },
    },
    {
      field: 'scope',
      title: $t('common.scope.label'),
      width: 220,
      align: 'left',
      headerAlign: 'left',
      slots: { default: 'scope_cell' },
    },
    {
      field: 'usage_count',
      title: $t('admin.ai.apiKey.usageCount'),
      width: 132,
      align: 'right',
      slots: { default: 'usageCount_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.apiKey.isActive'),
      width: 108,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'is_available',
      title: $t('admin.ai.apiKey.isAvailable'),
      width: 128,
      align: 'center',
      slots: { default: 'isAvailable_cell' },
    },
    {
      field: 'expires_at',
      title: $t('admin.ai.apiKey.expiresAt'),
      width: 128,
      align: 'center',
      slots: { default: 'expiresAt_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 128,
      sortable: true,
      align: 'center',
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

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.ai.apiKey.name'), {
      placeholder: $t('admin.ai.apiKey.placeholder.searchName'),
    }),
    select('filter[provider_id]', $t('admin.ai.apiKey.providerName'), {
      api: getAIProviderSelectApi,
      placeholder: $t('admin.ai.apiKey.placeholder.allProviders'),
    }),
    select('filter[scope][eq]', $t('common.scope.label'), {
      options: getApiKeyScopeOptions(),
    }),
  ];
}

export function useFormSchema(isEdit: boolean): VbenFormSchema[] {
  const providerField = select(
    'provider_id',
    $t('admin.ai.apiKey.providerId'),
    {
      api: getAIProviderSelectApi,
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

  if (!isEdit) {
    fields.push({
      ...inputField('api_key', $t('admin.ai.apiKey.apiKey'), {
        required: true,
        placeholder: $t('admin.ai.apiKey.placeholder.inputApiKey'),
      }),
      help: $t('admin.ai.apiKey.help.apiKey'),
    });
  }

  fields.push(
    ...useScopeFields({
      allowedScopes: ['admin_only', 'global_shared', 'selected_tenants'],
      ownerTenantWhenScopes: ['selected_tenants'],
      hideTenantIdsField: true,
      tenantIdRequired: true,
      scopeHelp: $t('admin.ai.apiKey.help.scope'),
      scopeDisabled: (values) => values._mode === 'edit',
    }),
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

export function getFormDefaults(): Record<string, unknown> {
  return {
    scope: 'global_shared',
    tenant_id: null,
    is_active: true,
  };
}

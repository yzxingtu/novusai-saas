/**
 * AI 配额管理 - 表格列、搜索和表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIQuotaInfo } from '#/api/admin/ai';

import {
  dividerField,
  inputField,
  numberField,
  select,
  switchField,
} from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

/**
 * 获取周期下拉选项
 */
function getPeriodOptions() {
  return [
    { label: $t('admin.ai.quota.period_options.daily'), value: 'daily' },
    { label: $t('admin.ai.quota.period_options.monthly'), value: 'monthly' },
  ];
}

/**
 * 获取配额类型下拉选项
 */
function getQuotaTypeOptions() {
  return [
    { label: $t('admin.ai.quota.type_options.soft'), value: 'soft' },
    { label: $t('admin.ai.quota.type_options.hard'), value: 'hard' },
  ];
}

/**
 * 获取周期文本
 */
export function getPeriodText(period: string | undefined): string {
  if (!period) return '-';
  switch (period) {
    case 'daily': {
      return $t('admin.ai.quota.period_options.daily');
    }
    case 'monthly': {
      return $t('admin.ai.quota.period_options.monthly');
    }
    default: {
      return period;
    }
  }
}

/**
 * 获取配额类型文本
 */
export function getQuotaTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'soft': {
      return $t('admin.ai.quota.type_options.soft');
    }
    case 'hard': {
      return $t('admin.ai.quota.type_options.hard');
    }
    default: {
      return type;
    }
  }
}

/**
 * 获取模型下拉选项
 */
async function getModelSelectOptions() {
  const response = await getAIModelListApi({
    'page[size]': 200,
    'sort': 'name',
    'filter[is_active]': true,
  });
  return response.items.map((item) => ({
    label: `${item.name} (${item.provider_name || '-'})`,
    value: item.id,
  }));
}

/**
 * 表格列定义
 */
export function useColumns<T = AIQuotaInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'tenant_name',
      title: $t('admin.ai.quota.tenantName'),
      width: 140,
      align: 'center',
      slots: { default: 'tenantName_cell' },
    },
    {
      field: 'model_name',
      title: $t('admin.ai.quota.modelName'),
      width: 160,
      align: 'center',
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'period',
      title: $t('admin.ai.quota.period'),
      width: 100,
      align: 'center',
      slots: { default: 'period_cell' },
    },
    {
      field: 'limit',
      title: $t('admin.ai.quota.limit'),
      width: 140,
      align: 'right',
      slots: { default: 'limit_cell' },
    },
    {
      field: 'quota_type',
      title: $t('admin.ai.quota.quotaType'),
      width: 110,
      align: 'center',
      slots: { default: 'quotaType_cell' },
    },
    {
      field: 'warning_threshold',
      title: $t('admin.ai.quota.warningThreshold'),
      width: 130,
      align: 'center',
      slots: { default: 'threshold_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.quota.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 130,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_quota',
          nameField: 'id',
          nameTitle: $t('admin.ai.quota.title'),
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
    select('filter[tenant_id]', $t('admin.ai.quota.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.quota.placeholder.allTenants'),
    }),
    select('filter[period][eq]', $t('admin.ai.quota.period'), {
      options: getPeriodOptions(),
      placeholder: $t('admin.ai.quota.placeholder.allPeriods'),
    }),
    select('filter[quota_type][eq]', $t('admin.ai.quota.quotaType'), {
      options: getQuotaTypeOptions(),
      placeholder: $t('admin.ai.quota.placeholder.allTypes'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(): VbenFormSchema[] {
  return [
    dividerField('basic_divider', $t('admin.ai.quota.section.basic')),
    select('tenant_id', $t('admin.ai.quota.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectTenant'),
    }),
    select('model_id', $t('admin.ai.quota.modelId'), {
      api: getModelSelectOptions,
      placeholder: $t('admin.ai.quota.placeholder.selectModel'),
    }),

    dividerField('config_divider', $t('admin.ai.quota.section.config')),
    select('period', $t('admin.ai.quota.period'), {
      options: getPeriodOptions(),
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectPeriod'),
    }),
    numberField('limit', $t('admin.ai.quota.limit'), {
      required: true,
      min: 1,
      placeholder: $t('admin.ai.quota.placeholder.inputLimit'),
    }),
    select('quota_type', $t('admin.ai.quota.quotaType'), {
      options: getQuotaTypeOptions(),
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectType'),
    }),
    numberField('warning_threshold', $t('admin.ai.quota.warningThreshold'), {
      min: 0,
      max: 100,
      placeholder: $t('admin.ai.quota.placeholder.inputThreshold'),
    }),
    inputField('description', $t('admin.ai.quota.description'), {
      placeholder: $t('admin.ai.quota.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('admin.ai.quota.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    period: 'monthly',
    quota_type: 'soft',
    warning_threshold: 80,
    is_active: true,
  };
}

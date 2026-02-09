/**
 * AI 调用日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AICallLogInfo } from '#/api/admin/ai';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

function getStatusOptions() {
  return [
    { label: $t('admin.ai.callLog.status_options.success'), value: 'success' },
    { label: $t('admin.ai.callLog.status_options.failed'), value: 'failed' },
    { label: $t('admin.ai.callLog.status_options.timeout'), value: 'timeout' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'success': {
      return $t('admin.ai.callLog.status_options.success');
    }
    case 'failed': {
      return $t('admin.ai.callLog.status_options.failed');
    }
    case 'timeout': {
      return $t('admin.ai.callLog.status_options.timeout');
    }
    default: {
      return status;
    }
  }
}

/**
 * 格式化费用
 */
export function formatCost(cost: null | number | undefined): string {
  if (cost === null || cost === undefined) return '-';
  if (cost === 0) return '$0';
  if (cost < 0.001) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

/**
 * 表格列定义
 */
export function useColumns<T = AICallLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'created_at',
      title: $t('admin.ai.callLog.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'model_name',
      title: $t('admin.ai.callLog.modelName'),
      width: 180,
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'provider_name',
      title: $t('admin.ai.callLog.providerName'),
      width: 140,
      align: 'center',
    },
    {
      field: 'tenant_name',
      title: $t('admin.ai.callLog.tenantName'),
      width: 140,
      align: 'center',
      slots: { default: 'tenantName_cell' },
    },
    {
      field: 'status',
      title: $t('admin.ai.callLog.status'),
      width: 90,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'total_tokens',
      title: 'Tokens',
      width: 140,
      align: 'center',
      slots: { default: 'tokens_cell' },
    },
    {
      field: 'cost',
      title: $t('admin.ai.callLog.cost'),
      width: 100,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'latency_ms',
      title: $t('admin.ai.callLog.latency'),
      width: 100,
      align: 'center',
      slots: { default: 'latency_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_call_log',
          nameField: 'model_name',
          nameTitle: $t('admin.ai.callLog.modelName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('admin.ai.callLog.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_call_log:detail'],
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 100,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[model_name][ilike]', $t('admin.ai.callLog.modelName'), {
      placeholder: $t('admin.ai.callLog.placeholder.allModels'),
    }),
    select('filter[status][eq]', $t('admin.ai.callLog.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.ai.callLog.placeholder.allStatuses'),
    }),
    select('filter[tenant_id]', $t('admin.ai.callLog.tenantName'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.callLog.tenantName'),
    }),
  ];
}

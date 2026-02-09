/**
 * 租户端 AI 调用日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { TenantAICallLogInfo } from '#/api/tenant/ai';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

function getStatusOptions() {
  return [
    { label: $t('tenant.ai.callLog.status_options.success'), value: 'success' },
    { label: $t('tenant.ai.callLog.status_options.failed'), value: 'failed' },
    { label: $t('tenant.ai.callLog.status_options.timeout'), value: 'timeout' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'success': return $t('tenant.ai.callLog.status_options.success');
    case 'failed': return $t('tenant.ai.callLog.status_options.failed');
    case 'timeout': return $t('tenant.ai.callLog.status_options.timeout');
    default: return status;
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
export function useColumns<T = TenantAICallLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'created_at',
      title: $t('tenant.ai.callLog.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'model_name',
      title: $t('tenant.ai.callLog.modelName'),
      width: 180,
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'provider_name',
      title: $t('tenant.ai.callLog.providerName'),
      width: 130,
      align: 'center',
    },
    {
      field: 'status',
      title: $t('tenant.ai.callLog.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'input_tokens',
      title: $t('tenant.ai.callLog.inputTokens'),
      width: 120,
      align: 'right',
    },
    {
      field: 'output_tokens',
      title: $t('tenant.ai.callLog.outputTokens'),
      width: 120,
      align: 'right',
    },
    {
      field: 'total_tokens',
      title: $t('tenant.ai.callLog.totalTokens'),
      width: 120,
      align: 'right',
    },
    {
      field: 'cost',
      title: $t('tenant.ai.callLog.cost'),
      width: 120,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'latency_ms',
      title: $t('tenant.ai.callLog.latency'),
      width: 110,
      align: 'right',
      slots: { default: 'latency_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_tenant_call_log',
          nameField: 'model_name',
          nameTitle: $t('tenant.ai.callLog.modelName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.ai.callLog.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_tenant_call_log:detail'],
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 100,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[model_name][ilike]', $t('tenant.ai.callLog.modelName'), {
      placeholder: $t('tenant.ai.callLog.placeholder.allModels'),
    }),
    select('filter[status][eq]', $t('tenant.ai.callLog.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.ai.callLog.placeholder.allStatuses'),
    }),
  ];
}

/**
 * 企业端 AI 调用日志 - 表格列、搜索配置
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
    case 'failed': {
      return $t('tenant.ai.callLog.status_options.failed');
    }
    case 'success': {
      return $t('tenant.ai.callLog.status_options.success');
    }
    case 'timeout': {
      return $t('tenant.ai.callLog.status_options.timeout');
    }
    default: {
      return status;
    }
  }
}

/**
 * 获取状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'success': {
      return 'success';
    }
    case 'timeout': {
      return 'warning';
    }
    default: {
      return 'default';
    }
  }
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
      minWidth: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'model_name',
      title: $t('tenant.ai.callLog.modelName'),
      minWidth: 160,
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'provider_name',
      title: $t('tenant.ai.callLog.providerName'),
      minWidth: 140,
      align: 'center',
      slots: { default: 'providerName_cell' },
    },
    {
      field: 'caller_name',
      title: $t('tenant.ai.callLog.callerName'),
      minWidth: 130,
      showOverflow: 'tooltip',
      slots: { default: 'callerName_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.ai.callLog.status'),
      minWidth: 96,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'input_tokens',
      title: $t('tenant.ai.callLog.inputTokens'),
      minWidth: 108,
      align: 'right',
    },
    {
      field: 'output_tokens',
      title: $t('tenant.ai.callLog.outputTokens'),
      minWidth: 108,
      align: 'right',
    },
    {
      field: 'total_tokens',
      title: $t('tenant.ai.callLog.totalTokens'),
      minWidth: 108,
      align: 'right',
    },
    {
      field: 'cost',
      title: $t('tenant.ai.callLog.cost'),
      minWidth: 100,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'latency_ms',
      title: $t('tenant.ai.callLog.latency'),
      minWidth: 100,
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
      minWidth: 96,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput(
      'filter[model_name][ilike]',
      $t('tenant.ai.callLog.modelName'),
      {
        placeholder: $t('tenant.ai.callLog.placeholder.allModels'),
      },
    ),
    select('filter[status][eq]', $t('tenant.ai.callLog.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.ai.callLog.placeholder.allStatuses'),
    }),
  ];
}

export { formatCost } from '#/utils/format';

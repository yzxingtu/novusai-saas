/**
 * AI 调用日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AICallLogInfo } from '#/api/admin/ai';

import { searchDateRange, searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { PLATFORM_TENANT_ID } from '#/constants';
import { $t } from '#/locales';

function getStatusOptions() {
  return [
    { label: $t('admin.ai.callLog.status_options.success'), value: 'success' },
    { label: $t('admin.ai.callLog.status_options.failed'), value: 'failed' },
    { label: $t('admin.ai.callLog.status_options.timeout'), value: 'timeout' },
  ];
}

export function isPlatformCall(tenantId: null | number | undefined): boolean {
  return tenantId === PLATFORM_TENANT_ID;
}

export function getCallSourceText(tenantId: null | number | undefined): string {
  return isPlatformCall(tenantId)
    ? $t('admin.ai.callLog.source_options.platform')
    : $t('admin.ai.callLog.source_options.tenant');
}

export function getCallSourceColor(
  tenantId: null | number | undefined,
): string {
  return isPlatformCall(tenantId) ? 'processing' : 'success';
}

export function getTenantDisplayName(
  tenantId: null | number | undefined,
  tenantName: null | string | undefined,
): string {
  if (isPlatformCall(tenantId)) {
    return $t('admin.ai.callLog.platformTenant');
  }
  return tenantName || '-';
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'failed': {
      return $t('admin.ai.callLog.status_options.failed');
    }
    case 'success': {
      return $t('admin.ai.callLog.status_options.success');
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
      minWidth: 180,
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'provider_name',
      title: $t('admin.ai.callLog.providerName'),
      minWidth: 140,
      align: 'center',
      slots: { default: 'providerName_cell' },
    },
    {
      field: 'call_source',
      title: $t('admin.ai.callLog.source'),
      width: 110,
      align: 'center',
      slots: { default: 'source_cell' },
    },
    {
      field: 'tenant_name',
      title: $t('admin.ai.callLog.tenantName'),
      minWidth: 120,
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
      title: $t('admin.ai.callLog.totalTokens'),
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
    searchDateRange({
      field: 'created_at',
      label: $t('admin.ai.callLog.createdAt'),
    }),
  ];
}

export { formatCost } from '#/utils/format';

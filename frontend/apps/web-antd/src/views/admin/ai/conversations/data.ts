/**
 * AI 对话监控 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import { formatCost, formatTokens } from '#/utils/format';

export { formatCost, formatTokens };

function getStatusOptions() {
  return [
    { label: $t('admin.ai.conversation.status_options.active'), value: 'active' },
    { label: $t('admin.ai.conversation.status_options.archived'), value: 'archived' },
    { label: $t('admin.ai.conversation.status_options.closed'), value: 'closed' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'active': {
      return $t('admin.ai.conversation.status_options.active');
    }
    case 'archived': {
      return $t('admin.ai.conversation.status_options.archived');
    }
    case 'closed': {
      return $t('admin.ai.conversation.status_options.closed');
    }
    default: {
      return status;
    }
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = Record<string, unknown>>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'id',
      title: 'ID',
      width: 80,
      sortable: true,
    },
    {
      field: 'agent_name',
      title: $t('admin.ai.conversation.agentName'),
      width: 160,
    },
    {
      field: 'title',
      title: $t('admin.ai.conversation.title'),
      minWidth: 200,
      slots: { default: 'title_cell' },
    },
    {
      field: 'tenant_name',
      title: $t('admin.ai.conversation.tenantName'),
      width: 140,
      slots: { default: 'tenant_cell' },
    },
    {
      field: 'user_info',
      title: $t('admin.ai.conversation.user'),
      width: 160,
      slots: { default: 'user_cell' },
    },
    {
      field: 'status',
      title: $t('admin.ai.conversation.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'token_count',
      title: $t('admin.ai.conversation.tokenCount'),
      width: 110,
      align: 'right',
      slots: { default: 'tokens_cell' },
    },
    {
      field: 'cost',
      title: $t('admin.ai.conversation.cost'),
      width: 100,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.ai.conversation.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_conversation',
          nameField: 'title',
          nameTitle: $t('admin.ai.conversation.title'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('admin.ai.conversation.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_conversation:detail'],
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
    searchInput('filter[agent_id][eq]', $t('admin.ai.conversation.agentName'), {
      placeholder: $t('admin.ai.conversation.placeholder.agentId'),
    }),
    select('filter[status][eq]', $t('admin.ai.conversation.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.ai.conversation.placeholder.allStatuses'),
    }),
    select('filter[tenant_id]', $t('admin.ai.conversation.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.conversation.placeholder.allTenants'),
    }),
  ];
}


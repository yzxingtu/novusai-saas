/**
 * 租户端对话管理 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { ConversationInfo } from '#/api/tenant/conversations';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';
import { formatCost } from '#/utils/format';

export { formatCost };

function getStatusOptions() {
  return [
    { label: $t('tenant.ai.conversation.status_options.active'), value: 'active' },
    { label: $t('tenant.ai.conversation.status_options.archived'), value: 'archived' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'active': return $t('tenant.ai.conversation.status_options.active');
    case 'archived': return $t('tenant.ai.conversation.status_options.archived');
    default: return status;
  }
}

/**
 * 格式化 Token 数量
 */
export function formatTokenCount(count: null | number | undefined): string {
  if (count === null || count === undefined) return '-';
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return String(count);
}

/**
 * 表格列定义
 */
export function useColumns<T = ConversationInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'title',
      title: $t('tenant.ai.conversation.title'),
      minWidth: 200,
      slots: { default: 'title_cell' },
    },
    {
      field: 'agent_name',
      title: $t('tenant.ai.conversation.agentName'),
      width: 150,
      slots: { default: 'agentName_cell' },
    },
    {
      field: 'user_info',
      title: $t('tenant.ai.conversation.user'),
      width: 150,
      slots: { default: 'user_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.ai.conversation.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'token_count',
      title: $t('tenant.ai.conversation.tokenCount'),
      width: 120,
      align: 'right',
      slots: { default: 'tokenCount_cell' },
    },
    {
      field: 'cost',
      title: $t('tenant.ai.conversation.cost'),
      width: 110,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.ai.conversation.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'agent_conversation',
          nameField: 'title',
          nameTitle: $t('tenant.ai.conversation.title'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.ai.conversation.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['agent_conversation:detail'],
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
    searchInput('title', $t('tenant.ai.conversation.title'), {
      placeholder: $t('tenant.ai.conversation.placeholder.searchTitle'),
    }),
    select('filter[status][eq]', $t('tenant.ai.conversation.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.ai.conversation.placeholder.allStatuses'),
    }),
  ];
}

/**
 * 租户端 AI 操作审计日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { ActionLogItem } from '#/api/tenant/action-logs';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

export type { ActionLogItem };

function getTypeOptions() {
  return [
    { label: $t('tenant.ai.actionLog.type_options.query'), value: 'query' },
    { label: $t('tenant.ai.actionLog.type_options.action'), value: 'action' },
    { label: $t('tenant.ai.actionLog.type_options.confirm'), value: 'confirm' },
  ];
}

function getStatusOptions() {
  return [
    {
      label: $t('tenant.ai.actionLog.status_options.success'),
      value: 'success',
    },
    { label: $t('tenant.ai.actionLog.status_options.failed'), value: 'failed' },
    {
      label: $t('tenant.ai.actionLog.status_options.rejected'),
      value: 'rejected',
    },
    {
      label: $t('tenant.ai.actionLog.status_options.pending'),
      value: 'pending',
    },
  ];
}

export function getTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'action': {
      return $t('tenant.ai.actionLog.type_options.action');
    }
    case 'confirm': {
      return $t('tenant.ai.actionLog.type_options.confirm');
    }
    case 'query': {
      return $t('tenant.ai.actionLog.type_options.query');
    }
    default: {
      return type;
    }
  }
}

export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'failed': {
      return $t('tenant.ai.actionLog.status_options.failed');
    }
    case 'pending': {
      return $t('tenant.ai.actionLog.status_options.pending');
    }
    case 'rejected': {
      return $t('tenant.ai.actionLog.status_options.rejected');
    }
    case 'success': {
      return $t('tenant.ai.actionLog.status_options.success');
    }
    default: {
      return status;
    }
  }
}

export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'pending': {
      return 'processing';
    }
    case 'rejected': {
      return 'warning';
    }
    case 'success': {
      return 'success';
    }
    default: {
      return 'default';
    }
  }
}

export function getTypeColor(type: string | undefined): string {
  switch (type) {
    case 'action': {
      return 'purple';
    }
    case 'confirm': {
      return 'orange';
    }
    case 'query': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = ActionLogItem>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'created_at',
      title: $t('tenant.ai.actionLog.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'action_name',
      title: $t('tenant.ai.actionLog.actionName'),
      minWidth: 160,
      slots: { default: 'actionName_cell' },
    },
    {
      field: 'action_type',
      title: $t('tenant.ai.actionLog.actionType'),
      width: 120,
      align: 'center',
      slots: { default: 'actionType_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.ai.actionLog.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'agent_name',
      title: $t('tenant.ai.actionLog.agentName'),
      width: 140,
    },
    {
      field: 'execution_time_ms',
      title: $t('tenant.ai.actionLog.executionTime'),
      width: 120,
      align: 'right',
      slots: { default: 'executionTime_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_action_log',
          nameField: 'action_name',
          nameTitle: $t('tenant.ai.actionLog.actionName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.ai.actionLog.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_action_log:detail'],
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
    searchInput(
      'filter[action_name][ilike]',
      $t('tenant.ai.actionLog.actionName'),
      {
        placeholder: $t('tenant.ai.actionLog.placeholder.searchName'),
      },
    ),
    select('filter[action_type][eq]', $t('tenant.ai.actionLog.actionType'), {
      options: getTypeOptions(),
      placeholder: $t('tenant.ai.actionLog.placeholder.allTypes'),
    }),
    select('filter[status][eq]', $t('tenant.ai.actionLog.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.ai.actionLog.placeholder.allStatuses'),
    }),
  ];
}

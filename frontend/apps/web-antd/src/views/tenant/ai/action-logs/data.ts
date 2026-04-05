/**
 * 企业端 AI 操作审计日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { ActionLogItem } from '#/api/tenant/action-logs';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

export function getExecutionDecisionTypeText(value?: string): string {
  switch (value) {
    case 'confirmation': {
      return $t('tenant.ai.executionDecision.typeOptions.confirmation');
    }
    case 'consent': {
      return $t('tenant.ai.executionDecision.typeOptions.consent');
    }
    default: {
      return value || '-';
    }
  }
}

export function getExecutionDecisionStatusText(value?: string): string {
  switch (value) {
    case 'approved': {
      return $t('tenant.ai.executionDecision.statusOptions.approved');
    }
    case 'auto_approved': {
      return $t('tenant.ai.executionDecision.statusOptions.autoApproved');
    }
    case 'expired': {
      return $t('tenant.ai.executionDecision.statusOptions.expired');
    }
    case 'pending': {
      return $t('tenant.ai.executionDecision.statusOptions.pending');
    }
    case 'rejected': {
      return $t('tenant.ai.executionDecision.statusOptions.rejected');
    }
    default: {
      return value || '-';
    }
  }
}

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
      value: 'pending_confirm',
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
    case 'pending_confirm': {
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
    case 'pending_confirm': {
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

export function getLevelText(level: string | undefined): string {
  if (!level) return '-';
  switch (level) {
    case 'dangerous': {
      return $t('tenant.ai.actionLog.level_options.dangerous');
    }
    case 'read': {
      return $t('tenant.ai.actionLog.level_options.read');
    }
    case 'safe_write': {
      return $t('tenant.ai.actionLog.level_options.safe_write');
    }
    default: {
      return level;
    }
  }
}

export function getLevelColor(level: string | undefined): string {
  switch (level) {
    case 'dangerous': {
      return 'red';
    }
    case 'read': {
      return 'green';
    }
    case 'safe_write': {
      return 'orange';
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
      align: 'left',
      minWidth: 180,
      slots: { default: 'agent_cell' },
    },
    {
      field: 'operator_name',
      title: $t('tenant.ai.actionLog.operatorId'),
      align: 'left',
      minWidth: 180,
      slots: { default: 'operator_cell' },
    },
    {
      field: 'duration_ms',
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
    searchInput('filter[trace_id][ilike]', $t('tenant.ai.actionLog.traceId'), {
      placeholder: $t('tenant.ai.actionLog.placeholder.searchTrace'),
    }),
    searchInput(
      'filter[tool_call_id][ilike]',
      $t('tenant.ai.actionLog.toolCallId'),
      {
        placeholder: $t('tenant.ai.actionLog.placeholder.searchToolCall'),
      },
    ),
    searchInput(
      'filter[execution_decision_id][eq]',
      $t('tenant.ai.actionLog.executionDecisionId'),
      {
        placeholder: $t('tenant.ai.actionLog.placeholder.searchDecision'),
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

/**
 * 平台端 AI 操作审计日志 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';

import type { AdminActionLogItem } from '#/api/admin/action-logs';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

export type { AdminActionLogItem as ActionLogItem } from '#/api/admin/action-logs';

function getTypeOptions() {
  return [
    { label: $t('admin.ai.actionLog.type_options.query'), value: 'query' },
    { label: $t('admin.ai.actionLog.type_options.action'), value: 'action' },
    { label: $t('admin.ai.actionLog.type_options.confirm'), value: 'confirm' },
  ];
}

function getStatusOptions() {
  return [
    { label: $t('admin.ai.actionLog.status_options.success'), value: 'success' },
    { label: $t('admin.ai.actionLog.status_options.failed'), value: 'failed' },
    { label: $t('admin.ai.actionLog.status_options.rejected'), value: 'rejected' },
    { label: $t('admin.ai.actionLog.status_options.pending'), value: 'pending_confirm' },
  ];
}

function getLevelOptions() {
  return [
    { label: $t('admin.ai.actionLog.level_options.read'), value: 'read' },
    { label: $t('admin.ai.actionLog.level_options.safe_write'), value: 'safe_write' },
    { label: $t('admin.ai.actionLog.level_options.dangerous'), value: 'dangerous' },
  ];
}

export function getTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'query': return $t('admin.ai.actionLog.type_options.query');
    case 'action': return $t('admin.ai.actionLog.type_options.action');
    case 'confirm': return $t('admin.ai.actionLog.type_options.confirm');
    default: return type;
  }
}

export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'success': return $t('admin.ai.actionLog.status_options.success');
    case 'failed': return $t('admin.ai.actionLog.status_options.failed');
    case 'rejected': return $t('admin.ai.actionLog.status_options.rejected');
    case 'pending_confirm': return $t('admin.ai.actionLog.status_options.pending');
    default: return status;
  }
}

export function getLevelText(level: string | undefined): string {
  if (!level) return '-';
  switch (level) {
    case 'read': return $t('admin.ai.actionLog.level_options.read');
    case 'safe_write': return $t('admin.ai.actionLog.level_options.safe_write');
    case 'dangerous': return $t('admin.ai.actionLog.level_options.dangerous');
    default: return level;
  }
}

export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'success': return 'success';
    case 'failed': return 'error';
    case 'rejected': return 'warning';
    case 'pending_confirm': return 'processing';
    default: return 'default';
  }
}

export function getTypeColor(type: string | undefined): string {
  switch (type) {
    case 'query': return 'blue';
    case 'action': return 'purple';
    case 'confirm': return 'orange';
    default: return 'default';
  }
}

export function getLevelColor(level: string | undefined): string {
  switch (level) {
    case 'read': return 'green';
    case 'safe_write': return 'orange';
    case 'dangerous': return 'red';
    default: return 'default';
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = AdminActionLogItem>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'created_at',
      title: $t('admin.ai.actionLog.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'action_name',
      title: $t('admin.ai.actionLog.actionName'),
      minWidth: 160,
      slots: { default: 'actionName_cell' },
    },
    {
      field: 'action_type',
      title: $t('admin.ai.actionLog.actionType'),
      width: 110,
      align: 'center',
      slots: { default: 'actionType_cell' },
    },
    {
      field: 'action_level',
      title: $t('admin.ai.actionLog.actionLevel'),
      width: 120,
      align: 'center',
      slots: { default: 'actionLevel_cell' },
    },
    {
      field: 'status',
      title: $t('admin.ai.actionLog.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'tenant_id',
      title: $t('admin.ai.actionLog.tenantId'),
      width: 100,
      align: 'center',
    },
    {
      field: 'duration_ms',
      title: $t('admin.ai.actionLog.executionTime'),
      width: 110,
      align: 'right',
      sortable: true,
      slots: { default: 'duration_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_action_log',
          nameField: 'action_name',
          nameTitle: $t('admin.ai.actionLog.actionName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('admin.ai.actionLog.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_action_log:detail'],
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
    searchInput('filter[action_name][ilike]', $t('admin.ai.actionLog.actionName'), {
      placeholder: $t('admin.ai.actionLog.placeholder.searchName'),
    }),
    select('filter[action_type][eq]', $t('admin.ai.actionLog.actionType'), {
      options: getTypeOptions(),
      placeholder: $t('admin.ai.actionLog.placeholder.allTypes'),
    }),
    select('filter[status][eq]', $t('admin.ai.actionLog.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.ai.actionLog.placeholder.allStatuses'),
    }),
    select('filter[action_level][eq]', $t('admin.ai.actionLog.actionLevel'), {
      options: getLevelOptions(),
      placeholder: $t('admin.ai.actionLog.placeholder.allLevels'),
    }),
  ];
}

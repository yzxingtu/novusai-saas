/**
 * 任务日志管理 - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

type TaskLogInfo = adminApi.TaskLogInfo;

/**
 * 获取任务状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  if (!status) return 'default';
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'pending': {
      return 'default';
    }
    case 'retrying': {
      return 'warning';
    }
    case 'running': {
      return 'processing';
    }
    case 'success': {
      return 'success';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 获取队列颜色
 */
export function getQueueColor(queue: string | undefined): string {
  if (!queue) return 'default';
  switch (queue) {
    case 'default': {
      return 'blue';
    }
    case 'high': {
      return 'red';
    }
    case 'low': {
      return 'green';
    }
    default: {
      return 'purple';
    }
  }
}

/**
 * 任务状态选项
 */
function getStatusOptions() {
  return [
    { label: $t('admin.system.taskLog.status.pending'), value: 'pending' },
    { label: $t('admin.system.taskLog.status.running'), value: 'running' },
    { label: $t('admin.system.taskLog.status.success'), value: 'success' },
    { label: $t('admin.system.taskLog.status.failed'), value: 'failed' },
    { label: $t('admin.system.taskLog.status.retrying'), value: 'retrying' },
  ];
}

/**
 * 表格列定义
 */
export function useColumns<T = TaskLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'taskName',
      title: $t('admin.system.taskLog.taskName'),
      minWidth: 200,
      slots: {
        default: 'taskName_cell',
      },
    },
    {
      field: 'status',
      title: $t('admin.system.taskLog.status.label'),
      width: 110,
      align: 'center',
      slots: {
        default: 'status_cell',
      },
    },
    {
      field: 'queue',
      title: $t('admin.system.taskLog.queue'),
      width: 100,
      align: 'center',
      slots: {
        default: 'queue_cell',
      },
    },
    {
      field: 'durationMs',
      title: $t('admin.system.taskLog.durationMs'),
      width: 110,
      align: 'center',
      slots: {
        default: 'durationMs_cell',
      },
    },
    {
      field: 'retryCount',
      title: $t('admin.system.taskLog.retryCount'),
      width: 100,
      align: 'center',
      slots: {
        default: 'retryCount_cell',
      },
    },
    {
      field: 'errorMessage',
      title: $t('admin.system.taskLog.errorMessage'),
      minWidth: 200,
      slots: {
        default: 'errorMessage_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('admin.system.taskLog.createdAt'),
      width: 160,
      slots: {
        default: 'createdAt_cell',
      },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'task_log',
          nameField: 'taskName',
          nameTitle: $t('admin.system.taskLog.taskName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('admin.system.taskLog.detail'),
            icon: 'lucide:eye',
            accessCodes: ['task_log:detail'],
          },
          {
            code: 'retry',
            text: $t('admin.system.taskLog.retry'),
            icon: 'lucide:rotate-ccw',
            accessCodes: ['task_log:retry'],
          },
        ],
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
    searchInput('task_name', $t('admin.system.taskLog.taskName'), {
      placeholder: $t('admin.system.taskLog.placeholder.searchTaskName'),
    }),
    select('filter[status][eq]', $t('admin.system.taskLog.status.label'), {
      options: getStatusOptions(),
      placeholder: $t('admin.system.taskLog.placeholder.allStatus'),
    }),
    searchInput('queue', $t('admin.system.taskLog.queue'), {
      placeholder: $t('admin.system.taskLog.placeholder.searchQueue'),
      op: 'eq',
    }),
    select('filter[tenant_id]', $t('admin.system.taskLog.tenantName'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.system.taskLog.placeholder.allTenant'),
    }),
  ];
}

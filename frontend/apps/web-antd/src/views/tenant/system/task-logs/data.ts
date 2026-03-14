/**
 * 企业端任务日志管理 - 表格列和搜索配置
 * 复用 admin 端 data.ts 的列/状态定义
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { tenantApi } from '#/api';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

type TaskLogInfo = tenantApi.TaskLogInfo;

export {
  getQueueColor,
  getStatusColor,
} from '#/views/admin/system/task-logs/data';

function getStatusOptions() {
  return [
    { label: $t('tenant.system.taskLog.status.pending'), value: 'pending' },
    { label: $t('tenant.system.taskLog.status.running'), value: 'running' },
    { label: $t('tenant.system.taskLog.status.success'), value: 'success' },
    { label: $t('tenant.system.taskLog.status.failed'), value: 'failed' },
    { label: $t('tenant.system.taskLog.status.retrying'), value: 'retrying' },
  ];
}

export function useColumns<T = TaskLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'taskName',
      title: $t('tenant.system.taskLog.taskName'),
      minWidth: 200,
      slots: { default: 'taskName_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.system.taskLog.status.label'),
      width: 110,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'queue',
      title: $t('tenant.system.taskLog.queue'),
      width: 100,
      align: 'center',
      slots: { default: 'queue_cell' },
    },
    {
      field: 'durationMs',
      title: $t('tenant.system.taskLog.durationMs'),
      width: 110,
      align: 'center',
      slots: { default: 'durationMs_cell' },
    },
    {
      field: 'retryCount',
      title: $t('tenant.system.taskLog.retryCount'),
      width: 100,
      align: 'center',
      slots: { default: 'retryCount_cell' },
    },
    {
      field: 'errorMessage',
      title: $t('tenant.system.taskLog.errorMessage'),
      minWidth: 200,
      slots: { default: 'errorMessage_cell' },
    },
    {
      field: 'createdAt',
      title: $t('tenant.system.taskLog.createdAt'),
      width: 160,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'task_log',
          nameField: 'taskName',
          nameTitle: $t('tenant.system.taskLog.taskName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.system.taskLog.detail'),
            icon: 'lucide:eye',
            accessCodes: ['task_log:detail'],
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

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('task_name', $t('tenant.system.taskLog.taskName'), {
      placeholder: $t('tenant.system.taskLog.placeholder.searchTaskName'),
    }),
    select('filter[status][eq]', $t('tenant.system.taskLog.status.label'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.system.taskLog.placeholder.allStatus'),
    }),
  ];
}

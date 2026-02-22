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
 * 从完整任务路径提取简短友好名称
 */
export function getTaskShortName(taskName: string): string {
  const funcName = taskName.split('.').at(-1) ?? taskName;
  for (const prefix of ['admin', 'tenant']) {
    const key = `${prefix}.system.taskLog.taskNames.${funcName}`;
    const translated = $t(key);
    if (translated !== key) return translated;
  }
  return funcName;
}

/**
 * 格式化耗时为易读字符串
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

/**
 * 从任务结果中提取摘要信息
 */
export function getResultSummary(
  row: TaskLogInfo,
): { text: string; type: 'error' | 'info' | 'success' } | null {
  if (row.errorMessage) {
    return { text: row.errorMessage, type: 'error' };
  }
  if (!row.result || typeof row.result !== 'object') return null;
  const r = row.result as Record<string, unknown>;
  const parts: string[] = [];
  if ('total_cleaned' in r) {
    parts.push(`${$t('admin.system.taskLog.resultKeys.cleaned')}: ${r.total_cleaned}`);
  }
  if ('cleaned' in r) {
    parts.push(`${$t('admin.system.taskLog.resultKeys.cleaned')}: ${r.cleaned}`);
  }
  if ('reset_count' in r) {
    parts.push(`${$t('admin.system.taskLog.resultKeys.reset')}: ${r.reset_count}`);
  }
  if ('db' in r) {
    parts.push(`DB: ${r.db}`);
  }
  if ('redis' in r) {
    parts.push(`Redis: ${r.redis}`);
  }
  if ('error' in r && typeof r.error === 'string') {
    return { text: r.error as string, type: 'error' };
  }
  if (parts.length > 0) {
    return { text: parts.join(' | '), type: 'success' };
  }
  return { text: JSON.stringify(r), type: 'info' };
}

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
    case 'high_priority': {
      return 'red';
    }
    case 'ai_gateway': {
      return 'purple';
    }
    case 'scheduled': {
      return 'cyan';
    }
    case 'notification': {
      return 'green';
    }
    default: {
      return 'default';
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
      minWidth: 220,
      slots: {
        default: 'taskName_cell',
      },
    },
    {
      field: 'status',
      title: $t('admin.system.taskLog.status.label'),
      width: 100,
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
      title: $t('admin.system.taskLog.duration'),
      width: 100,
      align: 'center',
      slots: {
        default: 'durationMs_cell',
      },
    },
    {
      field: 'result',
      title: $t('admin.system.taskLog.resultSummary'),
      minWidth: 240,
      slots: {
        default: 'result_cell',
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
            show: (row: Record<string, unknown>) => row.status === 'failed',
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 120,
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

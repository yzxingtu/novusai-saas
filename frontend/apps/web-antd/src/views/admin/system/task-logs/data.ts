/**
 * 任务日志运行中心 - 表格列与搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

type TaskLogInfo = adminApi.TaskLogInfo;

export function getTaskShortName(taskName: string): string {
  const funcName = taskName.split('.').at(-1) ?? taskName;
  for (const prefix of ['admin', 'tenant']) {
    const key = `${prefix}.system.taskLog.taskNames.${funcName}`;
    const translated = $t(key);
    if (translated !== key) return translated;
  }
  return funcName;
}

export function formatDuration(ms: null | number | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

export function getResultSummary(
  row: TaskLogInfo,
): null | { text: string; type: 'error' | 'info' | 'success' } {
  if (row.errorMessage) {
    return { text: row.errorMessage, type: 'error' };
  }
  if (!row.result || typeof row.result !== 'object') return null;
  const result = row.result as Record<string, unknown>;
  const parts: string[] = [];
  if ('total_cleaned' in result) {
    parts.push(
      `${$t('admin.system.taskLog.resultKeys.cleaned')}: ${result.total_cleaned}`,
    );
  }
  if ('cleaned' in result) {
    parts.push(
      `${$t('admin.system.taskLog.resultKeys.cleaned')}: ${result.cleaned}`,
    );
  }
  if ('reset_count' in result) {
    parts.push(
      `${$t('admin.system.taskLog.resultKeys.reset')}: ${result.reset_count}`,
    );
  }
  if ('db' in result) {
    parts.push(`DB: ${result.db}`);
  }
  if ('redis' in result) {
    parts.push(`Redis: ${result.redis}`);
  }
  if ('error' in result && typeof result.error === 'string') {
    return { text: result.error, type: 'error' };
  }
  if (parts.length > 0) {
    return { text: parts.join(' | '), type: 'success' };
  }
  return { text: JSON.stringify(result), type: 'info' };
}

export function getTriggerSourceText(
  source: null | string | undefined,
): string {
  if (!source) return '-';
  return $t(`admin.system.taskLog.triggerSourceValues.${source}`, source);
}

export function getRunKindText(kind: null | string | undefined): string {
  if (!kind) return '-';
  return $t(`admin.system.taskLog.runKindValues.${kind}`, kind);
}

export function getBindingContextText(
  bindingId: null | number | undefined,
): string {
  if (!bindingId) {
    return $t('admin.system.taskLog.relation.platformDirect');
  }
  return `${$t('admin.system.taskLog.bindingId')} #${bindingId}`;
}

export function getOwnerContextText(
  ownerTenantId: null | number | undefined,
): string {
  if (!ownerTenantId) {
    return $t('admin.system.taskLog.relation.ownerPlatform');
  }
  return `${$t('admin.system.taskLog.ownerTenantId')} #${ownerTenantId}`;
}

export function getEffectiveContextText(
  effectiveTenantId: null | number | undefined,
): string {
  if (!effectiveTenantId) {
    return $t('admin.system.taskLog.relation.effectivePlatform');
  }
  return `${$t('admin.system.taskLog.effectiveTenantId')} #${effectiveTenantId}`;
}

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

export function getQueueColor(queue: string | undefined): string {
  if (!queue) return 'default';
  switch (queue) {
    case 'ai_gateway': {
      return 'purple';
    }
    case 'default': {
      return 'blue';
    }
    case 'high_priority': {
      return 'red';
    }
    case 'notification': {
      return 'green';
    }
    case 'scheduled': {
      return 'cyan';
    }
    default: {
      return 'default';
    }
  }
}

function getStatusOptions() {
  return [
    { label: $t('admin.system.taskLog.status.pending'), value: 'pending' },
    { label: $t('admin.system.taskLog.status.running'), value: 'running' },
    { label: $t('admin.system.taskLog.status.success'), value: 'success' },
    { label: $t('admin.system.taskLog.status.failed'), value: 'failed' },
    { label: $t('admin.system.taskLog.status.retrying'), value: 'retrying' },
  ];
}

export function useColumns<T = TaskLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'taskName',
      title: $t('admin.system.taskLog.taskName'),
      minWidth: 320,
      slots: {
        default: 'taskName_cell',
      },
    },
    {
      field: 'relation',
      title: $t('admin.system.taskLog.relationInfo'),
      minWidth: 280,
      slots: {
        default: 'relation_cell',
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
      field: 'durationMs',
      title: $t('admin.system.taskLog.duration'),
      width: 96,
      align: 'center',
      slots: {
        default: 'durationMs_cell',
      },
    },
    {
      field: 'result',
      title: $t('admin.system.taskLog.resultSummary'),
      minWidth: 260,
      slots: {
        default: 'result_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('admin.system.taskLog.createdAt'),
      width: 150,
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
      width: 100,
    },
  ];
}

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
    select(
      'filter[effective_tenant_id][eq]',
      $t('admin.system.taskLog.tenantName'),
      {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        placeholder: $t('admin.system.taskLog.placeholder.allTenant'),
      },
    ),
  ];
}

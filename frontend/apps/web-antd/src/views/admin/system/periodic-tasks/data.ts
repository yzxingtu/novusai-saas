/**
 * 定时任务管理 - 表格列、搜索和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import {
  dividerField,
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { useScopeFields } from '#/components/business/scope-select';
import { $t } from '#/locales';
import { getScopeOptions as _getScopeOptions } from '#/utils/scope-helpers';

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

function getScopeOptions() {
  return _getScopeOptions(['admin_only', 'all_tenants']);
}

/**
 * 获取调度类型文本
 */
export function getScheduleTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'cron': {
      return $t('admin.system.periodicTask.scheduleType.cron');
    }
    case 'interval': {
      return $t('admin.system.periodicTask.scheduleType.interval');
    }
    default: {
      return type;
    }
  }
}

/**
 * 格式化间隔秒数为可读文本
 */
export function formatInterval(seconds: null | number | undefined): string {
  if (!seconds) return '-';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86_400)}d`;
}

/**
 * 格式化 Cron 表达式为可读文本
 */
function formatCronHuman(cron: null | string | undefined): string {
  if (!cron) return '-';
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [minute, hour, dom, , dow] = parts;

  if (dom !== '*' && dow === '*') {
    return `${$t('admin.system.periodicTask.cronHuman.monthly')} ${dom}${$t('admin.system.periodicTask.cronHuman.day')} ${hour}:${minute?.padStart(2, '0')}`;
  }
  if (hour !== '*' && minute !== '*') {
    return `${$t('admin.system.periodicTask.cronHuman.daily')} ${hour}:${minute?.padStart(2, '0')}`;
  }
  if (hour === '*' && minute !== '*') {
    return `${$t('admin.system.periodicTask.cronHuman.hourly')} :${minute?.padStart(2, '0')}`;
  }
  return cron;
}

/**
 * 获取调度显示文本（合并类型 + 表达式）
 */
export function getScheduleDisplay(row: PeriodicTaskInfo): string {
  if (row.scheduleType === 'cron') {
    return formatCronHuman(row.cronExpression);
  }
  return formatInterval(row.intervalSeconds);
}

/**
 * 调度类型选项
 */
function getScheduleTypeOptions() {
  return [
    { label: $t('admin.system.periodicTask.scheduleType.cron'), value: 'cron' },
    {
      label: $t('admin.system.periodicTask.scheduleType.interval'),
      value: 'interval',
    },
  ];
}

/**
 * 获取任务图标（根据 task_path 推断）
 */
export function getTaskIcon(taskPath: string): string {
  if (taskPath.includes('health_check') || taskPath.includes('health'))
    return 'lucide:heart-pulse';
  if (
    taskPath.includes('cleanup') ||
    taskPath.includes('clean') ||
    taskPath.includes('recycle')
  )
    return 'lucide:trash-2';
  if (taskPath.includes('reset')) return 'lucide:rotate-ccw';
  if (taskPath.includes('ssl') || taskPath.includes('certificate'))
    return 'lucide:shield-check';
  if (taskPath.includes('upload')) return 'lucide:upload-cloud';
  if (taskPath.includes('notification') || taskPath.includes('notify'))
    return 'lucide:bell';
  if (taskPath.includes('ai') || taskPath.includes('agent'))
    return 'lucide:bot';
  if (taskPath.includes('email') || taskPath.includes('mail'))
    return 'lucide:mail';
  return 'lucide:clock';
}

/**
 * 获取任务图标颜色
 */
export function getTaskIconColor(taskPath: string): string {
  if (taskPath.includes('health_check') || taskPath.includes('health'))
    return 'text-emerald-500';
  if (
    taskPath.includes('cleanup') ||
    taskPath.includes('clean') ||
    taskPath.includes('recycle')
  )
    return 'text-orange-500';
  if (taskPath.includes('reset')) return 'text-blue-500';
  if (taskPath.includes('ssl') || taskPath.includes('certificate'))
    return 'text-violet-500';
  if (taskPath.includes('upload')) return 'text-cyan-500';
  if (taskPath.includes('notification') || taskPath.includes('notify'))
    return 'text-amber-500';
  if (taskPath.includes('ai') || taskPath.includes('agent'))
    return 'text-pink-500';
  if (taskPath.includes('email') || taskPath.includes('mail'))
    return 'text-indigo-500';
  return 'text-slate-500';
}

/**
 * 获取任务图标背景色
 */
export function getTaskIconBg(taskPath: string): string {
  if (taskPath.includes('health_check') || taskPath.includes('health'))
    return 'bg-emerald-500/10';
  if (
    taskPath.includes('cleanup') ||
    taskPath.includes('clean') ||
    taskPath.includes('recycle')
  )
    return 'bg-orange-500/10';
  if (taskPath.includes('reset')) return 'bg-blue-500/10';
  if (taskPath.includes('ssl') || taskPath.includes('certificate'))
    return 'bg-violet-500/10';
  if (taskPath.includes('upload')) return 'bg-cyan-500/10';
  if (taskPath.includes('notification') || taskPath.includes('notify'))
    return 'bg-amber-500/10';
  if (taskPath.includes('ai') || taskPath.includes('agent'))
    return 'bg-pink-500/10';
  if (taskPath.includes('email') || taskPath.includes('mail'))
    return 'bg-indigo-500/10';
  return 'bg-slate-500/10';
}

/**
 * 表格列定义
 */
export function useColumns<T = PeriodicTaskInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.system.periodicTask.name'),
      minWidth: 260,
      slots: { default: 'name_cell' },
    },
    {
      field: 'schedule',
      title: $t('admin.system.periodicTask.schedule'),
      width: 140,
      align: 'center',
      slots: { default: 'schedule_cell' },
    },
    {
      field: 'isActive',
      title: $t('admin.system.periodicTask.isActive'),
      width: 80,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'lastRunAt',
      title: $t('admin.system.periodicTask.runInfo'),
      width: 170,
      slots: { default: 'runInfo_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'periodic_task',
          nameField: 'name',
          nameTitle: $t('admin.system.periodicTask.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          'edit',
          {
            code: 'trigger',
            text: $t('admin.system.periodicTask.trigger'),
            icon: 'lucide:play',
            accessCodes: ['periodic_task:trigger'],
          },
          {
            code: 'logs',
            text: $t('admin.system.periodicTask.viewLogs'),
            icon: 'lucide:scroll-text',
          },
          'delete',
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
    searchInput('name', $t('admin.system.periodicTask.name'), {
      placeholder: $t('admin.system.periodicTask.placeholder.searchName'),
    }),
    select(
      'filter[schedule_type][eq]',
      $t('admin.system.periodicTask.scheduleTypeLabel'),
      {
        options: getScheduleTypeOptions(),
        placeholder: $t(
          'admin.system.periodicTask.placeholder.allScheduleTypes',
        ),
      },
    ),
    select('filter[scope][eq]', $t('admin.system.periodicTask.scopeLabel'), {
      options: getScopeOptions(),
      placeholder: $t('admin.system.periodicTask.placeholder.allScopes'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit: boolean): VbenFormSchema[] {
  return [
    dividerField(
      'basic_divider',
      $t('admin.system.periodicTask.section.basic'),
    ),
    inputField('name', $t('admin.system.periodicTask.name'), {
      required: true,
      placeholder: $t('admin.system.periodicTask.placeholder.inputName'),
    }),
    inputField('task_path', $t('admin.system.periodicTask.taskPath'), {
      required: true,
      placeholder: $t('admin.system.periodicTask.placeholder.inputTaskPath'),
      disabled: isEdit,
    }),
    {
      ...select(
        'schedule_type',
        $t('admin.system.periodicTask.scheduleTypeLabel'),
        {
          options: getScheduleTypeOptions(),
          required: true,
          placeholder: $t(
            'admin.system.periodicTask.placeholder.selectScheduleType',
          ),
        },
      ),
      help: $t('admin.system.periodicTask.scheduleTypeHelp'),
    },
    {
      component: 'CronPicker',
      fieldName: 'cron_expression',
      formItemClass: 'col-span-full',
      label: $t('admin.system.periodicTask.cronExpression'),
      dependencies: {
        triggerFields: ['schedule_type'],
        show: (values) => values.schedule_type === 'cron',
      },
    },
    {
      ...numberField(
        'interval_seconds',
        $t('admin.system.periodicTask.intervalSeconds'),
        {
          min: 10,
          placeholder: $t(
            'admin.system.periodicTask.placeholder.inputInterval',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['schedule_type'],
        show: (values) => values.schedule_type === 'interval',
      },
    },
    switchField('is_active', $t('admin.system.periodicTask.isActive'), {
      defaultValue: true,
    }),
    textareaField('description', $t('admin.system.periodicTask.description'), {
      placeholder: $t('admin.system.periodicTask.placeholder.inputDescription'),
    }),

    dividerField(
      'scope_divider',
      $t('admin.system.periodicTask.section.scope'),
    ),
    ...useScopeFields({
      allowedScopes: ['admin_only', 'all_tenants'],
      showTenantId: true,
    }),

    dividerField(
      'protection_divider',
      $t('admin.system.periodicTask.section.protection'),
    ),
    switchField('is_locked', $t('admin.system.periodicTask.isLocked'), {
      defaultValue: false,
    }),
    switchField('is_editable', $t('admin.system.periodicTask.isEditable'), {
      defaultValue: true,
    }),

    dividerField(
      'retry_divider',
      $t('admin.system.periodicTask.section.retry'),
    ),
    numberField('max_retries', $t('admin.system.periodicTask.maxRetries'), {
      min: 0,
      max: 10,
      placeholder: $t('admin.system.periodicTask.placeholder.inputMaxRetries'),
    }),
    numberField('retry_delay', $t('admin.system.periodicTask.retryDelay'), {
      min: 1,
      max: 3600,
      placeholder: $t('admin.system.periodicTask.placeholder.inputRetryDelay'),
    }),
    numberField('timeout', $t('admin.system.periodicTask.timeout'), {
      min: 10,
      max: 86_400,
      placeholder: $t('admin.system.periodicTask.placeholder.inputTimeout'),
    }),

    dividerField(
      'notify_divider',
      $t('admin.system.periodicTask.section.notify'),
    ),
    switchField(
      'notify_on_failure',
      $t('admin.system.periodicTask.notifyOnFailure'),
      {
        defaultValue: false,
      },
    ),
    {
      ...inputField(
        'notify_emails',
        $t('admin.system.periodicTask.notifyEmails'),
        {
          placeholder: $t(
            'admin.system.periodicTask.placeholder.inputNotifyEmails',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['notify_on_failure'],
        show: (values) => values.notify_on_failure === true,
      },
    },
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    schedule_type: 'interval',
    interval_seconds: 60,
    is_active: true,
    scope: 'admin_only',
    is_locked: false,
    is_editable: true,
    max_retries: 0,
    retry_delay: 60,
    timeout: 3600,
    notify_on_failure: false,
  };
}

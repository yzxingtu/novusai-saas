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
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

function getScopeOptions() {
  return [
    { label: $t('admin.system.periodicTask.scope.platform'), value: 'platform' },
    { label: $t('admin.system.periodicTask.scope.tenant'), value: 'tenant' },
    { label: $t('admin.system.periodicTask.scope.allTenants'), value: 'all_tenants' },
  ];
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
export function formatInterval(seconds: number | null | undefined): string {
  if (!seconds) return '-';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/**
 * 调度类型选项
 */
function getScheduleTypeOptions() {
  return [
    { label: $t('admin.system.periodicTask.scheduleType.cron'), value: 'cron' },
    { label: $t('admin.system.periodicTask.scheduleType.interval'), value: 'interval' },
  ];
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
      minWidth: 180,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'taskPath',
      title: $t('admin.system.periodicTask.taskPath'),
      minWidth: 200,
      slots: {
        default: 'taskPath_cell',
      },
    },
    {
      field: 'scheduleType',
      title: $t('admin.system.periodicTask.scheduleTypeLabel'),
      width: 120,
      align: 'center',
      slots: {
        default: 'scheduleType_cell',
      },
    },
    {
      field: 'schedule',
      title: $t('admin.system.periodicTask.schedule'),
      width: 140,
      align: 'center',
      slots: {
        default: 'schedule_cell',
      },
    },
    {
      field: 'scope',
      title: $t('admin.system.periodicTask.scopeLabel'),
      width: 120,
      align: 'center',
      slots: { default: 'scope_cell' },
    },
    {
      field: 'isActive',
      title: $t('admin.system.periodicTask.isActive'),
      width: 100,
      align: 'center',
      slots: {
        default: 'isActive_cell',
      },
    },
    {
      field: 'lastRunAt',
      title: $t('admin.system.periodicTask.lastRunAt'),
      width: 160,
      slots: {
        default: 'lastRunAt_cell',
      },
    },
    {
      field: 'nextRunAt',
      title: $t('admin.system.periodicTask.nextRunAt'),
      width: 160,
      slots: {
        default: 'nextRunAt_cell',
      },
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
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 200,
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
    searchInput('task_path', $t('admin.system.periodicTask.taskPath'), {
      placeholder: $t('admin.system.periodicTask.placeholder.searchTaskPath'),
    }),
    select('filter[schedule_type][eq]', $t('admin.system.periodicTask.scheduleTypeLabel'), {
      options: getScheduleTypeOptions(),
      placeholder: $t('admin.system.periodicTask.placeholder.allScheduleTypes'),
    }),
    select('filter[scope][eq]', $t('admin.system.periodicTask.scopeLabel'), {
      options: getScopeOptions(),
      placeholder: $t('admin.system.periodicTask.placeholder.allScopes'),
    }),
    select('filter[tenant_id]', $t('admin.system.periodicTask.tenantName'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.system.periodicTask.placeholder.allTenant'),
    }),
  ];
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit: boolean): VbenFormSchema[] {
  return [
    dividerField('basic_divider', $t('admin.system.periodicTask.section.basic')),
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
      ...select('schedule_type', $t('admin.system.periodicTask.scheduleTypeLabel'), {
        options: getScheduleTypeOptions(),
        required: true,
        placeholder: $t('admin.system.periodicTask.placeholder.selectScheduleType'),
      }),
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
      ...numberField('interval_seconds', $t('admin.system.periodicTask.intervalSeconds'), {
        min: 10,
        placeholder: $t('admin.system.periodicTask.placeholder.inputInterval'),
      }),
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

    dividerField('scope_divider', $t('admin.system.periodicTask.section.scope')),
    select('scope', $t('admin.system.periodicTask.scopeLabel'), {
      options: getScopeOptions(),
      required: true,
      placeholder: $t('admin.system.periodicTask.placeholder.selectScope'),
    }),
    {
      ...select('tenant_id', $t('admin.system.periodicTask.tenantName'), {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        placeholder: $t('admin.system.periodicTask.placeholder.selectTenant'),
      }),
      dependencies: {
        triggerFields: ['scope'],
        show: (values) => values.scope === 'tenant',
      },
    },

    dividerField('protection_divider', $t('admin.system.periodicTask.section.protection')),
    switchField('is_locked', $t('admin.system.periodicTask.isLocked'), {
      defaultValue: false,
    }),
    switchField('is_editable', $t('admin.system.periodicTask.isEditable'), {
      defaultValue: true,
    }),

    dividerField('retry_divider', $t('admin.system.periodicTask.section.retry')),
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
      max: 86400,
      placeholder: $t('admin.system.periodicTask.placeholder.inputTimeout'),
    }),

    dividerField('notify_divider', $t('admin.system.periodicTask.section.notify')),
    switchField('notify_on_failure', $t('admin.system.periodicTask.notifyOnFailure'), {
      defaultValue: false,
    }),
    {
      ...inputField('notify_emails', $t('admin.system.periodicTask.notifyEmails'), {
        placeholder: $t('admin.system.periodicTask.placeholder.inputNotifyEmails'),
      }),
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
    scope: 'platform',
    is_locked: false,
    is_editable: true,
    max_retries: 0,
    retry_delay: 60,
    timeout: 3600,
    notify_on_failure: false,
  };
}

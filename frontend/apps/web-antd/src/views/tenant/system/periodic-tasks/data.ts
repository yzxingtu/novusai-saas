/**
 * 企业端定时任务管理 - 表格列、搜索和表单配置
 * 复用 admin 端 data.ts 的辅助函数
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { tenantApi } from '#/api';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

type PeriodicTaskInfo = tenantApi.PeriodicTaskInfo;

export { formatInterval } from '#/views/admin/system/periodic-tasks/data';

export function getScheduleTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'cron': {
      return $t('tenant.system.periodicTask.scheduleType.cron');
    }
    case 'interval': {
      return $t('tenant.system.periodicTask.scheduleType.interval');
    }
    default: {
      return type;
    }
  }
}

function getScheduleTypeOptions() {
  return [
    {
      label: $t('tenant.system.periodicTask.scheduleType.cron'),
      value: 'cron',
    },
    {
      label: $t('tenant.system.periodicTask.scheduleType.interval'),
      value: 'interval',
    },
  ];
}

export function useColumns<T = PeriodicTaskInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.system.periodicTask.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'taskPath',
      title: $t('tenant.system.periodicTask.taskPath'),
      minWidth: 200,
      slots: { default: 'taskPath_cell' },
    },
    {
      field: 'scheduleType',
      title: $t('tenant.system.periodicTask.scheduleTypeLabel'),
      width: 120,
      align: 'center',
      slots: { default: 'scheduleType_cell' },
    },
    {
      field: 'schedule',
      title: $t('tenant.system.periodicTask.schedule'),
      width: 140,
      align: 'center',
      slots: { default: 'schedule_cell' },
    },
    {
      field: 'isActive',
      title: $t('tenant.system.periodicTask.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'lastRunAt',
      title: $t('tenant.system.periodicTask.lastRunAt'),
      width: 160,
      slots: { default: 'lastRunAt_cell' },
    },
    {
      field: 'nextRunAt',
      title: $t('tenant.system.periodicTask.nextRunAt'),
      width: 160,
      slots: { default: 'nextRunAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'periodic_task',
          nameField: 'name',
          nameTitle: $t('tenant.system.periodicTask.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          'edit',
          {
            code: 'trigger',
            text: $t('tenant.system.periodicTask.trigger'),
            icon: 'lucide:play',
            accessCodes: ['periodic_task:trigger'],
          },
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 200,
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.system.periodicTask.name'), {
      placeholder: $t('tenant.system.periodicTask.placeholder.searchName'),
    }),
    select(
      'filter[schedule_type][eq]',
      $t('tenant.system.periodicTask.scheduleTypeLabel'),
      {
        options: getScheduleTypeOptions(),
        placeholder: $t(
          'tenant.system.periodicTask.placeholder.allScheduleTypes',
        ),
      },
    ),
  ];
}

export function useFormSchema(isEdit: boolean): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.system.periodicTask.name'), {
      required: true,
      placeholder: $t('tenant.system.periodicTask.placeholder.inputName'),
    }),
    inputField('task_path', $t('tenant.system.periodicTask.taskPath'), {
      required: true,
      placeholder: $t('tenant.system.periodicTask.placeholder.inputTaskPath'),
      disabled: isEdit,
    }),
    {
      ...select(
        'schedule_type',
        $t('tenant.system.periodicTask.scheduleTypeLabel'),
        {
          options: getScheduleTypeOptions(),
          required: true,
          placeholder: $t(
            'tenant.system.periodicTask.placeholder.selectScheduleType',
          ),
        },
      ),
      help: $t('tenant.system.periodicTask.scheduleTypeHelp'),
    },
    {
      component: 'CronPicker',
      fieldName: 'cron_expression',
      formItemClass: 'col-span-full',
      label: $t('tenant.system.periodicTask.cronExpression'),
      dependencies: {
        triggerFields: ['schedule_type'],
        show: (values) => values.schedule_type === 'cron',
      },
    },
    {
      ...numberField(
        'interval_seconds',
        $t('tenant.system.periodicTask.intervalSeconds'),
        {
          min: 10,
          placeholder: $t(
            'tenant.system.periodicTask.placeholder.inputInterval',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['schedule_type'],
        show: (values) => values.schedule_type === 'interval',
      },
    },
    switchField('is_active', $t('tenant.system.periodicTask.isActive'), {
      defaultValue: true,
    }),
    textareaField('description', $t('tenant.system.periodicTask.description'), {
      placeholder: $t(
        'tenant.system.periodicTask.placeholder.inputDescription',
      ),
    }),
  ];
}

export function getFormDefaults(): Record<string, unknown> {
  return {
    schedule_type: 'interval',
    interval_seconds: 60,
    is_active: true,
  };
}

/**
 * 通知模板管理 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';

import { select } from '#/adapter/form';
import { $t } from '#/locales';

function getCategoryOptions() {
  return [
    {
      label: $t('admin.system.notificationTemplate.category_options.system'),
      value: 'system',
    },
    {
      label: $t('admin.system.notificationTemplate.category_options.ai'),
      value: 'ai',
    },
    {
      label: $t('admin.system.notificationTemplate.category_options.task'),
      value: 'task',
    },
    {
      label: $t('admin.system.notificationTemplate.category_options.biz'),
      value: 'biz',
    },
    {
      label: $t('admin.system.notificationTemplate.category_options.audit'),
      value: 'audit',
    },
  ];
}

function getPriorityOptions() {
  return [
    {
      label: $t('admin.system.notificationTemplate.priority_options.low'),
      value: 'low',
    },
    {
      label: $t('admin.system.notificationTemplate.priority_options.normal'),
      value: 'normal',
    },
    {
      label: $t('admin.system.notificationTemplate.priority_options.high'),
      value: 'high',
    },
    {
      label: $t('admin.system.notificationTemplate.priority_options.urgent'),
      value: 'urgent',
    },
  ];
}

function getEnabledOptions() {
  return [
    {
      label: $t('admin.system.notificationTemplate.enabled'),
      value: 'true',
    },
    {
      label: $t('admin.system.notificationTemplate.disabled'),
      value: 'false',
    },
  ];
}

export function getCategoryColor(category: string): string {
  switch (category) {
    case 'ai': {
      return 'purple';
    }
    case 'audit': {
      return 'red';
    }
    case 'biz': {
      return 'orange';
    }
    case 'system': {
      return 'blue';
    }
    case 'task': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

export function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'high': {
      return 'orange';
    }
    case 'low': {
      return 'default';
    }
    case 'normal': {
      return 'blue';
    }
    case 'urgent': {
      return 'red';
    }
    default: {
      return 'default';
    }
  }
}

export function getChannelLabel(channel: string): string {
  switch (channel) {
    case 'email': {
      return $t('admin.system.notificationTemplate.channelEmail');
    }
    case 'inbox': {
      return $t('admin.system.notificationTemplate.channelInbox');
    }
    case 'webhook': {
      return $t('admin.system.notificationTemplate.channelWebhook');
    }
    case 'ws': {
      return $t('admin.system.notificationTemplate.channelWs');
    }
    default: {
      return channel;
    }
  }
}

export function getChannelColor(channel: string): string {
  switch (channel) {
    case 'email': {
      return 'orange';
    }
    case 'inbox': {
      return 'blue';
    }
    case 'webhook': {
      return 'purple';
    }
    case 'ws': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

export function getScopeLabel(scope: null | string | undefined): string {
  if (!scope) {
    return $t('admin.system.notificationTemplate.scopeGlobal');
  }
  const key = `admin.system.notificationTemplate.scope_options.${scope}`;
  return $t(key);
}

export function getSourceLabel(source: null | string | undefined): string {
  if (!source) {
    return $t('admin.system.notificationTemplate.sourceSystem');
  }
  const key = `admin.system.notificationTemplate.source_options.${source}`;
  return $t(key);
}

export function getOverrideLabel(isOverride: boolean): string {
  return isOverride
    ? $t('admin.system.notificationTemplate.override')
    : $t('admin.system.notificationTemplate.defaultTemplate');
}

export function useColumns<T = Record<string, unknown>>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'code',
      title: $t('admin.system.notificationTemplate.code'),
      width: 200,
      slots: { default: 'code_cell' },
    },
    {
      field: 'titleTemplate',
      title: $t('admin.system.notificationTemplate.titleTemplate'),
      minWidth: 200,
      slots: { default: 'title_cell' },
    },
    {
      field: 'bodyTemplate',
      title: $t('admin.system.notificationTemplate.bodyTemplate'),
      minWidth: 260,
      slots: { default: 'body_cell' },
    },
    {
      field: 'category',
      title: $t('admin.system.notificationTemplate.category'),
      width: 100,
      align: 'center',
      slots: { default: 'category_cell' },
    },
    {
      field: 'channels',
      title: $t('admin.system.notificationTemplate.channels'),
      width: 200,
      slots: { default: 'channels_cell' },
    },
    {
      field: 'priority',
      title: $t('admin.system.notificationTemplate.priority'),
      width: 100,
      align: 'center',
      slots: { default: 'priority_cell' },
    },
    {
      field: 'scope',
      title: $t('admin.system.notificationTemplate.scope'),
      width: 150,
      slots: { default: 'scope_cell' },
    },
    {
      field: 'source',
      title: $t('admin.system.notificationTemplate.source'),
      width: 160,
      slots: { default: 'source_cell' },
    },
    {
      field: 'enabled',
      title: $t('admin.system.notificationTemplate.enabled'),
      width: 96,
      align: 'center',
      slots: { default: 'enabled_cell' },
    },
    {
      field: 'isSystem',
      title: $t('admin.system.notificationTemplate.isSystem'),
      width: 120,
      align: 'center',
      slots: { default: 'isSystem_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'notification_template',
          nameField: 'code',
          nameTitle: $t('admin.system.notificationTemplate.code'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'preview',
            text: $t('admin.system.notificationTemplate.preview'),
            icon: 'lucide:eye',
            accessCodes: ['notification_template:list'],
          },
          {
            code: 'test',
            text: $t('admin.system.notificationTemplate.test'),
            icon: 'lucide:play',
            accessCodes: ['notification_template:test'],
          },
          {
            code: 'edit',
            text: $t('common.edit'),
            icon: 'lucide:pencil',
            accessCodes: ['notification_template:update'],
          },
          {
            code: 'restore',
            text: $t('admin.system.notificationTemplate.restoreDefault'),
            icon: 'lucide:rotate-ccw',
            accessCodes: ['notification_template:update'],
            show: (row: Record<string, unknown>) =>
              row.isOverride === true || row.isSystem === false,
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 190,
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    select(
      'filter[category][eq]',
      $t('admin.system.notificationTemplate.category'),
      {
        options: getCategoryOptions(),
        placeholder: $t(
          'admin.system.notificationTemplate.placeholder.allCategories',
        ),
      },
    ),
    select(
      'filter[priority][eq]',
      $t('admin.system.notificationTemplate.priority'),
      {
        options: getPriorityOptions(),
        placeholder: $t(
          'admin.system.notificationTemplate.placeholder.allPriorities',
        ),
      },
    ),
    select(
      'filter[is_enabled][eq]',
      $t('admin.system.notificationTemplate.enabled'),
      {
        options: getEnabledOptions(),
        placeholder: $t(
          'admin.system.notificationTemplate.placeholder.allEnabledStates',
        ),
      },
    ),
  ];
}

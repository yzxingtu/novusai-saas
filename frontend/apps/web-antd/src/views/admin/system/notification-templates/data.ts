/**
 * 通知模板管理 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';

import { select } from '#/adapter/form';
import { $t } from '#/locales';

function getCategoryOptions() {
  return [
    { label: $t('admin.system.notificationTemplate.category_options.system'), value: 'system' },
    { label: $t('admin.system.notificationTemplate.category_options.ai'), value: 'ai' },
    { label: $t('admin.system.notificationTemplate.category_options.task'), value: 'task' },
    { label: $t('admin.system.notificationTemplate.category_options.biz'), value: 'biz' },
    { label: $t('admin.system.notificationTemplate.category_options.audit'), value: 'audit' },
  ];
}

function getPriorityOptions() {
  return [
    { label: $t('admin.system.notificationTemplate.priority_options.low'), value: 'low' },
    { label: $t('admin.system.notificationTemplate.priority_options.normal'), value: 'normal' },
    { label: $t('admin.system.notificationTemplate.priority_options.high'), value: 'high' },
    { label: $t('admin.system.notificationTemplate.priority_options.urgent'), value: 'urgent' },
  ];
}

export function getCategoryColor(category: string): string {
  switch (category) {
    case 'system': return 'blue';
    case 'ai': return 'purple';
    case 'task': return 'green';
    case 'biz': return 'orange';
    case 'audit': return 'red';
    default: return 'default';
  }
}

export function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'low': return 'default';
    case 'normal': return 'blue';
    case 'high': return 'orange';
    case 'urgent': return 'red';
    default: return 'default';
  }
}

export function getChannelLabel(channel: string): string {
  switch (channel) {
    case 'ws': return $t('admin.system.notificationTemplate.channelWs');
    case 'inbox': return $t('admin.system.notificationTemplate.channelInbox');
    case 'email': return $t('admin.system.notificationTemplate.channelEmail');
    case 'webhook': return $t('admin.system.notificationTemplate.channelWebhook');
    default: return channel;
  }
}

export function getChannelColor(channel: string): string {
  switch (channel) {
    case 'ws': return 'green';
    case 'inbox': return 'blue';
    case 'email': return 'orange';
    case 'webhook': return 'purple';
    default: return 'default';
  }
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
      field: 'title_template',
      title: $t('admin.system.notificationTemplate.titleTemplate'),
      minWidth: 200,
      slots: { default: 'title_cell' },
    },
    {
      field: 'body_template',
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
      field: 'is_system',
      title: $t('admin.system.notificationTemplate.isSystem'),
      width: 100,
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
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 140,
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    select('filter[category][eq]', $t('admin.system.notificationTemplate.category'), {
      options: getCategoryOptions(),
      placeholder: $t('admin.system.notificationTemplate.placeholder.allCategories'),
    }),
    select('filter[priority][eq]', $t('admin.system.notificationTemplate.priority'), {
      options: getPriorityOptions(),
      placeholder: $t('admin.system.notificationTemplate.placeholder.allPriorities'),
    }),
  ];
}

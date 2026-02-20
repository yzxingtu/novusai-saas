/**
 * 邮件日志管理 - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { EmailLogInfo } from '#/api/admin/email-log';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

/**
 * 获取状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'sent': return 'success';
    case 'failed': return 'error';
    case 'pending': return 'processing';
    default: return 'default';
  }
}

/**
 * 获取触发来源颜色
 */
export function getTriggerColor(trigger: string | undefined): string {
  switch (trigger) {
    case 'manual': return 'blue';
    case 'task_failure': return 'red';
    case 'password_reset': return 'orange';
    case 'test': return 'cyan';
    case 'welcome': return 'green';
    case 'ssl_expiry': return 'purple';
    default: return 'default';
  }
}

/**
 * 状态选项
 */
function getStatusOptions() {
  return [
    { label: $t('admin.system.emailLog.status.sent'), value: 'sent' },
    { label: $t('admin.system.emailLog.status.failed'), value: 'failed' },
    { label: $t('admin.system.emailLog.status.pending'), value: 'pending' },
  ];
}

/**
 * 触发来源选项
 */
function getTriggerOptions() {
  return [
    { label: $t('admin.system.emailLog.trigger.manual'), value: 'manual' },
    { label: $t('admin.system.emailLog.trigger.taskFailure'), value: 'task_failure' },
    { label: $t('admin.system.emailLog.trigger.passwordReset'), value: 'password_reset' },
    { label: $t('admin.system.emailLog.trigger.test'), value: 'test' },
    { label: $t('admin.system.emailLog.trigger.welcome'), value: 'welcome' },
    { label: $t('admin.system.emailLog.trigger.sslExpiry'), value: 'ssl_expiry' },
  ];
}

/**
 * 表格列定义
 */
export function useColumns<T = EmailLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'toAddress',
      title: $t('admin.system.emailLog.toAddress'),
      minWidth: 200,
      slots: { default: 'toAddress_cell' },
    },
    {
      field: 'subject',
      title: $t('admin.system.emailLog.subject'),
      minWidth: 200,
      slots: { default: 'subject_cell' },
    },
    {
      field: 'status',
      title: $t('admin.system.emailLog.statusLabel'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'triggeredBy',
      title: $t('admin.system.emailLog.triggeredBy'),
      width: 120,
      align: 'center',
      slots: { default: 'trigger_cell' },
    },
    {
      field: 'errorMessage',
      title: $t('admin.system.emailLog.errorMessage'),
      minWidth: 180,
      slots: { default: 'error_cell' },
    },
    {
      field: 'createdAt',
      title: $t('admin.system.emailLog.createdAt'),
      width: 160,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'email_log',
          nameField: 'subject',
          nameTitle: $t('admin.system.emailLog.subject'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['delete'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 80,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('to_address', $t('admin.system.emailLog.toAddress'), {
      placeholder: $t('admin.system.emailLog.placeholder.searchTo'),
    }),
    searchInput('subject', $t('admin.system.emailLog.subject'), {
      placeholder: $t('admin.system.emailLog.placeholder.searchSubject'),
    }),
    select('filter[status][eq]', $t('admin.system.emailLog.statusLabel'), {
      options: getStatusOptions(),
      placeholder: $t('admin.system.emailLog.placeholder.allStatus'),
    }),
    select('filter[triggered_by][eq]', $t('admin.system.emailLog.triggeredBy'), {
      options: getTriggerOptions(),
      placeholder: $t('admin.system.emailLog.placeholder.allTrigger'),
    }),
  ];
}

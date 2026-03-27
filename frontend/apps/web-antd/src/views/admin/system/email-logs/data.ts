/**
 * 邮件日志管理 - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { EmailLogInfo } from '#/api/admin/email-log';

import { $te } from '@vben/locales';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

const LEGACY_AI_TRIGGERS = new Set([
  'ai_tool',
  'quota_exhausted',
  'quota_warning',
]);
const LEGACY_SYSTEM_TRIGGERS = new Set([
  'notification',
  'password_reset',
  'security_alert',
  'ssl_expiry',
  'task_failure',
  'tenant_welcome',
  'welcome',
]);

const EMAIL_TRIGGER_VALUES = [
  'manual',
  'test',
  'notification',
  'ai_tool',
  'password_reset',
  'security_alert',
  'tenant_welcome',
  'task_failure',
  'ssl_expiry',
  'system.announcement',
  'system.maintenance',
  'system.security_alert',
  'system.password_reset',
  'system.tenant_welcome',
  'system.task_failure',
  'system.ssl_expiry',
  'ai.batch_progress',
  'ai.batch_complete',
  'ai.batch_failed',
  'ai.kb_index_complete',
  'ai.kb_index_failed',
  'ai.soft_quota_exceeded',
  'ai.quota_warning',
  'ai.quota_exhausted',
  'task.failed',
  'biz.tenant_expired',
  'biz.plugin_installed',
  'biz.plugin_enabled',
  'biz.plugin_disabled',
  'biz.plugin_uninstalled',
  'biz.user_registration_pending',
  'biz.user_approved',
  'biz.user_rejected',
  'audit.suspicious_login',
  'audit.permission_changed',
  'audit.role_changed',
  'audit.account_locked',
] as const;

function humanizeTriggerSegment(segment: string): string {
  return segment
    .replaceAll('_', ' ')
    .replaceAll(/\b\w/g, (char) => char.toUpperCase());
}

function formatTriggerFallback(trigger: string): string {
  return trigger
    .split('.')
    .map((segment) => humanizeTriggerSegment(segment))
    .join(' / ');
}

export function getTriggerLabel(trigger: string | undefined): string {
  if (!trigger) return '-';
  const key = `admin.system.emailLog.trigger.${trigger}`;
  return $te(key) ? $t(key) : formatTriggerFallback(trigger);
}

/**
 * 获取状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'pending': {
      return 'processing';
    }
    case 'sent': {
      return 'success';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 获取触发来源颜色
 */
export function getTriggerColor(trigger: string | undefined): string {
  if (!trigger) return 'default';
  if (trigger === 'manual') return 'blue';
  if (trigger === 'test') return 'cyan';
  if (LEGACY_AI_TRIGGERS.has(trigger)) return 'purple';
  if (LEGACY_SYSTEM_TRIGGERS.has(trigger)) return 'orange';
  const category = trigger.split('.')[0];
  switch (category) {
    case 'ai': {
      return 'purple';
    }
    case 'audit': {
      return 'volcano';
    }
    case 'biz': {
      return 'green';
    }
    case 'system': {
      return 'orange';
    }
    case 'task': {
      return 'red';
    }
    default: {
      return 'default';
    }
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
  return EMAIL_TRIGGER_VALUES.map((value) => ({
    label: getTriggerLabel(value),
    value,
  }));
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
        options: ['detail', 'delete'],
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
    select(
      'filter[triggered_by][eq]',
      $t('admin.system.emailLog.triggeredBy'),
      {
        options: getTriggerOptions(),
        placeholder: $t('admin.system.emailLog.placeholder.allTrigger'),
      },
    ),
  ];
}

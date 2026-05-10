/**
 * 定时任务治理页配置
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
import { getAdminScopeOptions, getScopeText } from '#/utils/scope-helpers';

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

function getScopeOptions() {
  return getAdminScopeOptions();
}

export function normalizeScopeValue(
  scope: null | string | undefined,
): null | string {
  if (scope === 'platform' || scope === 'platform_only') {
    return 'admin_only';
  }
  return scope ?? null;
}

function getDefinitionTypeOptions() {
  return [
    {
      label: $t('admin.system.periodicTask.definitionType.system'),
      value: 'system',
    },
    {
      label: $t('admin.system.periodicTask.definitionType.plugin'),
      value: 'plugin',
    },
  ];
}

function getEnabledOptions() {
  return [
    {
      label: $t('admin.system.periodicTask.status.enabled'),
      value: 'true',
    },
    {
      label: $t('admin.system.periodicTask.status.disabled'),
      value: 'false',
    },
  ];
}

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

export function formatInterval(seconds: null | number | undefined): string {
  if (!seconds) return '-';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86_400)}d`;
}

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

export function getScheduleDisplay(row: PeriodicTaskInfo): string {
  if (row.scheduleType === 'cron') {
    return formatCronHuman(row.cronExpression);
  }
  return formatInterval(row.intervalSeconds);
}

function getScheduleTypeOptions() {
  return [
    { label: $t('admin.system.periodicTask.scheduleType.cron'), value: 'cron' },
    {
      label: $t('admin.system.periodicTask.scheduleType.interval'),
      value: 'interval',
    },
  ];
}

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
  return 'lucide:clock-3';
}

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

export function isTenantDistributed(scope: null | string | undefined): boolean {
  const normalizedScope = normalizeScopeValue(scope);
  return (
    normalizedScope === 'all_tenants' ||
    normalizedScope === 'selected_tenants' ||
    normalizedScope === 'admin_and_selected_tenants'
  );
}

export function requiresTenantBindings(
  scope: null | string | undefined,
): boolean {
  const normalizedScope = normalizeScopeValue(scope);
  return (
    normalizedScope === 'selected_tenants' ||
    normalizedScope === 'admin_and_selected_tenants'
  );
}

export function scopeNeedsExplicitBindings(
  scope: null | string | undefined,
): boolean {
  return requiresTenantBindings(scope);
}

export function getDefinitionTypeText(
  definitionType: null | string | undefined,
): string {
  if (definitionType === 'plugin') {
    return $t('admin.system.periodicTask.definitionType.plugin');
  }
  return $t('admin.system.periodicTask.definitionType.system');
}

export function getGovernanceSummary(scope: null | string | undefined): string {
  switch (normalizeScopeValue(scope)) {
    case 'admin_and_selected_tenants': {
      return $t(
        'admin.system.periodicTask.scopeSemantics.adminAndSelectedGovernance',
      );
    }
    case 'admin_only': {
      return $t('admin.system.periodicTask.scopeSemantics.adminOnlyGovernance');
    }
    case 'all_tenants': {
      return $t(
        'admin.system.periodicTask.scopeSemantics.allTenantsGovernance',
      );
    }
    case 'global_shared': {
      return $t(
        'admin.system.periodicTask.scopeSemantics.globalSharedGovernance',
      );
    }
    case 'selected_tenants': {
      return $t(
        'admin.system.periodicTask.scopeSemantics.selectedTenantsGovernance',
      );
    }
    default: {
      return '-';
    }
  }
}

export function getExecutionSummary(row: PeriodicTaskInfo): string {
  const scope = normalizeScopeValue(row.scope);
  if (scope === 'all_tenants') {
    return $t('admin.system.periodicTask.executionSemantics.allTenants');
  }
  if (scope === 'selected_tenants') {
    return $t('admin.system.periodicTask.executionSemantics.selectedTenants', {
      count: row.bindingCount,
    });
  }
  if (scope === 'admin_and_selected_tenants') {
    return $t(
      'admin.system.periodicTask.executionSemantics.adminAndSelectedTenants',
      {
        count: row.bindingCount,
      },
    );
  }
  if (scope === 'global_shared') {
    return $t('admin.system.periodicTask.executionSemantics.globalShared');
  }
  return $t('admin.system.periodicTask.executionSemantics.platformOnly');
}

export function getBindingSummary(row: PeriodicTaskInfo): string {
  const scope = normalizeScopeValue(row.scope);
  if (!requiresTenantBindings(scope)) {
    if (scope === 'global_shared') {
      return $t('admin.system.periodicTask.bindingSummary.globalShared');
    }
    if (scope === 'all_tenants') {
      return $t('admin.system.periodicTask.bindingSummary.allTenants');
    }
    return $t('admin.system.periodicTask.bindingSummary.adminOnly');
  }
  if (row.bindingSummary) {
    return row.bindingSummary;
  }
  return buildBindingSummary(scope, row.bindingCount, row.assignedTenantNames);
}

export function getDistributionCompactText(row: PeriodicTaskInfo): string {
  const scope = normalizeScopeValue(row.scope);
  if (scope === 'global_shared') {
    return $t('admin.system.periodicTask.bindingSummary.globalShared');
  }
  if (scope === 'all_tenants') {
    return $t('admin.system.periodicTask.bindingSummary.allTenants');
  }
  if (scope === 'selected_tenants' || scope === 'admin_and_selected_tenants') {
    if (row.bindingCount > 0) {
      return $t('admin.system.periodicTask.bindingSummary.selectedCount', {
        count: row.bindingCount,
      });
    }
    return $t('admin.system.periodicTask.bindingSummary.pending');
  }
  return $t('admin.system.periodicTask.bindingSummary.adminOnly');
}

export function getDistributionStatusText(row: PeriodicTaskInfo): string {
  if (row.bindingRequired && !row.bindingConfigured) {
    return $t('admin.system.periodicTask.bindingSummary.pending');
  }
  if (row.bindingCount > 0) {
    return $t('admin.system.periodicTask.bindingSummary.selectedCount', {
      count: row.bindingCount,
    });
  }
  return '';
}

export function buildBindingSummary(
  scope: null | string | undefined,
  bindingCount: number,
  tenantNames: string[],
): string {
  if (scope === 'global_shared') {
    return $t('admin.system.periodicTask.bindingSummary.globalShared');
  }
  if (scope === 'all_tenants') {
    return $t('admin.system.periodicTask.bindingSummary.allTenants');
  }
  if (!requiresTenantBindings(scope)) {
    return $t('admin.system.periodicTask.bindingSummary.adminOnly');
  }
  if (bindingCount <= 0) {
    return $t('admin.system.periodicTask.bindingSummary.pending');
  }
  if (tenantNames.length <= 3) {
    return $t('admin.system.periodicTask.bindingSummary.selectedCount', {
      count: bindingCount,
    });
  }
  return $t('admin.system.periodicTask.bindingSummary.selectedPreview', {
    count: bindingCount,
    names: tenantNames.slice(0, 3).join(' / '),
  });
}

export function getDistributionHeadline(
  scope: null | string | undefined,
): string {
  switch (scope) {
    case 'admin_and_selected_tenants': {
      return $t('admin.system.periodicTask.scopeGuide.adminAndSelectedTenants');
    }
    case 'all_tenants': {
      return $t('admin.system.periodicTask.scopeGuide.allTenants');
    }
    case 'global_shared': {
      return $t('admin.system.periodicTask.scopeGuide.globalShared');
    }
    case 'selected_tenants': {
      return $t('admin.system.periodicTask.scopeGuide.selectedTenants');
    }
    default: {
      return $t('admin.system.periodicTask.scopeGuide.adminOnly');
    }
  }
}

export function getAdminSurfaceSummary(
  scope: null | string | undefined,
): string {
  switch (scope) {
    case 'all_tenants': {
      return $t('admin.system.periodicTask.adminSurface.allTenants');
    }
    case 'selected_tenants': {
      return $t('admin.system.periodicTask.adminSurface.selectedTenants');
    }
    default: {
      return $t('admin.system.periodicTask.adminSurface.platform');
    }
  }
}

export function getTenantSurfaceSummary(
  scope: null | string | undefined,
  bindingCount: number,
): string {
  switch (scope) {
    case 'admin_and_selected_tenants': {
      return $t(
        'admin.system.periodicTask.tenantSurface.adminAndSelectedTenants',
        {
          count: bindingCount,
        },
      );
    }
    case 'all_tenants': {
      return $t('admin.system.periodicTask.tenantSurface.allTenants');
    }
    case 'global_shared': {
      return $t('admin.system.periodicTask.tenantSurface.globalShared');
    }
    case 'selected_tenants': {
      return $t('admin.system.periodicTask.tenantSurface.selectedTenants', {
        count: bindingCount,
      });
    }
    default: {
      return $t('admin.system.periodicTask.tenantSurface.none');
    }
  }
}

export function isPlatformOnlyTask(
  row: Pick<PeriodicTaskInfo, 'scope'>,
): boolean {
  return normalizeScopeValue(row.scope) === 'admin_only';
}

export function useColumns<T = PeriodicTaskInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      align: 'left',
      field: 'name',
      title: $t('admin.system.periodicTask.name'),
      minWidth: 320,
      slots: { default: 'name_cell' },
    },
    {
      align: 'left',
      field: 'distribution',
      title: $t('admin.system.periodicTask.distributionLabel'),
      width: 220,
      slots: { default: 'distribution_cell' },
    },
    {
      align: 'left',
      field: 'schedule',
      title: $t('admin.system.periodicTask.schedule'),
      width: 140,
      slots: { default: 'schedule_cell' },
    },
    {
      field: 'isActive',
      title: $t('admin.system.periodicTask.isActive'),
      width: 88,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'left',
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
          {
            code: 'edit',
            text: $t('common.edit'),
            accessCodes: ['periodic_task:update'],
            icon: 'lucide:pen-line',
            show: (row: Record<string, unknown>) => row.isEditable !== false,
          },
          {
            code: 'trigger',
            text: $t('admin.system.periodicTask.trigger'),
            icon: 'lucide:play',
            accessCodes: ['periodic_task:trigger'],
            disabled: (row: Record<string, unknown>) =>
              row.definitionType === 'plugin' && row.pluginEnabled === false,
          },
          {
            code: 'logs',
            text: $t('admin.system.periodicTask.viewLogs'),
            icon: 'lucide:scroll-text',
            accessCodes: ['task_log:list'],
          },
          {
            code: 'bindings',
            text: $t('admin.system.periodicTask.manageBindings'),
            icon: 'lucide:building-2',
            accessCodes: ['periodic_task:bindings'],
            show: (row: Record<string, unknown>) =>
              !isPlatformOnlyTask({
                scope:
                  typeof row.scope === 'string' || row.scope === null
                    ? row.scope
                    : null,
              }),
          },
          {
            code: 'delete',
            text: $t('common.delete'),
            icon: 'lucide:trash-2',
            accessCodes: ['periodic_task:delete'],
            show: (row: Record<string, unknown>) => row.isLocked !== true,
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
    searchInput('name', $t('admin.system.periodicTask.name'), {
      placeholder: $t('admin.system.periodicTask.placeholder.searchName'),
    }),
    select(
      'filter[definition_type][eq]',
      $t('admin.system.periodicTask.definitionType.label'),
      {
        options: getDefinitionTypeOptions(),
        placeholder: $t(
          'admin.system.periodicTask.placeholder.allDefinitionTypes',
        ),
      },
    ),
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
    select(
      'filter[is_enabled][eq]',
      $t('admin.system.periodicTask.status.label'),
      {
        options: getEnabledOptions(),
        placeholder: $t('admin.system.periodicTask.placeholder.allStatus'),
      },
    ),
  ];
}

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
    textareaField('description', $t('admin.system.periodicTask.description'), {
      placeholder: $t('admin.system.periodicTask.placeholder.inputDescription'),
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

    dividerField(
      'scope_divider',
      $t('admin.system.periodicTask.section.scope'),
    ),
    ...useScopeFields({
      allowedScopes: [
        'global_shared',
        'admin_only',
        'all_tenants',
        'admin_and_selected_tenants',
        'selected_tenants',
      ],
      scopeDefaultValue: 'admin_only',
      scopeHelp: $t('admin.system.periodicTask.scopeHelp'),
      showTenantId: false,
      tenantIdsRequired: false,
      tenantIdsField: 'tenant_ids',
    }),

    dividerField(
      'queue_divider',
      $t('admin.system.periodicTask.section.queue'),
    ),
    numberField(
      'default_priority',
      $t('admin.system.periodicTask.defaultPriority'),
      {
        min: 0,
        max: 9,
        precision: 0,
        placeholder: $t('admin.system.periodicTask.placeholder.inputPriority'),
      },
    ),
    inputField(
      'required_feature_codes',
      $t('admin.system.periodicTask.requiredFeatureCodes'),
      {
        placeholder: $t(
          'admin.system.periodicTask.placeholder.inputRequiredFeatureCodes',
        ),
      },
    ),
    inputField(
      'required_plugin_names',
      $t('admin.system.periodicTask.requiredPluginNames'),
      {
        placeholder: $t(
          'admin.system.periodicTask.placeholder.inputRequiredPluginNames',
        ),
      },
    ),

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

export function getFormDefaults(): Record<string, unknown> {
  return {
    schedule_type: 'interval',
    interval_seconds: 60,
    is_active: true,
    scope: 'admin_only',
    tenant_ids: [],
    default_priority: null,
    required_feature_codes: '',
    required_plugin_names: '',
    max_retries: 0,
    retry_delay: 60,
    timeout: 3600,
    notify_on_failure: false,
  };
}

export function getScopeModeLabel(scope: null | string | undefined): string {
  return getScopeText(normalizeScopeValue(scope) ?? undefined);
}

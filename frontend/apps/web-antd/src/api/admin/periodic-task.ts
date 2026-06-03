/**
 * Periodic task API / 定时任务 API
 * Backend: /admin/periodic-tasks/*
 */
import type {
  PeriodicTaskFormData,
  PeriodicTaskInfo,
  PeriodicTaskListParams,
  PeriodicTaskListResponse,
} from '#/api/shared/periodic-task-types';
import type { ApiRequestOptions } from '#/utils/request';

import { $t, $te } from '#/locales';
import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions (imported from shared) / 类型定义（从 shared 导入）
// ============================================================

export type {
  PeriodicTaskFormData,
  PeriodicTaskInfo,
  PeriodicTaskListParams,
  PeriodicTaskListResponse,
} from '#/api/shared/periodic-task-types';

/** Periodic task info (backend raw snake_case) / 定时任务信息（后端原始） */
export interface PeriodicTaskInfoRaw {
  id: number;
  name: string;
  task_path: string;
  definition_type?: string;
  schedule_type: string;
  cron_expression: null | string;
  interval_seconds: null | number;
  is_active: boolean;
  last_run_at: null | string;
  next_run_at: null | string;
  description: null | string;
  plugin_enabled?: boolean;
  plugin_name?: null | string;
  created_at: string;
  scope: null | string;
  owner_tenant_id: null | number;
  assigned_tenant_ids?: number[];
  assigned_tenant_names?: string[];
  binding_count?: number;
  binding_required?: boolean;
  binding_configured?: boolean;
  tenant_access_mode?: string;
  binding_summary?: null | string;
  is_locked: boolean;
  is_editable: boolean;
  default_priority?: null | number;
  required_feature_codes?: string[];
  required_plugin_names?: string[];
  max_retries: number;
  retry_delay: number;
  timeout: null | number;
  notify_on_failure: boolean;
  notify_emails: null | string;
}

export interface PeriodicTaskBindingInfo {
  id: number;
  tenantId: number;
  tenantName: null | string;
  isEnabled: boolean;
  disabledReason: null | string;
  scheduleTypeOverride: null | string;
  cronExpressionOverride: null | string;
  intervalSecondsOverride: null | number;
  kwargsOverride: null | Record<string, unknown>;
  configOverride: null | Record<string, unknown>;
  effectiveScheduleType: null | string;
  effectiveCronExpression: null | string;
  effectiveIntervalSeconds: null | number;
  lastRunAt: null | string;
  nextRunAt: null | string;
}

export interface PeriodicTaskBindingInfoRaw {
  id: number;
  tenant_id: number;
  tenant_name?: null | string;
  is_enabled?: boolean;
  disabled_reason?: null | string;
  schedule_type_override?: null | string;
  cron_expression_override?: null | string;
  interval_seconds_override?: null | number;
  kwargs_override?: null | Record<string, unknown>;
  config_override?: null | Record<string, unknown>;
  effective_schedule_type?: null | string;
  effective_cron_expression?: null | string;
  effective_interval_seconds?: null | number;
  last_run_at?: null | string;
  next_run_at?: null | string;
}

export interface PeriodicTaskBindingUpdatePayload {
  isEnabled?: boolean;
  disabledReason?: null | string;
  scheduleTypeOverride?: null | string;
  cronExpressionOverride?: null | string;
  intervalSecondsOverride?: null | number;
  kwargsOverride?: null | Record<string, unknown>;
  configOverride?: null | Record<string, unknown>;
}

export interface PeriodicTaskBindingSyncItemPayload extends PeriodicTaskBindingUpdatePayload {
  tenantId: number;
}

export interface PeriodicTaskBindingSyncPayload {
  bindings?: PeriodicTaskBindingSyncItemPayload[];
  scope?: null | string;
  tenant_ids?: number[];
}

function getTaskLeafCandidates(raw: PeriodicTaskInfoRaw): string[] {
  const candidates = [raw.task_path, raw.name]
    .filter(Boolean)
    .flatMap((value) => {
      const trimmed = value.trim();
      const leaf = trimmed.split('.').at(-1) || trimmed;
      return [trimmed, leaf];
    });

  return [...new Set(candidates)];
}

function translateSystemTaskName(raw: PeriodicTaskInfoRaw): string {
  if (raw.definition_type === 'plugin') {
    return raw.name;
  }

  for (const candidate of getTaskLeafCandidates(raw)) {
    const key = `admin.system.taskLog.taskNames.${candidate}`;
    if ($te(key)) {
      return $t(key);
    }
  }

  return raw.name;
}

function translateSystemTaskDescription(
  raw: PeriodicTaskInfoRaw,
): null | string {
  if (raw.definition_type === 'plugin' || !raw.description) {
    return raw.description;
  }

  for (const candidate of getTaskLeafCandidates(raw)) {
    const key = `admin.system.periodicTask.taskDescriptions.${candidate}`;
    if ($te(key)) {
      return $t(key);
    }
  }

  return raw.description;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

function transformPeriodicTaskInfo(raw: PeriodicTaskInfoRaw): PeriodicTaskInfo {
  return {
    id: raw.id,
    name: translateSystemTaskName(raw),
    taskPath: raw.task_path,
    definitionType: raw.definition_type ?? 'system',
    scheduleType: raw.schedule_type,
    cronExpression: raw.cron_expression,
    intervalSeconds: raw.interval_seconds,
    isActive: raw.is_active,
    lastRunAt: raw.last_run_at,
    nextRunAt: raw.next_run_at,
    description: translateSystemTaskDescription(raw),
    pluginEnabled: raw.plugin_enabled ?? true,
    pluginName: raw.plugin_name ?? null,
    createdAt: raw.created_at,
    scope: raw.scope,
    tenantId: raw.owner_tenant_id,
    assignedTenantIds: raw.assigned_tenant_ids ?? [],
    assignedTenantNames: raw.assigned_tenant_names ?? [],
    bindingCount: raw.binding_count ?? 0,
    bindingRequired: raw.binding_required ?? false,
    bindingConfigured: raw.binding_configured ?? true,
    tenantAccessMode: raw.tenant_access_mode ?? 'none',
    bindingSummary: raw.binding_summary ?? null,
    isLocked: raw.is_locked,
    isEditable: raw.is_editable,
    defaultPriority: raw.default_priority ?? null,
    requiredFeatureCodes: raw.required_feature_codes ?? [],
    requiredPluginNames: raw.required_plugin_names ?? [],
    maxRetries: raw.max_retries,
    retryDelay: raw.retry_delay,
    timeout: raw.timeout,
    notifyOnFailure: raw.notify_on_failure,
    notifyEmails: raw.notify_emails,
  };
}

function transformPeriodicTaskBindingInfo(
  raw: PeriodicTaskBindingInfoRaw,
): PeriodicTaskBindingInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    tenantName: raw.tenant_name ?? null,
    isEnabled: raw.is_enabled ?? true,
    disabledReason: raw.disabled_reason ?? null,
    scheduleTypeOverride: raw.schedule_type_override ?? null,
    cronExpressionOverride: raw.cron_expression_override ?? null,
    intervalSecondsOverride: raw.interval_seconds_override ?? null,
    kwargsOverride: raw.kwargs_override ?? null,
    configOverride: raw.config_override ?? null,
    effectiveScheduleType: raw.effective_schedule_type ?? null,
    effectiveCronExpression: raw.effective_cron_expression ?? null,
    effectiveIntervalSeconds: raw.effective_interval_seconds ?? null,
    lastRunAt: raw.last_run_at ?? null,
    nextRunAt: raw.next_run_at ?? null,
  };
}

function compactPayload<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined),
  ) as T;
}

function toBindingRawPayload(payload: PeriodicTaskBindingUpdatePayload) {
  return compactPayload({
    is_enabled: payload.isEnabled,
    disabled_reason: payload.disabledReason,
    schedule_type_override: payload.scheduleTypeOverride,
    cron_expression_override: payload.cronExpressionOverride,
    interval_seconds_override: payload.intervalSecondsOverride,
    kwargs_override: payload.kwargsOverride,
    config_override: payload.configOverride,
  });
}

function toBindingSyncRawPayload(payload: PeriodicTaskBindingSyncItemPayload) {
  return {
    tenant_id: payload.tenantId,
    ...toBindingRawPayload(payload),
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/admin/periodic-tasks';

/**
 * Get periodic task list / 获取定时任务列表
 * GET /admin/periodic-tasks
 */
export async function getPeriodicTaskListApi(
  params?: PeriodicTaskListParams,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskListResponse> {
  const response = await requestClient.get<{
    items: PeriodicTaskInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformPeriodicTaskInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get periodic task detail / 获取定时任务详情
 * GET /admin/periodic-tasks/{id}
 */
export async function getPeriodicTaskDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.get<PeriodicTaskInfoRaw>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

/**
 * Create periodic task / 创建定时任务
 * POST /admin/periodic-tasks
 */
export async function createPeriodicTaskApi(
  data: PeriodicTaskFormData,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.post<PeriodicTaskInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

/**
 * Update periodic task / 更新定时任务
 * PUT /admin/periodic-tasks/{id}
 */
export async function updatePeriodicTaskApi(
  id: number,
  data: Partial<PeriodicTaskFormData>,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.put<PeriodicTaskInfoRaw>(
    `${API_PREFIX}/${id}`,
    data,
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

/**
 * Delete periodic task / 删除定时任务
 * DELETE /admin/periodic-tasks/{id}
 */
export async function deletePeriodicTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${id}`, options);
}

/**
 * Enable/disable periodic task / 启用/禁用定时任务
 * POST /admin/periodic-tasks/{id}/toggle
 */
export async function togglePeriodicTaskApi(
  id: number,
  isActive: boolean,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.post<PeriodicTaskInfoRaw>(
    `${API_PREFIX}/${id}/toggle`,
    { is_active: isActive },
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

/**
 * Manually trigger periodic task / 手动触发定时任务
 * POST /admin/periodic-tasks/{id}/trigger
 */
export async function triggerPeriodicTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<{ triggeredTaskId: string }> {
  const raw = await requestClient.post<{ triggered_task_id: string }>(
    `${API_PREFIX}/${id}/trigger`,
    {},
    options,
  );
  return { triggeredTaskId: raw.triggered_task_id };
}

/**
 * Get periodic task tenant bindings / 获取定时任务企业绑定
 * GET /admin/periodic-tasks/{id}/bindings
 */
export async function getPeriodicTaskBindingsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskBindingInfo[]> {
  const response = await requestClient.get<PeriodicTaskBindingInfoRaw[]>(
    `${API_PREFIX}/${id}/bindings`,
    options,
  );
  return response.map((item) => transformPeriodicTaskBindingInfo(item));
}

/**
 * Sync periodic task tenant bindings / 同步定时任务企业绑定
 * PUT /admin/periodic-tasks/{id}/bindings
 */
export async function syncPeriodicTaskBindingsApi(
  id: number,
  payload: PeriodicTaskBindingSyncPayload,
  options?: ApiRequestOptions,
): Promise<{ added: number; reenabled: number; removed: number }> {
  const body = compactPayload({
    scope: payload.scope,
    tenant_ids: payload.tenant_ids ?? [],
    bindings: payload.bindings?.map((item) => toBindingSyncRawPayload(item)),
  });
  return await requestClient.put<{
    added: number;
    reenabled: number;
    removed: number;
  }>(`${API_PREFIX}/${id}/bindings`, body, options);
}

/**
 * Update one tenant binding / 更新单个企业绑定
 * PATCH /admin/periodic-tasks/{id}/bindings/{tenant_id}
 */
export async function updatePeriodicTaskBindingApi(
  id: number,
  tenantId: number,
  payload: PeriodicTaskBindingUpdatePayload,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskBindingInfo> {
  const raw = await requestClient.patch<PeriodicTaskBindingInfoRaw>(
    `${API_PREFIX}/${id}/bindings/${tenantId}`,
    toBindingRawPayload(payload),
    options,
  );
  return transformPeriodicTaskBindingInfo(raw);
}

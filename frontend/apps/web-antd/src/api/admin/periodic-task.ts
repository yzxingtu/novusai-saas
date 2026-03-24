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
  schedule_type: string;
  cron_expression: null | string;
  interval_seconds: null | number;
  is_active: boolean;
  last_run_at: null | string;
  next_run_at: null | string;
  description: null | string;
  created_at: string;
  scope: null | string;
  owner_tenant_id: null | number;
  is_locked: boolean;
  is_editable: boolean;
  max_retries: number;
  retry_delay: number;
  timeout: null | number;
  notify_on_failure: boolean;
  notify_emails: null | string;
}

export interface PeriodicTaskBindingInfo {
  id: number;
  tenant_id: number;
  tenant_name: null | string;
  is_enabled: boolean;
  schedule_type_override: null | string;
  cron_expression_override: null | string;
  interval_seconds_override: null | number;
  last_run_at: null | string;
  next_run_at: null | string;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

function transformPeriodicTaskInfo(raw: PeriodicTaskInfoRaw): PeriodicTaskInfo {
  return {
    id: raw.id,
    name: raw.name,
    taskPath: raw.task_path,
    scheduleType: raw.schedule_type,
    cronExpression: raw.cron_expression,
    intervalSeconds: raw.interval_seconds,
    isActive: raw.is_active,
    lastRunAt: raw.last_run_at,
    nextRunAt: raw.next_run_at,
    description: raw.description,
    createdAt: raw.created_at,
    scope: raw.scope,
    tenantId: raw.owner_tenant_id,
    isLocked: raw.is_locked,
    isEditable: raw.is_editable,
    maxRetries: raw.max_retries,
    retryDelay: raw.retry_delay,
    timeout: raw.timeout,
    notifyOnFailure: raw.notify_on_failure,
    notifyEmails: raw.notify_emails,
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
  return await requestClient.get<PeriodicTaskBindingInfo[]>(
    `${API_PREFIX}/${id}/bindings`,
    options,
  );
}

/**
 * Sync periodic task tenant bindings / 同步定时任务企业绑定
 * PUT /admin/periodic-tasks/{id}/bindings
 */
export async function syncPeriodicTaskBindingsApi(
  id: number,
  tenantIds: number[],
  options?: ApiRequestOptions,
): Promise<{ added: number; removed: number; reenabled: number }> {
  return await requestClient.put<{
    added: number;
    removed: number;
    reenabled: number;
  }>(
    `${API_PREFIX}/${id}/bindings`,
    { tenant_ids: tenantIds },
    options,
  );
}

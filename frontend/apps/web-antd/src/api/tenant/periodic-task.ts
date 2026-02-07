/**
 * 定时任务 API（租户端）
 * 对接后端 /tenant/periodic-tasks/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义（复用 admin 端类型）
// ============================================================

export type {
  PeriodicTaskFormData,
  PeriodicTaskInfo,
  PeriodicTaskListParams,
  PeriodicTaskListResponse,
} from '#/api/admin/periodic-task';

/** 后端原始格式（内部使用） */
interface PeriodicTaskInfoRaw {
  id: number;
  name: string;
  task_path: string;
  schedule_type: string;
  cron_expression: string | null;
  interval_seconds: number | null;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  description: string | null;
  created_at: string;
  scope: string | null;
  tenant_id: number | null;
  is_locked: boolean;
  is_editable: boolean;
  max_retries: number;
  retry_delay: number;
  timeout: number | null;
  notify_on_failure: boolean;
  notify_emails: string | null;
}

// ============================================================
// 转换函数
// ============================================================

import type { PeriodicTaskInfo } from '#/api/admin/periodic-task';

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
    tenantId: raw.tenant_id,
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
// API 接口
// ============================================================

const API_PREFIX = '/tenant/periodic-tasks';

export async function getPeriodicTaskListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
) {
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

export async function createPeriodicTaskApi(
  data: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.post<PeriodicTaskInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

export async function updatePeriodicTaskApi(
  id: number,
  data: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PeriodicTaskInfo> {
  const raw = await requestClient.put<PeriodicTaskInfoRaw>(
    `${API_PREFIX}/${id}`,
    data,
    options,
  );
  return transformPeriodicTaskInfo(raw);
}

export async function deletePeriodicTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${id}`, options);
}

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

/**
 * 定时任务 API
 * 对接后端 /admin/periodic-tasks/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 定时任务列表查询参数 */
export type PeriodicTaskListParams = Record<string, unknown>;

/** 定时任务信息（后端原始格式 snake_case） */
export interface PeriodicTaskInfoRaw {
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

/** 定时任务信息（前端格式 camelCase） */
export interface PeriodicTaskInfo {
  id: number;
  name: string;
  taskPath: string;
  scheduleType: string;
  cronExpression: string | null;
  intervalSeconds: number | null;
  isActive: boolean;
  lastRunAt: string | null;
  nextRunAt: string | null;
  description: string | null;
  createdAt: string;
  scope: string | null;
  tenantId: number | null;
  isLocked: boolean;
  isEditable: boolean;
  maxRetries: number;
  retryDelay: number;
  timeout: number | null;
  notifyOnFailure: boolean;
  notifyEmails: string | null;
}

/** 定时任务创建/更新请求 */
export interface PeriodicTaskFormData {
  name: string;
  task_path: string;
  schedule_type: string;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  args?: Record<string, unknown> | null;
  kwargs?: Record<string, unknown> | null;
  is_active?: boolean;
  description?: string | null;
}

/** 分页列表响应 */
export interface PeriodicTaskListResponse {
  items: PeriodicTaskInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
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

const API_PREFIX = '/admin/periodic-tasks';

/**
 * 获取定时任务列表
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
 * 获取定时任务详情
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
 * 创建定时任务
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
 * 更新定时任务
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
 * 删除定时任务
 * DELETE /admin/periodic-tasks/{id}
 */
export async function deletePeriodicTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${id}`, options);
}

/**
 * 启用/禁用定时任务
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
 * 手动触发定时任务
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

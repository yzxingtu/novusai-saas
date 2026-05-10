/**
 * Task log API / 任务日志 API
 * Backend: /admin/tasks/*
 */
import type {
  TaskLogDetailInfo,
  TaskLogInfo,
  TaskLogListParams,
  TaskLogListResponse,
  TaskStatsItem,
} from '#/api/shared/task-log-types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions (imported from shared) / 类型定义（从 shared 导入）
// ============================================================

export type {
  TaskLogDetailInfo,
  TaskLogInfo,
  TaskLogListParams,
  TaskLogListResponse,
  TaskLogListView,
  TaskStatsItem,
} from '#/api/shared/task-log-types';

/** Task run info (backend raw snake_case) / 任务运行信息（后端原始格式） */
export interface TaskLogInfoRaw {
  id: number;
  task_id: string;
  run_key: null | string;
  task_name: string;
  handler_path?: null | string;
  task_definition_id?: null | number;
  binding_id?: null | number;
  task_definition_name?: null | string;
  task_scope?: null | string;
  owner_tenant_id?: null | number;
  owner_tenant_name?: null | string;
  effective_tenant_id?: null | number;
  effective_tenant_name?: null | string;
  queue: string;
  status: string;
  args?: null | Record<string, unknown> | unknown[];
  kwargs?: null | Record<string, unknown>;
  result?: null | Record<string, unknown>;
  error_message?: null | string;
  trigger_source?: null | string;
  run_kind?: null | string;
  trace_id?: null | string;
  started_at: null | string;
  finished_at: null | string;
  duration_ms: null | number;
  retry_count: number;
  created_at: string;
}

/** Task log detail raw format / 任务日志详情原始格式 */
interface TaskLogDetailInfoRaw extends TaskLogInfoRaw {
  traceback?: null | string;
}

/** Task stats item (backend raw format) / 任务统计项（后端原始格式） */
interface TaskStatsItemRaw {
  status: string;
  count: number;
  avg_duration_ms: number;
}

/** Active task (backend raw format) / 活跃任务（后端原始格式） */
interface ActiveTaskRaw {
  task_id: string;
  task_name: string;
  worker: string;
  started_at: null | number;
}

/** Active task / 活跃任务 */
export interface ActiveTaskInfo {
  taskId: string;
  taskName: string;
  worker: string;
  startedAt: null | number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

function transformTaskLogInfo(raw: TaskLogInfoRaw): TaskLogInfo {
  return {
    id: raw.id,
    taskId: raw.task_id,
    runKey: raw.run_key,
    taskName: raw.task_name,
    handlerPath: raw.handler_path ?? null,
    taskDefinitionId: raw.task_definition_id ?? null,
    bindingId: raw.binding_id ?? null,
    taskDefinitionName: raw.task_definition_name ?? null,
    taskScope: raw.task_scope ?? null,
    ownerTenantId: raw.owner_tenant_id ?? null,
    ownerTenantName: raw.owner_tenant_name ?? null,
    effectiveTenantId: raw.effective_tenant_id ?? null,
    effectiveTenantName: raw.effective_tenant_name ?? null,
    queue: raw.queue,
    status: raw.status,
    args: raw.args ?? null,
    kwargs: raw.kwargs ?? null,
    result: raw.result ?? null,
    errorMessage: raw.error_message ?? null,
    triggerSource: raw.trigger_source ?? null,
    runKind: raw.run_kind ?? null,
    traceId: raw.trace_id ?? null,
    startedAt: raw.started_at,
    finishedAt: raw.finished_at,
    durationMs: raw.duration_ms,
    retryCount: raw.retry_count,
    createdAt: raw.created_at,
  };
}

function transformTaskLogDetailInfo(
  raw: TaskLogDetailInfoRaw,
): TaskLogDetailInfo {
  return {
    ...transformTaskLogInfo(raw),
    traceback: raw.traceback ?? null,
  };
}

function transformActiveTask(raw: ActiveTaskRaw): ActiveTaskInfo {
  return {
    taskId: raw.task_id,
    taskName: raw.task_name,
    worker: raw.worker,
    startedAt: raw.started_at,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/admin/tasks';

/**
 * Get task log list / 获取任务日志列表
 * GET /admin/tasks
 */
export async function getTaskLogListApi(
  params?: TaskLogListParams,
  options?: ApiRequestOptions,
): Promise<TaskLogListResponse> {
  const response = await requestClient.get<{
    items: TaskLogInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformTaskLogInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get task log detail / 获取任务日志详情
 * GET /admin/tasks/{id}
 */
export async function getTaskLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TaskLogDetailInfo> {
  const raw = await requestClient.get<TaskLogDetailInfoRaw>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return transformTaskLogDetailInfo(raw);
}

/**
 * Get task statistics / 获取任务统计
 * GET /admin/tasks/stats
 */
export async function getTaskStatsApi(
  days: number = 7,
  options?: ApiRequestOptions,
): Promise<TaskStatsItem[]> {
  const rawList = await requestClient.get<TaskStatsItemRaw[]>(
    `${API_PREFIX}/stats`,
    { params: { days }, ...options },
  );
  return rawList.map((item) => ({
    status: item.status,
    count: item.count,
    avgDurationMs: item.avg_duration_ms,
  }));
}

/**
 * Get active tasks / 获取活跃任务
 * GET /admin/tasks/active
 */
export async function getActiveTasksApi(
  options?: ApiRequestOptions,
): Promise<ActiveTaskInfo[]> {
  const rawList = await requestClient.get<ActiveTaskRaw[]>(
    `${API_PREFIX}/active`,
    options,
  );
  return rawList.map((item) => transformActiveTask(item));
}

/**
 * Retry task / 重试任务
 * POST /admin/tasks/{id}/retry
 */
export async function retryTaskApi(
  id: number,
  queue?: string,
  options?: ApiRequestOptions,
): Promise<{ newTaskId: string }> {
  const raw = await requestClient.post<{ new_task_id: string }>(
    `${API_PREFIX}/${id}/retry`,
    queue ? { queue } : {},
    options,
  );
  return { newTaskId: raw.new_task_id };
}

/**
 * Cancel task / 取消任务
 * POST /admin/tasks/{id}/cancel
 */
export async function cancelTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(`${API_PREFIX}/${id}/cancel`, {}, options);
}

/**
 * 任务日志 API
 * 对接后端 /admin/tasks/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义（从 shared 导入）
// ============================================================

export type {
  TaskLogDetailInfo,
  TaskLogInfo,
  TaskLogListParams,
  TaskLogListResponse,
  TaskStatsItem,
} from '#/api/shared/task-log-types';

import type {
  TaskLogDetailInfo,
  TaskLogInfo,
  TaskLogListParams,
  TaskLogListResponse,
  TaskStatsItem,
} from '#/api/shared/task-log-types';

/** 任务日志信息（后端原始格式 snake_case） */
export interface TaskLogInfoRaw {
  id: number;
  task_id: string;
  task_name: string;
  queue: string;
  status: string;
  args: Record<string, unknown> | null;
  kwargs: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  retry_count: number;
  tenant_id: number | null;
  created_at: string;
}

/** 任务日志详情原始格式 */
interface TaskLogDetailInfoRaw extends TaskLogInfoRaw {
  traceback: string | null;
}

/** 任务统计项（后端原始格式） */
interface TaskStatsItemRaw {
  status: string;
  count: number;
  avg_duration_ms: number;
}

/** 活跃任务（后端原始格式） */
interface ActiveTaskRaw {
  task_id: string;
  task_name: string;
  worker: string;
  started_at: number | null;
}

/** 活跃任务 */
export interface ActiveTaskInfo {
  taskId: string;
  taskName: string;
  worker: string;
  startedAt: number | null;
}

// ============================================================
// 转换函数
// ============================================================

function transformTaskLogInfo(raw: TaskLogInfoRaw): TaskLogInfo {
  return {
    id: raw.id,
    taskId: raw.task_id,
    taskName: raw.task_name,
    queue: raw.queue,
    status: raw.status,
    args: raw.args,
    kwargs: raw.kwargs,
    result: raw.result,
    errorMessage: raw.error_message,
    startedAt: raw.started_at,
    finishedAt: raw.finished_at,
    durationMs: raw.duration_ms,
    retryCount: raw.retry_count,
    tenantId: raw.tenant_id,
    createdAt: raw.created_at,
  };
}

function transformTaskLogDetailInfo(
  raw: TaskLogDetailInfoRaw,
): TaskLogDetailInfo {
  return {
    ...transformTaskLogInfo(raw),
    traceback: raw.traceback,
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
// API 接口
// ============================================================

const API_PREFIX = '/admin/tasks';

/**
 * 获取任务日志列表
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
 * 获取任务日志详情
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
 * 获取任务统计
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
 * 获取活跃任务
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
 * 重试任务
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
 * 取消任务
 * POST /admin/tasks/{id}/cancel
 */
export async function cancelTaskApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(`${API_PREFIX}/${id}/cancel`, {}, options);
}

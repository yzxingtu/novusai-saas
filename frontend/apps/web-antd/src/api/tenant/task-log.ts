/**
 * 任务日志 API（租户端）
 * 对接后端 /tenant/tasks/* 接口
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

/** 后端原始格式（内部使用） */
interface TaskLogInfoRaw {
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
  created_at: string;
}

interface TaskLogDetailInfoRaw extends TaskLogInfoRaw {
  traceback: string | null;
}

interface TaskStatsItemRaw {
  status: string;
  count: number;
  avg_duration_ms: number;
}

// ============================================================
// 转换函数
// ============================================================

import type { TaskLogDetailInfo, TaskLogInfo, TaskStatsItem } from '#/api/shared/task-log-types';

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
    tenantId: null,
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

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/tenant/tasks';

export async function getTaskLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
) {
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

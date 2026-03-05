/**
 * 任务日志共享类型定义
 * Admin 端和 Tenant 端共同使用
 */

/** 任务日志列表查询参数 */
export type TaskLogListParams = Record<string, unknown>;

/** 任务日志信息（前端格式 camelCase） */
export interface TaskLogInfo {
  id: number;
  taskId: string;
  taskName: string;
  queue: string;
  status: string;
  args: null | Record<string, unknown>;
  kwargs: null | Record<string, unknown>;
  result: null | Record<string, unknown>;
  errorMessage: null | string;
  startedAt: null | string;
  finishedAt: null | string;
  durationMs: null | number;
  retryCount: number;
  tenantId: null | number;
  createdAt: string;
}

/** 任务日志详情（含堆栈） */
export interface TaskLogDetailInfo extends TaskLogInfo {
  traceback: null | string;
}

/** 任务统计项 */
export interface TaskStatsItem {
  status: string;
  count: number;
  avgDurationMs: number;
}

/** 分页列表响应 */
export interface TaskLogListResponse {
  items: TaskLogInfo[];
  total: number;
  page: number;
  page_size: number;
}

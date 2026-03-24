/**
 * Task log shared type definitions / 任务日志共享类型定义
 * Used by both Admin and Tenant endpoints / Admin 端和 Tenant 端共同使用
 */

/** Task log list query params / 任务日志列表查询参数 */
export type TaskLogListView = 'all' | 'execution' | 'internal';

/** Task log list query params / 任务日志列表查询参数 */
export interface TaskLogListParams extends Record<string, unknown> {
  view?: TaskLogListView;
}

/** Task log info (frontend camelCase format) / 任务日志信息 */
export interface TaskLogInfo {
  id: number;
  taskId: string;
  taskName: string;
  handlerPath: null | string;
  queue: string;
  status: string;
  args: null | Record<string, unknown> | unknown[];
  kwargs: null | Record<string, unknown>;
  result: null | Record<string, unknown>;
  errorMessage: null | string;
  triggerSource: null | string;
  runKind: null | string;
  traceId: null | string;
  startedAt: null | string;
  finishedAt: null | string;
  durationMs: null | number;
  retryCount: number;
  tenantId: null | number;
  createdAt: string;
}

/** Task log detail (with traceback) / 任务日志详情（含堆栈） */
export interface TaskLogDetailInfo extends TaskLogInfo {
  traceback: null | string;
}

/** Task stats item / 任务统计项 */
export interface TaskStatsItem {
  status: string;
  count: number;
  avgDurationMs: number;
}

/** Paginated list response / 分页列表响应 */
export interface TaskLogListResponse {
  items: TaskLogInfo[];
  total: number;
  page: number;
  page_size: number;
}

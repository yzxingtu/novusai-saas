/**
 * Periodic task shared type definitions / 定时任务共享类型定义
 * Used by both Admin and Tenant endpoints / Admin 端和 Tenant 端共同使用
 */

/** Periodic task list query params / 定时任务列表查询参数 */
export type PeriodicTaskListParams = Record<string, unknown>;

/** Periodic task info (frontend camelCase format) / 定时任务信息 */
export interface PeriodicTaskInfo {
  id: number;
  name: string;
  taskPath: string;
  scheduleType: string;
  cronExpression: null | string;
  intervalSeconds: null | number;
  isActive: boolean;
  lastRunAt: null | string;
  nextRunAt: null | string;
  description: null | string;
  createdAt: string;
  scope: null | string;
  tenantId: null | number;
  isLocked: boolean;
  isEditable: boolean;
  maxRetries: number;
  retryDelay: number;
  timeout: null | number;
  notifyOnFailure: boolean;
  notifyEmails: null | string;
}

/** Periodic task create/update request / 定时任务创建/更新请求 */
export interface PeriodicTaskFormData {
  name: string;
  task_path: string;
  schedule_type: string;
  cron_expression?: null | string;
  interval_seconds?: null | number;
  args?: null | Record<string, unknown>;
  kwargs?: null | Record<string, unknown>;
  is_active?: boolean;
  description?: null | string;
}

/** Paginated list response / 分页列表响应 */
export interface PeriodicTaskListResponse {
  items: PeriodicTaskInfo[];
  total: number;
  page: number;
  page_size: number;
}

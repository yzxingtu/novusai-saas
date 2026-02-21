/**
 * 定时任务共享类型定义
 * Admin 端和 Tenant 端共同使用
 */

/** 定时任务列表查询参数 */
export type PeriodicTaskListParams = Record<string, unknown>;

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

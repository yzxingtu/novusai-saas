/**
 * Tenant AI action audit log API / 企业端 AI 操作审计日志 API
 * Backend: /tenant/ai/action-logs/* / 对接后端 /tenant/ai/action-logs/* 接口
 */
import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Action log list item / 操作日志列表项 */
export interface ActionLogItem {
  id: number;
  execution_decision_id?: null | number;
  trace_id?: null | string;
  tool_call_id?: null | string;
  agent_avatar?: null | string;
  agent_name: null | string;
  action_name: string;
  action_type: string;
  status: string;
  agent_id: null | number;
  duration_ms: null | number;
  error_message: null | string;
  operator_id: null | number;
  operator_avatar?: null | string;
  operator_name?: null | string;
  operator_nickname?: null | string;
  operator_type?: null | string;
  created_at: string;
}

/** Action log detail / 操作日志详情 */
export interface ActionLogDetail extends ActionLogItem {
  action_level: string;
  operator_id: null | number;
  request_data: null | Record<string, unknown>;
  response_data: null | Record<string, unknown>;
}

/** Action log statistics (actual backend response) / 操作日志统计 */
export interface ActionLogStats {
  total: number;
  success_count: number;
  failed_count: number;
  rejected_count: number;
  pending_count: number;
  level_read: number;
  level_safe_write: number;
  level_dangerous: number;
  avg_duration_ms: null | number;
}

/** Action log paginated response / 操作日志列表分页响应 */
interface ActionLogPageResponse {
  items: ActionLogItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/tenant/ai/action-logs';

/** Get action log list / 获取操作日志列表 */
export async function getActionLogListApi(
  params?: Record<string, unknown>,
): Promise<ActionLogPageResponse> {
  return requestClient.get<ActionLogPageResponse>(PREFIX, { params });
}

/** Get action log statistics / 获取操作日志统计 */
export async function getActionLogStatsApi(): Promise<ActionLogStats> {
  const res = await requestClient.get<{ stats: ActionLogStats }>(
    `${PREFIX}/stats`,
  );
  return res.stats;
}

/** Get action log detail / 获取操作日志详情 */
export async function getActionLogDetailApi(
  id: number,
): Promise<ActionLogDetail> {
  return requestClient.get<ActionLogDetail>(`${PREFIX}/${id}`);
}

/**
 * 租户端 AI 操作审计日志 API
 * 对接后端 /tenant/ai/action-logs/* 接口
 */
import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 操作日志列表项 */
export interface ActionLogItem {
  id: number;
  action_name: string;
  action_type: string;
  status: string;
  agent_id: number | null;
  agent_name: string | null;
  execution_time_ms: number | null;
  error_message: string | null;
  created_at: string;
}

/** 操作日志统计 */
export interface ActionLogStats {
  total_actions: number;
  success_count: number;
  failed_count: number;
  today_actions: number;
}

/** 操作日志列表分页响应 */
interface ActionLogPageResponse {
  items: ActionLogItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/action-logs';

/** 获取操作日志列表 */
export async function getActionLogListApi(
  params?: Record<string, unknown>,
): Promise<ActionLogPageResponse> {
  return requestClient.get<ActionLogPageResponse>(PREFIX, { params });
}

/** 获取操作日志统计 */
export async function getActionLogStatsApi(): Promise<ActionLogStats> {
  return requestClient.get<ActionLogStats>(`${PREFIX}/stats`);
}

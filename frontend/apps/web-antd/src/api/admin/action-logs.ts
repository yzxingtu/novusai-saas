/**
 * Platform AI action audit log API / 平台端 AI 操作审计日志 API
 * Backend: /admin/ai/action-logs/*
 */
import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Action log list item / 操作日志列表项 */
export interface AdminActionLogItem {
  id: number;
  tenant_id: number;
  tenant_code: null | string;
  tenant_name: null | string;
  action_name: string;
  action_type: string;
  action_level: string;
  status: string;
  agent_id: null | number;
  operator_id: null | number;
  duration_ms: null | number;
  error_message: null | string;
  created_at: string;
}

/** Action log detail / 操作日志详情 */
export interface AdminActionLogDetail extends AdminActionLogItem {
  request_data: null | Record<string, unknown>;
  response_data: null | Record<string, unknown>;
}

/** Action log paginated response / 操作日志列表分页响应 */
interface AdminActionLogPageResponse {
  items: AdminActionLogItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/admin/ai/action-logs';

/** Get action log list / 获取操作日志列表 */
export async function getAdminActionLogListApi(
  params?: Record<string, unknown>,
): Promise<AdminActionLogPageResponse> {
  return requestClient.get<AdminActionLogPageResponse>(PREFIX, { params });
}

/** Get action log detail / 获取操作日志详情 */
export async function getAdminActionLogDetailApi(
  id: number,
): Promise<AdminActionLogDetail> {
  return requestClient.get<AdminActionLogDetail>(`${PREFIX}/${id}`);
}

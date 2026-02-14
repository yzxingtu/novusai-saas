/**
 * 平台端 AI 操作审计日志 API
 * 对接后端 /admin/ai/action-logs/* 接口
 */
import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 操作日志列表项 */
export interface AdminActionLogItem {
  id: number;
  tenant_id: number;
  action_name: string;
  action_type: string;
  action_level: string;
  status: string;
  agent_id: number | null;
  operator_id: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
}

/** 操作日志详情 */
export interface AdminActionLogDetail extends AdminActionLogItem {
  request_data: Record<string, unknown> | null;
  response_data: Record<string, unknown> | null;
}

/** 操作日志列表分页响应 */
interface AdminActionLogPageResponse {
  items: AdminActionLogItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/admin/ai/action-logs';

/** 获取操作日志列表 */
export async function getAdminActionLogListApi(
  params?: Record<string, unknown>,
): Promise<AdminActionLogPageResponse> {
  return requestClient.get<AdminActionLogPageResponse>(PREFIX, { params });
}

/** 获取操作日志详情 */
export async function getAdminActionLogDetailApi(
  id: number,
): Promise<AdminActionLogDetail> {
  return requestClient.get<AdminActionLogDetail>(`${PREFIX}/${id}`);
}

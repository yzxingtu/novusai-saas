/**
 * AI call logs & usage stats API / AI 调用日志 & 使用量统计 API
 * Backend: /admin/ai/call-logs, /admin/ai/usage
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions - Call logs / 类型定义 - 调用日志
// ============================================================

/** Call log info / 调用日志信息 */
export interface AICallLogInfo {
  id: number;
  tenant_id: null | number;
  agent_id?: null | number;
  conversation_id?: null | number;
  model_id: null | number;
  provider_id: null | number;
  request_type: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  latency_ms: null | number;
  status: string;
  error_message: null | string;
  user_id: null | number;
  user_type: null | string;
  created_at: string;
  // Related names / 关联名称
  model_name?: null | string;
  provider_name?: null | string;
  provider_icon?: null | string;
  tenant_name?: null | string;
  /** 列表展示优先使用快照，避免智能体删除后名称丢失 */
  agent_name?: null | string;
  caller_name?: null | string;
  // Routing fields (multi-model routing) / 路由字段（多模型路由）
  routed_model_id?: null | number;
  route_reason?: null | string;
  routed_model_name?: null | string;
  // Detail fields (only returned by detail API) / 详情字段（仅详情 API 返回）
  request_data?: null | Record<string, unknown>;
  response_data?: null | Record<string, unknown>;
}

// ============================================================
// Type definitions - AI usage stats / 类型定义 - AI 使用量统计
// ============================================================

/** Usage stat record / 使用量统计记录（按计费事实聚合，无独立 id） */
export interface AIUsageStatInfo {
  id: string;
  tenant_id: null | number;
  model_id: number;
  request_type: string;
  stat_date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  call_count: number;
  success_count: number;
  failed_count: number;
  total_cost: number;
  avg_latency_ms: null | number;
  max_latency_ms: null | number;
  // Related names / 关联名称
  tenant_name?: null | string;
  model_name?: null | string;
}

// ============================================================
// Generic paginated response / 通用分页响应
// ============================================================

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API - Call logs / API 接口 - 调用日志
// ============================================================

const CALL_LOG_PREFIX = '/admin/ai/call-logs';

/** Get call log list / 获取调用日志列表 */
export async function getAICallLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AICallLogInfo>> {
  return requestClient.get<PageResponse<AICallLogInfo>>(CALL_LOG_PREFIX, {
    params,
    ...options,
  });
}

/** Get call log detail / 获取调用日志详情 */
export async function getAICallLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AICallLogInfo> {
  return requestClient.get<AICallLogInfo>(`${CALL_LOG_PREFIX}/${id}`, options);
}

/** Get call statistics / 获取调用统计 */
export async function getAICallLogStatisticsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${CALL_LOG_PREFIX}/statistics`,
    { params, ...options },
  );
}

/** Get failed call logs / 获取失败的调用日志 */
export async function getAICallLogFailedApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AICallLogInfo[]> {
  return requestClient.get<AICallLogInfo[]>(`${CALL_LOG_PREFIX}/failed`, {
    params,
    ...options,
  });
}

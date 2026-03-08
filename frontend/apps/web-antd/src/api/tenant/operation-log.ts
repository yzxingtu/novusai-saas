/**
 * 操作日志 API（租户端）
 * 对接后端 /tenant/operation-logs/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 操作日志列表查询参数 */
export type OperationLogListParams = Record<string, unknown>;

/** 操作人下拉选项 */
export interface OperatorItem {
  user_id: number;
  user_type: string;
  username: string;
  nickname?: null | string;
  avatar?: null | string;
}

/** 操作日志信息（后端原始格式 snake_case） */
export interface OperationLogInfoRaw {
  id: number;
  tenant_id: null | number;
  user_type: string;
  user_id: null | number;
  username: null | string;
  nickname?: null | string;
  module: string;
  module_label?: string;
  action: string;
  action_label?: string;
  method: string;
  path: string;
  query_params: null | Record<string, unknown>;
  request_body: null | Record<string, unknown>;
  status_code: number;
  response_code: number;
  ip: string;
  duration_ms: number;
  created_at: string;
}

/** 操作日志信息（前端格式 camelCase） */
export interface OperationLogInfo {
  id: number;
  tenantId: null | number;
  userType: string;
  userId: null | number;
  username: null | string;
  nickname?: null | string;
  module: string;
  moduleLabel?: string;
  action: string;
  actionLabel?: string;
  method: string;
  path: string;
  queryParams: null | Record<string, unknown>;
  requestBody: null | Record<string, unknown>;
  statusCode: number;
  responseCode: number;
  ip: string;
  durationMs: number;
  createdAt: string;
}

/** 分页列表响应 */
export interface OperationLogListResponse {
  items: OperationLogInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformOperationLogInfo(raw: OperationLogInfoRaw): OperationLogInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    userType: raw.user_type,
    userId: raw.user_id,
    username: raw.username,
    nickname: raw.nickname,
    module: raw.module,
    moduleLabel: raw.module_label,
    action: raw.action,
    actionLabel: raw.action_label,
    method: raw.method,
    path: raw.path,
    queryParams: raw.query_params,
    requestBody: raw.request_body,
    statusCode: raw.status_code,
    responseCode: raw.response_code,
    ip: raw.ip,
    durationMs: raw.duration_ms,
    createdAt: raw.created_at,
  };
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/tenant/operation-logs';

/**
 * 获取操作日志列表
 * GET /tenant/operation-logs
 */
export async function getOperationLogListApi(
  params?: OperationLogListParams,
  options?: ApiRequestOptions,
): Promise<OperationLogListResponse> {
  const response = await requestClient.get<{
    items: OperationLogInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformOperationLogInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * 获取操作人下拉列表（含头像，全量模式）
 * GET /tenant/operation-logs/operators
 */
export async function getOperatorsApi(): Promise<OperatorItem[]> {
  return requestClient.get<OperatorItem[]>(`${API_PREFIX}/operators`);
}

/**
 * 获取操作人分页下拉列表（供 ApiSelect 使用）
 * GET /tenant/operation-logs/operators?page=1&page_size=10&search=xxx&user_type=xxx
 */
export async function getOperatorsSelectApi(
  params: Record<string, unknown>,
): Promise<{ items: { label: string; value: string }[]; page: number; page_size: number; total: number }> {
  return requestClient.get(`${API_PREFIX}/operators`, { params });
}

/**
 * 获取操作日志详情
 * GET /tenant/operation-logs/{id}
 */
export async function getOperationLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<OperationLogInfo> {
  const raw = await requestClient.get<OperationLogInfoRaw>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return transformOperationLogInfo(raw);
}

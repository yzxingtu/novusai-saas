/**
 * 操作日志 API
 * 对接后端 /admin/operation-logs/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 操作日志列表查询参数 */
export type OperationLogListParams = Record<string, unknown>;

/** 操作日志信息（后端原始格式 snake_case） */
export interface OperationLogInfoRaw {
  id: number;
  tenant_id: null | number;
  user_type: string;
  username: null | string;
  module: string;
  action: string;
  method: string;
  path: string;
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
  username: null | string;
  module: string;
  action: string;
  method: string;
  path: string;
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
    username: raw.username,
    module: raw.module,
    action: raw.action,
    method: raw.method,
    path: raw.path,
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

const API_PREFIX = '/admin/operation-logs';

/**
 * 获取操作日志列表
 * GET /admin/operation-logs
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
 * 获取操作日志详情
 * GET /admin/operation-logs/{id}
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

/**
 * 删除操作日志（支持批量）
 * DELETE /admin/operation-logs
 */
export async function deleteOperationLogsApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(API_PREFIX, {
    data: { ids },
    ...options,
  });
}

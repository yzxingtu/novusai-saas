/**
 * 租户端工具管理 API
 * 对接后端 /tenant/ai/tools/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 工具定义信息 */
export interface ToolDefinitionInfo {
  id: number;
  tenant_id: number | null;
  name: string;
  description: string | null;
  type: string;
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
  config: Record<string, unknown> | null;
  timeout: number;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建工具请求 */
export interface ToolDefinitionCreateRequest {
  name: string;
  description?: string | null;
  type?: string;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
  config?: Record<string, unknown> | null;
  timeout?: number;
  is_active?: boolean;
}

/** 更新工具请求 */
export interface ToolDefinitionUpdateRequest {
  name?: string | null;
  description?: string | null;
  type?: string | null;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
  config?: Record<string, unknown> | null;
  timeout?: number | null;
  is_active?: boolean | null;
}

/** 工具测试请求 */
export interface ToolTestRequest {
  arguments: Record<string, unknown>;
}

/** 工具测试响应 */
export interface ToolTestResult {
  success: boolean;
  output: string;
  error: string | null;
  duration_ms: number;
}

/** 工具列表分页响应 */
interface ToolPageResponse {
  items: ToolDefinitionInfo[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/tools';

/** 获取工具列表 */
export async function getToolListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<ToolPageResponse> {
  return requestClient.get<ToolPageResponse>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取工具详情 */
export async function getToolDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<ToolDefinitionInfo> {
  return requestClient.get<ToolDefinitionInfo>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建工具 */
export async function createToolApi(
  data: ToolDefinitionCreateRequest,
  options?: ApiRequestOptions,
): Promise<ToolDefinitionInfo> {
  return requestClient.post<ToolDefinitionInfo>(
    PREFIX,
    data,
    options,
  );
}

/** 更新工具 */
export async function updateToolApi(
  id: number,
  data: ToolDefinitionUpdateRequest,
  options?: ApiRequestOptions,
): Promise<ToolDefinitionInfo> {
  return requestClient.put<ToolDefinitionInfo>(
    `${PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除工具 */
export async function deleteToolApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 测试执行工具 */
export async function testToolApi(
  id: number,
  data: ToolTestRequest,
  options?: ApiRequestOptions,
): Promise<ToolTestResult> {
  return requestClient.post<ToolTestResult>(
    `${PREFIX}/${id}/test`,
    data,
    options,
  );
}

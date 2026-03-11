/**
 * AI provider management API / AI 供应商管理 API
 * Backend: /admin/ai/providers, /admin/ai/api-keys, /admin/ai/health, /admin/ai/gateway
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions - AI providers / 类型定义 - AI 供应商
// ============================================================

/** Provider type / 供应商类型 */
export type ProviderType = string;

/** Adapter type info / 适配器类型信息 */
export interface AdapterTypeInfo {
  type: string;
  source: 'builtin' | 'plugin';
  plugin_name?: null | string;
  display_name: string;
  icon?: null | string;
  supports?: Record<string, boolean>;
  models?: Array<{ code: string; name: string }>;
}

/** AI provider info / AI 供应商信息 */
export interface AIProviderInfo {
  id: number;
  name: string;
  code: string;
  type: ProviderType;
  base_url: null | string;
  description: null | string;
  icon: null | string;
  is_active: boolean;
  sort_order: number;
  config: null | Record<string, unknown>;
  model_count: number;
  created_at: string;
  updated_at: string;
}

/** Create provider request / 创建供应商请求 */
export interface AIProviderCreateRequest {
  name: string;
  code: string;
  type: ProviderType;
  base_url?: null | string;
  description?: null | string;
  icon?: null | string;
  is_active?: boolean;
  sort_order?: number;
  config?: null | Record<string, unknown>;
}

/** Update provider request / 更新供应商请求 */
export interface AIProviderUpdateRequest {
  name?: null | string;
  code?: null | string;
  type?: null | string;
  base_url?: null | string;
  description?: null | string;
  icon?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  config?: null | Record<string, unknown>;
}

// ============================================================
// Type definitions - API Key / 类型定义 - API Key
// ============================================================

/** API Key info / API Key 信息 */
export interface AIApiKeyInfo {
  id: number;
  provider_id: number;
  tenant_id: null | number;
  name: string;
  is_active: boolean;
  usage_limit: null | number;
  usage_count: number;
  last_used_at: null | string;
  expires_at: null | string;
  provider_name: null | string;
  tenant_name: null | string;
  is_available: boolean;
  key_preview: null | string;
  created_at: string;
  updated_at: string;
}

/** Create API Key request / 创建 API Key 请求 */
export interface AIApiKeyCreateRequest {
  provider_id: number;
  tenant_id?: null | number;
  name: string;
  api_key: string;
  is_active?: boolean;
  usage_limit?: null | number;
  expires_at?: null | string;
}

/** Update API Key request / 更新 API Key 请求 */
export interface AIApiKeyUpdateRequest {
  name?: null | string;
  is_active?: boolean | null;
  usage_limit?: null | number;
  expires_at?: null | string;
}

// ============================================================
// Type definitions - AI health status / 类型定义 - AI 健康状态
// ============================================================

/** Provider health status / 供应商健康状态 */
export interface AIHealthStatus {
  provider_id: number;
  provider_code: string;
  provider_name: string;
  is_healthy: boolean;
  is_available: boolean;
  response_time_ms: number;
  consecutive_failures: number;
  error_message: null | string;
  checked_at: string;
}

// ============================================================
// Type definitions - AI gateway test / 类型定义 - AI 网关测试
// ============================================================

/** Model test request / 模型测试请求 */
export interface TestAIGatewayRequest {
  provider_id: number;
  model_code: string;
  test_prompt?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
}

/** Model test result / 模型测试结果 */
export interface TestAIGatewayResult {
  connected: boolean;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  response_text: string;
  error: null | string;
  model: string;
  provider: string;
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
// API - AI providers / API 接口 - AI 供应商
// ============================================================

const PROVIDER_PREFIX = '/admin/ai/providers';

/** Get provider list / 获取供应商列表 */
export async function getAIProviderListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIProviderInfo>> {
  return requestClient.get<PageResponse<AIProviderInfo>>(PROVIDER_PREFIX, {
    params,
    ...options,
  });
}

/** Get available adapter types (builtin + plugin) / 获取可用适配器类型列表 */
export async function getAdapterTypesApi(
  options?: ApiRequestOptions,
): Promise<AdapterTypeInfo[]> {
  return requestClient.get<AdapterTypeInfo[]>(
    `${PROVIDER_PREFIX}/adapter-types`,
    options,
  );
}

/** Get provider detail / 获取供应商详情 */
export async function getAIProviderDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.get<AIProviderInfo>(`${PROVIDER_PREFIX}/${id}`, options);
}

/** Create provider / 创建供应商 */
export async function createAIProviderApi(
  data: AIProviderCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.post<AIProviderInfo>(PROVIDER_PREFIX, data, options);
}

/** Update provider / 更新供应商 */
export async function updateAIProviderApi(
  id: number,
  data: AIProviderUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.put<AIProviderInfo>(
    `${PROVIDER_PREFIX}/${id}`,
    data,
    options,
  );
}

/** Delete provider / 删除供应商 */
export async function deleteAIProviderApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PROVIDER_PREFIX}/${id}`, options);
}

/** Toggle provider status / 切换供应商状态 */
export async function toggleAIProviderStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.put<AIProviderInfo>(
    `${PROVIDER_PREFIX}/${id}/status`,
    {},
    options,
  );
}

/** Batch reorder providers / 批量重排序供应商 */
export async function reorderAIProvidersApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(`${PROVIDER_PREFIX}/reorder`, { ids }, options);
}

// ============================================================
// API - API Key / API 接口 - API Key
// ============================================================

const API_KEY_PREFIX = '/admin/ai/api-keys';

/** Get API Key list / 获取 API Key 列表 */
export async function getAIApiKeyListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIApiKeyInfo>> {
  return requestClient.get<PageResponse<AIApiKeyInfo>>(API_KEY_PREFIX, {
    params,
    ...options,
  });
}

/** Get API Keys by provider / 获取供应商的 API Key 列表 */
export async function getAIApiKeysByProviderApi(
  providerId: number,
  tenantId?: number,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo[]> {
  const params: Record<string, unknown> = {};
  if (tenantId !== undefined) params.tenant_id = tenantId;
  return requestClient.get<AIApiKeyInfo[]>(
    `${API_KEY_PREFIX}/provider/${providerId}`,
    { params, ...options },
  );
}

/** Get API Key detail / 获取 API Key 详情 */
export async function getAIApiKeyDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.get<AIApiKeyInfo>(`${API_KEY_PREFIX}/${id}`, options);
}

/** Create API Key / 创建 API Key */
export async function createAIApiKeyApi(
  data: AIApiKeyCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.post<AIApiKeyInfo>(API_KEY_PREFIX, data, options);
}

/** Update API Key / 更新 API Key */
export async function updateAIApiKeyApi(
  id: number,
  data: AIApiKeyUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.put<AIApiKeyInfo>(
    `${API_KEY_PREFIX}/${id}`,
    data,
    options,
  );
}

/** Delete API Key / 删除 API Key */
export async function deleteAIApiKeyApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_KEY_PREFIX}/${id}`, options);
}

/** Toggle API Key status / 切换 API Key 状态 */
export async function toggleAIApiKeyStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.put<AIApiKeyInfo>(
    `${API_KEY_PREFIX}/${id}/status`,
    {},
    options,
  );
}

// ============================================================
// API - AI health status / API 接口 - AI 健康状态
// ============================================================

/** Get AI provider health status / 获取 AI 供应商健康状态 */
export async function getAIHealthStatusApi(
  options?: ApiRequestOptions,
): Promise<AIHealthStatus[]> {
  return requestClient.get<AIHealthStatus[]>('/admin/ai/health', options);
}

// ============================================================
// API - AI gateway test / API 接口 - AI 网关测试
// ============================================================

/** Test AI model connectivity / 测试 AI 模型连通性 */
export async function testAIGatewayApi(
  data: TestAIGatewayRequest,
  options?: ApiRequestOptions,
): Promise<TestAIGatewayResult> {
  return requestClient.post<TestAIGatewayResult>(
    '/admin/ai/gateway/test',
    data,
    options,
  );
}

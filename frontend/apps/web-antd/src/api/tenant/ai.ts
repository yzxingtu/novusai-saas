/**
 * 租户端 AI 配置与用量 API
 * 对接后端 /tenant/ai/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义 - 可用模型
// ============================================================

/** AI 模型信息 */
export interface TenantAIModelInfo {
  id: number;
  provider_id: number;
  name: string;
  code: string;
  type: string;
  context_window: null | number;
  max_output_tokens: null | number;
  input_price_per_1k: null | number;
  output_price_per_1k: null | number;
  supports_function_calling: boolean;
  supports_vision: boolean;
  supports_streaming: boolean;
  is_active: boolean;
  provider_name: null | string;
  created_at: string;
  updated_at: string;
}

// ============================================================
// 类型定义 - API Key
// ============================================================

/** 租户 API Key 信息 */
export interface TenantAIApiKeyInfo {
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

/** 创建 API Key 请求 */
export interface TenantAIApiKeyCreateRequest {
  provider_id: number;
  name: string;
  api_key: string;
  is_active?: boolean;
  usage_limit?: null | number;
}

// ============================================================
// 类型定义 - 用量统计
// ============================================================

/** 用量汇总 */
export interface TenantAIUsageSummary {
  total_tokens: number;
  total_cost: number;
  total_calls: number;
  success_calls: number;
  failed_calls: number;
  daily_stats?: TenantAIUsageDaily[];
  model_stats?: TenantAIUsageByModel[];
}

/** 每日用量 */
export interface TenantAIUsageDaily {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  calls: number;
}

/** 按模型用量 */
export interface TenantAIUsageByModel {
  model_id: number;
  model_name: string;
  total_tokens: number;
  cost: number;
  calls: number;
}

// ============================================================
// 类型定义 - 供应商选项（用于租户端下拉选择）
// ============================================================

/** 供应商简要信息（从模型列表中提取） */
export interface TenantProviderOption {
  label: string;
  value: number;
}

// ============================================================
// API 接口 - AI 配置
// ============================================================

const CONFIG_PREFIX = '/tenant/ai/config';

/** 获取可用 AI 模型列表 */
export async function getTenantAIModelsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantAIModelInfo[]> {
  return requestClient.get<TenantAIModelInfo[]>(
    `${CONFIG_PREFIX}/models`,
    { params, ...options },
  );
}

/** 获取我的 API Keys */
export async function getTenantAIKeysApi(
  options?: ApiRequestOptions,
): Promise<TenantAIApiKeyInfo[]> {
  return requestClient.get<TenantAIApiKeyInfo[]>(
    `${CONFIG_PREFIX}/keys`,
    options,
  );
}

/** 创建 API Key */
export async function createTenantAIKeyApi(
  data: TenantAIApiKeyCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantAIApiKeyInfo> {
  return requestClient.post<TenantAIApiKeyInfo>(
    `${CONFIG_PREFIX}/keys`,
    data,
    options,
  );
}

/** 删除 API Key */
export async function deleteTenantAIKeyApi(
  keyId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${CONFIG_PREFIX}/keys/${keyId}`, options);
}

// ============================================================
// API 接口 - 用量统计
// ============================================================

const USAGE_PREFIX = '/tenant/ai/usage';

/** 获取使用量汇总 */
export async function getTenantAIUsageSummaryApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantAIUsageSummary> {
  return requestClient.get<TenantAIUsageSummary>(
    `${USAGE_PREFIX}/summary`,
    { params, ...options },
  );
}

// ============================================================
// 类型定义 - 调用日志
// ============================================================

/** 调用日志信息 */
export interface TenantAICallLogInfo {
  id: number;
  tenant_id: null | number;
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
  request_data: null | Record<string, unknown>;
  response_data: null | Record<string, unknown>;
  created_at: string;
  model_name?: null | string;
  provider_name?: null | string;
}

interface TenantCallLogPageResponse {
  items: TenantAICallLogInfo[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口 - 调用日志
// ============================================================

const CALL_LOG_PREFIX = '/tenant/ai/call-logs';

/** 获取调用日志列表 */
export async function getTenantAICallLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantCallLogPageResponse> {
  return requestClient.get<TenantCallLogPageResponse>(
    CALL_LOG_PREFIX,
    { params, ...options },
  );
}

/** 获取调用日志详情 */
export async function getTenantAICallLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TenantAICallLogInfo> {
  return requestClient.get<TenantAICallLogInfo>(
    `${CALL_LOG_PREFIX}/${id}`,
    options,
  );
}

// ============================================================
// 类型定义 - 配额管理
// ============================================================

/** 租户配额信息 */
export interface TenantQuotaInfo {
  id: number;
  tenant_id: number;
  model_id: null | number;
  period: string;
  limit: number;
  quota_type: string;
  warning_threshold: null | number;
  description: null | string;
  is_active: boolean;
  model_name: null | string;
  created_at: string;
  updated_at: string;
}

/** 配额及使用量信息 */
export interface TenantQuotaWithUsageInfo {
  quota: TenantQuotaInfo;
  usage: number;
  limit: number;
  usage_percent: number;
  is_warning: boolean;
  is_exceeded: boolean;
  remaining: number;
}

/** 创建配额请求 */
export interface TenantQuotaCreateRequest {
  model_id?: null | number;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
}

/** 更新配额请求 */
export interface TenantQuotaUpdateRequest {
  limit?: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
  is_active?: boolean;
}

// ============================================================
// 类型定义 - 速率限制
// ============================================================

/** 租户速率限制信息 */
export interface TenantRateLimitInfo {
  id: number;
  tenant_id: number;
  model_id: number;
  rpm_limit: null | number;
  tpm_limit: null | number;
  description: null | string;
  is_active: boolean;
  model_name: null | string;
  created_at: string;
  updated_at: string;
}

/** 创建速率限制请求 */
export interface TenantRateLimitCreateRequest {
  model_id: number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
}

/** 更新速率限制请求 */
export interface TenantRateLimitUpdateRequest {
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
  is_active?: boolean;
}

// ============================================================
// API 接口 - 配额管理
// ============================================================

const QUOTA_PREFIX = '/tenant/ai/quotas';

/** 获取配额列表（含使用量） */
export async function getTenantQuotasApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantQuotaWithUsageInfo[]> {
  return requestClient.get<TenantQuotaWithUsageInfo[]>(
    QUOTA_PREFIX,
    { params: { include_usage: true, ...params }, ...options },
  );
}

/** 获取配额详情 */
export async function getTenantQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TenantQuotaWithUsageInfo> {
  return requestClient.get<TenantQuotaWithUsageInfo>(
    `${QUOTA_PREFIX}/${id}`,
    options,
  );
}

/** 创建配额 */
export async function createTenantQuotaApi(
  data: TenantQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantQuotaInfo> {
  return requestClient.post<TenantQuotaInfo>(
    QUOTA_PREFIX,
    data,
    options,
  );
}

/** 更新配额 */
export async function updateTenantQuotaApi(
  id: number,
  data: TenantQuotaUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantQuotaInfo> {
  return requestClient.put<TenantQuotaInfo>(
    `${QUOTA_PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除配额 */
export async function deleteTenantQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

// ============================================================
// API 接口 - 速率限制
// ============================================================

/** 获取速率限制列表 */
export async function getTenantRateLimitsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantRateLimitInfo[]> {
  return requestClient.get<TenantRateLimitInfo[]>(
    `${QUOTA_PREFIX}/rate-limits`,
    { params, ...options },
  );
}

/** 创建速率限制 */
export async function createTenantRateLimitApi(
  data: TenantRateLimitCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantRateLimitInfo> {
  return requestClient.post<TenantRateLimitInfo>(
    `${QUOTA_PREFIX}/rate-limits`,
    data,
    options,
  );
}

/** 更新速率限制 */
export async function updateTenantRateLimitApi(
  id: number,
  data: TenantRateLimitUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantRateLimitInfo> {
  return requestClient.put<TenantRateLimitInfo>(
    `${QUOTA_PREFIX}/rate-limits/${id}`,
    data,
    options,
  );
}

/** 删除速率限制 */
export async function deleteTenantRateLimitApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/rate-limits/${id}`, options);
}

// ============================================================
// 辅助函数 - 供应商下拉选项
// ============================================================

/**
 * 从可用模型列表中提取供应商下拉选项（去重）
 *
 * 租户端没有独立的供应商列表 API，通过模型列表的 provider_id/provider_name 提取。
 * 用于表单中的供应商下拉选择。
 */
export async function getTenantProviderSelectOptions(): Promise<TenantProviderOption[]> {
  try {
    const models = await getTenantAIModelsApi();
    const providerMap = new Map<number, string>();
    for (const model of models) {
      if (model.provider_id && !providerMap.has(model.provider_id)) {
        providerMap.set(model.provider_id, model.provider_name || `Provider #${model.provider_id}`);
      }
    }
    return Array.from(providerMap.entries()).map(([id, name]) => ({
      label: name,
      value: id,
    }));
  } catch {
    return [];
  }
}

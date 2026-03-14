/**
 * Tenant AI config & usage API / 企业端 AI 配置与用量 API
 * Backend: /tenant/ai/* / 对接后端 /tenant/ai/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions - Available models / 类型定义 - 可用模型
// ============================================================

/** AI model info / AI 模型信息 */
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
  tier: null | string;
  provider_name: null | string;
  created_at: string;
  updated_at: string;
}

// ============================================================
// Type definitions - API Key / 类型定义 - API Key
// ============================================================

/** Tenant API Key info / 企业 API Key 信息 */
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

/** Create API Key request / 创建 API Key 请求 */
export interface TenantAIApiKeyCreateRequest {
  provider_id: number;
  name: string;
  api_key: string;
  is_active?: boolean;
  usage_limit?: null | number;
}

// ============================================================
// Type definitions - Usage stats / 类型定义 - 用量统计
// ============================================================

/** Usage summary / 用量汇总 */
export interface TenantAIUsageSummary {
  total_tokens: number;
  total_cost: number;
  total_calls: number;
  success_calls: number;
  failed_calls: number;
  daily_stats?: TenantAIUsageDaily[];
  model_stats?: TenantAIUsageByModel[];
}

/** Daily usage / 每日用量 */
export interface TenantAIUsageDaily {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  calls: number;
}

/** Usage by model / 按模型用量 */
export interface TenantAIUsageByModel {
  model_id: number;
  model_name: string;
  total_tokens: number;
  cost: number;
  calls: number;
}

// ============================================================
// Type definitions - Provider options (for tenant dropdown) / 供应商选项
// ============================================================

/** Provider brief info (extracted from model list) / 供应商简要信息 */
export interface TenantProviderOption {
  label: string;
  value: number;
}

// ============================================================
// API functions - AI config / API 接口 - AI 配置
// ============================================================

const CONFIG_PREFIX = '/tenant/ai/config';

/** Get available AI model list / 获取可用 AI 模型列表 */
export async function getTenantAIModelsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantAIModelInfo[]> {
  return requestClient.get<TenantAIModelInfo[]>(`${CONFIG_PREFIX}/models`, {
    params,
    ...options,
  });
}

/** Get my API Keys / 获取我的 API Keys */
export async function getTenantAIKeysApi(
  options?: ApiRequestOptions,
): Promise<TenantAIApiKeyInfo[]> {
  return requestClient.get<TenantAIApiKeyInfo[]>(
    `${CONFIG_PREFIX}/keys`,
    options,
  );
}

/** Create API Key / 创建 API Key */
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

/** Delete API Key / 删除 API Key */
export async function deleteTenantAIKeyApi(
  keyId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${CONFIG_PREFIX}/keys/${keyId}`, options);
}

// ============================================================
// API functions - Usage stats / API 接口 - 用量统计
// ============================================================

const USAGE_PREFIX = '/tenant/ai/usage';

/** Get usage summary / 获取使用量汇总 */
export async function getTenantAIUsageSummaryApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantAIUsageSummary> {
  return requestClient.get<TenantAIUsageSummary>(`${USAGE_PREFIX}/summary`, {
    params,
    ...options,
  });
}

// ============================================================
// Type definitions - Call logs / 类型定义 - 调用日志
// ============================================================

/** Call log info / 调用日志信息 */
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
  provider_icon?: null | string;
}

interface TenantCallLogPageResponse {
  items: TenantAICallLogInfo[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API functions - Call logs / API 接口 - 调用日志
// ============================================================

const CALL_LOG_PREFIX = '/tenant/ai/call-logs';

/** Get call log list / 获取调用日志列表 */
export async function getTenantAICallLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantCallLogPageResponse> {
  return requestClient.get<TenantCallLogPageResponse>(CALL_LOG_PREFIX, {
    params,
    ...options,
  });
}

/** Get call log detail / 获取调用日志详情 */
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
// Type definitions - Quota management / 类型定义 - 配额管理
// ============================================================

/** Tenant quota info / 企业配额信息 */
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

/** Quota with usage info / 配额及使用量信息 */
export interface TenantQuotaWithUsageInfo {
  quota: TenantQuotaInfo;
  usage: number;
  limit: number;
  usage_percent: number;
  is_warning: boolean;
  is_exceeded: boolean;
  remaining: number;
}

/** Create quota request / 创建配额请求 */
export interface TenantQuotaCreateRequest {
  model_id?: null | number;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
}

/** Update quota request / 更新配额请求 */
export interface TenantQuotaUpdateRequest {
  limit?: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
  is_active?: boolean;
}

// ============================================================
// Type definitions - Rate limiting / 类型定义 - 速率限制
// ============================================================

/** Tenant rate limit info / 企业速率限制信息 */
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

/** Create rate limit request / 创建速率限制请求 */
export interface TenantRateLimitCreateRequest {
  model_id: number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
}

/** Update rate limit request / 更新速率限制请求 */
export interface TenantRateLimitUpdateRequest {
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
  is_active?: boolean;
}

// ============================================================
// API functions - Quota management / API 接口 - 配额管理
// ============================================================

const QUOTA_PREFIX = '/tenant/ai/quotas';

/** Get quota list (with usage) / 获取配额列表（含使用量） */
export async function getTenantQuotasApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantQuotaWithUsageInfo[]> {
  return requestClient.get<TenantQuotaWithUsageInfo[]>(QUOTA_PREFIX, {
    params: { include_usage: true, ...params },
    ...options,
  });
}

/** Get quota detail / 获取配额详情 */
export async function getTenantQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TenantQuotaWithUsageInfo> {
  return requestClient.get<TenantQuotaWithUsageInfo>(
    `${QUOTA_PREFIX}/${id}`,
    options,
  );
}

/** Create quota / 创建配额 */
export async function createTenantQuotaApi(
  data: TenantQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantQuotaInfo> {
  return requestClient.post<TenantQuotaInfo>(QUOTA_PREFIX, data, options);
}

/** Update quota / 更新配额 */
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

/** Delete quota / 删除配额 */
export async function deleteTenantQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

// ============================================================
// API functions - Rate limiting / API 接口 - 速率限制
// ============================================================

/** Get rate limit list / 获取速率限制列表 */
export async function getTenantRateLimitsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantRateLimitInfo[]> {
  return requestClient.get<TenantRateLimitInfo[]>(
    `${QUOTA_PREFIX}/rate-limits`,
    { params, ...options },
  );
}

/** Create rate limit / 创建速率限制 */
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

/** Update rate limit / 更新速率限制 */
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

/** Delete rate limit / 删除速率限制 */
export async function deleteTenantRateLimitApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/rate-limits/${id}`, options);
}

// ============================================================
// Helper - Provider dropdown options / 辅助函数 - 供应商下拉选项
// ============================================================

/**
 * Extract provider dropdown options from available models (deduplicated)
 * 从可用模型列表中提取供应商下拉选项（去重）
 *
 * No standalone provider list API on tenant side; extracted from model list.
 * 企业端无独立供应商 API，通过模型列表提取。
 */
export async function getTenantProviderSelectOptions(): Promise<
  TenantProviderOption[]
> {
  try {
    const models = await getTenantAIModelsApi();
    const providerMap = new Map<number, string>();
    for (const model of models) {
      if (model.provider_id && !providerMap.has(model.provider_id)) {
        providerMap.set(
          model.provider_id,
          model.provider_name || `Provider #${model.provider_id}`,
        );
      }
    }
    return [...providerMap.entries()].map(([id, name]) => ({
      label: name,
      value: id,
    }));
  } catch {
    return [];
  }
}

// ============================================================
// AI table policy override / AI 表策略覆盖
// ============================================================

/** Effective policy (global + tenant override merged) / 有效策略 */
export interface EffectiveTablePolicy {
  id: number;
  table_name: string;
  label: string;
  description: string;
  allow_read: boolean;
  allow_create: boolean;
  allow_update: boolean;
  allow_delete: boolean;
  max_rows: number;
  blocked_columns: string[];
  scope: string;
  permission_code: string;
  is_active: boolean;
  override_id: null | number;
  has_override: boolean;
}

/** Override update request / 覆盖更新请求 */
export interface TablePolicyOverrideRequest {
  allow_read?: boolean;
  allow_create?: boolean;
  allow_update?: boolean;
  allow_delete?: boolean;
  max_rows?: number;
  blocked_columns?: string[];
  is_active?: boolean;
}

/** Get current tenant effective policies / 获取当前企业的有效策略列表 */
export async function getTenantTablePoliciesApi() {
  return requestClient.get<EffectiveTablePolicy[]>('/tenant/ai/table-policies');
}

/** Create/update policy override / 创建或更新策略覆盖 */
export async function upsertTablePolicyOverrideApi(
  policyId: number,
  data: TablePolicyOverrideRequest,
) {
  return requestClient.put(
    `/tenant/ai/table-policies/${policyId}/override`,
    data,
  );
}

/** Delete policy override (restore global) / 删除策略覆盖（恢复全局） */
export async function removeTablePolicyOverrideApi(policyId: number) {
  return requestClient.delete(`/tenant/ai/table-policies/${policyId}/override`);
}

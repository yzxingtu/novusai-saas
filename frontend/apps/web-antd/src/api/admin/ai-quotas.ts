/**
 * AI quota and rate-limit management API / AI 配额与速率限制管理 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface AIQuotaInfo {
  id: number;
  tenant_id: number;
  model_id: null | number;
  period: string;
  limit: number;
  quota_type: string;
  warning_threshold: null | number;
  is_active: boolean;
  description: null | string;
  tenant_name: null | string;
  model_name: null | string;
  created_at: string;
  updated_at: string;
}

export interface AIQuotaDiagnosticsSummaryInfo {
  total_quota_rules: number;
  active_quota_rules: number;
  hard_quota_rules: number;
  soft_quota_rules: number;
  quota_warning_rules: number;
  quota_exceeded_rules: number;
  total_rate_limit_rules: number;
  active_rate_limit_rules: number;
  rate_limit_warning_rules: number;
  rate_limit_exceeded_rules: number;
}

export interface AIQuotaDiagnosticInfo extends AIQuotaInfo {
  scope_type: 'global' | 'model';
  tracking_model_id: number;
  usage: number;
  remaining: number;
  usage_percent: number;
  is_warning: boolean;
  is_exceeded: boolean;
  runtime_status: 'exceeded' | 'healthy' | 'inactive' | 'warning';
  exhaustion_action: 'allow' | 'deny';
  exhaustion_http_status: null | number;
  exhaustion_error_code: null | number;
  exhaustion_message_preview: null | string;
  is_latest_scope_rule: boolean;
}

export interface AIQuotaCreateRequest {
  tenant_id: number;
  model_id?: null | number;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
}

export interface AIQuotaUpdateRequest {
  limit?: null | number;
  quota_type?: null | string;
  warning_threshold?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

const QUOTA_PREFIX = '/admin/ai/quotas';

export async function getAIQuotaListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIQuotaDiagnosticInfo>> {
  return requestClient.get<PageResponse<AIQuotaDiagnosticInfo>>(QUOTA_PREFIX, {
    params,
    ...options,
  });
}

export async function getAIQuotaSummaryApi(
  options?: ApiRequestOptions,
): Promise<AIQuotaDiagnosticsSummaryInfo> {
  return requestClient.get<AIQuotaDiagnosticsSummaryInfo>(
    `${QUOTA_PREFIX}/summary`,
    options,
  );
}

export async function getAIQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.get<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, options);
}

export async function createAIQuotaApi(
  data: AIQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.post<AIQuotaInfo>(QUOTA_PREFIX, data, options);
}

export async function updateAIQuotaApi(
  id: number,
  data: AIQuotaUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.put<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, data, options);
}

export async function deleteAIQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

export interface AIRateLimitInfo {
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

export interface AIRateLimitDiagnosticInfo extends AIRateLimitInfo {
  tenant_name: null | string;
  configured_rpm_limit: null | number;
  configured_tpm_limit: null | number;
  model_default_rpm_limit: null | number;
  model_default_tpm_limit: null | number;
  effective_rpm_limit: null | number;
  effective_tpm_limit: null | number;
  rpm_source: 'model' | 'none' | 'tenant';
  tpm_source: 'model' | 'none' | 'tenant';
  current_rpm: number;
  current_tpm: number;
  rpm_usage_percent: number;
  tpm_usage_percent: number;
  is_warning: boolean;
  is_exceeded: boolean;
  runtime_status: 'exceeded' | 'healthy' | 'inactive' | 'warning';
  exhaustion_action: 'deny';
  exhaustion_http_status: number;
  exhaustion_error_code: number;
  exhaustion_message_preview: null | string;
  is_latest_model_rule: boolean;
}

export interface AIRateLimitCreateRequest {
  tenant_id: number;
  model_id: number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
}

export interface AIRateLimitUpdateRequest {
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

const RATE_LIMIT_PREFIX = '/admin/ai/quotas/rate-limits';

export async function getAIRateLimitListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIRateLimitDiagnosticInfo>> {
  return requestClient.get<PageResponse<AIRateLimitDiagnosticInfo>>(
    RATE_LIMIT_PREFIX,
    {
      params,
      ...options,
    },
  );
}

export async function createAIRateLimitApi(
  data: AIRateLimitCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIRateLimitInfo> {
  return requestClient.post<AIRateLimitInfo>(RATE_LIMIT_PREFIX, data, options);
}

export async function updateAIRateLimitApi(
  id: number,
  data: AIRateLimitUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIRateLimitInfo> {
  return requestClient.put<AIRateLimitInfo>(
    `${RATE_LIMIT_PREFIX}/${id}`,
    data,
    options,
  );
}

export async function deleteAIRateLimitApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${RATE_LIMIT_PREFIX}/${id}`, options);
}

/**
 * AI management API - Aggregated entry / AI 管理 API - 聚合入口
 *
 * Sub-modules are split into separate files. This file provides:
 * 1. Backward-compatible re-exports (no need to change existing imports).
 * 2. Quotas and other APIs not yet split out.
 *
 * 各子模块已拆分到独立文件，此文件提供向后兼容 re-export 及尚未独立的 API。
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Backward-compat re-export — Agents / 向后兼容 re-export — 智能体
// ============================================================

export {
  type AIAgentAccessConfig,
  type AIAgentCreateRequest,
  type AIAgentInfo,
  type AIAgentKBBatchBindRequest,
  type AIAgentKBBindingInfo,
  type AIAgentKBBindingUpdateRequest,
  type AIAgentKBBindRequest,
  type AIAgentMemoryConfig,
  type AIAgentMemoryUpdateRequest,
  type AIAgentSkillBatchGrantRequest,
  type AIAgentSkillGrantInfo,
  type AIAgentSkillGrantRequest,
  type AIAgentSkillGrantUpdateRequest,
  type AIAgentUpdateRequest,
  type AIAgentVersionDetail,
  type AIAgentVersionDiff,
  type AIAgentVersionItem,
  batchBindAIAgentKBsApi,
  batchBindAIAgentSkillsApi,
  bindAIAgentKBApi,
  bindAIAgentSkillApi,
  createAIAgentApi,
  deleteAIAgentApi,
  diffAIAgentVersionsApi,
  getAIAgentAccessApi,
  getAIAgentDetailApi,
  getAIAgentKBsApi,
  getAIAgentListApi,
  getAIAgentMemoryConfigApi,
  getAIAgentRecycleBinApi,
  getAIAgentRecycleBinCountApi,
  getAIAgentSkillsApi,
  getAIAgentVersionDetailApi,
  getAIAgentVersionsApi,
  permanentDeleteAIAgentApi,
  publishAIAgentApi,
  restoreAIAgentApi,
  rollbackAIAgentApi,
  unbindAIAgentKBApi,
  unbindAIAgentSkillApi,
  updateAIAgentAccessApi,
  updateAIAgentApi,
  updateAIAgentKBBindingApi,
  updateAIAgentMemoryConfigApi,
  updateAIAgentSkillGrantApi,
  updateAIAgentStatusApi,
} from './ai-agents';

// ============================================================
// Backward-compat re-export — Call logs & Usage / 向后兼容 re-export — 调用日志与使用量
// ============================================================

export {
  type AICallLogInfo,
  getAICallLogDetailApi,
  getAICallLogFailedApi,
  getAICallLogListApi,
  getAICallLogStatisticsApi,
} from './ai-call-logs';

// ============================================================
// Backward-compat re-export — Conversations / 向后兼容 re-export — 对话
// ============================================================

export {
  type AIConversationInfo,
  getAIConversationDetailApi,
  getAIConversationListApi,
} from './ai-conversations';

// ============================================================
// Backward-compat re-export — Models / 向后兼容 re-export — 模型
// ============================================================

export {
  type AIModelConfig,
  type AIModelCreateRequest,
  type AIModelInfo,
  type AIModelReasoningConfig,
  type AIModelUpdateRequest,
  createAIModelApi,
  deleteAIModelApi,
  fetchRemoteModelsApi,
  getAIModelDetailApi,
  getAIModelListApi,
  getAIModelsByProviderApi,
  getAIModelSelectApi,
  type ModelProviderType,
  type ModelType,
  type ReasoningEffort,
  type RemoteModelCapabilities,
  type RemoteModelInfo,
  toggleAIModelStatusApi,
  updateAIModelApi,
} from './ai-models';

// ============================================================
// Backward-compat re-export — Providers, API Key, Health, Gateway test
// 向后兼容 re-export — 供应商、API Key、健康、网关测试
// ============================================================

export {
  type AdapterTypeInfo,
  type AIApiKeyCreateRequest,
  type AIApiKeyInfo,
  type AIApiKeyUpdateRequest,
  type AIHealthStatus,
  type AIProviderCreateRequest,
  type AIProviderInfo,
  type AIProviderUpdateRequest,
  type ProviderWebSearchConfig,
  type ProviderWebSearchRuntime,
  type ProviderWebSearchVerifiedTarget,
  createAIApiKeyApi,
  createAIProviderApi,
  deleteAIApiKeyApi,
  deleteAIProviderApi,
  getAdapterTypesApi,
  getAIApiKeyDetailApi,
  getAIApiKeyListApi,
  getAIApiKeysByProviderApi,
  getAIHealthStatusApi,
  getAIProviderDetailApi,
  getAIProviderListApi,
  getAIProviderSelectApi,
  type ProviderType,
  reorderAIProvidersApi,
  testAIGatewayApi,
  type TestAIGatewayRequest,
  type TestAIGatewayResult,
  toggleAIApiKeyStatusApi,
  toggleAIProviderStatusApi,
  updateAIApiKeyApi,
  updateAIProviderApi,
} from './ai-providers';

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
// Type definitions - AI quotas / 类型定义 - AI 配额
// ============================================================

/** AI quota info / AI 配额信息 */
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

/** AI quota diagnostics summary / AI 配额诊断总览 */
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

/** AI quota diagnostic item / AI 配额诊断项 */
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

/** Create quota request (admin) / 创建配额请求（管理员） */
export interface AIQuotaCreateRequest {
  tenant_id: number;
  model_id?: null | number;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
}

/** Update quota request / 更新配额请求 */
export interface AIQuotaUpdateRequest {
  limit?: null | number;
  quota_type?: null | string;
  warning_threshold?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

// ============================================================
// API - AI quotas / API 接口 - AI 配额
// ============================================================

const QUOTA_PREFIX = '/admin/ai/quotas';

/** Get quota list / 获取配额列表 */
export async function getAIQuotaListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIQuotaDiagnosticInfo>> {
  return requestClient.get<PageResponse<AIQuotaDiagnosticInfo>>(QUOTA_PREFIX, {
    params,
    ...options,
  });
}

/** Get quota diagnostics summary / 获取配额诊断总览 */
export async function getAIQuotaSummaryApi(
  options?: ApiRequestOptions,
): Promise<AIQuotaDiagnosticsSummaryInfo> {
  return requestClient.get<AIQuotaDiagnosticsSummaryInfo>(
    `${QUOTA_PREFIX}/summary`,
    options,
  );
}

/** Get quota detail / 获取配额详情 */
export async function getAIQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.get<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, options);
}

/** Create quota / 创建配额 */
export async function createAIQuotaApi(
  data: AIQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.post<AIQuotaInfo>(QUOTA_PREFIX, data, options);
}

/** Update quota / 更新配额 */
export async function updateAIQuotaApi(
  id: number,
  data: AIQuotaUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.put<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, data, options);
}

/** Delete quota / 删除配额 */
export async function deleteAIQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

// ============================================================
// Type definitions - Rate limits / 类型定义 - 速率限制
// ============================================================

/** Rate limit info / 速率限制信息 */
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

/** Rate limit diagnostic item / 速率限制诊断项 */
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

/** Create rate limit request (admin) / 创建速率限制请求 */
export interface AIRateLimitCreateRequest {
  tenant_id: number;
  model_id: number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
}

/** Update rate limit request / 更新速率限制请求 */
export interface AIRateLimitUpdateRequest {
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

// ============================================================
// API - Rate limits / API 接口 - 速率限制
// ============================================================

const RATE_LIMIT_PREFIX = '/admin/ai/quotas/rate-limits';

/** Get rate limit list / 获取速率限制列表 */
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

/** Create rate limit / 创建速率限制 */
export async function createAIRateLimitApi(
  data: AIRateLimitCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIRateLimitInfo> {
  return requestClient.post<AIRateLimitInfo>(RATE_LIMIT_PREFIX, data, options);
}

/** Update rate limit / 更新速率限制 */
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

/** Delete rate limit / 删除速率限制 */
export async function deleteAIRateLimitApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${RATE_LIMIT_PREFIX}/${id}`, options);
}

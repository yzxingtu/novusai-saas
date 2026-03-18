/**
 * AI management API - Aggregated entry / AI 管理 API - 聚合入口
 *
 * Sub-modules are split into separate files. This file provides:
 * 1. Backward-compatible re-exports (no need to change existing imports).
 * 2. Table policies, quotas, skills, and other APIs not yet split out.
 *
 * 各子模块已拆分到独立文件，此文件提供向后兼容 re-export 及尚未独立的 API。
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Backward-compat re-export — Providers, API Key, Health, Gateway test
// 向后兼容 re-export — 供应商、API Key、健康、网关测试
// ============================================================

export {
  type AIAgentAccessConfig,
  type AIAgentCreateRequest,
  type AIAgentInfo,
  type AIAgentMemoryConfig,
  type AIAgentMemoryUpdateRequest,
  type AIAgentKBBindingInfo,
  type AIAgentKBBindRequest,
  type AIAgentKBBatchBindRequest,
  type AIAgentKBBindingUpdateRequest,
  type AIAgentSkillBatchBindRequest,
  type AIAgentSkillBindingInfo,
  type AIAgentSkillBindingUpdateRequest,
  type AIAgentSkillBindRequest,
  type AIAgentUpdateRequest,
  type AIAgentVersionItem,
  batchBindAIAgentKBsApi,
  batchBindAIAgentSkillsApi,
  bindAIAgentKBApi,
  bindAIAgentSkillApi,
  createAIAgentApi,
  deleteAIAgentApi,
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
  updateAIAgentSkillBindingApi,
  updateAIAgentStatusApi,
} from './ai-agents';

// ============================================================
// Backward-compat re-export — Models / 向后兼容 re-export — 模型
// ============================================================

export {
  type AICallLogInfo,
  type AIUsageStatInfo,
  getAICallLogDetailApi,
  getAICallLogFailedApi,
  getAICallLogListApi,
  getAICallLogStatisticsApi,
  getAIModelUsageSummaryApi,
  getAITenantUsageSummaryApi,
  getAIUsageStatsApi,
} from './ai-call-logs';

// ============================================================
// Backward-compat re-export — Agents / 向后兼容 re-export — 智能体
// ============================================================

export {
  type AIConversationInfo,
  getAIConversationDetailApi,
  getAIConversationListApi,
} from './ai-conversations';

// ============================================================
// Backward-compat re-export — Call logs & Usage / 向后兼容 re-export — 调用日志 & 使用量
// ============================================================

export {
  type AIModelCreateRequest,
  type AIModelInfo,
  type AIModelUpdateRequest,
  createAIModelApi,
  deleteAIModelApi,
  fetchRemoteModelsApi,
  getAIModelDetailApi,
  getAIModelListApi,
  getAIModelSelectApi,
  getAIModelsByProviderApi,
  type ModelType,
  type RemoteModelCapabilities,
  type RemoteModelInfo,
  toggleAIModelStatusApi,
  updateAIModelApi,
} from './ai-models';

// ============================================================
// Backward-compat re-export — Conversations / 向后兼容 re-export — 对话管理
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
// Type definitions - AI table policies / 类型定义 - AI 表策略
// ============================================================

/** AI table policy info / AI 表策略信息 */
export interface AITablePolicyInfo {
  id: number;
  table_name: string;
  label: string;
  description: null | string;
  keywords: null | string[];
  column_descriptions: null | Record<string, string>;
  allow_read: boolean;
  allow_create: boolean;
  allow_update: boolean;
  allow_delete: boolean;
  max_rows: number;
  blocked_columns: null | string[];
  readonly_columns: null | string[];
  permission_code: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Update table policy request / 更新表策略请求 */
export interface AITablePolicyUpdateRequest {
  label?: string;
  description?: null | string;
  keywords?: null | string[];
  column_descriptions?: null | Record<string, string>;
  allow_read?: boolean;
  allow_create?: boolean;
  allow_update?: boolean;
  allow_delete?: boolean;
  max_rows?: number;
  blocked_columns?: null | string[];
  readonly_columns?: null | string[];
  permission_code?: string;
  sort_order?: number;
  is_active?: boolean;
}

/** Table column info / 表列信息 */
export interface TableColumnInfo {
  name: string;
  type: string;
  comment: string;
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
// API - AI table policies / API 接口 - AI 表策略
// ============================================================

const TABLE_POLICY_PREFIX = '/admin/ai/table-policies';

/** Get table policy list / 获取表策略列表 */
export async function getAITablePolicyListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AITablePolicyInfo>> {
  return requestClient.get<PageResponse<AITablePolicyInfo>>(
    TABLE_POLICY_PREFIX,
    { params, ...options },
  );
}

/** Get table policy detail / 获取表策略详情 */
export async function getAITablePolicyDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AITablePolicyInfo> {
  return requestClient.get<AITablePolicyInfo>(
    `${TABLE_POLICY_PREFIX}/${id}`,
    options,
  );
}

/** Update table policy / 更新表策略 */
export async function updateAITablePolicyApi(
  id: number,
  data: AITablePolicyUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AITablePolicyInfo> {
  return requestClient.put<AITablePolicyInfo>(
    `${TABLE_POLICY_PREFIX}/${id}`,
    data,
    options,
  );
}

/** Get table column info / 获取表的列信息 */
export async function getAITablePolicyColumnsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TableColumnInfo[]> {
  return requestClient.get<TableColumnInfo[]>(
    `${TABLE_POLICY_PREFIX}/${id}/columns`,
    options,
  );
}

/** Trigger table policy sync / 触发表策略同步 */
export async function syncAITablePoliciesApi(
  options?: ApiRequestOptions,
): Promise<Record<string, number> & { declared_tables?: string[] }> {
  return requestClient.post<Record<string, number> & { declared_tables?: string[] }>(
    `${TABLE_POLICY_PREFIX}/sync`,
    {},
    options,
  );
}

/** Get declared table names (models with __ai_policy__) / 获取声明了 __ai_policy__ 的表名列表 */
export async function getAITablePolicyDeclaredTablesApi(
  options?: ApiRequestOptions,
): Promise<string[]> {
  return requestClient.get<string[]>(
    `${TABLE_POLICY_PREFIX}/declared-tables`,
    options,
  );
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
): Promise<PageResponse<AIQuotaInfo>> {
  return requestClient.get<PageResponse<AIQuotaInfo>>(QUOTA_PREFIX, {
    params,
    ...options,
  });
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
): Promise<AIRateLimitInfo[]> {
  return requestClient.get<AIRateLimitInfo[]>(RATE_LIMIT_PREFIX, {
    params,
    ...options,
  });
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

// ============================================================
// Skill management / 技能管理 (Skill)
// ============================================================

const SKILL_PREFIX = '/admin/ai/skills';

/** Skill info / 技能信息 */
export interface SkillInfo {
  id: number;
  tenant_id: null | number;
  name: string;
  description: null | string;
  avatar: null | string;
  type: string;
  scope: string;
  is_active: boolean;
  sort_order: number;
  timeout: number;
  created_at: string;
  updated_at: string;
}

/** Get skill list / 获取技能列表 */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
) {
  return requestClient.get(SKILL_PREFIX, { params, ...options });
}

/** Get skill detail / 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.get<SkillInfo>(`${SKILL_PREFIX}/${id}`, options);
}

/** Toggle skill status / 切换技能状态 */
export async function toggleSkillStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.put<SkillInfo>(
    `${SKILL_PREFIX}/${id}/status`,
    {},
    options,
  );
}

/** Delete skill / 删除技能 */
export async function deleteSkillApi(id: number, options?: ApiRequestOptions) {
  return requestClient.delete(`${SKILL_PREFIX}/${id}`, options);
}

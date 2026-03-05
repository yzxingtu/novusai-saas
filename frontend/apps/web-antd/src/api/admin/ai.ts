/**
 * AI 管理 API - 聚合入口
 *
 * 各子模块已拆分到独立文件，此文件提供：
 * 1. 向后兼容的 re-export（现有 import 无需修改）
 * 2. 表策略、配额、技能等尚未独立的 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 向后兼容 re-export — 供应商、API Key、健康、网关测试
// ============================================================

export {
  type AIAgentAccessConfig,
  type AIAgentCreateRequest,
  type AIAgentInfo,
  type AIAgentMemoryConfig,
  type AIAgentMemoryUpdateRequest,
  type AIAgentSkillBatchBindRequest,
  type AIAgentSkillBindingInfo,
  type AIAgentSkillBindingUpdateRequest,
  type AIAgentSkillBindRequest,
  type AIAgentUpdateRequest,
  type AIAgentVersionItem,
  batchBindAIAgentSkillsApi,
  bindAIAgentSkillApi,
  createAIAgentApi,
  deleteAIAgentApi,
  getAIAgentAccessApi,
  getAIAgentDetailApi,
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
  unbindAIAgentSkillApi,
  updateAIAgentAccessApi,
  updateAIAgentApi,
  updateAIAgentMemoryConfigApi,
  updateAIAgentSkillBindingApi,
  updateAIAgentStatusApi,
} from './ai-agents';

// ============================================================
// 向后兼容 re-export — 模型
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
// 向后兼容 re-export — 智能体
// ============================================================

export {
  type AIConversationInfo,
  getAIConversationDetailApi,
  getAIConversationListApi,
} from './ai-conversations';

// ============================================================
// 向后兼容 re-export — 调用日志 & 使用量
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
  getAIModelsByProviderApi,
  type ModelType,
  type RemoteModelInfo,
  toggleAIModelStatusApi,
  updateAIModelApi,
} from './ai-models';

// ============================================================
// 向后兼容 re-export — 对话管理
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
// 类型定义 - AI 表策略
// ============================================================

/** AI 表策略信息 */
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

/** 更新表策略请求 */
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

/** 表列信息 */
export interface TableColumnInfo {
  name: string;
  type: string;
  comment: string;
}

// ============================================================
// 通用分页响应
// ============================================================

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口 - AI 表策略
// ============================================================

const TABLE_POLICY_PREFIX = '/admin/ai/table-policies';

/** 获取表策略列表 */
export async function getAITablePolicyListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AITablePolicyInfo>> {
  return requestClient.get<PageResponse<AITablePolicyInfo>>(
    TABLE_POLICY_PREFIX,
    { params, ...options },
  );
}

/** 获取表策略详情 */
export async function getAITablePolicyDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AITablePolicyInfo> {
  return requestClient.get<AITablePolicyInfo>(
    `${TABLE_POLICY_PREFIX}/${id}`,
    options,
  );
}

/** 更新表策略 */
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

/** 获取表的列信息 */
export async function getAITablePolicyColumnsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<TableColumnInfo[]> {
  return requestClient.get<TableColumnInfo[]>(
    `${TABLE_POLICY_PREFIX}/${id}/columns`,
    options,
  );
}

/** 触发表策略同步 */
export async function syncAITablePoliciesApi(
  options?: ApiRequestOptions,
): Promise<Record<string, number>> {
  return requestClient.post<Record<string, number>>(
    `${TABLE_POLICY_PREFIX}/sync`,
    {},
    options,
  );
}

// ============================================================
// 类型定义 - AI 配额
// ============================================================

/** AI 配额信息 */
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

/** 创建配额请求（管理员） */
export interface AIQuotaCreateRequest {
  tenant_id: number;
  model_id?: null | number;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: null | number;
  description?: null | string;
}

/** 更新配额请求 */
export interface AIQuotaUpdateRequest {
  limit?: null | number;
  quota_type?: null | string;
  warning_threshold?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

// ============================================================
// API 接口 - AI 配额
// ============================================================

const QUOTA_PREFIX = '/admin/ai/quotas';

/** 获取配额列表 */
export async function getAIQuotaListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIQuotaInfo>> {
  return requestClient.get<PageResponse<AIQuotaInfo>>(QUOTA_PREFIX, {
    params,
    ...options,
  });
}

/** 获取配额详情 */
export async function getAIQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.get<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, options);
}

/** 创建配额 */
export async function createAIQuotaApi(
  data: AIQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.post<AIQuotaInfo>(QUOTA_PREFIX, data, options);
}

/** 更新配额 */
export async function updateAIQuotaApi(
  id: number,
  data: AIQuotaUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.put<AIQuotaInfo>(`${QUOTA_PREFIX}/${id}`, data, options);
}

/** 删除配额 */
export async function deleteAIQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

// ============================================================
// 类型定义 - 速率限制
// ============================================================

/** 速率限制信息 */
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

/** 创建速率限制请求（管理员） */
export interface AIRateLimitCreateRequest {
  tenant_id: number;
  model_id: number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
}

/** 更新速率限制请求 */
export interface AIRateLimitUpdateRequest {
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  description?: null | string;
  is_active?: boolean | null;
}

// ============================================================
// API 接口 - 速率限制
// ============================================================

const RATE_LIMIT_PREFIX = '/admin/ai/quotas/rate-limits';

/** 获取速率限制列表 */
export async function getAIRateLimitListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AIRateLimitInfo[]> {
  return requestClient.get<AIRateLimitInfo[]>(RATE_LIMIT_PREFIX, {
    params,
    ...options,
  });
}

/** 创建速率限制 */
export async function createAIRateLimitApi(
  data: AIRateLimitCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIRateLimitInfo> {
  return requestClient.post<AIRateLimitInfo>(RATE_LIMIT_PREFIX, data, options);
}

/** 更新速率限制 */
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

/** 删除速率限制 */
export async function deleteAIRateLimitApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${RATE_LIMIT_PREFIX}/${id}`, options);
}

// ============================================================
// 技能管理 (Skill)
// ============================================================

const SKILL_PREFIX = '/admin/ai/skills';

/** 技能信息 */
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

/** 获取技能列表 */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
) {
  return requestClient.get(SKILL_PREFIX, { params, ...options });
}

/** 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.get<SkillInfo>(`${SKILL_PREFIX}/${id}`, options);
}

/** 切换技能状态 */
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

/** 删除技能 */
export async function deleteSkillApi(id: number, options?: ApiRequestOptions) {
  return requestClient.delete(`${SKILL_PREFIX}/${id}`, options);
}

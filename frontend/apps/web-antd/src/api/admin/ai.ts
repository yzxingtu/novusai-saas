/**
 * AI 网关管理 API
 * 对接后端 /admin/ai/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义 - AI 供应商
// ============================================================

/** 供应商类型 */
export type ProviderType = string;

/** 适配器类型信息 */
export interface AdapterTypeInfo {
  type: string;
  source: 'builtin' | 'plugin';
  plugin_name?: null | string;
  display_name: string;
  icon?: null | string;
  supports?: Record<string, boolean>;
  models?: Array<{ code: string; name: string }>;
}

/** AI 供应商信息 */
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

/** 创建供应商请求 */
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

/** 更新供应商请求 */
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
// 类型定义 - AI 模型
// ============================================================

/** 模型类型 */
export type ModelType = 'chat' | 'embedding' | 'image';

/** AI 模型信息 */
export interface AIModelInfo {
  id: number;
  provider_id: number;
  name: string;
  code: string;
  type: ModelType;
  context_window: null | number;
  max_output_tokens: null | number;
  input_price_per_1k: null | number;
  output_price_per_1k: null | number;
  rpm_limit: null | number;
  tpm_limit: null | number;
  supports_function_calling: boolean;
  supports_vision: boolean;
  supports_streaming: boolean;
  is_active: boolean;
  config: null | Record<string, unknown>;
  provider_name: null | string;
  created_at: string;
  updated_at: string;
}

/** 创建模型请求 */
export interface AIModelCreateRequest {
  provider_id: number;
  name: string;
  code: string;
  type: ModelType;
  context_window?: null | number;
  max_output_tokens?: null | number;
  input_price_per_1k?: null | number;
  output_price_per_1k?: null | number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  supports_function_calling?: boolean;
  supports_vision?: boolean;
  supports_streaming?: boolean;
  is_active?: boolean;
  config?: null | Record<string, unknown>;
}

/** 更新模型请求 */
export interface AIModelUpdateRequest {
  provider_id?: null | number;
  name?: null | string;
  code?: null | string;
  type?: null | string;
  context_window?: null | number;
  max_output_tokens?: null | number;
  input_price_per_1k?: null | number;
  output_price_per_1k?: null | number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  supports_function_calling?: boolean | null;
  supports_vision?: boolean | null;
  supports_streaming?: boolean | null;
  is_active?: boolean | null;
  config?: null | Record<string, unknown>;
}

// ============================================================
// 类型定义 - API Key
// ============================================================

/** API Key 信息 */
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

/** 创建 API Key 请求 */
export interface AIApiKeyCreateRequest {
  provider_id: number;
  tenant_id?: null | number;
  name: string;
  api_key: string;
  is_active?: boolean;
  usage_limit?: null | number;
  expires_at?: null | string;
}

/** 更新 API Key 请求 */
export interface AIApiKeyUpdateRequest {
  name?: null | string;
  is_active?: boolean | null;
  usage_limit?: null | number;
  expires_at?: null | string;
}

// ============================================================
// 类型定义 - 调用日志
// ============================================================

/** 调用日志信息 */
export interface AICallLogInfo {
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
  created_at: string;
  // 关联名称
  model_name?: null | string;
  provider_name?: null | string;
  tenant_name?: null | string;
  // 详情字段（仅详情 API 返回）
  request_data?: null | Record<string, unknown>;
  response_data?: null | Record<string, unknown>;
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
// API 接口 - AI 供应商
// ============================================================

const PROVIDER_PREFIX = '/admin/ai/providers';

/** 获取供应商列表 */
export async function getAIProviderListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIProviderInfo>> {
  return requestClient.get<PageResponse<AIProviderInfo>>(
    PROVIDER_PREFIX,
    { params, ...options },
  );
}

/** 获取可用适配器类型列表（内置 + 插件） */
export async function getAdapterTypesApi(
  options?: ApiRequestOptions,
): Promise<AdapterTypeInfo[]> {
  return requestClient.get<AdapterTypeInfo[]>(
    `${PROVIDER_PREFIX}/adapter-types`,
    options,
  );
}

/** 获取供应商详情 */
export async function getAIProviderDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.get<AIProviderInfo>(
    `${PROVIDER_PREFIX}/${id}`,
    options,
  );
}

/** 创建供应商 */
export async function createAIProviderApi(
  data: AIProviderCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIProviderInfo> {
  return requestClient.post<AIProviderInfo>(
    PROVIDER_PREFIX,
    data,
    options,
  );
}

/** 更新供应商 */
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

/** 删除供应商 */
export async function deleteAIProviderApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PROVIDER_PREFIX}/${id}`, options);
}

/** 切换供应商状态 */
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

/** 批量重排序供应商 */
export async function reorderAIProvidersApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(`${PROVIDER_PREFIX}/reorder`, { ids }, options);
}

// ============================================================
// API 接口 - AI 模型
// ============================================================

const MODEL_PREFIX = '/admin/ai/models';

/** 获取模型列表 */
export async function getAIModelListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIModelInfo>> {
  return requestClient.get<PageResponse<AIModelInfo>>(
    MODEL_PREFIX,
    { params, ...options },
  );
}

/** 获取供应商的模型列表 */
export async function getAIModelsByProviderApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo[]> {
  return requestClient.get<AIModelInfo[]>(
    `${MODEL_PREFIX}/provider/${providerId}`,
    options,
  );
}

/** 远程模型信息（从供应商 API 拉取） */
export interface RemoteModelInfo {
  id: string;
  owned_by: null | string;
}

/** 从供应商远程拉取可用模型列表 */
export async function fetchRemoteModelsApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<RemoteModelInfo[]> {
  return requestClient.get<RemoteModelInfo[]>(
    `${MODEL_PREFIX}/fetch-remote/${providerId}`,
    options,
  );
}

/** 获取模型详情 */
export async function getAIModelDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.get<AIModelInfo>(
    `${MODEL_PREFIX}/${id}`,
    options,
  );
}

/** 创建模型 */
export async function createAIModelApi(
  data: AIModelCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.post<AIModelInfo>(
    MODEL_PREFIX,
    data,
    options,
  );
}

/** 更新模型 */
export async function updateAIModelApi(
  id: number,
  data: AIModelUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.put<AIModelInfo>(
    `${MODEL_PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除模型 */
export async function deleteAIModelApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${MODEL_PREFIX}/${id}`, options);
}

/** 切换模型状态 */
export async function toggleAIModelStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.put<AIModelInfo>(
    `${MODEL_PREFIX}/${id}/status`,
    {},
    options,
  );
}

// ============================================================
// API 接口 - API Key
// ============================================================

const API_KEY_PREFIX = '/admin/ai/api-keys';

/** 获取 API Key 列表 */
export async function getAIApiKeyListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIApiKeyInfo>> {
  return requestClient.get<PageResponse<AIApiKeyInfo>>(
    API_KEY_PREFIX,
    { params, ...options },
  );
}

/** 获取供应商的 API Key 列表 */
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

/** 获取 API Key 详情 */
export async function getAIApiKeyDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.get<AIApiKeyInfo>(
    `${API_KEY_PREFIX}/${id}`,
    options,
  );
}

/** 创建 API Key */
export async function createAIApiKeyApi(
  data: AIApiKeyCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIApiKeyInfo> {
  return requestClient.post<AIApiKeyInfo>(
    API_KEY_PREFIX,
    data,
    options,
  );
}

/** 更新 API Key */
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

/** 删除 API Key */
export async function deleteAIApiKeyApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_KEY_PREFIX}/${id}`, options);
}

/** 切换 API Key 状态 */
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
// API 接口 - 调用日志
// ============================================================

const CALL_LOG_PREFIX = '/admin/ai/call-logs';

/** 获取调用日志列表 */
export async function getAICallLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AICallLogInfo>> {
  return requestClient.get<PageResponse<AICallLogInfo>>(
    CALL_LOG_PREFIX,
    { params, ...options },
  );
}

/** 获取调用日志详情 */
export async function getAICallLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AICallLogInfo> {
  return requestClient.get<AICallLogInfo>(
    `${CALL_LOG_PREFIX}/${id}`,
    options,
  );
}

/** 获取调用统计 */
export async function getAICallLogStatisticsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${CALL_LOG_PREFIX}/statistics`,
    { params, ...options },
  );
}

/** 获取失败的调用日志 */
export async function getAICallLogFailedApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AICallLogInfo[]> {
  return requestClient.get<AICallLogInfo[]>(
    `${CALL_LOG_PREFIX}/failed`,
    { params, ...options },
  );
}

// ============================================================
// 类型定义 - AI 使用量统计
// ============================================================

/** 使用量统计记录 */
export interface AIUsageStatInfo {
  id: number;
  tenant_id: number;
  user_id: number | null;
  model_id: number;
  request_type: string;
  stat_date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  call_count: number;
  success_count: number;
  failed_count: number;
  total_cost: number;
  avg_latency_ms: number | null;
  max_latency_ms: number | null;
  // 关联名称
  tenant_name?: null | string;
  model_name?: null | string;
  created_at: string;
  updated_at: string;
}

// ============================================================
// API 接口 - AI 使用量统计
// ============================================================

const USAGE_PREFIX = '/admin/ai/usage';

/** 获取使用量统计列表 */
export async function getAIUsageStatsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIUsageStatInfo>> {
  return requestClient.get<PageResponse<AIUsageStatInfo>>(
    `${USAGE_PREFIX}/stats`,
    { params, ...options },
  );
}

/** 获取租户使用量汇总 */
export async function getAITenantUsageSummaryApi(
  tenantId: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${USAGE_PREFIX}/summary/tenant/${tenantId}`,
    { params, ...options },
  );
}

/** 获取模型使用量汇总 */
export async function getAIModelUsageSummaryApi(
  modelId: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${USAGE_PREFIX}/summary/model/${modelId}`,
    { params, ...options },
  );
}

// ============================================================
// 类型定义 - AI 健康状态
// ============================================================

/** 供应商健康状态 */
export interface AIHealthStatus {
  provider_id: number;
  provider_code: string;
  provider_name: string;
  is_healthy: boolean;
  is_available: boolean;
  response_time_ms: number;
  consecutive_failures: number;
  error_message: string | null;
  checked_at: string;
}

// ============================================================
// API 接口 - AI 健康状态
// ============================================================

/** 获取 AI 供应商健康状态 */
export async function getAIHealthStatusApi(
  options?: ApiRequestOptions,
): Promise<AIHealthStatus[]> {
  return requestClient.get<AIHealthStatus[]>('/admin/ai/health', options);
}

// ============================================================
// 类型定义 - AI 网关测试
// ============================================================

/** 模型测试请求 */
export interface TestAIGatewayRequest {
  provider_id: number;
  model_code: string;
  test_prompt?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
}

/** 模型测试结果 */
export interface TestAIGatewayResult {
  connected: boolean;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  response_text: string;
  error: string | null;
  model: string;
  provider: string;
}

// ============================================================
// API 接口 - AI 网关测试
// ============================================================

// ============================================================
// 类型定义 - 智能体管理
// ============================================================

/** 智能体信息 */
export interface AIAgentInfo {
  id: number;
  tenant_id: number | null;
  name: string;
  description: null | string;
  avatar: null | string;
  scope: string;
  status: string;
  execution_mode: string;
  is_system: boolean;
  model_id: number;
  model_name: null | string;
  skill_packages: { id: number; name: string }[];
  published_version: null | number;
  welcome_message: null | string;
  suggested_questions: string[] | null;
  system_prompt: null | string;
  temperature: number;
  max_tokens: number;
  knowledge_base_ids: number[] | null;
  tool_ids: number[] | null;
  created_at: string;
  updated_at: string;
}

/** 创建智能体请求 */
export interface AIAgentCreateRequest {
  name: string;
  description?: null | string;
  scope: string;
  tenant_id?: number | null;
  model_id: number;
  execution_mode?: string;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  knowledge_base_ids?: number[];
  tool_ids?: number[];
}

/** 更新智能体请求 */
export interface AIAgentUpdateRequest {
  name?: string;
  description?: null | string;
  scope?: string;
  tenant_id?: number | null;
  model_id?: number;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  knowledge_base_ids?: number[];
  tool_ids?: number[];
}

// ============================================================
// API 接口 - 智能体管理（平台）
// ============================================================

const AGENT_PREFIX = '/admin/ai/agents';

/** 获取智能体列表 */
export async function getAIAgentListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIAgentInfo>> {
  return requestClient.get<PageResponse<AIAgentInfo>>(
    AGENT_PREFIX,
    { params, ...options },
  );
}

/** 获取智能体详情 */
export async function getAIAgentDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.get<AIAgentInfo>(
    `${AGENT_PREFIX}/${id}`,
    options,
  );
}

/** 更新智能体状态 */
export async function updateAIAgentStatusApi(
  id: number,
  status: string,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.put<AIAgentInfo>(
    `${AGENT_PREFIX}/${id}/status`,
    {},
    { params: { status }, ...options },
  );
}

/** 创建智能体 */
export async function createAIAgentApi(
  data: AIAgentCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(AGENT_PREFIX, data, options);
}

/** 更新智能体 */
export async function updateAIAgentApi(
  id: number,
  data: AIAgentUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.put<AIAgentInfo>(
    `${AGENT_PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除智能体 */
export async function deleteAIAgentApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${AGENT_PREFIX}/${id}`, options);
}

// ============================================================
// API 接口 - 智能体技能绑定（平台）
// ============================================================

/** 技能绑定信息 */
export interface AIAgentSkillBindingInfo {
  id: number;
  agent_id: number;
  package_id: number;
  enabled: boolean;
  config_override: Record<string, unknown> | null;
  sort_order: number;
  consent_mode: string;
  package_name: string | null;
  package_description: string | null;
  package_scope: string | null;
}

/** 绑定技能包请求 */
export interface AIAgentSkillBindRequest {
  package_id: number;
  config_override?: Record<string, unknown> | null;
  sort_order?: number;
  consent_mode?: string;
}

/** 批量绑定请求 */
export interface AIAgentSkillBatchBindRequest {
  package_ids: number[];
}

/** 更新绑定请求 */
export interface AIAgentSkillBindingUpdateRequest {
  enabled?: boolean | null;
  config_override?: Record<string, unknown> | null;
  sort_order?: number | null;
  consent_mode?: string | null;
}

/** 获取智能体技能绑定列表 */
export async function getAIAgentSkillsApi(
  agentId: number,
): Promise<AIAgentSkillBindingInfo[]> {
  return requestClient.get<AIAgentSkillBindingInfo[]>(
    `${AGENT_PREFIX}/${agentId}/skills`,
  );
}

/** 绑定技能包到智能体 */
export async function bindAIAgentSkillApi(
  agentId: number,
  data: AIAgentSkillBindRequest,
): Promise<AIAgentSkillBindingInfo> {
  return requestClient.post<AIAgentSkillBindingInfo>(
    `${AGENT_PREFIX}/${agentId}/skills`,
    data,
  );
}

/** 批量绑定技能包（替换模式） */
export async function batchBindAIAgentSkillsApi(
  agentId: number,
  data: AIAgentSkillBatchBindRequest,
): Promise<AIAgentSkillBindingInfo[]> {
  return requestClient.put<AIAgentSkillBindingInfo[]>(
    `${AGENT_PREFIX}/${agentId}/skills/batch`,
    data,
  );
}

/** 更新技能绑定配置 */
export async function updateAIAgentSkillBindingApi(
  agentId: number,
  bindingId: number,
  data: AIAgentSkillBindingUpdateRequest,
): Promise<AIAgentSkillBindingInfo> {
  return requestClient.put<AIAgentSkillBindingInfo>(
    `${AGENT_PREFIX}/${agentId}/skills/${bindingId}`,
    data,
  );
}

/** 解绑技能包 */
export async function unbindAIAgentSkillApi(
  agentId: number,
  packageId: number,
): Promise<void> {
  await requestClient.delete(
    `${AGENT_PREFIX}/${agentId}/skills/${packageId}`,
  );
}

/** 测试 AI 模型连通性 */
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

// ============================================================
// 类型定义 - AI 配额
// ============================================================

/** AI 配额信息 */
export interface AIQuotaInfo {
  id: number;
  tenant_id: number;
  model_id: number | null;
  period: string;
  limit: number;
  quota_type: string;
  warning_threshold: number | null;
  is_active: boolean;
  description: string | null;
  tenant_name: string | null;
  model_name: string | null;
  created_at: string;
  updated_at: string;
}

/** 创建配额请求（管理员） */
export interface AIQuotaCreateRequest {
  tenant_id: number;
  model_id?: number | null;
  period: string;
  limit: number;
  quota_type?: string;
  warning_threshold?: number | null;
  description?: string | null;
}

/** 更新配额请求 */
export interface AIQuotaUpdateRequest {
  limit?: number | null;
  quota_type?: string | null;
  warning_threshold?: number | null;
  description?: string | null;
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
  return requestClient.get<PageResponse<AIQuotaInfo>>(
    QUOTA_PREFIX,
    { params, ...options },
  );
}

/** 获取配额详情 */
export async function getAIQuotaDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.get<AIQuotaInfo>(
    `${QUOTA_PREFIX}/${id}`,
    options,
  );
}

/** 创建配额 */
export async function createAIQuotaApi(
  data: AIQuotaCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.post<AIQuotaInfo>(
    QUOTA_PREFIX,
    data,
    options,
  );
}

/** 更新配额 */
export async function updateAIQuotaApi(
  id: number,
  data: AIQuotaUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIQuotaInfo> {
  return requestClient.put<AIQuotaInfo>(
    `${QUOTA_PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除配额 */
export async function deleteAIQuotaApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${QUOTA_PREFIX}/${id}`, options);
}

// ============================================================
// 类型定义 - 对话监控
// ============================================================

/** 管理端对话列表项 */
export interface AIConversationInfo {
  id: number;
  tenant_id: number;
  agent_id: number;
  user_id: number | null;
  title: string | null;
  status: string;
  token_count: number;
  cost: number;
  agent_name: string | null;
  created_at: string;
  updated_at: string;
}

// ============================================================
// API 接口 - 对话监控
// ============================================================

const CONV_PREFIX = '/admin/ai/conversations';

/** 获取全租户对话列表 */
export async function getAIConversationListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIConversationInfo>> {
  return requestClient.get<PageResponse<AIConversationInfo>>(
    CONV_PREFIX,
    { params, ...options },
  );
}

/** 获取对话详情 */
export async function getAIConversationDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${CONV_PREFIX}/${id}`,
    options,
  );
}

// ============================================================
// 类型定义 - AI 表策略
// ============================================================

/** AI 表策略信息 */
export interface AITablePolicyInfo {
  id: number;
  table_name: string;
  label: string;
  description: string | null;
  keywords: string[] | null;
  column_descriptions: Record<string, string> | null;
  allow_read: boolean;
  allow_create: boolean;
  allow_update: boolean;
  allow_delete: boolean;
  max_rows: number;
  blocked_columns: string[] | null;
  readonly_columns: string[] | null;
  permission_code: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 更新表策略请求 */
export interface AITablePolicyUpdateRequest {
  label?: string;
  description?: string | null;
  keywords?: string[] | null;
  column_descriptions?: Record<string, string> | null;
  allow_read?: boolean;
  allow_create?: boolean;
  allow_update?: boolean;
  allow_delete?: boolean;
  max_rows?: number;
  blocked_columns?: string[] | null;
  readonly_columns?: string[] | null;
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
export async function deleteSkillApi(
  id: number,
  options?: ApiRequestOptions,
) {
  return requestClient.delete(`${SKILL_PREFIX}/${id}`, options);
}

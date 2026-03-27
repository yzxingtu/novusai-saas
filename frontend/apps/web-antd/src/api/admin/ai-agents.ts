/**
 * AI agent management API (platform level) / AI 智能体管理 API（平台级）
 * Backend: /admin/ai/agents
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions - Agent management / 类型定义 - 智能体管理
// ============================================================

/** Agent info / 智能体信息 */
export interface AIAgentInfo {
  id: number;
  tenant_id: null | number;
  owner_tenant_id?: null | number;
  name: string;
  description: null | string;
  avatar: null | string;
  /** 统一资源作用域 ResourceScopeEnum */
  scope: string;
  /**
   * 展示用：由 owner_tenant_id 派生（有值 tenant / 无值 platform），非历史 DB 列 owner_type。
   * Display-only: derived from owner_tenant_id; not the legacy agents.owner_type column.
   */
  owner_type: string;
  status: string;
  execution_mode: string;
  is_system: boolean;
  model_id: number;
  model_name: null | string;
  skills: { id: number; name: string }[];
  published_version: null | number;
  welcome_message: null | string;
  suggested_questions: null | string[];
  system_prompt: null | string;
  temperature: number;
  max_tokens: null | number;
  top_p: null | number;
  knowledge_base_ids: null | number[];
  routing_config: null | Record<string, unknown>;
  quota_config: null | Record<string, unknown>;
  context_config: null | Record<string, unknown>;
  input_variables: null | Record<string, unknown>[];
  output_schema?: null | unknown[];
  rag_config?: AgentRagConfig | null;
  assigned_tenant_ids?: number[];
  created_at: string;
  updated_at: string;
}

export interface AgentRagConfig {
  search_mode?: 'hybrid' | 'keyword' | 'vector';
  top_k?: number;
  score_threshold?: number;
  rewrite_strategy?: 'hyde' | 'multi' | 'none';
  reranker_enabled?: boolean;
  context_token_ratio?: number;
}

/** Create agent request / 创建智能体请求 */
export interface AIAgentCreateRequest {
  name: string;
  description?: null | string;
  scope: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  model_id: number;
  execution_mode?: string;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  knowledge_base_ids?: number[];
  rag_config?: AgentRagConfig | null;
}

/** Update agent request / 更新智能体请求 */
export interface AIAgentUpdateRequest {
  name?: string;
  description?: null | string;
  avatar?: null | string;
  scope?: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  model_id?: number;
  execution_mode?: string;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  top_p?: null | number;
  welcome_message?: null | string;
  suggested_questions?: string[];
  routing_config?: null | Record<string, unknown>;
  quota_config?: null | Record<string, unknown>;
  context_config?: null | Record<string, unknown>;
  knowledge_base_ids?: number[];
  output_schema?: null | unknown[];
  rag_config?: AgentRagConfig | null;
}

/** Agent memory config (admin) / 智能体记忆配置（管理端） */
export interface AIAgentMemoryConfig {
  agent_id: number;
  platform_default_memory_enabled: boolean;
  admin_agent_memory_enabled: boolean;
  tenant_agent_memory_disabled: boolean;
  effective_memory_enabled: boolean;
}

/** Update agent memory toggle request (admin) / 更新智能体记忆开关请求 */
export interface AIAgentMemoryUpdateRequest {
  enabled: boolean;
}

// ============================================================
// Type definitions - Agent skill grants / 类型定义 - 智能体技能授权
// ============================================================

/** Skill grant info / 技能授权信息 */
export interface AIAgentSkillGrantInfo {
  id: null | number;
  agent_id: number;
  skill_id: number;
  enabled: boolean;
  config_override: null | Record<string, unknown>;
  sort_order: number;
  default_consent_mode: string;
  capability_consent_overrides: null | Record<string, string>;
  skill_name: null | string;
  skill_key: null | string;
  skill_description: null | string;
  skill_type: null | string;
  skill_source_type: null | string;
  skill_status: null | string;
  package_name: null | string;
  package_description: null | string;
  package_is_system: boolean;
}

/** Bind skill request / 绑定技能请求 */
export interface AIAgentSkillGrantRequest {
  skill_id: number;
  config_override?: null | Record<string, unknown>;
  sort_order?: number;
  default_consent_mode?: string;
  capability_consent_overrides?: null | Record<string, string>;
}

/** Batch grant request / 批量授权请求 */
export interface AIAgentSkillBatchGrantRequest {
  skill_ids: number[];
  default_consent_modes?: Record<string, string>;
}

/** Update skill grant request / 更新技能授权请求 */
export interface AIAgentSkillGrantUpdateRequest {
  enabled?: boolean | null;
  config_override?: null | Record<string, unknown>;
  sort_order?: null | number;
  default_consent_mode?: null | string;
  capability_consent_overrides?: null | Record<string, string>;
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
// API - Agent management (platform) / API 接口 - 智能体管理（平台）
// ============================================================

const AGENT_PREFIX = '/admin/ai/agents';

/** Get agent list / 获取智能体列表 */
export async function getAIAgentListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIAgentInfo>> {
  return requestClient.get<PageResponse<AIAgentInfo>>(AGENT_PREFIX, {
    params,
    ...options,
  });
}

/** Get agent detail / 获取智能体详情 */
export async function getAIAgentDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.get<AIAgentInfo>(`${AGENT_PREFIX}/${id}`, options);
}

/** Update agent status / 更新智能体状态 */
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

/** Create agent / 创建智能体 */
export async function createAIAgentApi(
  data: AIAgentCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(AGENT_PREFIX, data, options);
}

/** Update agent / 更新智能体 */
export async function updateAIAgentApi(
  id: number,
  data: AIAgentUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIAgentInfo> {
  return requestClient.put<AIAgentInfo>(`${AGENT_PREFIX}/${id}`, data, options);
}

/** Delete agent / 删除智能体 */
export async function deleteAIAgentApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${AGENT_PREFIX}/${id}`, options);
}

/** Get agent memory config / 获取智能体记忆配置 */
export async function getAIAgentMemoryConfigApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIAgentMemoryConfig> {
  return requestClient.get<AIAgentMemoryConfig>(
    `${AGENT_PREFIX}/${id}/memory`,
    options,
  );
}

/** Update agent memory toggle / 更新智能体记忆开关 */
export async function updateAIAgentMemoryConfigApi(
  id: number,
  data: AIAgentMemoryUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIAgentMemoryConfig> {
  return requestClient.put<AIAgentMemoryConfig>(
    `${AGENT_PREFIX}/${id}/memory`,
    data,
    options,
  );
}

// ============================================================
// API - Agent skill grants (platform) / API 接口 - 智能体技能授权（平台）
// ============================================================

/** Get agent skill grant list / 获取智能体技能授权列表 */
export async function getAIAgentSkillsApi(
  agentId: number,
): Promise<AIAgentSkillGrantInfo[]> {
  return requestClient.get<AIAgentSkillGrantInfo[]>(
    `${AGENT_PREFIX}/${agentId}/skills`,
  );
}

/** Bind skill to agent / 绑定技能到智能体 */
export async function bindAIAgentSkillApi(
  agentId: number,
  data: AIAgentSkillGrantRequest,
): Promise<AIAgentSkillGrantInfo> {
  return requestClient.post<AIAgentSkillGrantInfo>(
    `${AGENT_PREFIX}/${agentId}/skills`,
    data,
  );
}

/** Batch grant skills (replace mode) / 批量授权技能（替换模式） */
export async function batchBindAIAgentSkillsApi(
  agentId: number,
  data: AIAgentSkillBatchGrantRequest,
): Promise<AIAgentSkillGrantInfo[]> {
  return requestClient.put<AIAgentSkillGrantInfo[]>(
    `${AGENT_PREFIX}/${agentId}/skills/batch`,
    data,
  );
}

/** Update skill grant config / 更新技能授权配置 */
export async function updateAIAgentSkillGrantApi(
  agentId: number,
  bindingId: number,
  data: AIAgentSkillGrantUpdateRequest,
): Promise<AIAgentSkillGrantInfo> {
  return requestClient.put<AIAgentSkillGrantInfo>(
    `${AGENT_PREFIX}/${agentId}/skills/${bindingId}`,
    data,
  );
}

/** Unbind skill / 解绑技能 */
export async function unbindAIAgentSkillApi(
  agentId: number,
  skillId: number,
): Promise<void> {
  await requestClient.delete(`${AGENT_PREFIX}/${agentId}/skills/${skillId}`);
}

// ============================================================
// Type definitions - Agent KB bindings / 类型定义 - 智能体知识库绑定
// ============================================================

/** KB binding info / 知识库绑定信息 */
export interface AIAgentKBBindingInfo {
  id: number;
  agent_id: number;
  knowledge_base_id: number;
  weight: number;
  enabled: boolean;
  sort_order: number;
  kb_name: null | string;
  kb_description: null | string;
  kb_scope: null | string;
  kb_visibility: null | string;
  kb_document_count: null | number;
  kb_chunk_strategy: null | string;
  kb_embedding_model_id: null | number;
  kb_embedding_model_name: null | string;
  kb_embedding_dimensions: null | number;
}

/** Bind KB request / 绑定知识库请求 */
export interface AIAgentKBBindRequest {
  knowledge_base_id: number;
  weight?: number;
  sort_order?: number;
  enabled?: boolean;
}

/** Batch bind KB request / 批量绑定知识库请求 */
export interface AIAgentKBBatchBindRequest {
  knowledge_base_ids: number[];
}

/** Update KB binding request / 更新知识库绑定请求 */
export interface AIAgentKBBindingUpdateRequest {
  weight?: null | number;
  enabled?: boolean | null;
  sort_order?: null | number;
}

// ============================================================
// API - Agent KB bindings (platform) / API 接口 - 智能体知识库绑定（平台）
// ============================================================

/** Get agent KB binding list / 获取智能体知识库绑定列表 */
export async function getAIAgentKBsApi(
  agentId: number,
): Promise<AIAgentKBBindingInfo[]> {
  return requestClient.get<AIAgentKBBindingInfo[]>(
    `${AGENT_PREFIX}/${agentId}/knowledge-bases`,
  );
}

/** Bind KB to agent / 绑定知识库到智能体 */
export async function bindAIAgentKBApi(
  agentId: number,
  data: AIAgentKBBindRequest,
): Promise<AIAgentKBBindingInfo> {
  return requestClient.post<AIAgentKBBindingInfo>(
    `${AGENT_PREFIX}/${agentId}/knowledge-bases`,
    data,
  );
}

/** Batch bind KBs (replace mode) / 批量绑定知识库（替换模式） */
export async function batchBindAIAgentKBsApi(
  agentId: number,
  data: AIAgentKBBatchBindRequest,
): Promise<AIAgentKBBindingInfo[]> {
  return requestClient.put<AIAgentKBBindingInfo[]>(
    `${AGENT_PREFIX}/${agentId}/knowledge-bases/batch`,
    data,
  );
}

/** Update KB binding config / 更新知识库绑定配置 */
export async function updateAIAgentKBBindingApi(
  agentId: number,
  bindingId: number,
  data: AIAgentKBBindingUpdateRequest,
): Promise<AIAgentKBBindingInfo> {
  return requestClient.put<AIAgentKBBindingInfo>(
    `${AGENT_PREFIX}/${agentId}/knowledge-bases/${bindingId}`,
    data,
  );
}

/** Unbind KB / 解绑知识库 */
export async function unbindAIAgentKBApi(
  agentId: number,
  knowledgeBaseId: number,
): Promise<void> {
  await requestClient.delete(
    `${AGENT_PREFIX}/${agentId}/knowledge-bases/${knowledgeBaseId}`,
  );
}

// ============================================================
// API - Publish / version management / API 接口 - 发布 / 版本管理
// ============================================================

/** Version list item / 版本列表项 */
export interface AIAgentVersionItem {
  id: number;
  agent_id: number;
  version: number;
  change_log: null | string;
  created_by: null | number;
  execution_mode: string;
  created_at: string;
}

export interface AIAgentVersionDetail extends AIAgentVersionItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: null | number;
  top_p: null | number;
  input_variables: null | unknown[];
  welcome_message: null | string;
  suggested_questions: null | unknown[];
  context_config: null | Record<string, unknown>;
  output_schema: null | unknown[];
  quota_config: null | Record<string, unknown>;
  rag_config: AgentRagConfig | null;
}

export interface AIAgentVersionDiff {
  agent_id: number;
  v1: number;
  v2: number;
  changes: Record<string, { v1: unknown; v2: unknown }>;
}

/** Publish agent / 发布智能体 */
export async function publishAIAgentApi(
  agentId: number,
  data: { change_log?: null | string },
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(
    `${AGENT_PREFIX}/${agentId}/publish`,
    data,
  );
}

/** Rollback agent / 回滚智能体 */
export async function rollbackAIAgentApi(
  agentId: number,
  version: number,
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(
    `${AGENT_PREFIX}/${agentId}/rollback`,
    { version },
  );
}

/** Get version history / 获取版本历史 */
export async function getAIAgentVersionsApi(
  agentId: number,
): Promise<AIAgentVersionItem[]> {
  return requestClient.get<AIAgentVersionItem[]>(
    `${AGENT_PREFIX}/${agentId}/versions`,
  );
}

/** Get version detail / 获取版本详情 */
export async function getAIAgentVersionDetailApi(
  agentId: number,
  version: number,
): Promise<AIAgentVersionDetail> {
  return requestClient.get<AIAgentVersionDetail>(
    `${AGENT_PREFIX}/${agentId}/versions/${version}`,
  );
}

/** Diff versions / 对比版本 */
export async function diffAIAgentVersionsApi(
  agentId: number,
  v1: number,
  v2: number,
): Promise<AIAgentVersionDiff> {
  return requestClient.get<AIAgentVersionDiff>(
    `${AGENT_PREFIX}/${agentId}/versions/diff`,
    { params: { v1, v2 } },
  );
}

// ============================================================
// API - Access permission config / API 接口 - 访问权限配置
// ============================================================

/** Access permission config / 访问权限配置 */
export interface AIAgentAccessConfig {
  agent_id: number;
  admin_role_ids: null | number[];
  tenant_role_ids: null | number[];
  user_role_ids: null | number[];
}

/** Get access permission config / 获取访问权限配置 */
export async function getAIAgentAccessApi(
  agentId: number,
): Promise<AIAgentAccessConfig> {
  return requestClient.get<AIAgentAccessConfig>(
    `${AGENT_PREFIX}/${agentId}/access`,
  );
}

/** Update access permission config / 更新访问权限配置 */
export async function updateAIAgentAccessApi(
  agentId: number,
  data: {
    admin_role_ids?: null | number[];
    tenant_role_ids?: null | number[];
    user_role_ids?: null | number[];
  },
): Promise<AIAgentAccessConfig> {
  return requestClient.put<AIAgentAccessConfig>(
    `${AGENT_PREFIX}/${agentId}/access`,
    data,
  );
}

// ============================================================
// API - Recycle bin / API 接口 - 回收站
// ============================================================

/** Get recycle bin count / 获取回收站计数 */
export async function getAIAgentRecycleBinCountApi(): Promise<{
  count: number;
}> {
  return requestClient.get<{ count: number }>(
    `${AGENT_PREFIX}/recycle-bin/count`,
  );
}

/** Get recycle bin list / 获取回收站列表 */
export async function getAIAgentRecycleBinApi(
  params?: Record<string, unknown>,
): Promise<{ items: AIAgentInfo[]; total: number }> {
  return requestClient.get<{ items: AIAgentInfo[]; total: number }>(
    `${AGENT_PREFIX}/recycle-bin`,
    { params },
  );
}

/** Restore recycle bin item / 恢复回收站项 */
export async function restoreAIAgentApi(id: number): Promise<void> {
  await requestClient.post(`${AGENT_PREFIX}/recycle-bin/${id}/restore`);
}

/** Permanently delete recycle bin item / 永久删除回收站项 */
export async function permanentDeleteAIAgentApi(id: number): Promise<void> {
  await requestClient.delete(`${AGENT_PREFIX}/recycle-bin/${id}`);
}

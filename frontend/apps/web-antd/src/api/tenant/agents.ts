/**
 * Tenant agent management API / 企业端智能体管理 API
 * Backend: /tenant/ai/agents/* / 对接后端 /tenant/ai/agents/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Agent list item / 智能体列表项 */
export interface AgentListItem {
  id: number;
  tenant_id: number;
  name: string;
  avatar: null | string;
  description: null | string;
  status: string;
  execution_mode: string;
  scope: string;
  target_audience: string;
  is_system: boolean;
  model_name: null | string;
  skill_packages: { id: number; name: string }[];
  published_version: null | number;
  visibility: string;
  welcome_message: null | string;
  created_at: string;
  updated_at: string;
}

/** Agent access config / 智能体访问权限配置 */
export interface AgentAccessConfig {
  agent_id: number;
  admin_role_ids: null | number[];
  tenant_role_ids: null | number[];
  user_role_ids: null | number[];
}

/** Update agent access request / 更新智能体访问权限请求 */
export interface AgentAccessUpdateRequest {
  admin_role_ids?: null | number[];
  tenant_role_ids?: null | number[];
  user_role_ids?: null | number[];
}

/** Agent detail / 智能体详情 */
export interface AgentInfo extends AgentListItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: null | number;
  top_p: null | number;
  published_version: null | number;
  /** @deprecated replaced by AgentSkillBinding / 已废弃，由 AgentSkillBinding 替代 */
  tool_bindings: null | unknown[];
  input_variables: null | unknown[];
  welcome_message: null | string;
  suggested_questions: null | unknown[];
  model_code: null | string;
  quota_config: null | Record<string, unknown>;
  routing_config: null | Record<string, unknown>;
  context_config: null | Record<string, unknown>;
  output_schema: null | unknown[];
  knowledge_base_ids: null | number[];
  rag_config: null | Record<string, unknown>;
}

/** Create agent request / 创建智能体请求 */
export interface AgentCreateRequest {
  name: string;
  description?: null | string;
  avatar?: null | string;
  system_prompt: string;
  model_id: number;
  temperature?: number;
  max_tokens?: null | number;
  top_p?: null | number;
  execution_mode?: string;
  target_audience?: string;
  /** @deprecated replaced by AgentSkillBinding / 已废弃，由 AgentSkillBinding 替代 */
  tool_bindings?: null | unknown[];
  input_variables?: null | unknown[];
  welcome_message?: null | string;
  suggested_questions?: null | unknown[];
  context_config?: null | Record<string, unknown>;
  output_schema?: null | unknown[];
  quota_config?: null | Record<string, unknown>;
  visibility?: string;
  knowledge_base_ids?: null | number[];
  rag_config?: null | Record<string, unknown>;
}

/** Update agent request / 更新智能体请求 */
export interface AgentUpdateRequest {
  name?: null | string;
  description?: null | string;
  avatar?: null | string;
  system_prompt?: null | string;
  model_id?: null | number;
  temperature?: null | number;
  max_tokens?: null | number;
  top_p?: null | number;
  status?: null | string;
  execution_mode?: null | string;
  /** @deprecated replaced by AgentSkillBinding / 已废弃，由 AgentSkillBinding 替代 */
  tool_bindings?: null | unknown[];
  input_variables?: null | unknown[];
  welcome_message?: null | string;
  suggested_questions?: null | unknown[];
  context_config?: null | Record<string, unknown>;
  output_schema?: null | unknown[];
  quota_config?: null | Record<string, unknown>;
  visibility?: null | string;
  knowledge_base_ids?: null | number[];
  rag_config?: null | Record<string, unknown>;
}

/** Agent memory config (tenant side) / 智能体记忆配置（企业侧） */
export interface AgentMemoryConfig {
  agent_id: number;
  platform_default_memory_enabled: boolean;
  admin_agent_memory_enabled: boolean;
  tenant_agent_memory_disabled: boolean;
  effective_memory_enabled: boolean;
}

/** Update agent memory override (tenant side) / 更新智能体记忆覆盖 */
export interface AgentMemoryUpdateRequest {
  disabled: boolean;
}

/** Publish agent request / 发布智能体请求 */
export interface AgentPublishRequest {
  change_log?: null | string;
}

/** Rollback agent request / 回滚智能体请求 */
export interface AgentRollbackRequest {
  version: number;
}

/** Version list item / 版本列表项 */
export interface AgentVersionListItem {
  id: number;
  agent_id: number;
  version: number;
  change_log: null | string;
  created_by: null | number;
  execution_mode: string;
  created_at: string;
}

/** Version detail / 版本详情 */
export interface AgentVersionDetail extends AgentVersionListItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: null | number;
  top_p: null | number;
  tool_bindings: null | unknown[];
  input_variables: null | unknown[];
  welcome_message: null | string;
  suggested_questions: null | unknown[];
  quota_config: null | Record<string, unknown>;
}

/** Version diff result / 版本对比结果 */
export interface AgentVersionDiff {
  agent_id: number;
  v1: number;
  v2: number;
  changes: Record<string, { v1: unknown; v2: unknown }>;
}

/** Agent paginated response / 智能体列表分页响应 */
interface AgentPageResponse {
  items: AgentListItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/tenant/ai/agents';

/** Get agent list / 获取智能体列表 */
export async function getAgentListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AgentPageResponse> {
  return requestClient.get<AgentPageResponse>(PREFIX, { params, ...options });
}

/** Get agent detail / 获取智能体详情 */
export async function getAgentDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.get<AgentInfo>(`${PREFIX}/${id}`, options);
}

/** Create agent / 创建智能体 */
export async function createAgentApi(
  data: AgentCreateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.post<AgentInfo>(PREFIX, data, options);
}

/** Update agent / 更新智能体 */
export async function updateAgentApi(
  id: number,
  data: AgentUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.put<AgentInfo>(`${PREFIX}/${id}`, data, options);
}

/** Delete agent / 删除智能体 */
export async function deleteAgentApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** Publish agent / 发布智能体 */
export async function publishAgentApi(
  id: number,
  data?: AgentPublishRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.post<AgentInfo>(
    `${PREFIX}/${id}/publish`,
    data ?? {},
    options,
  );
}

/** Rollback agent to specified version / 回滚智能体到指定版本 */
export async function rollbackAgentApi(
  id: number,
  data: AgentRollbackRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.post<AgentInfo>(
    `${PREFIX}/${id}/rollback`,
    data,
    options,
  );
}

/** Get agent version history / 获取智能体版本历史 */
export async function getAgentVersionsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentVersionListItem[]> {
  return requestClient.get<AgentVersionListItem[]>(
    `${PREFIX}/${id}/versions`,
    options,
  );
}

/** Get agent version detail / 获取智能体版本详情 */
export async function getAgentVersionDetailApi(
  id: number,
  version: number,
  options?: ApiRequestOptions,
): Promise<AgentVersionDetail> {
  return requestClient.get<AgentVersionDetail>(
    `${PREFIX}/${id}/versions/${version}`,
    options,
  );
}

/** Diff two versions / 对比两个版本差异 */
export async function diffAgentVersionsApi(
  id: number,
  v1: number,
  v2: number,
  options?: ApiRequestOptions,
): Promise<AgentVersionDiff> {
  return requestClient.get<AgentVersionDiff>(`${PREFIX}/${id}/versions/diff`, {
    params: { v1, v2 },
    ...options,
  });
}

// ============================================================
// Access control API / 访问权限 API
// ============================================================

/** Get agent access config / 获取智能体访问权限配置 */
export async function getAgentAccessApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentAccessConfig> {
  return requestClient.get<AgentAccessConfig>(
    `${PREFIX}/${id}/access`,
    options,
  );
}

/** Update agent access config / 更新智能体访问权限配置 */
export async function updateAgentAccessApi(
  id: number,
  data: AgentAccessUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AgentAccessConfig> {
  return requestClient.put<AgentAccessConfig>(
    `${PREFIX}/${id}/access`,
    data,
    options,
  );
}

/** Get agent memory config / 获取智能体记忆配置 */
export async function getAgentMemoryConfigApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentMemoryConfig> {
  return requestClient.get<AgentMemoryConfig>(
    `${PREFIX}/${id}/memory`,
    options,
  );
}

/** Update tenant-side memory override / 更新企业侧记忆覆盖 */
export async function updateAgentMemoryConfigApi(
  id: number,
  data: AgentMemoryUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AgentMemoryConfig> {
  return requestClient.put<AgentMemoryConfig>(
    `${PREFIX}/${id}/memory`,
    data,
    options,
  );
}

// ============================================================
// Skill package binding API / 技能包绑定 API
// ============================================================

/** Skill package binding info / 技能包绑定信息 */
export interface AgentSkillBindingInfo {
  id: null | number;
  agent_id: number;
  package_id: number;
  enabled: boolean;
  config_override: null | Record<string, unknown>;
  sort_order: number;
  consent_mode: string;
  is_auto_bound: boolean;
  package_name: null | string;
  package_description: null | string;
  package_target_audience: null | string;
  package_bind_mode: string;
  package_is_system: boolean;
}

/** Get agent skill bindings / 获取智能体绑定的技能包列表 */
export async function getAgentSkillsApi(
  agentId: number,
  options?: ApiRequestOptions,
): Promise<AgentSkillBindingInfo[]> {
  return requestClient.get<AgentSkillBindingInfo[]>(
    `${PREFIX}/${agentId}/skills`,
    options,
  );
}

/** Batch bind skill packages (replace mode) / 批量绑定技能包 */
export async function batchBindPackagesApi(
  agentId: number,
  packageIds: number[],
  consentModes?: Record<string, string>,
  options?: ApiRequestOptions,
): Promise<AgentSkillBindingInfo[]> {
  return requestClient.put<AgentSkillBindingInfo[]>(
    `${PREFIX}/${agentId}/skills/batch`,
    { package_ids: packageIds, consent_modes: consentModes },
    options,
  );
}

/** Update skill binding config (consent_mode / enabled etc.) / 更新技能绑定配置 */
export async function updateAgentSkillBindingApi(
  agentId: number,
  bindingId: number,
  data: {
    config_override?: null | Record<string, unknown>;
    consent_mode?: string;
    enabled?: boolean;
    sort_order?: null | number;
  },
  options?: ApiRequestOptions,
): Promise<AgentSkillBindingInfo> {
  return requestClient.put<AgentSkillBindingInfo>(
    `${PREFIX}/${agentId}/skills/${bindingId}`,
    data,
    options,
  );
}

/** Unbind skill package / 解绑技能包 */
export async function unbindPackageApi(
  agentId: number,
  packageId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${PREFIX}/${agentId}/skills/${packageId}`,
    options,
  );
}

// ============================================================
// Knowledge base binding API / 知识库绑定 API
// ============================================================

/** KB binding info / 知识库绑定信息 */
export interface AgentKBBindingInfo {
  id: number;
  agent_id: number;
  knowledge_base_id: number;
  weight: number;
  enabled: boolean;
  sort_order: number;
  kb_name: string | null;
  kb_description: string | null;
  kb_scope: string | null;
  kb_visibility: string | null;
  kb_document_count: number | null;
}

/** Get agent KB bindings / 获取智能体知识库绑定列表 */
export async function getAgentKBsApi(
  agentId: number,
  options?: ApiRequestOptions,
): Promise<AgentKBBindingInfo[]> {
  return requestClient.get<AgentKBBindingInfo[]>(
    `${PREFIX}/${agentId}/knowledge-bases`,
    options,
  );
}

/** Batch bind knowledge bases (replace mode) / 批量绑定知识库 */
export async function batchBindKBsApi(
  agentId: number,
  knowledgeBaseIds: number[],
  options?: ApiRequestOptions,
): Promise<AgentKBBindingInfo[]> {
  return requestClient.put<AgentKBBindingInfo[]>(
    `${PREFIX}/${agentId}/knowledge-bases/batch`,
    { knowledge_base_ids: knowledgeBaseIds },
    options,
  );
}

/** Update KB binding config / 更新知识库绑定配置 */
export async function updateAgentKBBindingApi(
  agentId: number,
  bindingId: number,
  data: {
    enabled?: boolean;
    sort_order?: null | number;
    weight?: null | number;
  },
  options?: ApiRequestOptions,
): Promise<AgentKBBindingInfo> {
  return requestClient.put<AgentKBBindingInfo>(
    `${PREFIX}/${agentId}/knowledge-bases/${bindingId}`,
    data,
    options,
  );
}

/** Unbind knowledge base / 解绑知识库 */
export async function unbindKBApi(
  agentId: number,
  knowledgeBaseId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${PREFIX}/${agentId}/knowledge-bases/${knowledgeBaseId}`,
    options,
  );
}

// ============================================================
// Recycle bin / 回收站
// ============================================================

/** Get recycle bin count / 获取回收站计数 */
export async function getAgentRecycleBinCountApi(): Promise<{ count: number }> {
  return requestClient.get<{ count: number }>(`${PREFIX}/recycle-bin/count`);
}

/** Get recycle bin list / 获取回收站列表 */
export async function getAgentRecycleBinApi(
  params?: Record<string, unknown>,
): Promise<{ items: AgentListItem[]; total: number }> {
  return requestClient.get<{ items: AgentListItem[]; total: number }>(
    `${PREFIX}/recycle-bin`,
    { params },
  );
}

/** Restore recycle bin item / 恢复回收站项 */
export async function restoreAgentApi(id: number): Promise<void> {
  await requestClient.post(`${PREFIX}/recycle-bin/${id}/restore`);
}

/** Permanently delete recycle bin item / 永久删除回收站项 */
export async function permanentDeleteAgentApi(id: number): Promise<void> {
  await requestClient.delete(`${PREFIX}/recycle-bin/${id}`);
}

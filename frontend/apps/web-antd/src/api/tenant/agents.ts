/**
 * 租户端智能体管理 API
 * 对接后端 /tenant/ai/agents/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 智能体列表项 */
export interface AgentListItem {
  id: number;
  tenant_id: number;
  name: string;
  avatar: null | string;
  description: null | string;
  status: string;
  execution_mode: string;
  scope: string;
  is_system: boolean;
  model_name: null | string;
  skill_packages: { id: number; name: string }[];
  published_version: null | number;
  visibility: string;
  welcome_message: null | string;
  created_at: string;
  updated_at: string;
}

/** 智能体访问权限配置 */
export interface AgentAccessConfig {
  agent_id: number;
  visibility: string;
  access_type: string;
  org_node_ids: null | number[];
  user_ids: null | number[];
}

/** 更新智能体访问权限请求 */
export interface AgentAccessUpdateRequest {
  visibility: string;
  access_type: string;
  org_node_ids?: null | number[];
  user_ids?: null | number[];
}

/** 智能体详情 */
export interface AgentInfo extends AgentListItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: null | number;
  top_p: null | number;
  published_version: null | number;
  /** @deprecated replaced by AgentSkillBinding */
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

/** 创建智能体请求 */
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
  /** @deprecated replaced by AgentSkillBinding */
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

/** 更新智能体请求 */
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
  /** @deprecated replaced by AgentSkillBinding */
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

/** 智能体记忆配置（租户侧） */
export interface AgentMemoryConfig {
  agent_id: number;
  platform_default_memory_enabled: boolean;
  admin_agent_memory_enabled: boolean;
  tenant_agent_memory_disabled: boolean;
  effective_memory_enabled: boolean;
}

/** 更新智能体记忆覆盖（租户侧） */
export interface AgentMemoryUpdateRequest {
  disabled: boolean;
}

/** 发布智能体请求 */
export interface AgentPublishRequest {
  change_log?: null | string;
}

/** 回滚智能体请求 */
export interface AgentRollbackRequest {
  version: number;
}

/** 版本列表项 */
export interface AgentVersionListItem {
  id: number;
  agent_id: number;
  version: number;
  change_log: null | string;
  created_by: null | number;
  execution_mode: string;
  created_at: string;
}

/** 版本详情 */
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

/** 版本对比结果 */
export interface AgentVersionDiff {
  agent_id: number;
  v1: number;
  v2: number;
  changes: Record<string, { v1: unknown; v2: unknown }>;
}

/** 智能体列表分页响应 */
interface AgentPageResponse {
  items: AgentListItem[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/agents';

/** 获取智能体列表 */
export async function getAgentListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AgentPageResponse> {
  return requestClient.get<AgentPageResponse>(PREFIX, { params, ...options });
}

/** 获取智能体详情 */
export async function getAgentDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.get<AgentInfo>(`${PREFIX}/${id}`, options);
}

/** 创建智能体 */
export async function createAgentApi(
  data: AgentCreateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.post<AgentInfo>(PREFIX, data, options);
}

/** 更新智能体 */
export async function updateAgentApi(
  id: number,
  data: AgentUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.put<AgentInfo>(`${PREFIX}/${id}`, data, options);
}

/** 删除智能体 */
export async function deleteAgentApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 发布智能体 */
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

/** 回滚智能体到指定版本 */
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

/** 获取智能体版本历史 */
export async function getAgentVersionsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentVersionListItem[]> {
  return requestClient.get<AgentVersionListItem[]>(
    `${PREFIX}/${id}/versions`,
    options,
  );
}

/** 获取智能体版本详情 */
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

/** 对比两个版本差异 */
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
// 访问权限 API
// ============================================================

/** 获取智能体访问权限配置 */
export async function getAgentAccessApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentAccessConfig> {
  return requestClient.get<AgentAccessConfig>(
    `${PREFIX}/${id}/access`,
    options,
  );
}

/** 更新智能体访问权限配置 */
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

/** 获取智能体记忆配置 */
export async function getAgentMemoryConfigApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentMemoryConfig> {
  return requestClient.get<AgentMemoryConfig>(
    `${PREFIX}/${id}/memory`,
    options,
  );
}

/** 更新租户侧记忆覆盖 */
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
// 技能包绑定 API
// ============================================================

/** 技能包绑定信息 */
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
  package_scope: null | string;
  package_bind_mode: string;
  package_is_system: boolean;
}

/** 获取智能体绑定的技能包列表 */
export async function getAgentSkillsApi(
  agentId: number,
  options?: ApiRequestOptions,
): Promise<AgentSkillBindingInfo[]> {
  return requestClient.get<AgentSkillBindingInfo[]>(
    `${PREFIX}/${agentId}/skills`,
    options,
  );
}

/** 批量绑定技能包（替换模式） */
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

/** 更新技能绑定配置（consent_mode / enabled 等） */
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

/** 解绑技能包 */
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
// 回收站
// ============================================================

/** 获取回收站计数 */
export async function getAgentRecycleBinCountApi(): Promise<{ count: number }> {
  return requestClient.get<{ count: number }>(`${PREFIX}/recycle-bin/count`);
}

/** 获取回收站列表 */
export async function getAgentRecycleBinApi(
  params?: Record<string, unknown>,
): Promise<{ items: AgentListItem[]; total: number }> {
  return requestClient.get<{ items: AgentListItem[]; total: number }>(
    `${PREFIX}/recycle-bin`,
    { params },
  );
}

/** 恢复回收站项 */
export async function restoreAgentApi(id: number): Promise<void> {
  await requestClient.post(`${PREFIX}/recycle-bin/${id}/restore`);
}

/** 永久删除回收站项 */
export async function permanentDeleteAgentApi(id: number): Promise<void> {
  await requestClient.delete(`${PREFIX}/recycle-bin/${id}`);
}

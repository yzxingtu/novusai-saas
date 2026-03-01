/**
 * AI 智能体管理 API（平台级）
 * 对接后端 /admin/ai/agents 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

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
  top_p: number | null;
  knowledge_base_ids: number[] | null;
  routing_config: Record<string, unknown> | null;
  assigned_tenant_ids?: number[];
  created_at: string;
  updated_at: string;
}

/** 创建智能体请求 */
export interface AIAgentCreateRequest {
  name: string;
  description?: null | string;
  scope: string;
  tenant_id?: number | null;
  tenant_ids?: number[];
  model_id: number;
  execution_mode?: string;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  knowledge_base_ids?: number[];
}

/** 更新智能体请求 */
export interface AIAgentUpdateRequest {
  name?: string;
  description?: null | string;
  scope?: string;
  tenant_id?: number | null;
  tenant_ids?: number[];
  model_id?: number;
  system_prompt?: null | string;
  temperature?: number;
  max_tokens?: number;
  knowledge_base_ids?: number[];
}

// ============================================================
// 类型定义 - 智能体技能绑定
// ============================================================

/** 技能绑定信息 */
export interface AIAgentSkillBindingInfo {
  id: number | null;
  agent_id: number;
  package_id: number;
  enabled: boolean;
  config_override: Record<string, unknown> | null;
  sort_order: number;
  consent_mode: string;
  is_auto_bound: boolean;
  package_name: string | null;
  package_description: string | null;
  package_scope: string | null;
  package_bind_mode: string;
  package_is_system: boolean;
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
  consent_modes?: Record<string, string>;
}

/** 更新绑定请求 */
export interface AIAgentSkillBindingUpdateRequest {
  enabled?: boolean | null;
  config_override?: Record<string, unknown> | null;
  sort_order?: number | null;
  consent_mode?: string | null;
  skill_consent_overrides?: Record<string, string> | null;
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

// ============================================================
// API 接口 - 发布 / 版本管理
// ============================================================

/** 版本列表项 */
export interface AIAgentVersionItem {
  id: number;
  agent_id: number;
  version: number;
  change_log: string | null;
  created_by: number | null;
  execution_mode: string;
  created_at: string;
}

/** 发布智能体 */
export async function publishAIAgentApi(
  agentId: number,
  data: { change_log?: null | string },
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(
    `${AGENT_PREFIX}/${agentId}/publish`,
    data,
  );
}

/** 回滚智能体 */
export async function rollbackAIAgentApi(
  agentId: number,
  version: number,
): Promise<AIAgentInfo> {
  return requestClient.post<AIAgentInfo>(
    `${AGENT_PREFIX}/${agentId}/rollback`,
    { version },
  );
}

/** 获取版本历史 */
export async function getAIAgentVersionsApi(
  agentId: number,
): Promise<AIAgentVersionItem[]> {
  return requestClient.get<AIAgentVersionItem[]>(
    `${AGENT_PREFIX}/${agentId}/versions`,
  );
}

/** 获取版本详情 */
export async function getAIAgentVersionDetailApi(
  agentId: number,
  version: number,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${AGENT_PREFIX}/${agentId}/versions/${version}`,
  );
}

// ============================================================
// API 接口 - 访问权限配置
// ============================================================

/** 访问权限配置 */
export interface AIAgentAccessConfig {
  visibility: string;
  access_type: string;
  org_node_ids: number[] | null;
  user_ids: number[] | null;
  access_rules: Array<Record<string, unknown>>;
}

/** 获取访问权限配置 */
export async function getAIAgentAccessApi(
  agentId: number,
): Promise<AIAgentAccessConfig> {
  return requestClient.get<AIAgentAccessConfig>(
    `${AGENT_PREFIX}/${agentId}/access`,
  );
}

/** 更新访问权限配置 */
export async function updateAIAgentAccessApi(
  agentId: number,
  data: {
    visibility?: string;
    access_type?: string;
    org_node_ids?: number[] | null;
    user_ids?: number[] | null;
  },
): Promise<AIAgentAccessConfig> {
  return requestClient.put<AIAgentAccessConfig>(
    `${AGENT_PREFIX}/${agentId}/access`,
    data,
  );
}

// ============================================================
// API 接口 - 回收站
// ============================================================

/** 获取回收站计数 */
export async function getAIAgentRecycleBinCountApi(): Promise<{ count: number }> {
  return requestClient.get<{ count: number }>(
    `${AGENT_PREFIX}/recycle-bin/count`,
  );
}

/** 获取回收站列表 */
export async function getAIAgentRecycleBinApi(
  params?: Record<string, unknown>,
): Promise<{ items: AIAgentInfo[]; total: number }> {
  return requestClient.get<{ items: AIAgentInfo[]; total: number }>(
    `${AGENT_PREFIX}/recycle-bin`,
    { params },
  );
}

/** 恢复回收站项 */
export async function restoreAIAgentApi(id: number): Promise<void> {
  await requestClient.post(`${AGENT_PREFIX}/recycle-bin/${id}/restore`);
}

/** 永久删除回收站项 */
export async function permanentDeleteAIAgentApi(id: number): Promise<void> {
  await requestClient.delete(`${AGENT_PREFIX}/recycle-bin/${id}`);
}

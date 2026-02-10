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
  avatar: string | null;
  description: string | null;
  status: string;
  execution_mode: string;
  model_name: string | null;
  published_version: number | null;
  visibility: string;
  created_at: string;
  updated_at: string;
}

/** 智能体访问权限配置 */
export interface AgentAccessConfig {
  agent_id: number;
  visibility: string;
  access_type: string;
  org_node_ids: number[] | null;
  user_ids: number[] | null;
}

/** 更新智能体访问权限请求 */
export interface AgentAccessUpdateRequest {
  visibility: string;
  access_type: string;
  org_node_ids?: number[] | null;
  user_ids?: number[] | null;
}

/** 智能体详情 */
export interface AgentInfo extends AgentListItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: number | null;
  top_p: number | null;
  published_version: number | null;
  tool_bindings: unknown[] | null;
  input_variables: unknown[] | null;
  welcome_message: string | null;
  suggested_questions: unknown[] | null;
  model_code: string | null;
  quota_config: Record<string, unknown> | null;
  context_config: Record<string, unknown> | null;
  output_schema: unknown[] | null;
}

/** 创建智能体请求 */
export interface AgentCreateRequest {
  name: string;
  description?: string | null;
  avatar?: string | null;
  system_prompt: string;
  model_id: number;
  temperature?: number;
  max_tokens?: number | null;
  top_p?: number | null;
  execution_mode?: string;
  tool_bindings?: unknown[] | null;
  input_variables?: unknown[] | null;
  welcome_message?: string | null;
  suggested_questions?: unknown[] | null;
  context_config?: Record<string, unknown> | null;
  output_schema?: unknown[] | null;
  quota_config?: Record<string, unknown> | null;
  visibility?: string;
}

/** 更新智能体请求 */
export interface AgentUpdateRequest {
  name?: string | null;
  description?: string | null;
  avatar?: string | null;
  system_prompt?: string | null;
  model_id?: number | null;
  temperature?: number | null;
  max_tokens?: number | null;
  top_p?: number | null;
  status?: string | null;
  execution_mode?: string | null;
  tool_bindings?: unknown[] | null;
  input_variables?: unknown[] | null;
  welcome_message?: string | null;
  suggested_questions?: unknown[] | null;
  context_config?: Record<string, unknown> | null;
  output_schema?: unknown[] | null;
  quota_config?: Record<string, unknown> | null;
  visibility?: string | null;
}

/** 发布智能体请求 */
export interface AgentPublishRequest {
  change_log?: string | null;
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
  change_log: string | null;
  created_by: number | null;
  execution_mode: string;
  created_at: string;
}

/** 版本详情 */
export interface AgentVersionDetail extends AgentVersionListItem {
  system_prompt: string;
  model_id: number;
  temperature: number;
  max_tokens: number | null;
  top_p: number | null;
  tool_bindings: unknown[] | null;
  input_variables: unknown[] | null;
  welcome_message: string | null;
  suggested_questions: unknown[] | null;
  quota_config: Record<string, unknown> | null;
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
  return requestClient.get<AgentPageResponse>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取智能体详情 */
export async function getAgentDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.get<AgentInfo>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建智能体 */
export async function createAgentApi(
  data: AgentCreateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.post<AgentInfo>(
    PREFIX,
    data,
    options,
  );
}

/** 更新智能体 */
export async function updateAgentApi(
  id: number,
  data: AgentUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AgentInfo> {
  return requestClient.put<AgentInfo>(
    `${PREFIX}/${id}`,
    data,
    options,
  );
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
  return requestClient.get<AgentVersionDiff>(
    `${PREFIX}/${id}/versions/diff`,
    { params: { v1, v2 }, ...options },
  );
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

/**
 * System agent assignment API (shared) / 系统智能体绑定 API（共享）
 *
 * Provides resolve function to get bound agent_id by feature_code.
 * Automatically selects endpoint based on current user API prefix (admin/tenant).
 * 提供 resolve 函数，根据 feature_code 获取绑定的 agent_id。
 */

import { requestClient } from '#/utils/request';

/** Resolve response / Resolve 响应 */
export interface AgentAssignmentResolveResult {
  feature_code: string;
  agent_id: null | number;
  agent_name: null | string;
  config: null | Record<string, unknown>;
  is_active: boolean;
  is_override?: boolean;
}

/** Assignment list item / 绑定列表项 */
export interface AgentAssignmentItem {
  id: number;
  feature_code: string;
  feature_name: string;
  description: null | string;
  agent_id: null | number;
  agent_name: null | string;
  agent_avatar: null | string;
  is_active: boolean;
  is_override: boolean;
  config?: null | Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  global_agent_id?: null | number;
  global_agent_name?: null | string;
  display_name?: Record<string, string>;
  description_i18n?: Record<string, string>;
}

/**
 * Resolve agent assignment / Resolve 智能体绑定
 *
 * @param apiPrefix - '/admin' or '/tenant'
 * @param featureCode - Feature code, e.g. 'general_chat' / 功能代码
 */
export async function resolveAgentAssignmentApi(
  apiPrefix: string,
  featureCode: string,
): Promise<AgentAssignmentResolveResult> {
  return requestClient.get<AgentAssignmentResolveResult>(
    `${apiPrefix}/ai/agent-assignments/resolve/${featureCode}`,
  );
}

/**
 * Get agent assignment list / 获取智能体绑定列表
 *
 * @param apiPrefix - '/admin' or '/tenant'
 */
export async function getAgentAssignmentListApi(
  apiPrefix: string,
): Promise<{ items: AgentAssignmentItem[]; total: number }> {
  return requestClient.get<{ items: AgentAssignmentItem[]; total: number }>(
    `${apiPrefix}/ai/agent-assignments`,
  );
}

/** Published agent option / 已发布智能体选项 */
export interface PublishedAgentOption {
  id: number;
  name: string;
  status: string;
}

/**
 * Get published agents list (for Select dropdown) / 获取已发布智能体列表
 *
 * @param apiPrefix - '/admin' or '/tenant'
 */
export async function getPublishedAgentsApi(
  apiPrefix: string,
): Promise<{ items: PublishedAgentOption[] }> {
  return requestClient.get<{ items: PublishedAgentOption[] }>(
    `${apiPrefix}/ai/agents`,
    { params: { 'filter[status][eq]': 'published', 'page[size]': 100 } },
  );
}

/**
 * Update agent assignment / 更新智能体绑定
 *
 * @param apiPrefix - '/admin' or '/tenant'
 * @param featureCode - Feature code / 功能代码
 * @param data - Update data / 更新数据
 * @param data.agent_id - Bound agent ID (null to unbind) / 绑定的智能体 ID
 * @param data.is_active - Whether this assignment is active / 是否启用
 */
export async function updateAgentAssignmentApi(
  apiPrefix: string,
  featureCode: string,
  data: { agent_id?: null | number; is_active?: boolean },
): Promise<unknown> {
  return requestClient.put(
    `${apiPrefix}/ai/agent-assignments/${featureCode}`,
    data,
  );
}

/**
 * Delete tenant override (restore global default) / 删除企业覆盖（恢复全局默认）
 *
 * @param apiPrefix - '/admin' or '/tenant'
 * @param featureCode - Feature code / 功能代码
 */
export async function deleteAgentAssignmentApi(
  apiPrefix: string,
  featureCode: string,
): Promise<unknown> {
  return requestClient.delete(
    `${apiPrefix}/ai/agent-assignments/${featureCode}`,
  );
}

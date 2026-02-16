/**
 * 系统智能体绑定 API（共享）
 *
 * 提供 resolve 函数，根据 feature_code 获取绑定的 agent_id。
 * 自动根据当前用户 API 前缀（admin/tenant）选择对应端点。
 */

import { requestClient } from '#/utils/request';

/** Resolve 响应 */
export interface AgentAssignmentResolveResult {
  feature_code: string;
  agent_id: number | null;
  agent_name: string | null;
  config: Record<string, unknown> | null;
  is_active: boolean;
  is_override?: boolean;
}

/** 绑定列表项 */
export interface AgentAssignmentItem {
  feature_code: string;
  feature_name: string;
  description: string | null;
  agent_id: number | null;
  agent_name: string | null;
  agent_avatar: string | null;
  is_active: boolean;
  is_override: boolean;
  config?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
  global_agent_id?: number | null;
  global_agent_name?: string | null;
}

/**
 * Resolve 智能体绑定
 *
 * @param apiPrefix - '/admin' 或 '/tenant'
 * @param featureCode - 功能代码，如 'crud_generator'
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
 * 获取智能体绑定列表
 *
 * @param apiPrefix - '/admin' 或 '/tenant'
 */
export async function getAgentAssignmentListApi(
  apiPrefix: string,
): Promise<AgentAssignmentItem[]> {
  return requestClient.get<AgentAssignmentItem[]>(
    `${apiPrefix}/ai/agent-assignments`,
  );
}

/**
 * AI Chat API (shared) / AI Chat API（共享）
 *
 * Wraps all requestClient calls from use-ai-chat.ts.
 * Differentiates admin/tenant via apiPrefix parameter.
 * 封装 use-ai-chat.ts 中的所有 requestClient 调用。
 */
import type { ChatAttachment } from '#/components/business/ai-chat-panel/types';

import { requestClient } from '#/utils/request';

// ============ Types ============

export interface PaginatedResponse<T = Record<string, unknown>> {
  items: T[];
  total: number;
}

export interface RawMessageItem {
  role: string;
  content: null | string;
  tool_calls?: Array<{
    function?: { arguments?: string; name?: string };
    id?: string;
  }> | null;
  tool_call_id?: null | string;
  tool_name?: null | string;
  metadata?: null | { attachments?: ChatAttachment[] };
}

export interface ConversationDetailResponse {
  agent_id?: null | number;
  message_list: RawMessageItem[];
}

export interface FileUploadResponse {
  url: string;
  attachment: {
    extension?: null | string;
    id: number;
    mime_type?: null | string;
    name: string;
    original_name?: null | string;
    size: number;
  };
  used_bytes: number;
}

export interface SSEOptions {
  abortController: AbortController;
  onMessage: (rawChunk: string) => void;
  onEnd: () => void;
  onError: (error: Error) => void;
}

// ============ API Functions ============

function chatBaseUrl(apiPrefix: string): string {
  return `${apiPrefix}/ai/agent-chat`;
}

/**
 * Get published agent list / 获取已发布智能体列表
 *
 * Admin: returns only admin-visible scopes (admin_only / admin_and_all / admin_and_assigned).
 * Tenant: backend auto-filters by tenant_id + scope.
 * 管理端：仅返回管理端可见作用域；租户端：后端自动过滤。
 */
export async function getChatAgentsApi<T = Record<string, unknown>>(
  apiPrefix: string,
): Promise<PaginatedResponse<T>> {
  const params: Record<string, number | string> = {
    'filter[status][eq]': 'published',
    'page[size]': 100,
  };
  if (apiPrefix.includes('/admin')) {
    params['filter[scope][in]'] = 'admin_only,admin_and_all,admin_and_assigned';
  }
  return requestClient.get<PaginatedResponse<T>>(`${apiPrefix}/ai/agents`, {
    params,
  });
}

/**
 * Get global conversation list (cross-agent) / 获取全局对话列表（跨智能体）
 */
export async function getGlobalConversationsApi<T = Record<string, unknown>>(
  apiPrefix: string,
  pageSize = 50,
): Promise<PaginatedResponse<T>> {
  return requestClient.get<PaginatedResponse<T>>(
    `${chatBaseUrl(apiPrefix)}/conversations`,
    { params: { 'page[size]': pageSize, sort: '-created_at' } },
  );
}

/**
 * Delete conversation / 删除对话
 */
export async function deleteChatConversationApi(
  apiPrefix: string,
  conversationId: number,
): Promise<unknown> {
  return requestClient.delete(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}`,
  );
}

/**
 * Clear conversation memory state (without deleting messages) / 清空会话记忆状态
 */
export async function clearChatConversationMemoryApi(
  apiPrefix: string,
  conversationId: number,
): Promise<{ deleted_count: number }> {
  return requestClient.delete<{ deleted_count: number }>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/memory-state`,
  );
}

/**
 * Get conversation memory state (preferences/constraints/tasks/facts) / 获取会话记忆状态
 */
export interface MemoryState {
  preferences: string[];
  constraints: string[];
  task_states: string[];
  verified_facts: string[];
  version: number;
  updated_at: number;
}

export async function getChatConversationMemoryApi(
  apiPrefix: string,
  conversationId: number,
): Promise<MemoryState> {
  return requestClient.get<MemoryState>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/memory-state`,
  );
}

/**
 * Get conversation message list / 获取对话消息列表
 */
export async function getChatConversationMessagesApi(
  apiPrefix: string,
  conversationId: number,
): Promise<ConversationDetailResponse> {
  return requestClient.get<ConversationDetailResponse>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}`,
  );
}

/**
 * Upload chat attachment / 上传聊天附件
 *
 * @param uploadUrl - Upload endpoint URL
 * @param file - File to upload
 * @param extraData - Additional form fields (e.g. tenant_id for admin endpoint)
 */
export async function uploadChatFileApi(
  uploadUrl: string,
  file: File,
  extraData?: Record<string, string>,
): Promise<FileUploadResponse> {
  const uploadData: Record<string, Blob | File | string> = { file };
  if (extraData) {
    Object.assign(uploadData, extraData);
  }
  return requestClient.upload<FileUploadResponse>(
    uploadUrl,
    uploadData as { [key: string]: Blob | File | string; file: File },
  );
}

// ============ Route Types ============

export interface PageContext {
  page_key: string;
  page_title?: string;
  page_data?: Record<string, unknown>;
}

export interface AgentChatImageParams {
  n?: number;
  quality?: string;
  size?: string;
  style?: string;
}

export interface AgentChatRequestBody {
  attachments?: ChatAttachment[];
  consented_actions?: string[];
  conversation_id?: null | number;
  image_params?: AgentChatImageParams;
  knowledge_base_ids?: number[];
  message: string;
  page_context?: null | PageContext;
  page_session_id?: null | string;
  variables?: Record<string, string>;
}

export interface AgentRouteResponse {
  agent_id: number;
  agent_name: string;
  confidence: number;
  routed_by: string;
}

/**
 * Smart routing — select target agent based on message and context / 智能路由
 */
export async function routeMessageApi(
  apiPrefix: string,
  body: {
    conversation_id?: null | number;
    message: string;
    page_context?: null | PageContext;
    pinned_agent_id?: null | number;
  },
): Promise<AgentRouteResponse> {
  return requestClient.post<AgentRouteResponse>(
    `${chatBaseUrl(apiPrefix)}/route`,
    body,
    {
      showCodeMessage: false,
      showErrorMessage: false,
    },
  );
}

// ============ Agent KB Bindings ============

export interface ChatKBBindingInfo {
  id: number;
  knowledge_base_id: number;
  kb_name: null | string;
  enabled: boolean;
}

/**
 * Get agent's bound knowledge base list (enabled only) / 获取智能体已绑定的知识库列表
 */
export async function getChatAgentKBBindingsApi(
  apiPrefix: string,
  agentId: number,
): Promise<ChatKBBindingInfo[]> {
  return requestClient.get<ChatKBBindingInfo[]>(
    `${apiPrefix}/ai/agents/${agentId}/knowledge-bases`,
  );
}

// ============ Agent Skill Bindings ============

export interface ChatSkillBindingInfo {
  id: null | number;
  agent_id: number;
  package_id: number;
  package_name: null | string;
  package_description: null | string;
  package_is_system: boolean;
  is_auto_bound: boolean;
  consent_mode: string;
}

export interface ChatSkillInfo {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  description?: null | string;
}

/**
 * Get agent's skill binding list (shared, auto routes by apiPrefix) / 获取智能体的技能绑定列表
 */
export async function getChatAgentSkillsApi(
  apiPrefix: string,
  agentId: number,
): Promise<ChatSkillBindingInfo[]> {
  return requestClient.get<ChatSkillBindingInfo[]>(
    `${apiPrefix}/ai/agents/${agentId}/skills`,
  );
}

/**
 * Get skills in a skill package (shared) / 获取技能包内的技能列表
 */
export async function getChatPackageSkillsApi(
  apiPrefix: string,
  packageId: number,
): Promise<{ items: ChatSkillInfo[]; total: number }> {
  return requestClient.get<{ items: ChatSkillInfo[]; total: number }>(
    `${apiPrefix}/ai/skill-packages/${packageId}/skills`,
    { params: { 'page[size]': 100 } },
  );
}

/**
 * Send SSE streaming chat message / 发送 SSE 流式聊天消息
 */
export async function sendChatStreamApi(
  apiPrefix: string,
  agentId: number,
  body: AgentChatRequestBody,
  sseOptions: SSEOptions,
): Promise<void> {
  return requestClient.postSSE(
    `${chatBaseUrl(apiPrefix)}/${agentId}/chat/stream`,
    body,
    sseOptions,
  );
}

/**
 * AI Chat API（共享）
 *
 * 封装 use-ai-chat.ts 中的所有 requestClient 调用。
 * 通过 apiPrefix 参数区分 admin/tenant。
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
 * 获取已发布智能体列表
 *
 * 管理端：仅返回管理端可见的作用域（admin_only / admin_and_all / admin_and_assigned），
 * 排除仅租户端作用域（all_tenants / assigned_tenants）。
 * 租户端：后端已自动按 tenant_id + scope 过滤，无需额外传参。
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
 * 获取对话列表
 */
export async function getChatConversationsApi<T = Record<string, unknown>>(
  apiPrefix: string,
  agentId: number,
  pageSize = 50,
): Promise<PaginatedResponse<T>> {
  return requestClient.get<PaginatedResponse<T>>(
    `${chatBaseUrl(apiPrefix)}/${agentId}/conversations`,
    { params: { 'page[size]': pageSize, sort: '-created_at' } },
  );
}

/**
 * 删除对话
 */
export async function deleteChatConversationApi(
  apiPrefix: string,
  agentId: number,
  conversationId: number,
): Promise<unknown> {
  return requestClient.delete(
    `${chatBaseUrl(apiPrefix)}/${agentId}/conversations/${conversationId}`,
  );
}

/**
 * 清空会话记忆状态（不删除对话消息）
 */
export async function clearChatConversationMemoryApi(
  apiPrefix: string,
  agentId: number,
  conversationId: number,
): Promise<{ deleted_count: number }> {
  return requestClient.delete<{ deleted_count: number }>(
    `${chatBaseUrl(apiPrefix)}/${agentId}/conversations/${conversationId}/memory-state`,
  );
}

/**
 * 获取对话消息列表
 */
export async function getChatConversationMessagesApi(
  apiPrefix: string,
  agentId: number,
  conversationId: number,
): Promise<ConversationDetailResponse> {
  return requestClient.get<ConversationDetailResponse>(
    `${chatBaseUrl(apiPrefix)}/${agentId}/conversations/${conversationId}`,
  );
}

/**
 * 上传聊天附件
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

/**
 * 发送 SSE 流式聊天消息
 */
export async function sendChatStreamApi(
  apiPrefix: string,
  agentId: number,
  body: Record<string, unknown>,
  sseOptions: SSEOptions,
): Promise<void> {
  return requestClient.postSSE(
    `${chatBaseUrl(apiPrefix)}/${agentId}/chat/stream`,
    body,
    sseOptions,
  );
}

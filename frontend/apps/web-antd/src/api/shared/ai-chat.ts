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
  content: string | null;
  tool_calls?: Array<{
    id?: string;
    function?: { name?: string; arguments?: string };
  }> | null;
  tool_call_id?: string | null;
  tool_name?: string | null;
  metadata?: { attachments?: ChatAttachment[] } | null;
}

export interface ConversationDetailResponse {
  message_list: RawMessageItem[];
}

export interface FileUploadResponse {
  url: string;
  attachment: { id: number; filename: string; mime_type: string };
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
 */
export async function getChatAgentsApi<T = Record<string, unknown>>(
  apiPrefix: string,
): Promise<PaginatedResponse<T>> {
  return requestClient.get<PaginatedResponse<T>>(
    `${apiPrefix}/ai/agents`,
    { params: { 'filter[status][eq]': 'published', 'page[size]': 100 } },
  );
}

/**
 * 获取对话列表
 */
export async function getChatConversationsApi<T = Record<string, unknown>>(
  apiPrefix: string,
  agentId: number,
): Promise<PaginatedResponse<T>> {
  return requestClient.get<PaginatedResponse<T>>(
    `${chatBaseUrl(apiPrefix)}/${agentId}/conversations`,
    { params: { 'page[size]': 50, sort: '-created_at' } },
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
 */
export async function uploadChatFileApi(
  uploadUrl: string,
  file: File,
): Promise<FileUploadResponse> {
  return requestClient.upload<FileUploadResponse>(
    uploadUrl,
    { file, tenant_id: '0' },
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

/**
 * Tenant conversation management API / 企业端对话管理 API
 * Backend: /tenant/ai/conversations/* / 对接后端 /tenant/ai/conversations/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** User brief info / 用户简要信息 */
export interface ConversationUserInfo {
  id: number;
  username: string;
  nickname: null | string;
  avatar: null | string;
}

/** Conversation list item / 对话列表项 */
export interface ConversationInfo {
  id: number;
  tenant_id: number;
  agent_id: number;
  user_id: null | number;
  title: null | string;
  status: string;
  token_count: number;
  cost: number;
  agent_name: null | string;
  agent_avatar: null | string;
  user_info: ConversationUserInfo | null;
  created_at: string;
  updated_at: string;
}

/** Conversation message / 对话消息 */
export interface ConversationMessageAttachment {
  attachment_id?: number;
  mime_type?: string;
  name?: string;
  type: 'audio' | 'file' | 'image' | 'video';
  url: string;
}

export interface ConversationMessageMetadata {
  attachments?: ConversationMessageAttachment[];
  [key: string]: unknown;
}

export interface ConversationMessageInfo {
  id: number;
  conversation_id: number;
  role: string;
  content: null | string;
  sequence: number;
  token_count: number;
  tool_calls: null | unknown[];
  tool_call_id: null | string;
  model_id: null | number;
  metadata?: ConversationMessageMetadata | null;
  created_at: string;
}

/** Conversation detail / 对话详情 */
export interface ConversationDetailInfo extends ConversationInfo {
  message_list: ConversationMessageInfo[];
  message_count: number;
  metadata: null | Record<string, unknown>;
}

/** Message search result / 消息搜索结果 */
export interface MessageSearchResult {
  items: ConversationMessageInfo[];
  total: number;
  page: number;
  page_size: number;
}

/** Conversation paginated response / 对话列表分页响应 */
interface ConversationPageResponse {
  items: ConversationInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** Export result / 导出响应 */
export interface ConversationExportResult {
  content: string;
  filename: string;
  format: string;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/tenant/ai/conversations';

/** Get conversation list / 获取对话列表 */
export async function getConversationListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<ConversationPageResponse> {
  return requestClient.get<ConversationPageResponse>(PREFIX, {
    params,
    ...options,
  });
}

/** Get conversation detail / 获取对话详情 */
export async function getConversationDetailApi(
  id: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<ConversationDetailInfo> {
  return requestClient.get<ConversationDetailInfo>(`${PREFIX}/${id}`, {
    params,
    ...options,
  });
}

/** Search messages / 搜索消息 */
export async function searchConversationMessagesApi(
  params: { keyword: string; page?: number; page_size?: number },
  options?: ApiRequestOptions,
): Promise<MessageSearchResult> {
  return requestClient.get<MessageSearchResult>(`${PREFIX}/search`, {
    params,
    ...options,
  });
}

/** Archive conversation / 归档对话 */
export async function archiveConversationApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<ConversationInfo> {
  return requestClient.post<ConversationInfo>(
    `${PREFIX}/${id}/archive`,
    {},
    options,
  );
}

/** Delete conversation / 删除对话 */
export async function deleteConversationApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** Export conversation / 导出对话 */
export async function exportConversationApi(
  id: number,
  format: 'json' | 'markdown' = 'json',
  options?: ApiRequestOptions,
): Promise<ConversationExportResult> {
  return requestClient.get<ConversationExportResult>(`${PREFIX}/${id}/export`, {
    params: { format },
    ...options,
  });
}

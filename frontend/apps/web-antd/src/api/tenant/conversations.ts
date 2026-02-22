/**
 * 租户端对话管理 API
 * 对接后端 /tenant/ai/conversations/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 用户简要信息 */
export interface ConversationUserInfo {
  id: number;
  username: string;
  nickname: string | null;
  avatar: string | null;
}

/** 对话列表项 */
export interface ConversationInfo {
  id: number;
  tenant_id: number;
  agent_id: number;
  user_id: number | null;
  title: string | null;
  status: string;
  token_count: number;
  cost: number;
  agent_name: string | null;
  agent_avatar: string | null;
  user_info: ConversationUserInfo | null;
  created_at: string;
  updated_at: string;
}

/** 对话消息 */
export interface ConversationMessageInfo {
  id: number;
  conversation_id: number;
  role: string;
  content: string | null;
  sequence: number;
  token_count: number;
  tool_calls: unknown[] | null;
  tool_call_id: string | null;
  model_id: number | null;
  created_at: string;
}

/** 对话详情 */
export interface ConversationDetailInfo extends ConversationInfo {
  message_list: ConversationMessageInfo[];
  message_count: number;
  metadata: Record<string, unknown> | null;
}

/** 消息搜索结果 */
export interface MessageSearchResult {
  items: ConversationMessageInfo[];
  total: number;
  page: number;
  page_size: number;
}

/** 对话列表分页响应 */
interface ConversationPageResponse {
  items: ConversationInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** 批量归档请求 */
export interface BatchArchiveRequest {
  agent_id?: number | null;
  before_days?: number;
}

/** 导出响应 */
export interface ConversationExportResult {
  content: string;
  filename: string;
  format: string;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/conversations';

/** 获取对话列表 */
export async function getConversationListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<ConversationPageResponse> {
  return requestClient.get<ConversationPageResponse>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取对话详情 */
export async function getConversationDetailApi(
  id: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<ConversationDetailInfo> {
  return requestClient.get<ConversationDetailInfo>(
    `${PREFIX}/${id}`,
    { params, ...options },
  );
}

/** 搜索消息 */
export async function searchConversationMessagesApi(
  params: { keyword: string; page?: number; page_size?: number },
  options?: ApiRequestOptions,
): Promise<MessageSearchResult> {
  return requestClient.get<MessageSearchResult>(
    `${PREFIX}/search`,
    { params, ...options },
  );
}

/** 归档对话 */
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

/** 批量归档 */
export async function batchArchiveConversationsApi(
  data: BatchArchiveRequest,
  options?: ApiRequestOptions,
): Promise<{ archived_count: number }> {
  return requestClient.post<{ archived_count: number }>(
    `${PREFIX}/batch-archive`,
    data,
    options,
  );
}

/** 删除对话 */
export async function deleteConversationApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 导出对话 */
export async function exportConversationApi(
  id: number,
  format: 'json' | 'markdown' = 'json',
  options?: ApiRequestOptions,
): Promise<ConversationExportResult> {
  return requestClient.get<ConversationExportResult>(
    `${PREFIX}/${id}/export`,
    { params: { format }, ...options },
  );
}

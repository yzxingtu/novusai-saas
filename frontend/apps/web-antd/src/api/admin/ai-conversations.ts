/**
 * AI 对话管理 API
 * 对接后端 /admin/ai/conversations 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义 - 对话管理
// ============================================================

/** 用户简要信息 */
export interface ConversationUserInfo {
  id: number;
  username: string;
  nickname: null | string;
  avatar: null | string;
}

/** 管理端对话列表项 */
export interface AIConversationInfo {
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
  tenant_name: null | string;
  user_info: ConversationUserInfo | null;
  created_at: string;
  updated_at: string;
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
// API 接口 - 对话管理
// ============================================================

const CONV_PREFIX = '/admin/ai/conversations';

/** 获取全租户对话列表 */
export async function getAIConversationListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIConversationInfo>> {
  return requestClient.get<PageResponse<AIConversationInfo>>(CONV_PREFIX, {
    params,
    ...options,
  });
}

/** 获取对话详情 */
export async function getAIConversationDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(
    `${CONV_PREFIX}/${id}`,
    options,
  );
}

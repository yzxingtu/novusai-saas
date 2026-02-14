/**
 * 平台管理端知识库监控 API
 * 对接后端 /admin/ai/knowledge-bases/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** 知识库列表项（全租户） */
export interface AdminKnowledgeBaseItem {
  id: number;
  tenant_id: number | null;
  name: string;
  description: string | null;
  scope: string;
  embedding_model_name: string | null;
  embedding_model_id: number | null;
  document_count: number;
  total_chunks: number;
  total_size_bytes: number;
  status: string;
  chunk_size?: number;
  chunk_overlap?: number;
  top_k?: number;
  score_threshold?: number;
  created_at: string;
}

/** 创建知识库请求 */
export interface AdminKnowledgeBaseCreateParams {
  name: string;
  description?: string;
  scope: string;
  tenant_id?: number | null;
  embedding_model_id: number;
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_strategy?: string;
  search_mode?: string;
  top_k?: number;
  score_threshold?: number;
}

/** 更新知识库请求 */
export interface AdminKnowledgeBaseUpdateParams {
  name?: string;
  description?: string;
  scope?: string;
  tenant_id?: number | null;
  embedding_model_id?: number;
}

/** 全局统计 */
export interface KnowledgeBaseGlobalStats {
  total_knowledge_bases: number;
  total_documents: number;
  total_chunks: number;
  total_size_bytes: number;
}

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

const PREFIX = '/admin/ai/knowledge-bases';

/** 获取知识库列表 */
export async function getAdminKnowledgeBaseListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AdminKnowledgeBaseItem>> {
  return requestClient.get<PageResponse<AdminKnowledgeBaseItem>>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取全局统计 */
export async function getKnowledgeBaseStatsApi(
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseGlobalStats> {
  return requestClient.get<KnowledgeBaseGlobalStats>(
    `${PREFIX}/stats`,
    options,
  );
}

/** 获取知识库详情 */
export async function getAdminKnowledgeBaseDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeBaseItem> {
  return requestClient.get<AdminKnowledgeBaseItem>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建知识库 */
export async function createAdminKnowledgeBaseApi(
  data: AdminKnowledgeBaseCreateParams,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeBaseItem> {
  return requestClient.post<AdminKnowledgeBaseItem>(PREFIX, data, options);
}

/** 更新知识库 */
export async function updateAdminKnowledgeBaseApi(
  id: number,
  data: AdminKnowledgeBaseUpdateParams,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeBaseItem> {
  return requestClient.put<AdminKnowledgeBaseItem>(
    `${PREFIX}/${id}`,
    data,
    options,
  );
}

/** 强制删除知识库 */
export async function deleteAdminKnowledgeBaseApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 可选知识库项 */
export interface SelectableKBItem {
  id: number;
  name: string;
  scope: string;
  description: string | null;
}

/** 获取可选知识库列表（管理端：admin + global） */
export async function getAdminSelectableKBApi(
  options?: ApiRequestOptions,
): Promise<SelectableKBItem[]> {
  return requestClient.get<SelectableKBItem[]>(
    `${PREFIX}/selectable`,
    options,
  );
}

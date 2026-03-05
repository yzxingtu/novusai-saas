/**
 * 平台管理端知识库监控 API
 * 对接后端 /admin/ai/knowledge-bases/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** 知识库列表项（全租户） */
export interface AdminKnowledgeBaseItem {
  id: number;
  tenant_id: null | number;
  name: string;
  description: null | string;
  scope: string;
  visibility?: string;
  assigned_tenant_ids?: number[];
  embedding_model_name: null | string;
  embedding_model_id: null | number;
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
  visibility?: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  assigned_tenant_ids?: number[];
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
  visibility?: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  assigned_tenant_ids?: number[];
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
  return requestClient.get<PageResponse<AdminKnowledgeBaseItem>>(PREFIX, {
    params,
    ...options,
  });
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
  return requestClient.get<AdminKnowledgeBaseItem>(`${PREFIX}/${id}`, options);
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

// ============================================================
// 文档子资源 API
// ============================================================

/** 知识库文档 */
export interface AdminKnowledgeDocumentItem {
  id: number;
  knowledge_base_id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  file_hash: null | string;
  status: string;
  error_message: null | string;
  error_stage: null | string;
  chunk_count: number;
  token_count: number;
  char_count: number;
  created_at: string;
  updated_at: string;
}

/** 检索结果项 */
export interface AdminSearchResultItem {
  chunk_id: number;
  content: string;
  score: number;
  metadata: null | Record<string, unknown>;
  document_name: string;
  document_id: number;
  highlight: null | string;
}

/** 文档处理进度 */
export interface AdminDocumentProgress {
  stage: string;
  progress: number;
  total_chunks: number;
  processed_chunks: number;
}

/** 获取文档列表 */
export async function getAdminDocumentListApi(
  kbId: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AdminKnowledgeDocumentItem>> {
  return requestClient.get<PageResponse<AdminKnowledgeDocumentItem>>(
    `${PREFIX}/${kbId}/documents`,
    { params, ...options },
  );
}

/** 上传文档 */
export async function uploadAdminDocumentApi(
  kbId: number,
  file: File,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeDocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<AdminKnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/upload`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...options,
    },
  );
}

/** 删除文档 */
export async function deleteAdminDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${kbId}/documents/${docId}`, options);
}

/** 重试文档 */
export async function retryAdminDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeDocumentItem> {
  return requestClient.post<AdminKnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/${docId}/retry`,
    {},
    options,
  );
}

/** 获取文档处理进度 */
export async function getAdminDocumentProgressApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<AdminDocumentProgress> {
  return requestClient.get<AdminDocumentProgress>(
    `${PREFIX}/${kbId}/documents/${docId}/progress`,
    options,
  );
}

/** 重新向量化 */
export async function reindexAdminKnowledgeBaseApi(
  kbId: number,
  options?: ApiRequestOptions,
): Promise<{ document_count: number }> {
  return requestClient.post<{ document_count: number }>(
    `${PREFIX}/${kbId}/reindex`,
    {},
    options,
  );
}

/** 文档分块预览（管理端） */
export async function getAdminDocumentChunksApi(
  kbId: number,
  docId: number,
  params?: { page?: number; page_size?: number },
  options?: ApiRequestOptions,
): Promise<{
  chunks: Array<{
    char_count: number;
    chunk_index: number;
    content: string;
    id: number;
    metadata: Record<string, unknown>;
    token_count: number;
  }>;
  total: number;
}> {
  return requestClient.get(`${PREFIX}/${kbId}/documents/${docId}/chunks`, {
    params,
    ...options,
  });
}

/** 检索测试 */
export async function searchAdminKnowledgeBaseApi(
  kbId: number,
  data: {
    query: string;
    score_threshold?: number;
    search_mode?: string;
    top_k?: number;
  },
  options?: ApiRequestOptions,
): Promise<AdminSearchResultItem[]> {
  return requestClient.post<AdminSearchResultItem[]>(
    `${PREFIX}/${kbId}/search`,
    data,
    options,
  );
}

/** 直接文本输入创建文档 */
export async function createAdminTextDocumentApi(
  kbId: number,
  data: { content: string; title: string },
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeDocumentItem> {
  return requestClient.post<AdminKnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/text`,
    data,
    options,
  );
}

/** 添加 Q&A 问答对 */
export async function createAdminQAPairApi(
  kbId: number,
  data: { answer: string; question: string },
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeDocumentItem> {
  return requestClient.post<AdminKnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/qa-pairs`,
    data,
    options,
  );
}

/** URL 网页导入 */
export async function importAdminUrlApi(
  kbId: number,
  urls: string[],
  options?: ApiRequestOptions,
): Promise<{ created: number }> {
  const formData = new FormData();
  urls.forEach((u) => formData.append('urls', u));
  return requestClient.post(
    `${PREFIX}/${kbId}/documents/url`,
    formData,
    options,
  );
}

/** 批量导入 Q&A 问答对（CSV/Excel） */
export async function batchImportAdminQAApi(
  kbId: number,
  file: File,
  options?: ApiRequestOptions,
): Promise<{ errors: string[]; imported: number; skipped: number }> {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(
    `${PREFIX}/${kbId}/qa-pairs/batch`,
    formData,
    options,
  );
}

/** 可选知识库项 */
export interface SelectableKBItem {
  id: number;
  name: string;
  scope: string;
  description: null | string;
}

/** 获取可选知识库列表（管理端：admin + global） */
export async function getAdminSelectableKBApi(
  options?: ApiRequestOptions,
): Promise<SelectableKBItem[]> {
  return requestClient.get<SelectableKBItem[]>(`${PREFIX}/selectable`, options);
}

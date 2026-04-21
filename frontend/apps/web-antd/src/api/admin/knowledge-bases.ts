/**
 * Platform admin knowledge base monitoring API / 平台管理端知识库监控 API
 * Backend: /admin/ai/knowledge-bases/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** Knowledge base list item (all tenants) / 知识库列表项（全企业） */
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
  vision_model_id?: null | number;
  vision_model_name?: null | string;
  extract_images?: boolean;
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

/** Create knowledge base request / 创建知识库请求 */
export interface AdminKnowledgeBaseCreateParams {
  name: string;
  description?: string;
  scope: string;
  visibility?: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  assigned_tenant_ids?: number[];
  embedding_model_id: number;
  vision_model_id?: null | number;
  extract_images?: boolean;
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_strategy?: string;
  search_mode?: string;
  top_k?: number;
  score_threshold?: number;
}

/** Update knowledge base request / 更新知识库请求 */
export interface AdminKnowledgeBaseUpdateParams {
  name?: string;
  description?: string;
  scope?: string;
  visibility?: string;
  tenant_id?: null | number;
  tenant_ids?: number[];
  assigned_tenant_ids?: number[];
  embedding_model_id?: number;
  vision_model_id?: null | number;
  extract_images?: boolean;
}

/** Global stats / 全局统计 */
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

/** Get knowledge base list / 获取知识库列表 */
export async function getAdminKnowledgeBaseListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AdminKnowledgeBaseItem>> {
  return requestClient.get<PageResponse<AdminKnowledgeBaseItem>>(PREFIX, {
    params,
    ...options,
  });
}

/** Get global stats / 获取全局统计 */
export async function getKnowledgeBaseStatsApi(
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseGlobalStats> {
  return requestClient.get<KnowledgeBaseGlobalStats>(
    `${PREFIX}/stats`,
    options,
  );
}

/** Get knowledge base detail / 获取知识库详情 */
export async function getAdminKnowledgeBaseDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeBaseItem> {
  return requestClient.get<AdminKnowledgeBaseItem>(`${PREFIX}/${id}`, options);
}

/** Create knowledge base / 创建知识库 */
export async function createAdminKnowledgeBaseApi(
  data: AdminKnowledgeBaseCreateParams,
  options?: ApiRequestOptions,
): Promise<AdminKnowledgeBaseItem> {
  return requestClient.post<AdminKnowledgeBaseItem>(PREFIX, data, options);
}

/** Update knowledge base / 更新知识库 */
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

/** Force delete knowledge base / 强制删除知识库 */
export async function deleteAdminKnowledgeBaseApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

// ============================================================
// Document sub-resource API / 文档子资源 API
// ============================================================

/** Knowledge base document / 知识库文档 */
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

/** Search result item / 检索结果项 */
export interface AdminSearchResultItem {
  chunk_id: number;
  content: string;
  score: number;
  metadata: null | Record<string, unknown>;
  document_name: string;
  document_id: number;
  highlight: null | string;
}

/** Document processing progress / 文档处理进度 */
export interface AdminDocumentProgress {
  stage: string;
  progress: number;
  total_chunks: number;
  processed_chunks: number;
}

/** Get document list / 获取文档列表 */
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

/** Upload document / 上传文档 */
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

/** Delete document / 删除文档 */
export async function deleteAdminDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${kbId}/documents/${docId}`, options);
}

/** Retry document / 重试文档 */
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

/** Get document processing progress / 获取文档处理进度 */
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

/** Re-vectorize / 重新向量化 */
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

/** Document chunk preview (admin) / 文档分块预览（管理端） */
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

/** Search test / 检索测试 */
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

/** Create document from direct text input / 直接文本输入创建文档 */
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

/** Add Q&A pair / 添加 Q&A 问答对 */
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

/** Import from URL / URL 网页导入 */
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

/** Batch import Q&A pairs (CSV/Excel) / 批量导入 Q&A 问答对 */
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

/** Selectable knowledge base item / 可选知识库项 */
export interface SelectableKBItem {
  id: number;
  name: string;
  scope: string;
  description: null | string;
  owner_tenant_id: null | number;
  owner_tenant_name: null | string;
}

export interface AdminSelectableKBParams {
  agent_id?: number;
}

/** Get selectable knowledge base list / 获取可选知识库列表 */
export async function getAdminSelectableKBApi(
  params?: AdminSelectableKBParams,
  options?: ApiRequestOptions,
): Promise<SelectableKBItem[]> {
  return requestClient.get<SelectableKBItem[]>(`${PREFIX}/selectable`, {
    params,
    ...options,
  });
}

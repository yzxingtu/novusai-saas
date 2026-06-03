/**
 * Tenant knowledge base management API / 企业端知识库管理 API
 * Backend: /tenant/ai/knowledge-bases/* / 对接后端 /tenant/ai/knowledge-bases/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Knowledge base list item / 知识库列表项 */
export interface KnowledgeBaseItem {
  id: number;
  tenant_id: null | number;
  name: string;
  description: null | string;
  avatar: null | string;
  scope: string;
  embedding_model_id: number;
  embedding_model_name: null | string;
  vision_model_id?: null | number;
  vision_model_name?: null | string;
  extract_images?: boolean;
  chunk_size: number;
  chunk_overlap: number;
  chunk_strategy: string;
  search_mode: string;
  top_k: number;
  score_threshold: number;
  document_count: number;
  total_chunks: number;
  total_size_bytes: number;
  status: string;
  created_at: string;
  updated_at: string;
}

/** Create knowledge base request / 创建知识库请求 */
export interface KnowledgeBaseCreateRequest {
  name: string;
  description?: null | string;
  avatar?: null | string;
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
export interface KnowledgeBaseUpdateRequest {
  name?: null | string;
  description?: null | string;
  avatar?: null | string;
  vision_model_id?: null | number;
  extract_images?: boolean;
  chunk_size?: null | number;
  chunk_overlap?: null | number;
  chunk_strategy?: null | string;
  search_mode?: null | string;
  top_k?: null | number;
  score_threshold?: null | number;
  status?: null | string;
}

/** Knowledge base document / 知识库文档 */
export interface KnowledgeDocumentItem {
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
export interface SearchResultItem {
  chunk_id: number;
  content: string;
  score: number;
  metadata: null | Record<string, unknown>;
  document_name: string;
  document_id: number;
  highlight: null | string;
}

/** Q&A pair create request / Q&A 对创建请求 */
export interface QAPairCreateRequest {
  question: string;
  answer: string;
}

/** Document processing progress / 文档处理进度 */
export interface DocumentProgress {
  stage: string;
  progress: number;
  total_chunks: number;
  processed_chunks: number;
}

/** Paginated response / 分页响应 */
interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/tenant/ai/knowledge-bases';

/** Get knowledge base list / 获取知识库列表 */
export async function getKnowledgeBaseListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<KnowledgeBaseItem>> {
  return requestClient.get<PageResponse<KnowledgeBaseItem>>(PREFIX, {
    params,
    ...options,
  });
}

/** Get knowledge base detail / 获取知识库详情 */
export async function getKnowledgeBaseDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.get<KnowledgeBaseItem>(`${PREFIX}/${id}`, options);
}

/** Create knowledge base / 创建知识库 */
export async function createKnowledgeBaseApi(
  data: KnowledgeBaseCreateRequest,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.post<KnowledgeBaseItem>(PREFIX, data, options);
}

/** Update knowledge base / 更新知识库 */
export async function updateKnowledgeBaseApi(
  id: number,
  data: KnowledgeBaseUpdateRequest,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.put<KnowledgeBaseItem>(`${PREFIX}/${id}`, data, options);
}

/** Delete knowledge base / 删除知识库 */
export async function deleteKnowledgeBaseApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** Get document list / 获取文档列表 */
export async function getDocumentListApi(
  kbId: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<KnowledgeDocumentItem>> {
  return requestClient.get<PageResponse<KnowledgeDocumentItem>>(
    `${PREFIX}/${kbId}/documents`,
    { params, ...options },
  );
}

/** Upload document / 上传文档 */
export async function uploadDocumentApi(
  kbId: number,
  file: File,
  options?: ApiRequestOptions,
): Promise<KnowledgeDocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<KnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/upload`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...options,
    },
  );
}

/** Delete document / 删除文档 */
export async function deleteDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${kbId}/documents/${docId}`, options);
}

/** Retry document / 重试文档 */
export async function retryDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<KnowledgeDocumentItem> {
  return requestClient.post<KnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/${docId}/retry`,
    {},
    options,
  );
}

/** Get document processing progress / 获取文档处理进度 */
export async function getDocumentProgressApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<DocumentProgress> {
  return requestClient.get<DocumentProgress>(
    `${PREFIX}/${kbId}/documents/${docId}/progress`,
    options,
  );
}

/** Re-index (re-vectorize) / 重新向量化 */
export async function reindexKnowledgeBaseApi(
  kbId: number,
  options?: ApiRequestOptions,
): Promise<{ document_count: number }> {
  return requestClient.post<{ document_count: number }>(
    `${PREFIX}/${kbId}/reindex`,
    {},
    options,
  );
}

/** Create document from text input / 直接文本输入创建文档 */
export async function createTextDocumentApi(
  kbId: number,
  data: { content: string; title: string },
  options?: ApiRequestOptions,
): Promise<KnowledgeDocumentItem> {
  return requestClient.post<KnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/documents/text`,
    data,
    options,
  );
}

/** Add Q&A pair / 添加 Q&A 问答对 */
export async function createQAPairApi(
  kbId: number,
  data: QAPairCreateRequest,
  options?: ApiRequestOptions,
): Promise<KnowledgeDocumentItem> {
  return requestClient.post<KnowledgeDocumentItem>(
    `${PREFIX}/${kbId}/qa-pairs`,
    data,
    options,
  );
}

/** Import from URL / URL 网页导入 */
export async function importUrlApi(
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
export async function batchImportQAApi(
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

/** Get selectable knowledge base list (tenant: own + global) / 获取可选知识库列表 */
export async function getTenantSelectableKBApi(
  options?: ApiRequestOptions,
): Promise<SelectableKBItem[]> {
  return requestClient.get<SelectableKBItem[]>(`${PREFIX}/selectable`, options);
}

/** Document chunk preview / 文档分块预览 */
export async function getDocumentChunksApi(
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
export async function searchKnowledgeBaseApi(
  kbId: number,
  data: {
    query: string;
    score_threshold?: number;
    search_mode?: string;
    top_k?: number;
  },
  options?: ApiRequestOptions,
): Promise<SearchResultItem[]> {
  return requestClient.post<SearchResultItem[]>(
    `${PREFIX}/${kbId}/search`,
    data,
    options,
  );
}

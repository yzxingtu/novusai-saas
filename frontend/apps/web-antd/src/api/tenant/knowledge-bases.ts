/**
 * 租户端知识库管理 API
 * 对接后端 /tenant/ai/knowledge-bases/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 知识库列表项 */
export interface KnowledgeBaseItem {
  id: number;
  tenant_id: number;
  name: string;
  description: string | null;
  avatar: string | null;
  embedding_model_id: number;
  embedding_model_name: string | null;
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

/** 创建知识库请求 */
export interface KnowledgeBaseCreateRequest {
  name: string;
  description?: string | null;
  avatar?: string | null;
  embedding_model_id: number;
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_strategy?: string;
  search_mode?: string;
  top_k?: number;
  score_threshold?: number;
}

/** 更新知识库请求 */
export interface KnowledgeBaseUpdateRequest {
  name?: string | null;
  description?: string | null;
  avatar?: string | null;
  chunk_size?: number | null;
  chunk_overlap?: number | null;
  chunk_strategy?: string | null;
  search_mode?: string | null;
  top_k?: number | null;
  score_threshold?: number | null;
  status?: string | null;
}

/** 知识库文档 */
export interface KnowledgeDocumentItem {
  id: number;
  knowledge_base_id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  file_hash: string | null;
  status: string;
  error_message: string | null;
  error_stage: string | null;
  chunk_count: number;
  token_count: number;
  char_count: number;
  created_at: string;
  updated_at: string;
}

/** 检索结果项 */
export interface SearchResultItem {
  chunk_id: number;
  content: string;
  score: number;
  metadata: Record<string, unknown> | null;
  document_name: string;
  document_id: number;
  highlight: string | null;
}

/** Q&A 对创建请求 */
export interface QAPairCreateRequest {
  question: string;
  answer: string;
}

/** 文档处理进度 */
export interface DocumentProgress {
  stage: string;
  progress: number;
  total_chunks: number;
  processed_chunks: number;
}

/** 分页响应 */
interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/knowledge-bases';

/** 获取知识库列表 */
export async function getKnowledgeBaseListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<KnowledgeBaseItem>> {
  return requestClient.get<PageResponse<KnowledgeBaseItem>>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取知识库详情 */
export async function getKnowledgeBaseDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.get<KnowledgeBaseItem>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建知识库 */
export async function createKnowledgeBaseApi(
  data: KnowledgeBaseCreateRequest,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.post<KnowledgeBaseItem>(
    PREFIX,
    data,
    options,
  );
}

/** 更新知识库 */
export async function updateKnowledgeBaseApi(
  id: number,
  data: KnowledgeBaseUpdateRequest,
  options?: ApiRequestOptions,
): Promise<KnowledgeBaseItem> {
  return requestClient.put<KnowledgeBaseItem>(
    `${PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除知识库 */
export async function deleteKnowledgeBaseApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 获取文档列表 */
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

/** 上传文档 */
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

/** 删除文档 */
export async function deleteDocumentApi(
  kbId: number,
  docId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${PREFIX}/${kbId}/documents/${docId}`,
    options,
  );
}

/** 重试文档 */
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

/** 获取文档处理进度 */
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

/** 重新向量化 */
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

/** 添加 Q&A 问答对 */
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

/** 可选知识库项 */
export interface SelectableKBItem {
  id: number;
  name: string;
  scope: string;
  description: string | null;
}

/** 获取可选知识库列表（租户端：自己的 + global） */
export async function getTenantSelectableKBApi(
  options?: ApiRequestOptions,
): Promise<SelectableKBItem[]> {
  return requestClient.get<SelectableKBItem[]>(
    `${PREFIX}/selectable`,
    options,
  );
}

/** 检索测试 */
export async function searchKnowledgeBaseApi(
  kbId: number,
  data: { query: string; top_k?: number; score_threshold?: number; search_mode?: string },
  options?: ApiRequestOptions,
): Promise<SearchResultItem[]> {
  return requestClient.post<SearchResultItem[]>(
    `${PREFIX}/${kbId}/search`,
    data,
    options,
  );
}

/**
 * Admin long-term memory debug API / 平台管理端长期记忆调试 API
 */

import { requestClient } from '#/utils/request';

const MEMORY_PREFIX = '/admin/ai/long-term-memory/debug';
const EPHEMERAL_PREFIX = '/admin/ai/ephemeral-rag/documents';

export interface AdminMemoryRecordItem {
  agent_id: null | number;
  confidence: number;
  content_hash: string;
  created_at: string;
  embedding_dimensions?: null | number;
  embedding_model_id?: null | number;
  id: number;
  importance: number;
  last_recalled_at?: null | string;
  memory_type: string;
  scope_key: string;
  scope_type: string;
  source_kind?: null | string;
  source_ref?: null | string;
  status: string;
  summary?: null | string;
  tenant_id: number;
  updated_at: string;
  user_id: null | number;
}

export interface AdminProfileSnapshotItem {
  agent_id: null | number;
  created_at: string;
  id: number;
  profile_json?: null | Record<string, unknown>;
  record_count: number;
  scope_key: string;
  scope_type: string;
  source_updated_at?: null | string;
  summary?: null | string;
  tenant_id: number;
  updated_at: string;
  user_id: null | number;
}

export interface AdminEphemeralDocumentItem {
  agent_id: null | number;
  content_kind: string;
  conversation_id: null | number;
  created_at: string;
  expires_at?: null | string;
  id: number;
  last_used_at?: null | string;
  promoted_document_id?: null | number;
  promoted_knowledge_base_id?: null | number;
  scope_key: string;
  scope_type: string;
  source_ref?: null | string;
  status: string;
  tenant_id: number;
  title: string;
  updated_at: string;
  user_id: null | number;
}

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export function getAdminMemoryRecordListApi(params?: Record<string, unknown>) {
  return requestClient.get<PageResponse<AdminMemoryRecordItem>>(
    `${MEMORY_PREFIX}/records`,
    { params },
  );
}

export function getAdminProfileSnapshotListApi(params?: Record<string, unknown>) {
  return requestClient.get<PageResponse<AdminProfileSnapshotItem>>(
    `${MEMORY_PREFIX}/profiles`,
    { params },
  );
}

export function getAdminProfileSnapshotDetailApi(id: number) {
  return requestClient.get<AdminProfileSnapshotItem | null>(
    `${MEMORY_PREFIX}/profiles/${id}`,
  );
}

export function getAdminEphemeralDocumentListApi(params?: Record<string, unknown>) {
  return requestClient.get<PageResponse<AdminEphemeralDocumentItem>>(
    EPHEMERAL_PREFIX,
    { params },
  );
}

export function getAdminEphemeralDocumentDetailApi(id: number) {
  return requestClient.get<
    (AdminEphemeralDocumentItem & { content?: string | null }) | null
  >(`${EPHEMERAL_PREFIX}/${id}`);
}

export function promoteAdminEphemeralDocumentApi(
  id: number,
  knowledgeBaseId: number,
) {
  return requestClient.post<{
    document_id: number;
    knowledge_base_id: number;
    status: string;
  }>(`${EPHEMERAL_PREFIX}/${id}/promote`, null, {
    params: { knowledge_base_id: knowledgeBaseId },
  });
}

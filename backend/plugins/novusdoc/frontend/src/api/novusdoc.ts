/**
 * NovusDoc API layer — uses host requestClient from NovusPluginShared
 * NovusDoc API 层 — 使用宿主 NovusPluginShared 的 requestClient
 */

import type { DocDetail, DocItem, Folder, Tag } from '../types';

const getClient = () => {
  const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
    requestClient: {
      get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
      post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
      put: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
      delete: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    };
  };
  return shared.requestClient;
};

function resolveBase(): string {
  return location.pathname.includes('/admin/')
    ? '/admin/plugins/novusdoc/api'
    : '/tenant/plugins/novusdoc/api';
}

// ── Documents ─────────────────────────────────────────────

interface ListDocsResult {
  items: DocItem[];
  total: number;
  page: number;
  size: number;
}

export async function listDocs(params: {
  page?: number;
  size?: number;
  folder_id?: number | null;
  status?: string | null;
  tenant_id?: number;
}): Promise<ListDocsResult> {
  const base = resolveBase();
  const q = new URLSearchParams();
  if (params.page) q.set('page', String(params.page));
  if (params.size) q.set('size', String(params.size));
  if (params.folder_id) q.set('folder_id', String(params.folder_id));
  if (params.status) q.set('status', params.status);
  if (params.tenant_id) q.set('tenant_id', String(params.tenant_id));
  return getClient().get<ListDocsResult>(`${base}/docs?${q.toString()}`);
}

export async function getDoc(docId: number, tenantId?: number): Promise<{ document: DocDetail }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().get<{ document: DocDetail }>(`${base}/docs/${docId}${q}`);
}

export async function createDoc(data: Record<string, unknown>, tenantId?: number): Promise<{ document: DocDetail }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().post<{ document: DocDetail }>(`${base}/docs${q}`, data);
}

export async function updateDoc(docId: number, data: Record<string, unknown>, tenantId?: number): Promise<{ document: DocDetail }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().put<{ document: DocDetail }>(`${base}/docs/${docId}${q}`, data);
}

export async function deleteDoc(docId: number, tenantId?: number): Promise<void> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  await getClient().delete(`${base}/docs/${docId}${q}`);
}

// ── Folders ───────────────────────────────────────────────

export async function listFolders(tenantId?: number): Promise<{ items: Folder[]; total: number }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().get<{ items: Folder[]; total: number }>(`${base}/folders${q}`);
}

export async function createFolder(data: { name: string; parent_id?: number | null }, tenantId?: number): Promise<{ folder: Folder }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().post<{ folder: Folder }>(`${base}/folders${q}`, data);
}

export async function updateFolder(folderId: number, data: { name: string }, tenantId?: number): Promise<{ folder: Folder }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().put<{ folder: Folder }>(`${base}/folders/${folderId}${q}`, data);
}

export async function deleteFolder(folderId: number, tenantId?: number): Promise<void> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  await getClient().delete(`${base}/folders/${folderId}${q}`);
}

// ── Tags ──────────────────────────────────────────────────

export async function listTags(tenantId?: number): Promise<{ items: Tag[]; total: number }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().get<{ items: Tag[]; total: number }>(`${base}/tags${q}`);
}

export async function createTag(data: { name: string; color?: string }, tenantId?: number): Promise<{ tag: Tag }> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  return getClient().post<{ tag: Tag }>(`${base}/tags${q}`, data);
}

export async function deleteTag(tagId: number, tenantId?: number): Promise<void> {
  const base = resolveBase();
  const q = tenantId ? `?tenant_id=${tenantId}` : '';
  await getClient().delete(`${base}/tags/${tagId}${q}`);
}

// ── Search ────────────────────────────────────────────────

export async function searchDocs(query: string, params?: { page?: number; size?: number; tenant_id?: number }): Promise<{ items: DocItem[]; total: number }> {
  const base = resolveBase();
  const q = new URLSearchParams();
  q.set('q', query);
  if (params?.page) q.set('page', String(params.page));
  if (params?.size) q.set('size', String(params.size));
  if (params?.tenant_id) q.set('tenant_id', String(params.tenant_id));
  return getClient().get<{ items: DocItem[]; total: number }>(`${base}/search?${q.toString()}`);
}

// ── Export ─────────────────────────────────────────────────

export function getExportUrl(docId: number, format: 'html' | 'md' = 'html', tenantId?: number): string {
  const base = resolveBase();
  const q = new URLSearchParams({ format });
  if (tenantId) q.set('tenant_id', String(tenantId));
  const relative = `${base}/docs/${docId}/export?${q.toString()}`;
  const client = getClient() as unknown as { getBaseUrl?: () => string | undefined };
  const apiBase = client.getBaseUrl?.()?.replace(/\/+$/, '') ?? '';
  return apiBase ? `${apiBase}${relative}` : relative;
}

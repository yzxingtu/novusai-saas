/**
 * NovusDoc 文档 API
 *
 * 通过 @novus/plugin-shared 的 requestClient 调用插件 API dispatcher
 */

import { requestClient } from '@novus/plugin-shared';

const BASE = '/tenant/plugins/novusdoc/api';

export interface DocItem {
  id: number;
  tenant_id: number;
  title: string;
  folder_id: number | null;
  status: string;
  is_starred: boolean;
  word_count: number;
  cover_image: string | null;
  creator_id: number | null;
  creator_type: string | null;
  last_edited_by: number | null;
  last_edited_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  content?: Record<string, unknown> | null;
  content_html?: string | null;
}

export interface FolderItem {
  id: number;
  name: string;
  parent_id: number | null;
  sort_order: number;
  creator_id: number | null;
  created_at: string | null;
  children: FolderItem[];
}

export interface TagItem {
  id: number;
  name: string;
  color: string | null;
}

export interface ListResponse<T> {
  data: {
    items: T[];
    total: number;
    page?: number;
    size?: number;
    tree?: T[];
  };
}

export function listDocsApi(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : '';
  return requestClient.get<ListResponse<DocItem>>(`${BASE}/docs${query}`);
}

export function getDocApi(id: number) {
  return requestClient.get<{ data: DocItem }>(`${BASE}/docs/${id}`);
}

export function createDocApi(data: Record<string, unknown>) {
  return requestClient.post<{ data: DocItem }>(`${BASE}/docs`, data);
}

export function updateDocApi(id: number, data: Record<string, unknown>) {
  return requestClient.put<{ data: DocItem }>(`${BASE}/docs/${id}`, data);
}

export function deleteDocApi(id: number) {
  return requestClient.delete<{ data: { message: string } }>(`${BASE}/docs/${id}`);
}

export function listFoldersApi() {
  return requestClient.get<ListResponse<FolderItem>>(`${BASE}/folders`);
}

export function createFolderApi(data: { name: string; parent_id?: number | null }) {
  return requestClient.post<{ data: FolderItem }>(`${BASE}/folders`, data);
}

export function updateFolderApi(id: number, data: Record<string, unknown>) {
  return requestClient.put<{ data: FolderItem }>(`${BASE}/folders/${id}`, data);
}

export function deleteFolderApi(id: number) {
  return requestClient.delete<{ data: { message: string } }>(`${BASE}/folders/${id}`);
}

export function listTagsApi() {
  return requestClient.get<ListResponse<TagItem>>(`${BASE}/tags`);
}

export function createTagApi(data: { name: string; color?: string }) {
  return requestClient.post<{ data: TagItem }>(`${BASE}/tags`, data);
}

export function deleteTagApi(id: number) {
  return requestClient.delete<{ data: { message: string } }>(`${BASE}/tags/${id}`);
}

export function searchDocsApi(q: string, params?: Record<string, string>) {
  const p = new URLSearchParams({ q, ...params });
  return requestClient.get<ListResponse<DocItem>>(`${BASE}/search?${p.toString()}`);
}

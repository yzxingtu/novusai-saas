/**
 * NovusDoc Pro API helpers
 *
 * Called from base novusdoc editor when Pro plugin is detected.
 * Routes go through novusdoc-pro's API dispatcher.
 */

import { requestClient } from '@novus/plugin-shared';

function getProBase(): string {
  const path = window.location.pathname;
  if (path.startsWith('/admin')) {
    return '/admin/plugins/novusdoc-pro/api';
  }
  return '/tenant/plugins/novusdoc-pro/api';
}

// ── Version History ──

export interface VersionItem {
  id: number;
  title: string;
  word_count: number;
  creator_name: string | null;
  version_note: string | null;
  created_at: string | null;
}

export function listVersionsApi(docId: number) {
  return requestClient.get<{ items: VersionItem[]; total: number }>(
    `${getProBase()}/docs/${docId}/versions`,
  );
}

export function createVersionApi(docId: number, data: Record<string, unknown>) {
  return requestClient.post<{ id: number; title: string }>(
    `${getProBase()}/docs/${docId}/versions`,
    data,
  );
}

export function restoreVersionApi(docId: number, versionId: number) {
  return requestClient.post<{ message: string }>(
    `${getProBase()}/docs/${docId}/versions/${versionId}/restore`,
  );
}

// ── Comments ──

export interface CommentItem {
  id: number;
  document_id: number;
  content: string;
  creator_id: number | null;
  creator_name: string | null;
  is_resolved: boolean;
  anchor_from: number | null;
  anchor_to: number | null;
  quoted_text: string | null;
  created_at: string | null;
}

export function listCommentsApi(docId: number) {
  return requestClient.get<{ items: CommentItem[]; total: number }>(
    `${getProBase()}/docs/${docId}/comments`,
  );
}

export function createCommentApi(docId: number, data: Record<string, unknown>) {
  return requestClient.post<{ id: number }>(
    `${getProBase()}/docs/${docId}/comments`,
    data,
  );
}

export function resolveCommentApi(docId: number, commentId: number) {
  return requestClient.post<{ id: number; is_resolved: boolean }>(
    `${getProBase()}/docs/${docId}/comments/${commentId}/resolve`,
  );
}

// ── Share ──

export function createShareApi(docId: number, data: Record<string, unknown>) {
  return requestClient.post<{ token: string; permission: string }>(
    `${getProBase()}/docs/${docId}/share`,
    data,
  );
}

// ── Export ──

export function exportWordApi(docId: number) {
  return requestClient.post(`${getProBase()}/docs/${docId}/export/word`, {}, {
    responseType: 'blob',
  });
}

export function exportPdfApi(docId: number) {
  return requestClient.post(`${getProBase()}/docs/${docId}/export/pdf`, {}, {
    responseType: 'blob',
  });
}

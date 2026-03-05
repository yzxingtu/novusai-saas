/**
 * DataForge Studio Plugin - API functions
 * Following the storage-migration plugin pattern with requestClient from @novus/plugin-shared
 */
import type { NccProject, NccRecord, NccRelation, NccTableSchema } from './types';

import { requestClient } from '@novus/plugin-shared';

const PLUGIN_API_BASE = '/admin/plugins/novus-crud-code/api';

interface ApiEnvelope<T = unknown> {
  code: number;
  data: T;
  message: string;
}

function isApiEnvelope(value: unknown): value is ApiEnvelope {
  if (!value || typeof value !== 'object') return false;
  return 'code' in value && 'data' in value && 'message' in value;
}

function unwrapApiData<T>(payload: unknown): T {
  let current: unknown = payload;
  let depth = 0;
  while (isApiEnvelope(current) && depth < 8) {
    current = current.data;
    depth += 1;
  }
  return current as T;
}

// ── Projects ─────────────────────────────────────────────────────────────────

export function listProjectsApi(page = 1, size = 100) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects`, {
      params: { 'page[number]': page, 'page[size]': size, sort: '-created_at' },
    })
    .then((res: unknown) => unwrapApiData<{ items: NccProject[]; total: number }>(res));
}

export function getProjectApi(id: number) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects/${id}`)
    .then((res: unknown) => unwrapApiData<NccProject>(res));
}

export function createProjectApi(data: Partial<NccProject>) {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/projects`, data)
    .then((res: unknown) => unwrapApiData<NccProject>(res));
}

export function updateProjectApi(id: number, data: Partial<NccProject>) {
  return requestClient
    .put<unknown>(`${PLUGIN_API_BASE}/projects/${id}`, data)
    .then((res: unknown) => unwrapApiData<NccProject>(res));
}

export function deleteProjectApi(id: number) {
  return requestClient
    .delete<unknown>(`${PLUGIN_API_BASE}/projects/${id}`)
    .then((res: unknown) => unwrapApiData<void>(res));
}

// ── Schemas ──────────────────────────────────────────────────────────────────

export function listSchemasApi(projectId: number) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas`, {
      params: { 'page[size]': 100 },
    })
    .then((res: unknown) => unwrapApiData<{ items: NccTableSchema[] }>(res));
}

export function getSchemaApi(projectId: number, schemaId: number) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}`)
    .then((res: unknown) => unwrapApiData<NccTableSchema>(res));
}

export function createSchemaApi(projectId: number, data: Partial<NccTableSchema>) {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas`, data)
    .then((res: unknown) => unwrapApiData<NccTableSchema>(res));
}

export function updateSchemaApi(projectId: number, schemaId: number, data: Partial<NccTableSchema>) {
  return requestClient
    .put<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}`, data)
    .then((res: unknown) => unwrapApiData<NccTableSchema>(res));
}

export function deleteSchemaApi(projectId: number, schemaId: number) {
  return requestClient
    .delete<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}`)
    .then((res: unknown) => unwrapApiData<void>(res));
}

// ── Relations ────────────────────────────────────────────────────────────────

export function listRelationsApi(projectId: number) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/relations`)
    .then((res: unknown) => unwrapApiData<{ items: NccRelation[] }>(res));
}

// ── Records ──────────────────────────────────────────────────────────────────

export function listRecordsApi(projectId: number, schemaId: number, page = 1, size = 50) {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}/records`, {
      params: { 'page[number]': page, 'page[size]': size },
    })
    .then((res: unknown) => unwrapApiData<{ items: NccRecord[]; total: number }>(res));
}

export function createRecordApi(projectId: number, schemaId: number, data: Record<string, unknown>) {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}/records`, { data })
    .then((res: unknown) => unwrapApiData<NccRecord>(res));
}

export function updateRecordApi(projectId: number, schemaId: number, recordId: number, data: Record<string, unknown>) {
  return requestClient
    .put<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}/records/${recordId}`, { data })
    .then((res: unknown) => unwrapApiData<NccRecord>(res));
}

export function deleteRecordApi(projectId: number, schemaId: number, recordId: number) {
  return requestClient
    .delete<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}/records/${recordId}`)
    .then((res: unknown) => unwrapApiData<void>(res));
}

export function bulkDeleteRecordsApi(projectId: number, schemaId: number, ids: number[]) {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/schemas/${schemaId}/records/bulk`, { ids })
    .then((res: unknown) => unwrapApiData<void>(res));
}

// ── AI Chat ──────────────────────────────────────────────────────────────────

export function aiChatApi(projectId: number, msg: string, featureCode = 'data_analytics') {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/projects/${projectId}/ai/chat`, {
      message: msg,
      feature_code: featureCode,
    })
    .then((res: unknown) => unwrapApiData<{ reply: string }>(res));
}

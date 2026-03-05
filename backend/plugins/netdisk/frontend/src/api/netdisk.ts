/**
 * 企业网盘 API 封装
 * 必须使用 requestClient（来自宿主注入），禁止直接 fetch / axios
 */

// 从宿主注入的共享 API 获取 requestClient
const getClient = () => {
  const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
    requestClient: {
      get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
      post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
      patch: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
      delete: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    };
  };
  return shared.requestClient;
};

const BASE = '/tenant/plugins/netdisk/api';
const ADMIN_BASE = '/admin/plugins/netdisk/api';

// ── 类型定义 ──────────────────────────────────────────────────

export interface FileNode {
  id: number;
  parentId: number | null;
  name: string;
  nodeType: 'file' | 'folder';
  sizeBytes: number;
  mimeType: string | null;
  isDeleted: boolean;
  deletedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface BreadcrumbItem {
  id: number | null;
  name: string;
}

export interface QuotaInfo {
  quotaBytes: number;
  usedBytes: number;
  freeBytes: number;
  usedPercent: number;
}

export interface Share {
  id: number;
  nodeId: number;
  nodeName: string | null;
  nodeType: 'file' | 'folder' | null;
  shareToken: string;
  permission: 'read' | 'download';
  hasPassword: boolean;
  expiresAt: string | null;
  accessCount: number;
  isActive: boolean;
  createdAt: string | null;
}

export interface UploadInitResult {
  uploadId: string;
  chunkSize: number;
  totalSize: number;
}

// ── 文件节点 API ──────────────────────────────────────────────

export function listNodesApi(params: { parent_id?: number | null; sort?: string }) {
  const client = getClient();
  return client.get<{ data: FileNode[] }>(`${BASE}/nodes`, { params });
}

export function getNodeApi(nodeId: number) {
  const client = getClient();
  return client.get<{ data: { node: FileNode; breadcrumbs: FileNode[] } }>(`${BASE}/nodes/${nodeId}`);
}

export function createFolderApi(body: { parent_id?: number | null; name: string }) {
  const client = getClient();
  return client.post<{ data: FileNode }>(`${BASE}/nodes/folder`, body);
}

export function renameNodeApi(nodeId: number, name: string) {
  const client = getClient();
  return client.patch<{ data: FileNode }>(`${BASE}/nodes/${nodeId}`, { name });
}

export function moveNodeApi(nodeId: number, newParentId: number | null) {
  const client = getClient();
  return client.post<{ data: FileNode }>(`${BASE}/nodes/${nodeId}/move`, { new_parent_id: newParentId });
}

export function copyNodeApi(nodeId: number, newParentId: number | null) {
  const client = getClient();
  return client.post<{ data: FileNode }>(`${BASE}/nodes/${nodeId}/copy`, { new_parent_id: newParentId });
}

export function deleteNodeApi(nodeId: number, permanent = false) {
  const client = getClient();
  return client.delete<void>(`${BASE}/nodes/${nodeId}`, { params: { permanent } });
}

export function batchOpApi(action: 'delete' | 'move' | 'copy', nodeIds: number[], extra?: Record<string, unknown>) {
  const client = getClient();
  return client.post<{ data: { count: number } }>(`${BASE}/batch`, { action, node_ids: nodeIds, ...extra });
}

export function searchFilesApi(params: { q: string; node_type?: string; limit?: number }) {
  const client = getClient();
  return client.get<{ data: FileNode[] }>(`${BASE}/search`, { params });
}

// ── 上传 / 下载 API ───────────────────────────────────────────

export function initUploadApi(body: { filename: string; size: number; parent_id?: number | null }) {
  const client = getClient();
  return client.post<{ data: UploadInitResult }>(`${BASE}/upload/init`, body);
}

export function uploadPartApi(uploadId: string, partNo: number, data: Blob) {
  const client = getClient();
  const form = new FormData();
  form.append('file', data);
  return client.post<{ data: { part_no: number; status: string } }>(
    `${BASE}/upload/part?upload_id=${uploadId}&part_no=${partNo}`,
    form,
  );
}

export function completeUploadApi(uploadId: string) {
  const client = getClient();
  return client.post<{ data: FileNode }>(`${BASE}/upload/complete`, { upload_id: uploadId });
}

export function getUploadStatusApi(uploadId: string) {
  const client = getClient();
  return client.get<{ data: { uploaded_parts: number[] } }>(`${BASE}/upload/status/${uploadId}`);
}

export function getDownloadUrlApi(nodeId: number) {
  const client = getClient();
  return client.get<{ data: { url: string } }>(`${BASE}/nodes/${nodeId}/download`);
}

// ── 分享 API ──────────────────────────────────────────────────

export function createShareApi(
  nodeId: number,
  body: { permission?: string; password?: string; expires_days?: number },
) {
  const client = getClient();
  return client.post<{ data: Share }>(`${BASE}/nodes/${nodeId}/share`, body);
}

export function cancelShareApi(token: string) {
  const client = getClient();
  return client.delete<void>(`${BASE}/shares/${token}`);
}

export function listMySharesApi(page = 1, size = 50) {
  const client = getClient();
  return client.get<{ data: { items: Share[]; total: number } }>(
    `${BASE}/shares`,
    { params: { page, size } },
  );
}

export function listNodeSharesApi(nodeId: number) {
  const client = getClient();
  return client.get<{ data: Share[] }>(`${BASE}/nodes/${nodeId}/shares`);
}

// ── 配额 API ──────────────────────────────────────────────────

export function getQuotaApi() {
  const client = getClient();
  return client.get<{ data: QuotaInfo }>(`${BASE}/quota`);
}

// ── 回收站 API ────────────────────────────────────────────────

export function listTrashApi() {
  const client = getClient();
  return client.get<{ data: { items: FileNode[]; total: number } }>(`${BASE}/trash`);
}

export function restoreNodeApi(nodeId: number) {
  const client = getClient();
  return client.post<{ data: FileNode }>(`${BASE}/trash/${nodeId}/restore`, {});
}

export function clearTrashApi() {
  const client = getClient();
  return client.delete<void>(`${BASE}/trash`);
}

// ── 管理端 API ────────────────────────────────────────────────

export function adminGetStatsApi() {
  const client = getClient();
  return client.get<{ data: Record<string, number> }>(`${ADMIN_BASE}/admin/stats`);
}

export function adminListQuotasApi(page = 1, size = 20) {
  const client = getClient();
  return client.get(`${ADMIN_BASE}/admin/quotas`, { params: { page, size } });
}

export function adminUpdateQuotaApi(tenantId: number, quotaBytes: number) {
  const client = getClient();
  return client.patch(`${ADMIN_BASE}/admin/quotas/${tenantId}`, { quota_bytes: quotaBytes });
}

export function adminListSharesApi(page = 1, size = 20) {
  const client = getClient();
  return client.get(`${ADMIN_BASE}/admin/shares`, { params: { page, size } });
}

export function adminRevokeShareApi(token: string) {
  const client = getClient();
  return client.delete(`${ADMIN_BASE}/admin/shares/${token}`);
}

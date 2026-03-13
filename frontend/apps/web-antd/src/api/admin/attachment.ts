/**
 * Platform attachment management API / 平台端附件管理 API
 * Backend: /admin/attachments/*
 *
 * @module api/admin/attachment
 */
import type {
  AttachmentInfo,
  AttachmentInfoRaw,
  AttachmentListParams,
  AttachmentStats,
  AttachmentStatsByTenant,
  AttachmentUrlResult,
} from '#/types/attachment';
import type { PaginatedResponse, SelectOption } from '#/types/query';
import type { ApiRequestOptions } from '#/utils/request';

import { inferCategory } from '#/types/attachment';
import { computeFileHash } from '#/utils/file-hash';
import { requestClient } from '#/utils/request';

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend snake_case to frontend camelCase / 将后端 snake_case 转换为前端 camelCase */
function transformAttachmentInfo(raw: AttachmentInfoRaw): AttachmentInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    name: raw.name,
    originalName: raw.original_name,
    path: raw.path,
    size: raw.size,
    hash: raw.hash,
    mimeType: raw.mime_type,
    extension: raw.extension,
    visibility: raw.visibility,
    driver: raw.driver,
    baseUrl: raw.base_url,
    status: raw.status,
    source: raw.source,
    uploaderId: raw.uploader_id,
    businessType: raw.business_type,
    businessId: raw.business_id,
    meta: raw.meta,
    previewUrl: raw.preview_url,
    category: inferCategory(raw.mime_type),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Attachment list response / 附件列表响应 */
export interface AttachmentListResponse {
  items: AttachmentInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/admin/attachments';

/**
 * Get attachment list / 获取附件列表
 * GET /admin/attachments
 *
 * Permission: attachment:list
 * Supports tenant filter: filter[tenant_id][eq]=1
 */
export async function getAttachmentListApi(
  params?: AttachmentListParams,
  options?: ApiRequestOptions,
): Promise<AttachmentListResponse> {
  const response = await requestClient.get<
    PaginatedResponse<AttachmentInfoRaw>
  >(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformAttachmentInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get attachment detail / 获取附件详情
 * GET /admin/attachments/{attachment_id}
 *
 * Permission: attachment:detail
 */
export async function getAttachmentDetailApi(
  attachmentId: number,
  options?: ApiRequestOptions,
): Promise<AttachmentInfo> {
  const raw = await requestClient.get<AttachmentInfoRaw>(
    `${API_PREFIX}/${attachmentId}`,
    options,
  );
  return transformAttachmentInfo(raw);
}

/**
 * Delete attachment / 删除附件
 * DELETE /admin/attachments/{attachment_id}
 *
 * Permission: attachment:delete
 */
export async function deleteAttachmentApi(
  attachmentId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${attachmentId}`, options);
}

/**
 * Get attachment select options / 获取附件下拉选项
 * GET /admin/attachments/select
 */
export async function getAttachmentSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectOption[]> {
  const response = await requestClient.get<{ items: SelectOption[] }>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
  return response.items;
}

/**
 * Get attachment stats / 获取附件统计
 * GET /admin/attachments/stats
 */
export async function getAttachmentStatsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AttachmentStats> {
  return requestClient.get<AttachmentStats>(`${API_PREFIX}/stats`, {
    params,
    ...options,
  });
}

/**
 * Get attachment stats by tenant / 获取按租户分组的附件统计
 * GET /admin/attachments/stats/by-tenant
 */
export async function getAttachmentStatsByTenantApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AttachmentStatsByTenant[]> {
  const response = await requestClient.get<{
    items: AttachmentStatsByTenant[];
  }>(`${API_PREFIX}/stats/by-tenant`, { params, ...options });
  return response.items;
}

/**
 * Get download URL / 获取下载链接
 * GET /admin/attachments/{attachment_id}/download-url
 */
export async function getAttachmentDownloadUrlApi(
  attachmentId: number,
  params?: { expires?: number },
  options?: ApiRequestOptions,
): Promise<AttachmentUrlResult> {
  return requestClient.get<AttachmentUrlResult>(
    `${API_PREFIX}/${attachmentId}/download-url`,
    { params, ...options },
  );
}

/**
 * Get preview URL / 获取预览链接
 * GET /admin/attachments/{attachment_id}/preview-url
 */
export async function getAttachmentPreviewUrlApi(
  attachmentId: number,
  params?: { expires?: number },
  options?: ApiRequestOptions,
): Promise<AttachmentUrlResult> {
  return requestClient.get<AttachmentUrlResult>(
    `${API_PREFIX}/${attachmentId}/preview-url`,
    { params, ...options },
  );
}

// ============================================================
// Upload API / 上传接口
// ============================================================

/** Upload attachment response (backend nested structure) / 上传附件响应 */
export interface AdminUploadAttachmentResponse {
  attachment: AttachmentInfoRaw;
  url: string;
  used_bytes: number;
}

/** Chunk upload init response / 分片上传初始化响应 */
export interface AdminChunkUploadInitResponse {
  upload_id: string;
  filename: string;
  total_size: number;
  chunk_size: number;
  chunk_count: number;
  uploaded_chunks: number[];
  uploaded_bytes: number;
  progress: number;
}

/** Chunk upload progress response / 分片上传进度响应 */
export interface AdminChunkUploadResponse {
  upload_id: string;
  filename: string;
  total_size: number;
  chunk_size: number;
  chunk_count: number;
  uploaded_chunks: number[];
  uploaded_bytes: number;
  progress: number;
}

/**
 * Upload attachment (platform) / 上传附件（平台端）
 * POST /admin/attachments/upload
 *
 * Permission: attachment:upload
 */
/** @internal Only for smartUploadFile internal use / 仅供 smartUploadFile 内部调用 */
async function uploadAttachmentApi(
  params: {
    business_id?: number;
    business_type?: string;
    file: Blob | File;
    tenant_id?: number;
    visibility?: 'private' | 'public';
  },
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<AdminUploadAttachmentResponse> {
  const {
    file,
    tenant_id = 0,
    visibility = 'private',
    business_type,
    business_id,
  } = params;
  const uploadData: { [key: string]: Blob | File | string; file: Blob | File } =
    {
      file,
      tenant_id: String(tenant_id),
      ...(visibility ? { visibility } : {}),
      ...(business_type ? { business_type } : {}),
      ...(business_id ? { business_id: String(business_id) } : {}),
    };

  return requestClient.upload<AdminUploadAttachmentResponse>(
    `${API_PREFIX}/upload`,
    uploadData,
    {
      ...options,
      onUploadProgress: onProgress
        ? (progressEvent) => {
            const percent = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0;
            onProgress({ percent });
          }
        : undefined,
    },
  );
}

/** Batch upload single file result / 批量上传单文件结果 */
export interface AdminBatchUploadItemResult {
  filename: string;
  success: boolean;
  attachment?: AttachmentInfoRaw;
  url?: string;
  error?: string;
}

/** Batch upload response / 批量上传响应 */
export interface AdminBatchUploadResponse {
  items: AdminBatchUploadItemResult[];
  success_count: number;
  failure_count: number;
  used_bytes: number;
}

/**
 * Batch upload attachments (platform) / 批量上传附件（平台端）
 * POST /admin/attachments/batch-upload
 *
 * Submit multiple files at once (max 20). Single file failure doesn't affect others.
 * Not subject to tenant quota limits.
 *
 * Permission: attachment:upload
 */
export async function batchUploadAttachmentsApi(
  params: {
    files: File[];
    tenant_id?: number;
    visibility?: 'private' | 'public';
    business_type?: string;
    business_id?: number;
  },
  options?: ApiRequestOptions,
): Promise<AdminBatchUploadResponse> {
  const {
    files,
    tenant_id = 0,
    visibility = 'private',
    business_type,
    business_id,
  } = params;
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  formData.append('tenant_id', String(tenant_id));
  if (visibility) formData.append('visibility', visibility);
  if (business_type) formData.append('business_type', business_type);
  if (business_id) formData.append('business_id', String(business_id));
  return requestClient.post<AdminBatchUploadResponse>(
    `${API_PREFIX}/batch-upload`,
    formData,
    { ...options, headers: { 'Content-Type': 'multipart/form-data' } },
  );
}

/**
 * Init chunk upload (platform) / 初始化分片上传（平台端）
 * POST /admin/attachments/chunk/init
 */
export async function initChunkUploadApi(
  params: {
    business_id?: number;
    business_type?: string;
    chunk_size?: number;
    filename: string;
    mime_type: string;
    tenant_id?: number;
    total_size: number;
    visibility?: 'private' | 'public';
  },
  options?: ApiRequestOptions,
): Promise<AdminChunkUploadInitResponse> {
  const { data } = await requestClient.post<{
    data: AdminChunkUploadInitResponse;
  }>(`${API_PREFIX}/chunk/init`, params, options);
  return data;
}

/**
 * Upload chunk (platform) / 上传分片（平台端）
 * POST /admin/attachments/chunk/{upload_id}
 */
export async function uploadChunkApi(
  uploadId: string,
  chunkIndex: number,
  chunk: Blob,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<AdminChunkUploadResponse> {
  const formData = {
    chunk_index: String(chunkIndex),
    file: chunk,
  };
  const { data } = await requestClient.upload<{
    data: AdminChunkUploadResponse;
  }>(
    `${API_PREFIX}/chunk/${uploadId}`,
    formData,
    {
      ...options,
      onUploadProgress: onProgress
        ? (progressEvent) => {
            const percent = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0;
            onProgress({ percent });
          }
        : undefined,
    },
  );
  return data;
}

/**
 * Complete chunk upload (platform) / 完成分片上传（平台端）
 * POST /admin/attachments/chunk/{upload_id}/complete
 */
export async function completeChunkUploadApi(
  uploadId: string,
  options?: ApiRequestOptions,
): Promise<AdminUploadAttachmentResponse> {
  return requestClient.post<AdminUploadAttachmentResponse>(
    `${API_PREFIX}/chunk/${uploadId}/complete`,
    {},
    options,
  );
}

/**
 * Cancel chunk upload (platform) / 取消分片上传（平台端）
 * DELETE /admin/attachments/chunk/{upload_id}
 */
export async function cancelChunkUploadApi(
  uploadId: string,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/chunk/${uploadId}`, options);
}

/** Preflight response / 预检响应 */
export interface AdminPreflightResponse {
  exists: boolean;
  attachment: AttachmentInfoRaw | null;
  url: string | null;
  used_bytes: number | null;
}

/** Upload rules response / 上传规则响应 */
export interface AdminUploadRulesResponse {
  allowed_extensions: string;
  denied_extensions: string;
  max_file_size_mb: number;
}

/**
 * Preflight check if file already exists (instant upload, platform) / 预检文件是否已存在（秒传检查）
 * POST /admin/attachments/preflight
 */
export async function preflightCheckApi(
  params: {
    hash: string;
    filename: string;
    size: number;
    visibility?: 'private' | 'public';
  },
  tenantId: number = 0,
  options?: ApiRequestOptions,
): Promise<AdminPreflightResponse> {
  return requestClient.post<AdminPreflightResponse>(
    `${API_PREFIX}/preflight`,
    params,
    { ...options, params: { tenant_id: tenantId } },
  );
}

/**
 * Get upload rules (platform) / 获取上传规则（平台端）
 * GET /admin/attachments/upload-rules
 */
export async function getUploadRulesApi(
  options?: ApiRequestOptions,
): Promise<AdminUploadRulesResponse> {
  return requestClient.get<AdminUploadRulesResponse>(
    `${API_PREFIX}/upload-rules`,
    options,
  );
}

/**
 * Smart upload file (platform, auto-select normal or chunk upload)
 * 智能上传文件（平台端，自动选择普通上传或分片上传）
 *
 * Flow / 流程:
 * 1. Compute file SHA-256 hash (progress 0~5%) / 计算文件哈希
 * 2. Preflight check for instant upload (progress 5%) / 预检秒传
 * 3. If miss → choose normal/chunk upload by file size (progress 5~100%) / 未命中→选择上传方式
 */
export async function smartUploadFile(
  params: {
    business_id?: number;
    business_type?: string;
    file: Blob | File;
    tenant_id?: number;
    visibility?: 'private' | 'public';
  },
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<AdminUploadAttachmentResponse> {
  const file = params.file as File;
  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
  const CHUNK_THRESHOLD = 10 * 1024 * 1024; // 10MB
  const HASH_PROGRESS_END = 5;

  // ===== Step 1: Compute file hash / 第一步：计算文件哈希 =====
  const fileHash = await computeFileHash(file, {
    onProgress: (pct) => {
      onProgress?.({ percent: Math.round((pct / 100) * HASH_PROGRESS_END) });
    },
    signal: options?.signal,
  });

  // ===== Step 2: Preflight (instant upload, only when hash available) / 第二步：预检秒传 =====
  onProgress?.({ percent: HASH_PROGRESS_END });
  if (fileHash) {
    try {
      const preflight = await preflightCheckApi(
        {
          hash: fileHash,
          filename: file.name,
          size: file.size,
          visibility: params.visibility ?? 'private',
        },
        params.tenant_id ?? 0,
        options,
      );
      if (preflight.exists && preflight.attachment) {
        onProgress?.({ percent: 100 });
        return {
          attachment: preflight.attachment,
          url: preflight.url ?? '',
          used_bytes: 0,
        };
      }
    } catch {
      // Preflight failure doesn't affect normal upload flow / 预检失败不影响正常上传流程
    }
  }

  // ===== Step 3: Actual upload / 第三步：实际上传 =====
  const uploadProgressStart = HASH_PROGRESS_END;
  const uploadProgressRange = 100 - uploadProgressStart;

  const mapProgress = (uploadPercent: number) => {
    return Math.round(
      uploadProgressStart + (uploadPercent / 100) * uploadProgressRange,
    );
  };

  // Small file: direct upload / 小文件直接上传
  if (file.size <= CHUNK_THRESHOLD) {
    return uploadAttachmentApi(
      params,
      onProgress
        ? (p) => onProgress({ percent: mapProgress(p.percent) })
        : undefined,
      options,
    );
  }

  // Large file: chunk upload (with per-chunk real-time progress) / 大文件分片上传
  const {
    tenant_id = 0,
    visibility = 'private',
    business_type,
    business_id,
  } = params;

  const initResult = await initChunkUploadApi(
    {
      filename: file.name,
      total_size: file.size,
      chunk_size: CHUNK_SIZE,
      mime_type: file.type,
      tenant_id,
      visibility,
      business_type,
      business_id,
    },
    options,
  );

  const { upload_id, uploaded_chunks } = initResult;
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  let completedBytes = 0;

  for (const idx of uploaded_chunks) {
    completedBytes += Math.min(CHUNK_SIZE, file.size - idx * CHUNK_SIZE);
  }

  for (let i = 0; i < totalChunks; i++) {
    if (options?.signal?.aborted) {
      try {
        await cancelChunkUploadApi(upload_id);
      } catch {
        // ignore
      }
      throw new Error('Upload cancelled');
    }

    if (uploaded_chunks.includes(i)) continue;

    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = file.slice(start, end);
    const chunkSize = end - start;

    await uploadChunkApi(
      upload_id,
      i,
      chunk,
      onProgress
        ? (chunkProgress) => {
            const chunkBytes = (chunkProgress.percent / 100) * chunkSize;
            const totalBytes = completedBytes + chunkBytes;
            const uploadPercent = Math.round((totalBytes / file.size) * 100);
            onProgress({ percent: mapProgress(Math.min(uploadPercent, 99)) });
          }
        : undefined,
      options,
    );

    completedBytes += chunkSize;
  }

  const result = await completeChunkUploadApi(upload_id, options);
  onProgress?.({ percent: 100 });
  return result;
}

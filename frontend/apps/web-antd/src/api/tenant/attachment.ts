/**
 * 租户端附件管理 API
 * 对接后端 /tenant/attachments/* 接口
 *
 * @module api/tenant/attachment
 */
import type {
  AttachmentInfo,
  AttachmentInfoRaw,
  AttachmentListParams,
  AttachmentUrlResult,
  StorageQuotaInfo,
  StorageQuotaInfoRaw,
} from '#/types/attachment';
import type { PaginatedResponse, SelectOption } from '#/types/query';
import type { ApiRequestOptions } from '#/utils/request';

import { inferCategory } from '#/types/attachment';
import { computeFileHash } from '#/utils/file-hash';
import { requestClient } from '#/utils/request';

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
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
    category: inferCategory(raw.mime_type),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/** 转换存储配额信息 */
function transformStorageQuota(raw: StorageQuotaInfoRaw): StorageQuotaInfo {
  return {
    usedBytes: raw.used_bytes,
    limitBytes: raw.limit_bytes,
    limitGb: raw.limit_gb,
    remainingBytes: raw.remaining_bytes,
    usagePercent: raw.usage_percent,
    totalCount: raw.total_count,
    maxFileSizeMb: raw.max_file_size_mb,
    unlimited: raw.unlimited,
  };
}

// ============================================================
// 类型定义
// ============================================================

/** 附件列表响应 */
export interface AttachmentListResponse {
  items: AttachmentInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/tenant/attachments';

/**
 * 获取附件列表
 * GET /tenant/attachments
 *
 * 权限: attachment:list
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
 * 获取附件详情
 * GET /tenant/attachments/{attachment_id}
 *
 * 权限: attachment:detail
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
 * 删除附件
 * DELETE /tenant/attachments/{attachment_id}
 *
 * 权限: attachment:delete
 */
export async function deleteAttachmentApi(
  attachmentId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${attachmentId}`, options);
}

/**
 * 获取附件下拉选项
 * GET /tenant/attachments/select
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
 * 获取存储配额
 * GET /tenant/attachments/storage-quota
 *
 * 权限: attachment:storage_quota
 */
export async function getStorageQuotaApi(
  options?: ApiRequestOptions,
): Promise<StorageQuotaInfo> {
  const raw = await requestClient.get<StorageQuotaInfoRaw>(
    `${API_PREFIX}/storage-quota`,
    options,
  );
  return transformStorageQuota(raw);
}

/**
 * 获取下载链接
 * GET /tenant/attachments/{attachment_id}/download-url
 *
 * 权限: attachment:download_url
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
 * 获取预览链接
 * GET /tenant/attachments/{attachment_id}/preview-url
 *
 * 权限: attachment:preview_url
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
// 上传接口
// ============================================================

/** 上传附件参数 */
export interface UploadAttachmentParams {
  /** 文件 */
  file: Blob | File;
  /** 可见性，默认 private */
  visibility?: 'private' | 'public';
  /** 业务类型 (如 avatar, document) */
  business_type?: string;
  /** 业务 ID */
  business_id?: number;
}

/** 上传附件响应（后端返回嵌套结构） */
export interface UploadAttachmentResponse {
  attachment: AttachmentInfoRaw;
  url: string;
  used_bytes: number;
}

/** 分片上传初始化响应 */
export interface ChunkUploadInitResponse {
  upload_id: string;
  filename: string;
  total_size: number;
  chunk_size: number;
  chunk_count: number;
  uploaded_chunks: number[];
  uploaded_bytes: number;
  progress: number;
}

/** 分片上传响应 */
export interface ChunkUploadResponse {
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
 * 普通上传附件
 * POST /tenant/attachments/upload
 *
 * 权限: attachment:upload
 */
/** @internal 仅供 smartUploadFile 内部调用，外部请使用 smartUploadFile */
async function uploadAttachmentApi(
  params: UploadAttachmentParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadAttachmentResponse> {
  const { file, visibility = 'private', business_type, business_id } = params;

  const uploadData: { [key: string]: Blob | File | string; file: Blob | File } =
    { file };
  if (visibility) uploadData.visibility = visibility;
  if (business_type) uploadData.business_type = business_type;
  if (business_id) uploadData.business_id = String(business_id);

  return requestClient.upload<UploadAttachmentResponse>(
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

/**
 * 初始化分片上传
 * POST /tenant/attachments/chunk/init
 */
export async function initChunkUploadApi(
  params: {
    business_id?: number;
    business_type?: string;
    chunk_size?: number;
    filename: string;
    mime_type: string;
    total_size: number;
    visibility?: 'private' | 'public';
  },
  options?: ApiRequestOptions,
): Promise<ChunkUploadInitResponse> {
  const { data } = await requestClient.post<{ data: ChunkUploadInitResponse }>(
    `${API_PREFIX}/chunk/init`,
    params,
    options,
  );
  return data;
}

/**
 * 上传分片
 * POST /tenant/attachments/chunk/{upload_id}
 */
export async function uploadChunkApi(
  uploadId: string,
  chunkIndex: number,
  chunk: Blob,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<ChunkUploadResponse> {
  const formData = {
    chunk_index: String(chunkIndex),
    file: chunk,
  };

  const { data } = await requestClient.upload<{ data: ChunkUploadResponse }>(
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
 * 完成分片上传
 * POST /tenant/attachments/chunk/{upload_id}/complete
 */
export async function completeChunkUploadApi(
  uploadId: string,
  options?: ApiRequestOptions,
): Promise<UploadAttachmentResponse> {
  return requestClient.post<UploadAttachmentResponse>(
    `${API_PREFIX}/chunk/${uploadId}/complete`,
    {},
    options,
  );
}

/**
 * 获取分片上传状态
 * GET /tenant/attachments/chunk/{upload_id}/status
 */
export async function getChunkUploadStatusApi(
  uploadId: string,
  options?: ApiRequestOptions,
): Promise<ChunkUploadResponse> {
  const { data } = await requestClient.get<{ data: ChunkUploadResponse }>(
    `${API_PREFIX}/chunk/${uploadId}/status`,
    options,
  );
  return data;
}

/**
 * 取消分片上传
 * DELETE /tenant/attachments/chunk/{upload_id}
 */
export async function cancelChunkUploadApi(
  uploadId: string,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/chunk/${uploadId}`, options);
}

/** 批量上传单文件结果 */
export interface BatchUploadItemResult {
  filename: string;
  success: boolean;
  attachment?: AttachmentInfoRaw;
  url?: string;
  error?: string;
}

/** 批量上传响应 */
export interface BatchUploadResponse {
  items: BatchUploadItemResult[];
  success_count: number;
  failure_count: number;
  used_bytes: number;
}

/**
 * 批量上传附件
 * POST /tenant/attachments/batch-upload
 *
 * 一次提交多个文件（最多 20 个），单文件失败不影响其他。
 * 大文件请改用多次调用 smartUploadFile。
 *
 * 权限: attachment:upload
 */
export async function batchUploadAttachmentsApi(
  params: {
    files: File[];
    visibility?: 'private' | 'public';
    business_type?: string;
    business_id?: number;
  },
  options?: ApiRequestOptions,
): Promise<BatchUploadResponse> {
  const { files, visibility = 'private', business_type, business_id } = params;
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  if (visibility) formData.append('visibility', visibility);
  if (business_type) formData.append('business_type', business_type);
  if (business_id) formData.append('business_id', String(business_id));
  return requestClient.post<BatchUploadResponse>(
    `${API_PREFIX}/batch-upload`,
    formData,
    { ...options, headers: { 'Content-Type': 'multipart/form-data' } },
  );
}

/** 预检响应 */
export interface PreflightResponse {
  exists: boolean;
  attachment: AttachmentInfoRaw | null;
  url: string | null;
  used_bytes: number | null;
}

/** 上传规则响应 */
export interface UploadRulesResponse {
  allowed_extensions: string;
  denied_extensions: string;
  max_file_size_mb: number;
}

/**
 * 预检文件是否已存在（秒传检查）
 * POST /tenant/attachments/preflight
 */
export async function preflightCheckApi(
  params: {
    hash: string;
    filename: string;
    size: number;
    visibility?: 'private' | 'public';
  },
  options?: ApiRequestOptions,
): Promise<PreflightResponse> {
  return requestClient.post<PreflightResponse>(
    `${API_PREFIX}/preflight`,
    params,
    options,
  );
}

/**
 * 获取上传规则
 * GET /tenant/attachments/upload-rules
 */
export async function getUploadRulesApi(
  options?: ApiRequestOptions,
): Promise<UploadRulesResponse> {
  return requestClient.get<UploadRulesResponse>(
    `${API_PREFIX}/upload-rules`,
    options,
  );
}

/**
 * 智能上传文件（自动选择普通上传或分片上传）
 *
 * 流程：
 * 1. 计算文件 SHA-256 哈希（进度 0~5%）
 * 2. 预检接口检查秒传（进度 5%）
 * 3. 未命中→根据文件大小选择普通/分片上传（进度 5~100%）
 */
export async function smartUploadFile(
  params: UploadAttachmentParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadAttachmentResponse> {
  const file = params.file as File;
  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
  const CHUNK_THRESHOLD = 10 * 1024 * 1024; // 10MB
  const HASH_PROGRESS_END = 5; // 哈希计算占总进度的 0~5%

  // ===== 第一步：计算文件哈希 =====
  const fileHash = await computeFileHash(file, {
    onProgress: (pct) => {
      onProgress?.({ percent: Math.round((pct / 100) * HASH_PROGRESS_END) });
    },
    signal: options?.signal,
  });

  // ===== 第二步：预检（秒传）=====
  onProgress?.({ percent: HASH_PROGRESS_END });
  try {
    const preflight = await preflightCheckApi(
      {
        hash: fileHash,
        filename: file.name,
        size: file.size,
        visibility: params.visibility ?? 'private',
      },
      options,
    );
    if (preflight.exists && preflight.attachment) {
      onProgress?.({ percent: 100 });
      return {
        attachment: preflight.attachment,
        url: preflight.url ?? '',
        used_bytes: preflight.used_bytes ?? 0,
      };
    }
  } catch {
    // 预检失败不影响正常上传流程，静默继续
  }

  // ===== 第三步：实际上传 =====
  const uploadProgressStart = HASH_PROGRESS_END;
  const uploadProgressRange = 100 - uploadProgressStart;

  /** 将上传实际进度 (0~100) 映射到总进度 (5%~100%) */
  const mapProgress = (uploadPercent: number) => {
    return Math.round(
      uploadProgressStart + (uploadPercent / 100) * uploadProgressRange,
    );
  };

  // 小文件直接上传
  if (file.size <= CHUNK_THRESHOLD) {
    return uploadAttachmentApi(
      params,
      onProgress
        ? (p) => onProgress({ percent: mapProgress(p.percent) })
        : undefined,
      options,
    );
  }

  // 大文件分片上传（带片内实时进度）
  const { visibility = 'private', business_type, business_id } = params;

  // 1. 初始化
  const initResult = await initChunkUploadApi(
    {
      filename: file.name,
      total_size: file.size,
      chunk_size: CHUNK_SIZE,
      mime_type: file.type,
      visibility,
      business_type,
      business_id,
    },
    options,
  );

  const { upload_id, uploaded_chunks } = initResult;
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  let completedBytes = 0;

  // 统计已上传分片的字节数
  for (const idx of uploaded_chunks) {
    completedBytes += Math.min(CHUNK_SIZE, file.size - idx * CHUNK_SIZE);
  }

  // 2. 上传分片
  for (let i = 0; i < totalChunks; i++) {
    if (options?.signal?.aborted) {
      try {
        await cancelChunkUploadApi(upload_id);
      } catch {
        // ignore
      }
      throw new Error('Upload cancelled');
    }

    if (uploaded_chunks.includes(i)) {
      continue;
    }

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
            const uploadPercent = Math.round(
              (totalBytes / file.size) * 100,
            );
            onProgress({ percent: mapProgress(Math.min(uploadPercent, 99)) });
          }
        : undefined,
      options,
    );

    completedBytes += chunkSize;
  }

  // 3. 完成上传
  const result = await completeChunkUploadApi(upload_id, options);
  onProgress?.({ percent: 100 });
  return result;
}

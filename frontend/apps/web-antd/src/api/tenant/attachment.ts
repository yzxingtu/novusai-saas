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
import { inferCategory } from '#/types/attachment';
import type { PaginatedResponse, SelectOption } from '#/types/query';
import type { ApiRequestOptions } from '#/utils/request';

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
export async function uploadAttachmentApi(
  params: UploadAttachmentParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadAttachmentResponse> {
  const {
    file,
    visibility = 'private',
    business_type,
    business_id,
  } = params;

  const uploadData: { file: Blob | File; [key: string]: Blob | File | string } = { file };
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

/**
 * 智能上传文件（自动选择普通上传或分片上传）
 */
export async function smartUploadFile(
  params: UploadAttachmentParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadAttachmentResponse> {
  const file = params.file as File;
  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
  const CHUNK_THRESHOLD = 10 * 1024 * 1024; // 10MB

  // 小文件直接上传
  if (file.size <= CHUNK_THRESHOLD) {
    return uploadAttachmentApi(params, onProgress, options);
  }

  // 大文件分片上传
  const {
    visibility = 'private',
    business_type,
    business_id,
  } = params;

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

  // 2. 上传分片
  for (let i = 0; i < totalChunks; i++) {
    // 检查是否取消
    if (options?.signal?.aborted) {
      // 尝试调用后端取消接口
      // 注意：这里可能需要忽略错误，因为 abort 信号可能已经触发
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

    await uploadChunkApi(
      upload_id,
      i,
      chunk,
      (_progress) => {
        // 计算当前分片对总进度的贡献
        // 简单估算：总进度 = (已完成分片数 + 当前分片进度) / 总分片数
        // 为了平滑，我们只在分片上传时更新 UI
      },
      options,
    );

    // 更新总进度
    const overallProgress = Math.round(((i + 1) / totalChunks) * 100);
    onProgress?.({ percent: overallProgress });
  }

  // 3. 完成上传
  return completeChunkUploadApi(upload_id, options);
}

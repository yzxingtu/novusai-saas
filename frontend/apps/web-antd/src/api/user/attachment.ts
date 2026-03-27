/**
 * User attachment upload API / 用户端附件上传 API
 * Backend: /user/attachments/* / 对接后端 /user/attachments/* 接口
 */
import type {
  AttachmentInfo,
  AttachmentInfoRaw,
  AttachmentUrlResult,
} from '#/types/attachment';
import type { ApiRequestOptions } from '#/utils/request';

import { inferCategory } from '#/types/attachment';
import { downloadBlob } from '#/utils/download';
import { computeFileHash } from '#/utils/file-hash';
import { requestClient } from '#/utils/request';

const API_PREFIX = '/api/user/attachments';

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
  } satisfies AttachmentInfo;
}

/** Upload response / 上传响应 */
export interface UploadResult {
  attachment: AttachmentInfoRaw;
  url: string;
  used_bytes: number;
}

/** Preflight response / 预检响应 */
interface PreflightResult {
  attachment?: AttachmentInfoRaw;
  exists: boolean;
  url?: string;
  used_bytes?: number;
}

/** Upload params / 上传参数 */
export interface UserUploadParams {
  file: Blob | File;
  visibility?: 'private' | 'public';
}

/** Upload rules / 上传规则 */
export interface UploadRulesResponse {
  allowed_extensions: string;
  denied_extensions: string;
  max_file_size_mb: number;
}

/**
 * Preflight check (instant upload) / 预检（秒传）
 */
async function preflightCheckApi(
  params: {
    filename: string;
    hash: string;
    size: number;
    visibility?: string;
  },
  options?: ApiRequestOptions,
): Promise<PreflightResult> {
  return requestClient.post<PreflightResult>(
    `${API_PREFIX}/preflight`,
    params,
    options,
  );
}

/**
 * Normal upload / 普通上传
 */
async function uploadAttachmentApi(
  params: UserUploadParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadResult> {
  const { file, visibility = 'private' } = params;

  const uploadData: { [key: string]: Blob | File | string; file: Blob | File } =
    { file };
  if (visibility) uploadData.visibility = visibility;

  return requestClient.upload<UploadResult>(
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
 * Get upload rules / 获取上传规则
 */
export async function getUserUploadRulesApi(
  options?: ApiRequestOptions,
): Promise<UploadRulesResponse> {
  return requestClient.get<UploadRulesResponse>(
    `${API_PREFIX}/upload-rules`,
    options,
  );
}

/**
 * Get user attachment detail / 获取用户附件详情
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
 * Get user attachment preview URL / 获取用户附件预览链接
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

/**
 * Download user attachment blob / 下载用户附件二进制
 */
export async function downloadAttachmentApi(
  attachmentId: number,
  filename: string,
  mimeType?: null | string,
  options?: ApiRequestOptions,
): Promise<void> {
  const blob = await requestClient.download<Blob>(
    `${API_PREFIX}/${attachmentId}/download`,
    options,
  );
  downloadBlob(blob, {
    filename,
    ...(mimeType ? { mimeType } : {}),
  });
}

/**
 * Smart upload file (hash → preflight → upload) / 智能上传文件（哈希→预检→上传）
 *
 * Simplified user version, no chunked upload (for small files like avatars) / 用户端简化版，不含分片上传（头像等小文件场景）
 */
export async function smartUploadFile(
  params: UserUploadParams,
  onProgress?: (progress: { percent: number }) => void,
  options?: ApiRequestOptions,
): Promise<UploadResult> {
  const file = params.file as File;
  const HASH_PROGRESS_END = 5;

  // Step 1: compute file hash / 第一步：计算文件哈希
  const fileHash = await computeFileHash(file, {
    onProgress: (pct) => {
      onProgress?.({ percent: Math.round((pct / 100) * HASH_PROGRESS_END) });
    },
    signal: options?.signal,
  });

  // Step 2: preflight (instant upload, only when hash is available) / 第二步：预检（秒传，仅在哈希可用时执行）
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
      // Preflight failure does not affect normal upload / 预检失败不影响正常上传
    }
  }

  // Step 3: normal upload / 第三步：普通上传
  const uploadProgressStart = HASH_PROGRESS_END;
  const uploadProgressRange = 100 - uploadProgressStart;

  return uploadAttachmentApi(
    params,
    onProgress
      ? (p) =>
          onProgress({
            percent: Math.round(
              uploadProgressStart + (p.percent / 100) * uploadProgressRange,
            ),
          })
      : undefined,
    options,
  );
}

/**
 * User attachment upload API / 用户端附件上传 API
 * Backend: /user/attachments/* (simplified: upload + preflight only) / 对接后端 /user/attachments/* 接口（精简版，仅上传+预检）
 */
import type { ApiRequestOptions } from '#/utils/request';

import { computeFileHash } from '#/utils/file-hash';
import { requestClient } from '#/utils/request';

const API_PREFIX = '/api/user/attachments';

/** Attachment info (backend raw format) / 附件信息（后端原始格式） */
interface AttachmentRaw {
  base_url?: string;
  business_id?: number;
  business_type?: string;
  created_at?: string;
  driver?: string;
  extension?: string;
  hash?: string;
  id: number;
  mime_type?: string;
  name?: string;
  original_name?: string;
  path?: string;
  size?: number;
  source?: string;
  status?: string;
  tenant_id?: number;
  uploader_id?: number;
  visibility?: string;
}

/** Upload response / 上传响应 */
export interface UploadResult {
  attachment: AttachmentRaw;
  url: string;
  used_bytes: number;
}

/** Preflight response / 预检响应 */
interface PreflightResult {
  attachment?: AttachmentRaw;
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
              ? Math.round(
                  (progressEvent.loaded * 100) / progressEvent.total,
                )
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

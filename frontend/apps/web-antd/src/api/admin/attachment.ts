/**
 * 平台端附件管理 API
 * 对接后端 /admin/attachments/* 接口
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

const API_PREFIX = '/admin/attachments';

/**
 * 获取附件列表
 * GET /admin/attachments
 *
 * 权限: attachment:list
 * 支持按租户筛选: filter[tenant_id][eq]=1
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
 * GET /admin/attachments/{attachment_id}
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
 * DELETE /admin/attachments/{attachment_id}
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
 * 获取附件统计
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
 * 获取按租户分组的附件统计
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
 * 获取下载链接
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
 * 获取预览链接
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
// 上传接口
// ============================================================

/** 上传附件响应（后端返回嵌套结构） */
export interface AdminUploadAttachmentResponse {
  attachment: AttachmentInfoRaw;
  url: string;
  used_bytes: number;
}

/**
 * 上传附件（平台端）
 * POST /admin/attachments/upload
 *
 * 权限: attachment:upload
 */
export async function uploadAttachmentApi(
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

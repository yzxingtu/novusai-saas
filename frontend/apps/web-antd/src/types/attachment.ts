/**
 * Attachment storage system type definitions
 * 附件存储系统类型定义
 *
 * @module types/attachment
 */

/** File visibility / 文件可见性 */
export type StorageVisibility = 'private' | 'public';

/** Attachment category / 附件分类 */
export type AttachmentCategory =
  | 'archive'
  | 'audio'
  | 'document'
  | 'image'
  | 'other'
  | 'video';

/**
 * Infer attachment category from MIME type
 * Backend model has no category field; frontend computes virtual category from mime_type
 * 根据 MIME 类型推断附件分类
 * 后端模型无 category 字段，前端通过 mime_type 推算虚拟分类
 */
export function inferCategory(mimeType?: null | string): AttachmentCategory {
  if (!mimeType) return 'other';
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (
    mimeType.startsWith('application/') &&
    /zip|rar|7z|tar|gz|bz2/.test(mimeType)
  )
    return 'archive';
  if (mimeType.startsWith('application/') || mimeType.startsWith('text/'))
    return 'document';
  return 'other';
}

/**
 * Attachment info (backend raw format snake_case)
 * Corresponds to backend AttachmentResponse (admin) / AttachmentSafeResponse (tenant/user)
 * 附件信息（后端原始格式 snake_case）
 * 对应后端 AttachmentResponse（管理端）/ AttachmentSafeResponse（企业端/用户端）
 *
 * Fields marked optional with `?` are only present in admin (full) responses.
 * Tenant/user Safe responses omit: tenant_id, path, hash, driver, base_url
 */
export interface AttachmentInfoRaw {
  id: number;
  tenant_id?: number;
  name: string;
  original_name?: null | string;
  path?: string;
  size: number;
  hash?: null | string;
  mime_type?: null | string;
  extension?: null | string;
  visibility: StorageVisibility;
  driver?: string;
  base_url?: string;
  status: string;
  source?: null | string;
  uploader_id?: null | number;
  business_type?: null | string;
  business_id?: null | number;
  meta?: null | Record<string, unknown>;
  preview_url?: null | string;
  created_at: string;
  updated_at?: string;
}

/**
 * Attachment info (frontend format camelCase)
 * 附件信息（前端格式 camelCase）
 *
 * Fields marked optional with `?` are only present in admin (full) responses.
 * Tenant/user Safe responses omit: tenantId, path, hash, driver, baseUrl
 */
export interface AttachmentInfo {
  id: number;
  tenantId?: number;
  name: string;
  originalName?: null | string;
  path?: string;
  size: number;
  hash?: null | string;
  mimeType?: null | string;
  extension?: null | string;
  visibility: StorageVisibility;
  driver?: string;
  baseUrl?: string;
  status: string;
  source?: null | string;
  uploaderId?: null | number;
  businessType?: null | string;
  businessId?: null | number;
  meta?: null | Record<string, unknown>;
  /** Signed preview URL from backend / 后端生成的带签名预览 URL */
  previewUrl?: null | string;
  /** Inferred category (not returned by backend, computed from mimeType by frontend) / 推算分类（后端不返回，前端通过 mimeType 推算） */
  category?: AttachmentCategory | null;
  createdAt: string;
  updatedAt?: string;
}

/**
 * Attachment list query params
 * 附件列表查询参数
 */
export interface AttachmentListParams {
  /** Page number / 页码 */
  page?: number;
  /** Items per page / 每页数量 */
  page_size?: number;
  /** Sort field, e.g. -created_at,name / 排序字段，如 -created_at,name */
  sort?: string;
  /** Filter conditions / 筛选条件 */
  filter?: Record<string, unknown>;
  /** Other params / 其他参数 */
  [key: string]: unknown;
}

/**
 * URL result
 * URL 结果
 */
export interface AttachmentUrlResult {
  /** Access URL / 访问 URL */
  url: string;
  /** Expiry time (seconds) / 过期时间（秒） */
  expires_in?: number;
}

/**
 * Storage quota info (backend raw format)
 * Corresponds to backend TenantStorageQuotaResponse
 * 存储配额信息（后端原始格式）
 * 对应后端 TenantStorageQuotaResponse
 */
export interface StorageQuotaInfoRaw {
  used_bytes: number;
  limit_bytes: number;
  limit_gb: number;
  remaining_bytes: number;
  usage_percent: number;
  total_count: number;
  max_file_size_mb: number;
  plan_available?: boolean;
  unlimited: boolean;
}

/**
 * Storage quota info (frontend format)
 * 存储配额信息（前端格式）
 */
export interface StorageQuotaInfo {
  /** Used storage space (bytes) / 已使用存储空间 (bytes) */
  usedBytes: number;
  /** Storage limit (bytes), 0 means unlimited / 存储限制 (bytes)，0 表示无限制 */
  limitBytes: number;
  /** Storage limit (GB), 0 means unlimited / 存储限制 (GB)，0 表示无限制 */
  limitGb: number;
  /** Remaining storage space (bytes) / 剩余存储空间 (bytes) */
  remainingBytes: number;
  /** Usage percentage / 使用率百分比 */
  usagePercent: number;
  /** Total attachment count / 附件总数 */
  totalCount: number;
  /** Max single file size (MB), 0 means unlimited / 单文件大小限制 (MB)，0 表示无限制 */
  maxFileSizeMb: number;
  /** Whether the tenant has an active plan / 企业是否拥有有效套餐 */
  planAvailable: boolean;
  /** Whether unlimited / 是否无限制 */
  unlimited: boolean;
}

/**
 * Attachment statistics
 * 附件统计信息
 */
export interface AttachmentStats {
  /** Total file count / 总文件数 */
  total_count?: number;
  /** Total size (bytes) / 总大小 (bytes) */
  total_size?: number;
  /** Stats by category / 按分类统计 */
  by_category?: Record<string, { count: number; size: number }>;
  /** Stats by driver / 按驱动统计 */
  by_driver?: Record<string, { count: number; size: number }>;
  /** Other stat fields / 其他统计字段 */
  [key: string]: unknown;
}

/**
 * Stats by tenant
 * 按企业统计
 */
export interface AttachmentStatsByTenant {
  tenant_id: number;
  tenant_name?: string;
  total_count: number;
  total_size: number;
  [key: string]: unknown;
}

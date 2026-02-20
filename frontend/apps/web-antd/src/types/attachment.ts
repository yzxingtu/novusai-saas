/**
 * 附件存储系统类型定义
 *
 * @module types/attachment
 */

/** 文件可见性 */
export type StorageVisibility = 'private' | 'public';

/** 附件分类 */
export type AttachmentCategory =
  | 'archive'
  | 'audio'
  | 'document'
  | 'image'
  | 'other'
  | 'video';

/**
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
  if (
    mimeType.startsWith('application/') ||
    mimeType.startsWith('text/')
  )
    return 'document';
  return 'other';
}

/**
 * 附件信息（后端原始格式 snake_case）
 * 对应后端 AttachmentResponse / AttachmentListItem
 */
export interface AttachmentInfoRaw {
  id: number;
  tenant_id: number;
  name: string;
  original_name?: null | string;
  path: string;
  size: number;
  hash?: null | string;
  mime_type?: null | string;
  extension?: null | string;
  visibility: StorageVisibility;
  driver: string;
  base_url: string;
  status: string;
  source?: null | string;
  uploader_id?: null | number;
  business_type?: null | string;
  business_id?: null | number;
  meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at?: string;
}

/**
 * 附件信息（前端格式 camelCase）
 */
export interface AttachmentInfo {
  id: number;
  tenantId: number;
  name: string;
  originalName?: null | string;
  path: string;
  size: number;
  hash?: null | string;
  mimeType?: null | string;
  extension?: null | string;
  visibility: StorageVisibility;
  driver: string;
  baseUrl: string;
  status: string;
  source?: null | string;
  uploaderId?: null | number;
  businessType?: null | string;
  businessId?: null | number;
  meta?: Record<string, unknown> | null;
  /** 推算分类（后端不返回，前端通过 mimeType 推算） */
  category?: AttachmentCategory | null;
  createdAt: string;
  updatedAt?: string;
}

/**
 * 附件列表查询参数
 */
export interface AttachmentListParams {
  /** 页码 */
  page?: number;
  /** 每页数量 */
  page_size?: number;
  /** 排序字段，如 -created_at,name */
  sort?: string;
  /** 筛选条件 */
  filter?: Record<string, unknown>;
  /** 其他参数 */
  [key: string]: unknown;
}

/**
 * URL 结果
 */
export interface AttachmentUrlResult {
  /** 访问 URL */
  url: string;
  /** 过期时间（秒） */
  expires_in?: number;
}

/**
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
  unlimited: boolean;
}

/**
 * 存储配额信息（前端格式）
 */
export interface StorageQuotaInfo {
  /** 已使用存储空间 (bytes) */
  usedBytes: number;
  /** 存储限制 (bytes)，0 表示无限制 */
  limitBytes: number;
  /** 存储限制 (GB)，0 表示无限制 */
  limitGb: number;
  /** 剩余存储空间 (bytes) */
  remainingBytes: number;
  /** 使用率百分比 */
  usagePercent: number;
  /** 附件总数 */
  totalCount: number;
  /** 单文件大小限制 (MB)，0 表示无限制 */
  maxFileSizeMb: number;
  /** 是否无限制 */
  unlimited: boolean;
}

/**
 * 附件统计信息
 */
export interface AttachmentStats {
  /** 总文件数 */
  total_count?: number;
  /** 总大小 (bytes) */
  total_size?: number;
  /** 按分类统计 */
  by_category?: Record<string, { count: number; size: number }>;
  /** 按驱动统计 */
  by_driver?: Record<string, { count: number; size: number }>;
  /** 其他统计字段 */
  [key: string]: unknown;
}

/**
 * 按租户统计
 */
export interface AttachmentStatsByTenant {
  tenant_id: number;
  tenant_name?: string;
  total_count: number;
  total_size: number;
  [key: string]: unknown;
}

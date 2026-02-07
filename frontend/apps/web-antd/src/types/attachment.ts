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
 */
export interface AttachmentInfoRaw {
  id: number;
  tenant_id?: number;
  name: string;
  path: string;
  mime_type: string;
  size: number;
  hash: string;
  driver: string;
  base_url: string;
  visibility: StorageVisibility;
  folder_id?: null | number;
  category?: AttachmentCategory | null;
  ref_type?: null | string;
  ref_id?: null | number;
  metadata?: Record<string, unknown>;
  uploaded_by?: null | number;
  uploaded_at: string;
  created_at: string;
  updated_at?: string;
}

/**
 * 附件信息（前端格式 camelCase）
 */
export interface AttachmentInfo {
  id: number;
  tenantId?: number;
  name: string;
  path: string;
  mimeType: string;
  size: number;
  hash: string;
  driver: string;
  baseUrl: string;
  visibility: StorageVisibility;
  folderId?: null | number;
  category?: AttachmentCategory | null;
  refType?: null | string;
  refId?: null | number;
  metadata?: Record<string, unknown>;
  uploadedBy?: null | number;
  uploadedAt: string;
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
 */
export interface StorageQuotaInfoRaw {
  space_limit: number;
  space_used: number;
  space_available: number;
  space_percent: number;
  file_count: number;
  file_count_limit: number;
  max_file_size: number;
  bandwidth_limit: number;
  bandwidth_used: number;
}

/**
 * 存储配额信息（前端格式）
 */
export interface StorageQuotaInfo {
  /** 空间上限 (bytes) */
  spaceLimit: number;
  /** 已用空间 (bytes) */
  spaceUsed: number;
  /** 可用空间 (bytes) */
  spaceAvailable: number;
  /** 使用百分比 */
  spacePercent: number;
  /** 文件数量 */
  fileCount: number;
  /** 文件数量上限 */
  fileCountLimit: number;
  /** 单文件大小上限 (bytes) */
  maxFileSize: number;
  /** 流量上限 (bytes) */
  bandwidthLimit: number;
  /** 已用流量 (bytes) */
  bandwidthUsed: number;
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

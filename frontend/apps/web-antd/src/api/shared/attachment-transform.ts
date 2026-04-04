import type {
  AttachmentInfo,
  AttachmentInfoRaw,
  StorageQuotaInfo,
  StorageQuotaInfoRaw,
} from '#/types/attachment';

import { inferCategory } from '#/types/attachment';

export function transformAttachmentInfo(
  raw: AttachmentInfoRaw,
): AttachmentInfo {
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

export function transformStorageQuota(
  raw: StorageQuotaInfoRaw,
): StorageQuotaInfo {
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

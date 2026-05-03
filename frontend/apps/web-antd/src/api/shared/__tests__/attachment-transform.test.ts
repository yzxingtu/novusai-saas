import { describe, expect, it } from 'vitest';

import {
  transformAttachmentInfo,
  transformStorageQuota,
} from '../attachment-transform';

describe('attachmentTransform', () => {
  it('transforms attachment info from snake_case to camelCase', () => {
    const result = transformAttachmentInfo({
      id: 1,
      tenant_id: 8,
      name: 'report.pdf',
      size: 1024,
      visibility: 'private',
      status: 'active',
      mime_type: 'application/pdf',
      preview_url: '/preview',
      created_at: '2026-01-01T00:00:00Z',
    });

    expect(result).toMatchObject({
      id: 1,
      tenantId: 8,
      name: 'report.pdf',
      mimeType: 'application/pdf',
      previewUrl: '/preview',
      category: 'document',
      createdAt: '2026-01-01T00:00:00Z',
    });
  });

  it('transforms storage quota fields', () => {
    const result = transformStorageQuota({
      used_bytes: 10,
      limit_bytes: 20,
      limit_gb: 1,
      remaining_bytes: 10,
      usage_percent: 50,
      total_count: 4,
      max_file_size_mb: 100,
      plan_available: false,
      unlimited: false,
    });

    expect(result).toEqual({
      usedBytes: 10,
      limitBytes: 20,
      limitGb: 1,
      remainingBytes: 10,
      usagePercent: 50,
      totalCount: 4,
      maxFileSizeMb: 100,
      planAvailable: false,
      unlimited: false,
    });
  });
});

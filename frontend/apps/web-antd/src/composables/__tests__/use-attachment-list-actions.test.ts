import type { AttachmentInfo } from '#/types/attachment';

import { describe, expect, it, vi } from 'vitest';

import { useAttachmentListActions } from '../use-attachment-list-actions';

const mockRefs = vi.hoisted(() => ({
  messageSuccess: vi.fn(),
  open: vi.fn(),
  setData: vi.fn(() => ({
    open: vi.fn(),
  })),
}));

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: () => [
    { name: 'MockDrawer' },
    {
      setData: mockRefs.setData,
    },
  ],
}));

vi.mock('ant-design-vue', () => ({
  message: {
    success: mockRefs.messageSuccess,
  },
}));

vi.mock('#/utils/image', () => ({
  getAttachmentUrl: (row: { id: number }, options?: { preset?: string }) =>
    `${options?.preset ?? 'full'}:${row.id}`,
}));

describe('useAttachmentListActions', () => {
  it('derives preview helpers and opens the detail drawer', () => {
    const actions = useAttachmentListActions({
      connectedComponent: { name: 'DetailDrawer' },
      download: vi.fn(),
      downloadSuccessMessage: 'downloaded',
    });

    const row: AttachmentInfo = {
      id: 5,
      name: 'image.png',
      category: 'image',
      mimeType: 'image/png',
      size: 1,
      visibility: 'public',
      status: 'active',
      createdAt: '2026-01-01T00:00:00Z',
    };

    expect(actions.isImage(row)).toBe(true);
    expect(actions.getThumbnailUrl(row)).toBe('thumb:5');
    expect(actions.getPreviewUrl(row)).toBe('full:5');

    actions.onViewDetail(row);
    expect(mockRefs.setData).toHaveBeenCalledWith({ id: 5, mode: 'view' });
  });

  it('shows success feedback after a successful download', async () => {
    const download = vi.fn().mockResolvedValue(undefined);
    const actions = useAttachmentListActions({
      connectedComponent: { name: 'DetailDrawer' },
      download,
      downloadSuccessMessage: 'downloaded',
    });

    await actions.onDownload({
      id: 9,
      name: 'report.pdf',
      mimeType: 'application/pdf',
    } as AttachmentInfo);

    expect(download).toHaveBeenCalledWith(9, 'report.pdf', 'application/pdf');
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith('downloaded');
  });
});

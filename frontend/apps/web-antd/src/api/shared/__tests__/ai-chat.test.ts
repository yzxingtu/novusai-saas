import { describe, expect, it, vi } from 'vitest';

import {
  buildChatAttachmentFromUpload,
  normalizeChatAttachments,
} from '../ai-chat';

vi.mock('#/utils/image', () => ({
  toAbsoluteApiUrl: (url?: string) =>
    typeof url === 'string' && url.startsWith('/')
      ? `http://localhost:8000${url}`
      : (url ?? ''),
}));

describe('ai-chat upload attachment builder', () => {
  it('prefers preview_url and preserves attachment_id for private image uploads', () => {
    const file = new File(['image'], 'secret.png', { type: 'image/png' });

    const attachment = buildChatAttachmentFromUpload(file, {
      attachment: {
        id: 42,
        mime_type: 'image/png',
        original_name: 'secret.png',
        preview_url:
          '/api/public/attachments/42/image?exp=1&sign=abc&token=jwt',
      },
      url: '/api/public/attachments/42/access?exp=1&sign=def&token=jwt',
      used_bytes: 128,
    });

    expect(attachment).toEqual({
      attachment_id: 42,
      mime_type: 'image/png',
      name: 'secret.png',
      type: 'image',
      url: 'http://localhost:8000/api/public/attachments/42/image?exp=1&sign=abc&token=jwt',
    });
  });

  it('normalizes persisted relative attachment urls for history replay', () => {
    expect(
      normalizeChatAttachments([
        {
          attachment_id: 49,
          type: 'image',
          url: '/api/public/attachments/49/image?exp=1&sign=abc&token=jwt',
        },
      ]),
    ).toEqual([
      {
        attachment_id: 49,
        type: 'image',
        url: 'http://localhost:8000/api/public/attachments/49/image?exp=1&sign=abc&token=jwt',
      },
    ]);
  });
});

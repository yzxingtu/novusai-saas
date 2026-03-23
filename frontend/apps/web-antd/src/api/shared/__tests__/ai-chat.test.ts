import { describe, expect, it } from 'vitest';

import { buildChatAttachmentFromUpload } from '../ai-chat';

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
      url: '/api/public/attachments/42/image?exp=1&sign=abc&token=jwt',
    });
  });
});

import { describe, expect, it, vi } from 'vitest';

vi.mock('../api-url', () => ({
  getAppApiUrl: () => 'https://api.example.test',
}));

describe('image utilities', () => {
  it('normalizes only positive integer attachment IDs as canonical writable values', async () => {
    const { parseAttachmentId, toCanonicalAttachmentImageValue } = await import(
      '../image'
    );

    expect(parseAttachmentId('42')).toBe(42);
    expect(parseAttachmentId(42)).toBe(42);
    expect(toCanonicalAttachmentImageValue(' 42 ')).toBe('42');
    expect(toCanonicalAttachmentImageValue(42)).toBe('42');

    expect(parseAttachmentId('42.7')).toBeNull();
    expect(parseAttachmentId('/api/public/attachments/42/image')).toBeNull();
    expect(toCanonicalAttachmentImageValue('https://cdn.example.test/a.png')).toBe(
      '',
    );
    expect(toCanonicalAttachmentImageValue('0')).toBe('');
  });

  it('keeps legacy URLs isolated to read-only display helpers', async () => {
    const {
      isReadOnlyLegacyImageValue,
      toAttachmentImageUrl,
      toReadOnlyAttachmentImageDisplayUrl,
    } = await import('../image');

    expect(toAttachmentImageUrl('42', { preset: 'avatar' })).toBe(
      'https://api.example.test/api/public/attachments/42/image?p=avatar',
    );
    expect(toAttachmentImageUrl('/uploads/legacy.png')).toBe('');
    expect(isReadOnlyLegacyImageValue('/uploads/legacy.png')).toBe(true);
    expect(toReadOnlyAttachmentImageDisplayUrl('/uploads/legacy.png')).toBe(
      '/uploads/legacy.png',
    );
    expect(toReadOnlyAttachmentImageDisplayUrl('42')).toBe(
      'https://api.example.test/api/public/attachments/42/image',
    );
  });
});

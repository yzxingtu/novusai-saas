import { describe, expect, it } from 'vitest';

import {
  getAttachmentCategoryColor,
  getAttachmentMimeCategoryFilterValues,
  getAttachmentVisibilityColor,
} from '../attachment-presentation';

describe('attachmentPresentation', () => {
  it('returns stable category and visibility colors', () => {
    expect(getAttachmentCategoryColor('image')).toBe('green');
    expect(getAttachmentCategoryColor('archive')).toBe('orange');
    expect(getAttachmentCategoryColor(undefined)).toBe('default');
    expect(getAttachmentVisibilityColor('public')).toBe('green');
    expect(getAttachmentVisibilityColor('private')).toBe('orange');
  });

  it('returns the shared mime filter prefixes in a stable order', () => {
    expect(getAttachmentMimeCategoryFilterValues()).toEqual([
      'image/',
      'application/',
      'video/',
      'audio/',
    ]);
  });
});

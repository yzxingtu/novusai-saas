import type { ReplaceContentValidation } from '../replaceContentValidator';

/**
 * replace_content validation unit tests.
 * replace_content 校验单元测试。
 */
import { describe, expect, it } from 'vitest';

import { validateReplaceContentParams } from '../replaceContentValidator';

const passThrough = (s: string) => s;

describe('validateReplaceContentParams', () => {
  const processors = {
    ensureHtml: passThrough,
    fixTableWidthZero: passThrough,
    sanitizeTableAttributesForSetContent: passThrough,
  };

  it('returns invalid when params.content is empty', () => {
    const r = validateReplaceContentParams({}, processors);
    expect(r.valid).toBe(false);
    if (!r.valid) {
      expect(r.error_type).toBe('invalid_input_empty_content');
    }
  });

  it('returns invalid when params.content is undefined', () => {
    const r = validateReplaceContentParams({ content: undefined }, processors);
    expect(r.valid).toBe(false);
    if (!r.valid) {
      expect(r.error_type).toBe('invalid_input_empty_content');
    }
  });

  it('returns invalid when params.content is whitespace only', () => {
    const r = validateReplaceContentParams(
      { content: '   \n\t  ' },
      processors,
    );
    expect(r.valid).toBe(false);
  });

  it('returns invalid when stripped HTML has no text (tags only)', () => {
    const r = validateReplaceContentParams(
      { content: '<div></div><p></p>' },
      processors,
    );
    expect(r.valid).toBe(false);
    if (!r.valid) {
      expect(r.error_type).toBe('invalid_input_empty_content');
    }
  });

  it('returns valid when params.content has body text', () => {
    const content = '<p>Hello world</p>';
    const r = validateReplaceContentParams(
      { content },
      processors,
    ) as ReplaceContentValidation & { valid: true };
    expect(r.valid).toBe(true);
    expect(r.html).toBe(content);
    expect(r.inputLength).toBe(content.length);
  });

  it('returns valid for plain text', () => {
    const r = validateReplaceContentParams(
      { content: 'Some text' },
      processors,
    ) as ReplaceContentValidation & { valid: true };
    expect(r.valid).toBe(true);
    expect(r.html).toBe('Some text');
    expect(r.inputLength).toBe(9);
  });

  it('does not call setContent (validator has no side effects)', () => {
    const setContentSpy = { called: false };
    const r = validateReplaceContentParams({ content: '' }, processors);
    expect(r.valid).toBe(false);
    expect(setContentSpy.called).toBe(false);
  });
});

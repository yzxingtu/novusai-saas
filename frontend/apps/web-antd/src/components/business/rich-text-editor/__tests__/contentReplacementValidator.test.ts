import type { ContentReplacementValidation } from '../contentReplacementValidator';

/**
 * Test type: behavioral
 * Verifies: rich-text replacement input validation rejects empty content and normalizes valid body text.
 * Mock strategy: only pure processor callbacks are identity functions; no editor/runtime behavior is mocked.
 */
import { describe, expect, it } from 'vitest';

import { validateContentReplacementParams } from '../contentReplacementValidator';

const passThrough = (s: string) => s;

describe('validateContentReplacementParams', () => {
  const processors = {
    ensureHtml: passThrough,
    fixTableWidthZero: passThrough,
    sanitizeTableAttributesForSetContent: passThrough,
  };

  it('returns invalid when params.content is empty', () => {
    const r = validateContentReplacementParams({}, processors);
    expect(r.valid).toBe(false);
    if (!r.valid) {
      expect(r.error_type).toBe('invalid_input_empty_content');
    }
  });

  it('returns invalid when params.content is undefined', () => {
    const r = validateContentReplacementParams(
      { content: undefined },
      processors,
    );
    expect(r.valid).toBe(false);
    if (!r.valid) {
      expect(r.error_type).toBe('invalid_input_empty_content');
    }
  });

  it('returns invalid when params.content is whitespace only', () => {
    const r = validateContentReplacementParams(
      { content: '   \n\t  ' },
      processors,
    );
    expect(r.valid).toBe(false);
  });

  it('returns invalid when stripped HTML has no text', () => {
    const r = validateContentReplacementParams(
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
    const r = validateContentReplacementParams(
      { content },
      processors,
    ) as ContentReplacementValidation & { valid: true };
    expect(r.valid).toBe(true);
    expect(r.html).toBe(content);
    expect(r.inputLength).toBe(content.length);
  });

  it('returns valid for plain text', () => {
    const r = validateContentReplacementParams(
      { content: 'Some text' },
      processors,
    ) as ContentReplacementValidation & { valid: true };
    expect(r.valid).toBe(true);
    expect(r.html).toBe('Some text');
    expect(r.inputLength).toBe(9);
  });

  it('does not call setContent', () => {
    const setContentSpy = { called: false };
    const r = validateContentReplacementParams({ content: '' }, processors);
    expect(r.valid).toBe(false);
    expect(setContentSpy.called).toBe(false);
  });
});

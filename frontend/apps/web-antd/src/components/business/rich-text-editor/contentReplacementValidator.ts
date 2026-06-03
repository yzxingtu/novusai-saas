/**
 * Generic rich-text content replacement input validation.
 * 通用富文本内容替换输入校验。
 */

/** Result of validation: either valid with html to set, or invalid with error info. */
export type ContentReplacementValidation =
  | { error_type: 'invalid_input_empty_content'; valid: false }
  | { html: string; inputLength: number; valid: true };

/**
 * Validate replacement content without touching the editor instance.
 * 校验替换内容，不接触编辑器实例。
 */
export function validateContentReplacementParams(
  params: Record<string, unknown>,
  processors: {
    ensureHtml: (s: string) => string;
    fixTableWidthZero: (s: string) => string;
    sanitizeTableAttributesForSetContent: (s: string) => string;
  },
): ContentReplacementValidation {
  const raw = String(params.content ?? '').trim();
  if (!raw) {
    return { valid: false, error_type: 'invalid_input_empty_content' };
  }
  const html = processors.sanitizeTableAttributesForSetContent(
    processors.fixTableWidthZero(processors.ensureHtml(raw)),
  );
  const stripped = html.replaceAll(/<[^>]+>/g, '').trim();
  if (stripped.length === 0) {
    return { valid: false, error_type: 'invalid_input_empty_content' };
  }
  return { valid: true, html, inputLength: raw.length };
}

/**
 * replace_content input validation (extracted for testability).
 * replace_content 输入校验（提取以便单元测试）。
 */

/** Result of validation: either valid with html to set, or invalid with error info. */
export type ReplaceContentValidation =
  | { error_type: 'invalid_input_empty_content'; valid: false }
  | { html: string; inputLength: number; valid: true };

/**
 * Validate params for replace_content. Does not touch the editor.
 * 校验 replace_content 的 params，不接触编辑器。
 */
export function validateReplaceContentParams(
  params: Record<string, unknown>,
  processors: {
    ensureHtml: (s: string) => string;
    fixTableWidthZero: (s: string) => string;
    sanitizeTableAttributesForSetContent: (s: string) => string;
  },
): ReplaceContentValidation {
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

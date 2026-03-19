/**
 * Form option parameter utilities.
 * 表单远程选项参数工具。
 */

/**
 * Resolve remote-select field name from supported aliases.
 * 从兼容别名中解析远程选项字段名。
 */
export function resolveFormOptionsFieldName(
  params: Record<string, unknown>,
): string {
  const candidates = [params.field_name, params.fieldName, params.field];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
  }
  return '';
}

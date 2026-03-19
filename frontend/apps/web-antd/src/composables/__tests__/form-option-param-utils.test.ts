/**
 * Form option parameter utility tests.
 * 表单远程选项参数工具测试。
 */
import { describe, expect, it } from 'vitest';

import { resolveFormOptionsFieldName } from '../form-option-param-utils';

describe('resolveFormOptionsFieldName', () => {
  it('prefers canonical field_name', () => {
    expect(
      resolveFormOptionsFieldName({
        field_name: 'model_id',
        field: 'tenant_ids',
      }),
    ).toBe('model_id');
  });

  it('falls back to fieldName and field aliases', () => {
    expect(
      resolveFormOptionsFieldName({
        fieldName: 'tenant_ids',
      }),
    ).toBe('tenant_ids');

    expect(
      resolveFormOptionsFieldName({
        field: 'model_id',
      }),
    ).toBe('model_id');
  });

  it('returns empty string for missing aliases', () => {
    expect(resolveFormOptionsFieldName({})).toBe('');
  });
});

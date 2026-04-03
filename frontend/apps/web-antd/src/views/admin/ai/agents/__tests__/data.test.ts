import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useScopeFieldsMock } = vi.hoisted(() => ({
  useScopeFieldsMock: vi.fn(() => []),
}));

vi.mock('#/adapter/form', () => ({
  inputField: vi.fn(() => ({ fieldName: 'name' })),
  numberField: vi.fn(() => ({ fieldName: 'number' })),
  select: vi.fn(() => ({ fieldName: 'select' })),
  textareaField: vi.fn(() => ({ fieldName: 'textarea' })),
}));

vi.mock('#/api/admin/ai', () => ({
  getAIModelSelectApi: vi.fn(),
}));

vi.mock('#/components/business/scope-select/use-scope-fields', () => ({
  useScopeFields: useScopeFieldsMock,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import { useFormSchema } from '../data';

describe('admin agent form schema', () => {
  beforeEach(() => {
    useScopeFieldsMock.mockClear();
  });

  it('keeps tenant assignment required for regular admin agents', () => {
    useFormSchema(true, false, false);

    expect(useScopeFieldsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantIdsRequired: true,
      }),
    );
  });

  it('relaxes tenant assignment requirement for plugin-managed system agents', () => {
    useFormSchema(true, true, false, undefined, true);

    expect(useScopeFieldsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantIdsRequired: false,
      }),
    );
  });
});

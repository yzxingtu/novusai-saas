import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getFormDefaults, useFormSchema } from '../data';

const { useScopeFieldsMock } = vi.hoisted(() => ({
  useScopeFieldsMock: vi.fn(() => [{ fieldName: 'scope' }]),
}));

vi.mock('#/adapter/form', () => ({
  inputField: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Input',
    fieldName,
    label,
    ...options,
  })),
  numberField: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Number',
    fieldName,
    label,
    ...options,
  })),
  searchInput: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'SearchInput',
    fieldName,
    label,
    ...options,
  })),
  select: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Select',
    fieldName,
    label,
    ...options,
  })),
  switchField: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Switch',
    fieldName,
    label,
    ...options,
  })),
  textareaField: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Textarea',
    fieldName,
    label,
    ...options,
  })),
}));

vi.mock('#/api/admin/ai', () => ({
  getAIModelSelectApi: vi.fn(),
}));

vi.mock('#/components/business/scope-select', () => ({
  useScopeFields: useScopeFieldsMock,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('admin knowledge base form schema', () => {
  beforeEach(() => {
    useScopeFieldsMock.mockClear();
  });

  it('does not expose audio/video model selectors in the new SaaS form', () => {
    const schema = useFormSchema();
    const fieldNames = schema.map((item) => item.fieldName);

    expect(fieldNames).toContain('embedding_model_id');
    expect(fieldNames).toContain('vision_model_id');
    expect(fieldNames).toContain('extract_images');
    expect(fieldNames).not.toContain('audio_model_id');
    expect(fieldNames).not.toContain('video_model_id');
  });

  it('keeps defaults aligned with the surviving embedding + vision configuration', () => {
    const defaults = getFormDefaults() as Record<string, unknown>;

    expect(defaults.embedding_model_id).toBeUndefined();
    expect(defaults.vision_model_id).toBeNull();
    expect(defaults.extract_images).toBe(false);
    expect(
      Object.prototype.hasOwnProperty.call(defaults, 'audio_model_id'),
    ).toBe(false);
    expect(
      Object.prototype.hasOwnProperty.call(defaults, 'video_model_id'),
    ).toBe(false);
  });
});

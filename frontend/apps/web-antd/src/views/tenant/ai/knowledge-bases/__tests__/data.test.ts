import { describe, expect, it, vi } from 'vitest';

import { isTenantOwnedKnowledgeBase, useFormSchema } from '../data';

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

vi.mock('#/api/tenant/ai', () => ({
  getTenantAIModelsApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('tenant knowledge base ownership helper', () => {
  it('treats tenant-owned knowledge bases as manageable', () => {
    expect(isTenantOwnedKnowledgeBase(7)).toBe(true);
  });

  it('treats platform-delivered knowledge bases as readonly', () => {
    expect(isTenantOwnedKnowledgeBase(null)).toBe(false);
  });
});

describe('tenant knowledge base form schema', () => {
  it('does not expose audio/video model selectors in the new SaaS form', () => {
    const schema = useFormSchema();
    const fieldNames = schema.map((item) => item.fieldName);

    expect(fieldNames).toContain('embedding_model_id');
    expect(fieldNames).toContain('vision_model_id');
    expect(fieldNames).toContain('extract_images');
    expect(fieldNames).not.toContain('audio_model_id');
    expect(fieldNames).not.toContain('video_model_id');
  });
});

import { describe, expect, it, vi } from 'vitest';

vi.mock('#/adapter/form', () => ({
  inputField: vi.fn(),
  numberField: vi.fn(),
  searchInput: vi.fn(),
  select: vi.fn(() => ({})),
  switchField: vi.fn(),
  textareaField: vi.fn(),
}));

vi.mock('#/api/tenant/ai', () => ({
  getTenantAIModelsApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import { isTenantOwnedKnowledgeBase } from '../data';

describe('tenant knowledge base ownership helper', () => {
  it('treats tenant-owned knowledge bases as manageable', () => {
    expect(isTenantOwnedKnowledgeBase(7)).toBe(true);
  });

  it('treats platform-delivered knowledge bases as readonly', () => {
    expect(isTenantOwnedKnowledgeBase(null)).toBe(false);
  });
});

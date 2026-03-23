import { describe, expect, it, vi } from 'vitest';

import {
  hasForbiddenProviderEndpointSuffix,
  normalizeProviderBaseUrlInput,
  resolveProviderWireApi,
} from '../data';

vi.mock('#/adapter/form', () => ({
  inputField: vi.fn(),
  searchInput: vi.fn(),
  select: vi.fn(),
  switchField: vi.fn(),
  textareaField: vi.fn(),
  z: {},
}));

vi.mock('#/adapter/vxe-table', () => ({
  dragColumn: {},
}));

vi.mock('#/api/admin/ai', () => ({
  getAdapterTypesApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('provider connection settings helpers', () => {
  it('keeps base url input untouched except trimming whitespace', () => {
    expect(
      normalizeProviderBaseUrlInput(' https://code.respyun.com/v1/responses '),
    ).toBe('https://code.respyun.com/v1/responses');
  });

  it('returns null for blank base url input', () => {
    expect(normalizeProviderBaseUrlInput('   ')).toBeNull();
  });

  it('uses the explicit configured wire api', () => {
    expect(resolveProviderWireApi('openai_compatible', 'responses')).toBe(
      'responses',
    );
  });

  it('rejects endpoint-style base url only for openai-compatible providers', () => {
    expect(
      hasForbiddenProviderEndpointSuffix(
        'https://code.respyun.com/v1/responses',
        'openai_compatible',
      ),
    ).toBe(true);
    expect(
      hasForbiddenProviderEndpointSuffix(
        'https://plugins.example.com/responses',
        'custom_plugin',
      ),
    ).toBe(false);
  });

  it('defaults openai compatible providers to chat completions', () => {
    expect(resolveProviderWireApi('openai_compatible', null)).toBe(
      'chat_completions',
    );
  });

  it('does not expose wire api for non-openai-compatible providers', () => {
    expect(resolveProviderWireApi('anthropic', 'responses')).toBeNull();
  });
});

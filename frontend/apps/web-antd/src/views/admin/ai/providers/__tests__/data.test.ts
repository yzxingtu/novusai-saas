import { describe, expect, it, vi } from 'vitest';

import * as providerData from '../data';

function createZodStub() {
  return {
    refine: vi.fn(() => createZodStub()),
  };
}

vi.mock('#/adapter/form', () => ({
  inputField: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Input',
    fieldName,
    label,
    ...options,
  })),
  searchInput: vi.fn((fieldName: string, label: string, options = {}) => ({
    component: 'Input',
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
  z: {
    string: vi.fn(() => createZodStub()),
    number: vi.fn(() => createZodStub()),
    null: vi.fn(() => createZodStub()),
    undefined: vi.fn(() => createZodStub()),
    union: vi.fn(() => createZodStub()),
  },
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
      providerData.normalizeProviderBaseUrlInput(
        ' https://code.respyun.com/v1/responses ',
      ),
    ).toBe('https://code.respyun.com/v1/responses');
  });

  it('returns null for blank base url input', () => {
    expect(providerData.normalizeProviderBaseUrlInput('   ')).toBeNull();
  });

  it('uses the explicit configured wire api', () => {
    expect(
      providerData.resolveProviderWireApi('openai_compatible', 'responses'),
    ).toBe('responses');
  });

  it('rejects endpoint-style base url only for openai-compatible providers', () => {
    expect(
      providerData.hasForbiddenProviderEndpointSuffix(
        'https://code.respyun.com/v1/responses',
        'openai_compatible',
      ),
    ).toBe(true);
    expect(
      providerData.hasForbiddenProviderEndpointSuffix(
        'https://plugins.example.com/responses',
        'custom_plugin',
      ),
    ).toBe(false);
  });

  it('defaults openai compatible providers to chat completions', () => {
    expect(providerData.resolveProviderWireApi('openai_compatible', null)).toBe(
      'chat_completions',
    );
  });

  it('does not expose wire api for non-openai-compatible providers', () => {
    expect(
      providerData.resolveProviderWireApi('anthropic', 'responses'),
    ).toBeNull();
  });

  it('uses the localized fallback label for known adapter types', () => {
    expect(providerData.getProviderTypeText('openai_compatible')).toBe(
      'admin.ai.provider.type_options.openai_compatible',
    );
  });

  it('warns when an openai-compatible base url looks like it is missing /v1', () => {
    expect(
      providerData.hasLikelyMissingProviderApiVersion(
        'https://api.asxs.top',
        'openai_compatible',
      ),
    ).toBe(true);
    expect(
      providerData.hasLikelyMissingProviderApiVersion(
        'https://api.openai.com/v1',
        'openai_compatible',
      ),
    ).toBe(false);
  });
});

describe('provider form config contracts', () => {
  it('does not expose retired provider defaults', () => {
    const defaults = providerData.getFormDefaults();
    expect(defaults.type).toBe('openai_compatible');
    expect(defaults.is_active).toBe(true);
    expect(
      Object.prototype.hasOwnProperty.call(defaults, 'responses_tool_history_compat'),
    ).toBe(false);
  });

  it('does not expose retired compatibility fields in the provider form schema', () => {
    const schema = providerData.useFormSchema();

    expect(
      schema.some((item) => item.fieldName === 'responses_tool_history_compat'),
    ).toBe(false);
  });

  it('hides the type search filter when only one adapter type is available', () => {
    const schema = providerData.useGridFormSchema();

    expect(schema).toHaveLength(1);
    expect(schema[0]).toMatchObject({ fieldName: 'name' });
  });
});

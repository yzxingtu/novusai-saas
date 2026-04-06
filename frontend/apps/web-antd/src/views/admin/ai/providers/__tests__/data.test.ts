import { describe, expect, it, vi } from 'vitest';

import * as providerData from '../data';

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
    expect(providerData.resolveProviderWireApi('anthropic', 'responses')).toBeNull();
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

describe('provider web_search config contracts', () => {
  it('keeps getFormDefaults backward-compatible and allows web_search defaults when added', () => {
    const defaults = providerData.getFormDefaults();
    expect(defaults.type).toBe('openai_compatible');
    expect(defaults.is_active).toBe(true);

    const maybeDefaults = defaults as Record<string, unknown>;
    if ('web_search_enabled' in maybeDefaults) {
      expect(maybeDefaults.web_search_enabled).toBeTypeOf('boolean');
      expect(maybeDefaults.web_search_enabled).toBe(true);
    }
    if ('web_search_strategy' in maybeDefaults) {
      expect(maybeDefaults.web_search_strategy).toBe(
        'native_first_fallback_public',
      );
    }
  });

  it('validates optional web_search normalize helper when it exists', () => {
    const normalizeWebSearchConfig = (
      providerData as Record<string, unknown>
    ).normalizeWebSearchConfig;
    if (typeof normalizeWebSearchConfig !== 'function') {
      return;
    }

    const normalized = (
      normalizeWebSearchConfig as (config: unknown) => Record<string, unknown>
    )({
      enabled: true,
      strategy: 'native_first_fallback_public',
      max_results_cap: 8,
      native_timeout_seconds: 20,
      public_timeout_seconds: 15,
      public_providers: ['baidu', 'so360'],
    });

    expect(normalized.enabled).toBe(true);
    expect(normalized.strategy).toBe('native_first_fallback_public');
    expect(normalized.max_results_cap).toBe(8);
    expect(normalized.native_timeout_seconds).toBe(20);
    expect(normalized.public_timeout_seconds).toBe(15);
    expect(normalized.public_providers).toEqual(['baidu', 'so360']);
  });

  it('validates optional runtime web_search helper when it exists', () => {
    const resolveWebSearchRuntimeHint = (
      providerData as Record<string, unknown>
    ).resolveWebSearchRuntimeHint;
    if (typeof resolveWebSearchRuntimeHint !== 'function') {
      return;
    }

    const hint = (
      resolveWebSearchRuntimeHint as (
        runtime: Record<string, unknown>,
      ) => Record<string, unknown>
    )({
      native_supported: false,
      native_provider: 'openai_compatible',
      reason: 'unsupported_model',
    });

    expect(hint).toBeTruthy();
  });

  it.skip(
    'draft: should cover config <-> form mapping helper once main branch exports it',
    () => {
      // Expected helper candidates for main implementation:
      // - mapWebSearchConfigToForm(config)
      // - mapWebSearchFormToConfig(formValues)
      // Activate this test once those helpers are exported from ../data.
    },
  );
});

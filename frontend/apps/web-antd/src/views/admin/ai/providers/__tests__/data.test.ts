import { describe, expect, it, vi } from 'vitest';

import * as providerData from '../data';

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

  it('hides the type search filter when only one adapter type is available', () => {
    const schema = providerData.useGridFormSchema();

    expect(schema).toHaveLength(1);
    expect(schema[0]).toMatchObject({ fieldName: 'name' });
  });

  it('validates optional web_search normalize helper when it exists', () => {
    const normalizeWebSearchConfig = (providerData as Record<string, unknown>)
      .normalizeWebSearchConfig;
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

  it('preserves advanced web_search fields when resolving provider config', () => {
    const resolved = providerData.resolveProviderWebSearchConfig({
      web_search: {
        enabled: true,
        strategy: 'native_first_fallback_public',
        max_results_cap: 8,
        native_timeout_seconds: 20,
        public_timeout_seconds: 15,
        public_providers: ['baidu', 'so360'],
        allow_unverified_runtime_target: true,
        verified_native_target: {
          provider_code: 'openai',
          model_code: 'gpt-5.4',
        },
      },
    });

    expect(resolved.allow_unverified_runtime_target).toBe(true);
    expect(resolved.verified_native_target).toEqual({
      provider_code: 'openai',
      model_code: 'gpt-5.4',
    });
  });

  it('preserves advanced web_search fields from existing config on form submit rebuild', () => {
    const built = providerData.buildProviderWebSearchConfigFromForm(
      {
        web_search_enabled: true,
        web_search_strategy: 'native_first_fallback_public',
        web_search_max_results_cap: 5,
        web_search_native_timeout_seconds: 12,
        web_search_public_timeout_seconds: 9,
        web_search_public_providers: ['baidu'],
      },
      {
        enabled: true,
        strategy: 'native_first_fallback_public',
        max_results_cap: 8,
        native_timeout_seconds: 20,
        public_timeout_seconds: 15,
        public_providers: ['baidu', 'so360'],
        allow_unverified_runtime_target: false,
        verified_native_target: {
          provider_id: 10,
          model_code: 'gpt-5.4',
        },
      },
    );

    expect(built.enabled).toBe(true);
    expect(built.max_results_cap).toBe(5);
    expect(built.public_providers).toEqual(['baidu']);
    expect(built.allow_unverified_runtime_target).toBe(false);
    expect(built.verified_native_target).toEqual({
      provider_id: 10,
      model_code: 'gpt-5.4',
    });
  });

  it('builds advanced web_search fields directly from flat form inputs', () => {
    const built = providerData.buildProviderWebSearchConfigFromForm({
      web_search_enabled: true,
      web_search_strategy: 'native_first_fallback_public',
      web_search_max_results_cap: 5,
      web_search_native_timeout_seconds: 12,
      web_search_public_timeout_seconds: 9,
      web_search_public_providers: ['baidu'],
      web_search_allow_unverified_runtime_target: true,
      web_search_verified_provider_code: 'openai',
      web_search_verified_model_code: 'gpt-5.4',
    });

    expect(built.allow_unverified_runtime_target).toBe(true);
    expect(built.verified_native_target).toEqual({
      provider_code: 'openai',
      model_code: 'gpt-5.4',
    });
  });

  it('clears advanced web_search target fields when flat form inputs are blank', () => {
    const built = providerData.buildProviderWebSearchConfigFromForm(
      {
        web_search_enabled: true,
        web_search_strategy: 'native_first_fallback_public',
        web_search_max_results_cap: 5,
        web_search_native_timeout_seconds: 12,
        web_search_public_timeout_seconds: 9,
        web_search_public_providers: ['baidu'],
        web_search_allow_unverified_runtime_target: false,
        web_search_verified_provider_code: '',
        web_search_verified_model_code: '',
      },
      {
        enabled: true,
        strategy: 'native_first_fallback_public',
        max_results_cap: 8,
        native_timeout_seconds: 20,
        public_timeout_seconds: 15,
        public_providers: ['baidu', 'so360'],
        allow_unverified_runtime_target: true,
        verified_native_target: {
          provider_code: 'openai',
          model_code: 'gpt-5.4',
        },
      },
    );

    expect(built.allow_unverified_runtime_target).toBe(false);
    expect(built.verified_native_target).toBeNull();
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

  it.skip('draft: should cover config <-> form mapping helper once main branch exports it', () => {
    // Expected helper candidates for main implementation:
    // - mapWebSearchConfigToForm(config)
    // - mapWebSearchFormToConfig(formValues)
    // Activate this test once those helpers are exported from ../data.
  });
});

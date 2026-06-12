import { describe, expect, it, vi } from 'vitest';

import {
  buildModelConfig,
  buildModelFormValues,
  buildModelPayload,
  buildRemoteModelFormValues,
  resolveModelCodeForForm,
  resolveReasoningEffort,
  supportsReasoningEffort,
} from '../data';

vi.mock('#/adapter/form', () => ({
  dividerField: vi.fn(),
  inputField: vi.fn(),
  numberField: vi.fn(),
  searchInput: vi.fn(),
  select: vi.fn(),
  switchField: vi.fn(),
}));

vi.mock('#/api/admin/ai-models', () => ({
  getAIModelSelectApi: vi.fn(),
}));

vi.mock('#/api/admin/ai-providers', () => ({
  getAIProviderSelectApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('ai model runtime helpers', () => {
  it('reads reasoning effort only from structured runtime overrides', () => {
    expect(
      resolveReasoningEffort(
        {
          runtime_overrides: {
            openai_compatible: {
              responses: {
                reasoning: { effort: 'high' },
              },
            },
          },
        },
        'gpt-5.4-xhigh',
        'openai_compatible',
        'chat',
      ),
    ).toBe('high');
    expect(
      resolveReasoningEffort(
        {
          runtimeOverrides: {
            openai_compatible: {
              responses: {
                reasoning: { effort: 'xhigh' },
              },
            },
          },
          runtime_overrides: {
            openai_compatible: {
              chat_completions: { reasoning_effort: 'xhigh' },
            },
          },
          reasoningEffort: 'xhigh',
          reasoning_effort: 'xhigh',
        },
        'gpt-5.4',
        'openai_compatible',
        'chat',
      ),
    ).toBeNull();
    expect(
      resolveModelCodeForForm(
        {
          runtime_overrides: {
            openai_compatible: {
              responses: {
                reasoning: { effort: 'high' },
              },
            },
          },
        },
        'gpt-5.4',
      ),
    ).toBe('gpt-5.4');
  });

  it('builds model config with reasoning effort and removes empty reasoning block', () => {
    expect(
      buildModelConfig('xhigh', 'gpt-5.4', 'openai_compatible', 'chat', null),
    ).toEqual({
      runtime_overrides: {
        openai_compatible: {
          responses: { reasoning: { effort: 'xhigh' } },
        },
      },
    });
    expect(
      buildModelConfig(null, 'gpt-5.4', 'openai_compatible', 'chat', {
        runtime_overrides: {
          openai_compatible: {
            responses: { reasoning: { effort: 'high' } },
            chat_completions: { reasoning_effort: 'high' },
          },
        },
      }),
    ).toBeNull();
  });

  it('clears overrides when the model type no longer supports advanced runtime params', () => {
    expect(
      buildModelConfig('xhigh', 'gpt-5.4', 'openai_compatible', 'embedding', {
        runtime_overrides: {
          openai_compatible: {
            responses: { reasoning: { effort: 'high' } },
          },
        },
      }),
    ).toBeNull();
  });

  it('builds form values from model info without parsing model-code aliases', () => {
    const values = buildModelFormValues({
      id: 1,
      provider_id: 10,
      name: 'GPT-5.4 (Display)',
      code: 'gpt-5.4-xhigh',
      type: 'chat',
      context_window: null,
      max_output_tokens: null,
      input_price_per_1k: null,
      output_price_per_1k: null,
      rpm_limit: null,
      tpm_limit: null,
      supports_function_calling: true,
      supports_vision: false,
      supports_audio: false,
      supports_video: false,
      supports_streaming: true,
      embedding_dimensions: null,
      max_image_count: null,
      max_image_size_mb: null,
      is_active: true,
      config: null,
      fallback_model_id: null,
      fallback_model_name: null,
      tier: null,
      provider_name: '响应云',
      provider_type: 'openai_compatible',
      created_at: '',
      updated_at: '',
    });

    expect(values.code).toBe('gpt-5.4-xhigh');
    expect(values.reasoning_effort).toBeNull();
  });

  it('builds payload without dropping unrelated config keys', () => {
    const payload = buildModelPayload(
      {
        name: 'GPT-5.4',
        code: 'gpt-5.4',
        type: 'chat',
        provider_id: 10,
        provider_type: 'openai_compatible',
        supports_vision: false,
        supports_audio: false,
        supports_video: false,
        supports_streaming: true,
        supports_function_calling: true,
        is_active: true,
        reasoning_effort: 'xhigh',
      },
      {
        runtime_overrides: {
          openai_compatible: {
            responses: { reasoning: { effort: 'medium' } },
          },
        },
      },
    );

    expect(payload.config).toEqual({
      runtime_overrides: {
        openai_compatible: {
          responses: { reasoning: { effort: 'xhigh' } },
        },
      },
    });
  });

  it('does not expose reasoning effort for unsupported models like claude', () => {
    expect(supportsReasoningEffort('gpt-5.4')).toBe(true);
    expect(supportsReasoningEffort('claude-3-5-sonnet')).toBe(false);
    expect(
      resolveReasoningEffort(
        {
          runtime_overrides: {
            openai_compatible: {
              responses: { reasoning: { effort: 'xhigh' } },
            },
          },
        },
        'claude-3-5-sonnet',
        'openai_compatible',
        'chat',
      ),
    ).toBeNull();
    expect(
      buildModelPayload(
        {
          name: 'Claude',
          code: 'claude-3-5-sonnet',
          type: 'chat',
          provider_id: 10,
          provider_type: 'openai_compatible',
          supports_vision: false,
          supports_audio: false,
          supports_video: false,
          supports_streaming: true,
          supports_function_calling: true,
          is_active: true,
          reasoning_effort: 'xhigh',
        },
        {
          runtime_overrides: {
            openai_compatible: {
              responses: { reasoning: { effort: 'high' } },
            },
          },
        },
      ).config,
    ).toBeNull();
  });

  it('resets reasoning effort when remote model auto-fill runs', () => {
    const values = buildRemoteModelFormValues(
      'gpt-5.4',
      10,
      'openai_compatible',
      {
        model_type: 'chat',
        supports_function_calling: true,
        supports_streaming: true,
      },
    );

    expect(values.code).toBe('gpt-5.4');
    expect(values.reasoning_effort).toBeNull();
    expect(values.supports_function_calling).toBe(true);
  });
});

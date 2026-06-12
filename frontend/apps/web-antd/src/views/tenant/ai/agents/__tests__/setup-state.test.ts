// Test type: behavioral
// Verifies: tenant agent setup state hides creation only when no active chat model exists.
// Mock strategy: pure helper tests; no API, DOM, or real AI dialogue is used.

import type { TenantAIModelInfo } from '#/api/tenant/ai';

import { describe, expect, it } from 'vitest';

import {
  hasTenantActiveChatModel,
  resolveTenantAgentSetupState,
} from '../composables/setup-state';

function model(
  overrides: Partial<TenantAIModelInfo>,
): TenantAIModelInfo {
  return {
    code: 'gpt-5.4',
    context_window: 128_000,
    created_at: '2026-06-12T00:00:00Z',
    id: 1,
    input_price_per_1k: null,
    is_active: true,
    max_output_tokens: 4096,
    name: 'GPT-5.4',
    output_price_per_1k: null,
    provider_id: 1,
    provider_name: 'OpenAI',
    supports_function_calling: true,
    supports_streaming: true,
    supports_vision: false,
    tier: null,
    type: 'chat',
    updated_at: '2026-06-12T00:00:00Z',
    ...overrides,
  };
}

describe('tenant agent setup state', () => {
  it('detects active chat models only', () => {
    expect(
      hasTenantActiveChatModel([
        model({ is_active: false }),
        model({ id: 2, type: 'embedding' }),
        model({ id: 3, type: 'chat' }),
      ]),
    ).toBe(true);
  });

  it('ignores inactive and non-chat models', () => {
    expect(
      hasTenantActiveChatModel([
        model({ is_active: false }),
        model({ id: 2, type: 'embedding' }),
      ]),
    ).toBe(false);
  });

  it('reports checking while model status is unknown and loading', () => {
    expect(resolveTenantAgentSetupState(null, true)).toBe('checking');
  });

  it('reports missing model only when no active chat model is confirmed', () => {
    expect(resolveTenantAgentSetupState(false, false)).toBe('missing-model');
  });

  it('keeps normal state when status check fails to avoid blocking CRUD', () => {
    expect(resolveTenantAgentSetupState(null, false, true)).toBe('normal');
  });
});

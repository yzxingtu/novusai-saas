// Test type: behavioral
// Verifies: admin agent onboarding state is derived only from bootstrap status.
// Mock strategy: pure helper tests; no API, DOM, or real AI dialogue is used.

import type { AIAgentBootstrapStatus } from '#/api/admin/ai-agents';

import { describe, expect, it } from 'vitest';

import { resolveAdminAgentSetupState } from '../composables/setup-state';

function bootstrapStatus(
  overrides: Partial<AIAgentBootstrapStatus>,
): AIAgentBootstrapStatus {
  return {
    active_chat_model: null,
    active_provider: null,
    bootstrap_state: 'ready',
    has_active_chat_model: true,
    has_active_provider: true,
    needs_seed: false,
    runtime_ready: true,
    system_agents_ready: true,
    system_assignments: [],
    ...overrides,
  };
}

describe('admin agent setup state', () => {
  it('reports checking before bootstrap status arrives', () => {
    expect(resolveAdminAgentSetupState(null, true)).toBe('checking');
  });

  it('reports error when status request fails before data exists', () => {
    expect(resolveAdminAgentSetupState(null, false, true)).toBe('error');
  });

  it('reports missing provider before model readiness', () => {
    expect(
      resolveAdminAgentSetupState(
        bootstrapStatus({
          bootstrap_state: 'missing_provider',
          has_active_chat_model: false,
          has_active_provider: false,
          runtime_ready: false,
        }),
        false,
      ),
    ).toBe('missing-provider');
  });

  it('reports missing model when provider exists without active chat model', () => {
    expect(
      resolveAdminAgentSetupState(
        bootstrapStatus({
          bootstrap_state: 'missing_model',
          has_active_chat_model: false,
          runtime_ready: false,
        }),
        false,
      ),
    ).toBe('missing-model');
  });

  it('reports seed system when runtime is ready but Copilots need repair', () => {
    expect(
      resolveAdminAgentSetupState(
        bootstrapStatus({
          bootstrap_state: 'seed_system',
          needs_seed: true,
          system_agents_ready: false,
        }),
        false,
      ),
    ).toBe('seed-system');
  });

  it('reports normal when runtime and system agents are ready', () => {
    expect(resolveAdminAgentSetupState(bootstrapStatus({}), false)).toBe(
      'normal',
    );
  });
});

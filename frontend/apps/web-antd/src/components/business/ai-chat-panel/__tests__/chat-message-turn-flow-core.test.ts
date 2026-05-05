// Test type: behavioral
// Verifies: turn-flow merge preserves terminal failure metadata instead of
// leaving stale completed state from an earlier partial projection.
// Mock strategy: no external services; turn-flow core runs directly.
import { describe, expect, it } from 'vitest';

import { mergeTurnFlow } from '../chat-message-turn-flow-core';

describe('chat message turn-flow core', () => {
  it('preserves incoming failure kind and turn outcome during merge', () => {
    const merged = mergeTurnFlow(
      {
        completionReason: 'completed',
        evidence: [],
        finalStageStatus: 'completed',
        timeline: [],
      },
      {
        completionReason: 'provider_unavailable',
        evidence: [],
        failureKind: 'provider_unavailable',
        finalStageStatus: 'error',
        timeline: [],
        turnOutcome: 'partial',
      },
    );

    expect(merged?.completionReason).toBe('provider_unavailable');
    expect(merged?.failureKind).toBe('provider_unavailable');
    expect(merged?.turnOutcome).toBe('partial');
    expect(merged?.finalStageStatus).toBe('error');
  });
});

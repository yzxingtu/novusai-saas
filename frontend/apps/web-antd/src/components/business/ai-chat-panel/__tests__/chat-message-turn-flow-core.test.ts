// Test type: behavioral
// Verifies: live turnFlow accepts only canonical backend-owned timeline/evidence fields.
import type { ChatMessage } from '../types';

import { describe, expect, it } from 'vitest';

import {
  applyCanonicalDoneEvent,
  normalizeTurnFlowViewModel,
  settleTurnFlowAfterLifecycleFinalize,
} from '../chat-message-turn-flow-ingestion';

describe('chat-message-turn-flow canonical ownership', () => {
  it('ignores retired stages and sources aliases in the live normalizer', () => {
    expect(
      normalizeTurnFlowViewModel({
        sources: [{ id: 'legacy-source', kind: 'knowledge_base' }],
        stages: [{ id: 'legacy-stage', status: 'running', type: 'thinking' }],
      }),
    ).toBeUndefined();
  });

  it('does not fabricate turnFlow from lifecycle-only message state', () => {
    const message: ChatMessage = {
      clientKey: 'assistant-lifecycle-only',
      content: 'partial answer',
      error: {
        message: 'transport closed',
        source: 'sse',
      },
      partial: true,
      role: 'assistant',
      streaming: false,
    };

    settleTurnFlowAfterLifecycleFinalize(message);

    expect(message.turnFlow).toBeUndefined();
  });

  it('settles an existing canonical turnFlow after lifecycle finalization', () => {
    const message: ChatMessage = {
      clientKey: 'assistant-with-canonical-turn-flow',
      content: '',
      role: 'assistant',
      streaming: false,
      turnFlow: {
        evidence: [],
        timeline: [
          {
            id: 'thinking-1',
            status: 'running',
            type: 'thinking',
          },
        ],
      },
    };

    settleTurnFlowAfterLifecycleFinalize(message);

    const turnFlow = message.turnFlow;
    expect(turnFlow).toBeDefined();
    expect(message.turnFlow).toEqual(
      expect.objectContaining({
        complete: true,
        finalStageStatus: 'completed',
      }),
    );
    expect(turnFlow?.timeline?.[0]).toEqual(
      expect.objectContaining({
        id: 'thinking-1',
        status: 'completed',
      }),
    );
  });

  it('does not fabricate turnFlow from done event lifecycle fields alone', () => {
    const message: ChatMessage = {
      clientKey: 'assistant-done-without-canonical-turn-flow',
      content: 'done',
      role: 'assistant',
      streaming: false,
    };

    applyCanonicalDoneEvent(message, {
      completion_reason: 'completed',
      turn_flow_complete: true,
      turn_outcome: 'success',
    });

    expect(message.turnFlow).toBeUndefined();
    expect(message.completionReason).toBe('completed');
  });
});

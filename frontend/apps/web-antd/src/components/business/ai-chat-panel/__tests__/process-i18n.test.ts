// @vitest-environment happy-dom
// Test type: structural / behavioral
// Verifies: process/timeline helper fallbacks use locale keys and retrieval
// evidence helpers do not surface runtime-only diagnostics.
import type { ChatMessage } from '../types';

import { mount } from '@vue/test-utils';
import { computed } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { getRagSourcesForDisplay } from '../chat-message-turn-flow';
import {
  createEmptyTurnFlow,
  settleTurnFlowFinalState,
} from '../chat-message-turn-flow-core';
import ChatMessageDiagnostics from '../ChatMessageDiagnostics.vue';
import { buildTurnFlowState } from '../../ai-chat-kernel/TurnFlowState';

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) => {
    if (!params || Object.keys(params).length === 0) {
      return key;
    }
    const suffix = Object.entries(params)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, value]) => `${name}=${String(value)}`)
      .join(',');
    return `${key}:${suffix}`;
  },
}));

vi.mock('#/composables/use-diagnostics-policy', () => ({
  useDiagnosticsPolicy: () => ({
    showDiagnostics: computed(() => true),
  }),
}));

function createAssistantMessage(
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    clientKey: 'process-i18n-test',
    content: '',
    role: 'assistant',
    ...overrides,
  };
}

describe('process i18n helpers', () => {
  it('uses a localized fallback label for evidence chips without titles', () => {
    const state = buildTurnFlowState(
      createAssistantMessage({
        turnFlow: {
          evidence: [{ id: 'evidence-1', kind: 'tool', status: 'success' }],
          timeline: [],
        },
      }),
    );

    expect(state.selectedEvidence[0]?.label).toBe(
      'common.globalAiChat.referenceLinkFallback',
    );
  });

  it('uses a localized fallback label for retrieval sources without names', () => {
    const ragSources = getRagSourcesForDisplay(
      createAssistantMessage({
        turnFlow: {
          evidence: [
            { id: 'kb-1', kind: 'knowledge_base', score: 0.8 },
          ],
          timeline: [],
        },
      }),
    );

    expect(ragSources?.[0]?.doc_name).toBe(
      'common.globalAiChat.turnSourceFallback:index=1',
    );
  });

  it('does not expose runtime context diagnostics as retrieval sources', () => {
    const ragSources = getRagSourcesForDisplay(
      createAssistantMessage({
        turnFlow: {
          evidence: [
            { id: 'evidence-1', kind: 'knowledge_base', title: 'skill_resolver' },
            { id: 'evidence-2', kind: 'memory', title: 'long_term_memory' },
            { id: 'evidence-3', kind: 'knowledge_base', title: 'gpt-5.5' },
          ],
          timeline: [],
        },
      }),
    );

    expect(ragSources).toBeUndefined();
  });

  it('uses localized titles for synthetic terminal stages', () => {
    const completedFlow = createEmptyTurnFlow();
    settleTurnFlowFinalState(completedFlow, 'completed');

    expect(completedFlow.timeline.at(-1)?.title).toBe(
      'common.globalAiChat.turnStageType.completed',
    );

    const failedFlow = createEmptyTurnFlow();
    failedFlow.finalStageStatus = 'error';
    settleTurnFlowFinalState(failedFlow, 'error');

    expect(failedFlow.timeline.at(-1)?.title).toBe(
      'common.globalAiChat.turnStageType.failed',
    );
  });

  it('localizes known diagnostics context source kinds', () => {
    const wrapper = mount(ChatMessageDiagnostics, {
      props: {
        apiPrefix: '/admin',
        forceShow: true,
        msg: createAssistantMessage({
          contextSources: [
            {
              active: true,
              kind: 'knowledge_base',
              name: 'policy_kb',
            },
          ],
          requestFailedRetry: true,
          terminationReason: 'tool_error',
          turnOutcome: 'failed',
        }),
      },
    });

    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnEvidenceKind.knowledge_base:policy_kb',
    );
  });
});

// Test type: behavioral
// Verifies: canonical turnFlow display helpers expose real thinking detail lines and tool evidence without reading legacy assistant fields.
import type { ChatMessage } from '../types';

import { describe, expect, it, vi } from 'vitest';

import {
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
  getTurnFlowForDisplay,
} from '../chat-message-turn-flow';

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

describe('chat-message-turn-flow display helpers', () => {
  it('projects thinking detail lines and tool evidence from canonical turnFlow only', () => {
    const message: ChatMessage = {
      clientKey: 'assistant-canonical-turn-flow',
      content: '',
      role: 'assistant',
      streaming: true,
      turnFlow: {
        evidence: [
          {
            arguments: { status: 'active' },
            id: 'tool-evidence-1',
            kind: 'tool',
            output: JSON.stringify({
              rows: [{ name: 'Acme Supplier' }],
            }),
            status: 'running',
            toolCallId: 'tool-call-1',
            toolName: 'query_records',
          },
        ],
        timeline: [
          {
            detailLines: ['**Inspect** current filters', 'Call query_records'],
            id: 'thinking-stage-1',
            status: 'running',
            type: 'thinking',
          },
        ],
      },
    };

    expect(getThinkingContentForDisplay(message)).toBe(
      '**Inspect** current filters\n\nCall query_records',
    );

    expect(getTurnFlowForDisplay(message).timeline).toEqual([
      expect.objectContaining({
        id: 'thinking-stage-1',
        status: 'running',
        summary: 'Inspect current filters',
        type: 'thinking',
      }),
    ]);

    expect(getToolCallsForDisplay(message)).toEqual([
      expect.objectContaining({
        arguments: { status: 'active' },
        id: 'tool-call-1',
        name: 'query_records',
        output: JSON.stringify({
          rows: [{ name: 'Acme Supplier' }],
        }),
        status: 'running',
      }),
    ]);
  });
});

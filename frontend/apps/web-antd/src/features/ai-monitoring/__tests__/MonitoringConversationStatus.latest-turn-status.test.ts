// Test type: behavioral
// Scope: monitoring conversation status display for conversation 2344-style provider failures.
// Mock strategy: no mocked turn-flow or LLM output; this exercises the real display-status helper.
import { describe, expect, it } from 'vitest';

import {
  conversationStatusColor,
  getConversationDisplayStatus,
} from '../pages/monitoring-conversation/helpers';

describe('monitoring conversation latest-turn display status', () => {
  it('renders conversation 2344 active lifecycle as failed when the latest turn failed', () => {
    const status = getConversationDisplayStatus({
      display_status: null,
      latest_conversation_outcome: 'failed',
      latest_failure_kind: 'provider_unavailable',
      latest_turn_flow_terminal_status: 'error',
      latest_turn_flow_terminal_type: 'failed',
      latest_turn_outcome: 'partial',
      latest_turn_status: null,
      status: 'active',
    });

    expect(status).toBe('failed');
    expect(conversationStatusColor(status)).toBe('error');
  });

  it('keeps an active conversation in-progress when no terminal turn exists', () => {
    const status = getConversationDisplayStatus({
      display_status: null,
      latest_conversation_outcome: null,
      latest_failure_kind: null,
      latest_turn_flow_terminal_status: null,
      latest_turn_flow_terminal_type: null,
      latest_turn_outcome: null,
      latest_turn_status: null,
      status: 'active',
    });

    expect(status).toBe('active');
    expect(conversationStatusColor(status)).toBe('processing');
  });
});

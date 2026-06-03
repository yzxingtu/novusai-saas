import { describe, expect, it } from 'vitest';

import { resolveConversationRequestState } from '../conversation-binding';

describe('conversation-binding', () => {
  it('reuses the current conversation when no active conversation exists', () => {
    expect(
      resolveConversationRequestState({
        activeConversationAgentId: null,
        activeConversationId: null,
        targetAgentId: 7,
      }),
    ).toEqual({
      conversationId: null,
      shouldForkConversation: false,
    });
  });

  it('reuses the current conversation when the target agent matches the bound agent', () => {
    expect(
      resolveConversationRequestState({
        activeConversationAgentId: 7,
        activeConversationId: 101,
        targetAgentId: 7,
      }),
    ).toEqual({
      conversationId: 101,
      shouldForkConversation: false,
    });
  });

  it('forks to a new conversation when the target agent differs from the bound agent', () => {
    expect(
      resolveConversationRequestState({
        activeConversationAgentId: 7,
        activeConversationId: 101,
        targetAgentId: 9,
      }),
    ).toEqual({
      conversationId: null,
      shouldForkConversation: true,
    });
  });

  it('keeps the current conversation when the bound agent is unknown', () => {
    expect(
      resolveConversationRequestState({
        activeConversationAgentId: null,
        activeConversationId: 101,
        targetAgentId: 9,
      }),
    ).toEqual({
      conversationId: 101,
      shouldForkConversation: false,
    });
  });
});

export interface ConversationRequestStateInput {
  activeConversationAgentId: null | number;
  activeConversationId: null | number;
  targetAgentId: number;
}

export interface ConversationRequestStateResult {
  conversationId: null | number;
  shouldForkConversation: boolean;
}

export function resolveConversationRequestState(
  input: ConversationRequestStateInput,
): ConversationRequestStateResult {
  const {
    activeConversationAgentId,
    activeConversationId,
    targetAgentId,
  } = input;

  if (
    activeConversationId == null ||
    activeConversationAgentId == null ||
    activeConversationAgentId === targetAgentId
  ) {
    return {
      conversationId: activeConversationId,
      shouldForkConversation: false,
    };
  }

  return {
    conversationId: null,
    shouldForkConversation: true,
  };
}

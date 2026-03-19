import type { AgentItem, ChatMessage } from './types';

const LEADING_AGENT_MENTION_RE = /^\s*@([^\s]*)$/;

export function extractLeadingAgentMentionDraft(input: string): null | string {
  const match = LEADING_AGENT_MENTION_RE.exec(input);
  return match ? (match[1] ?? '') : null;
}

export function filterAgentsByMentionQuery(
  agents: AgentItem[],
  query: string,
): AgentItem[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return agents;
  }
  return agents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(normalized) ||
      (agent.description?.toLowerCase().includes(normalized) ?? false),
  );
}

export function moveStreamingContentToThinking(
  message: Pick<ChatMessage, 'content' | 'thinkingContent'>,
): void {
  if (!message.content) {
    return;
  }
  message.thinkingContent = `${message.thinkingContent || ''}${message.content}`;
  message.content = '';
}

import type { AgentItem, ChatMessage } from '../types';

import { describe, expect, it } from 'vitest';

import {
  extractLeadingAgentMentionDraft,
  filterAgentsByMentionQuery,
  filterKnowledgeBasesByMentionQuery,
  moveStreamingContentToThinking,
} from '../chat-input-utils';

function createAgent(
  id: number,
  name: string,
  description: null | string = null,
): AgentItem {
  return {
    id,
    tenant_id: 1,
    name,
    description,
    avatar: null,
    status: 'active',
  };
}

describe('chat-input-utils', () => {
  it('extracts leading mention draft only when input is still in mention mode', () => {
    expect(extractLeadingAgentMentionDraft('@DataBot')).toBe('DataBot');
    expect(extractLeadingAgentMentionDraft('   @')).toBe('');
    expect(extractLeadingAgentMentionDraft('@DataBot hello')).toBeNull();
    expect(extractLeadingAgentMentionDraft('hello @DataBot')).toBeNull();
  });

  it('filters agents by name and description case-insensitively', () => {
    const agents = [
      createAgent(1, 'DataBot', 'SQL expert'),
      createAgent(2, 'Writer', 'Content editor'),
      createAgent(3, 'Ops', 'Deployment helper'),
    ];

    expect(
      filterAgentsByMentionQuery(agents, 'data').map((agent) => agent.id),
    ).toEqual([1]);
    expect(
      filterAgentsByMentionQuery(agents, 'editor').map((agent) => agent.id),
    ).toEqual([2]);
    expect(
      filterAgentsByMentionQuery(agents, '').map((agent) => agent.id),
    ).toEqual([1, 2, 3]);
  });

  it('filters knowledge bases by name or id', () => {
    const bindings = [
      { knowledge_base_id: 10, kb_name: 'Product Docs' as null | string },
      { knowledge_base_id: 20, kb_name: 'HR Policy' as null | string },
    ];
    expect(
      filterKnowledgeBasesByMentionQuery(bindings, 'product').map(
        (b) => b.knowledge_base_id,
      ),
    ).toEqual([10]);
    expect(
      filterKnowledgeBasesByMentionQuery(bindings, '20').map(
        (b) => b.knowledge_base_id,
      ),
    ).toEqual([20]);
    expect(filterKnowledgeBasesByMentionQuery(bindings, '').length).toBe(2);
  });

  it('moves streamed tool-round content into the thinking block', () => {
    const message: ChatMessage = {
      clientKey: 'assistant-streaming-message',
      role: 'assistant',
      content: '先检查数据库。',
      thinkingContent: '先分析问题。',
    };

    moveStreamingContentToThinking(message);

    expect(message.content).toBe('');
    expect(message.thinkingContent).toBe('先分析问题。先检查数据库。');
  });
});

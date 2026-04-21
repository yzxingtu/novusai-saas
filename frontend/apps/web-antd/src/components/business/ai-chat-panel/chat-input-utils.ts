import type { AgentItem, MentionKnowledgeBaseBinding } from './types';

const LEADING_AGENT_MENTION_RE = /^\s*@(\S*)$/;

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

/** Filter agent-bound knowledge bases by @ draft query / 按 @ 草稿过滤已绑定知识库 */
export function filterKnowledgeBasesByMentionQuery(
  bindings: MentionKnowledgeBaseBinding[],
  query: string,
): MentionKnowledgeBaseBinding[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return bindings;
  }
  return bindings.filter((b) => {
    const label = (b.kb_name || `KB#${b.knowledge_base_id}`).toLowerCase();
    return (
      label.includes(normalized) ||
      String(b.knowledge_base_id).includes(normalized)
    );
  });
}

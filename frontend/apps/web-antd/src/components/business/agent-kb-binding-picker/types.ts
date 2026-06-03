import type { AIAgentKBBindingInfo } from '#/api/admin/ai-agents';
import type { SelectableKBItem } from '#/api/admin/knowledge-bases';

export interface AgentKnowledgeBaseBindingDraftItem {
  kb_description: null | string;
  kb_name: string;
  kb_owner_tenant_id: null | number;
  kb_owner_tenant_name: null | string;
  kb_scope: null | string;
  knowledge_base_id: number;
}

export function bindingsToDrafts(
  bindings: AIAgentKBBindingInfo[],
): AgentKnowledgeBaseBindingDraftItem[] {
  return bindings.map((binding) => ({
    knowledge_base_id: binding.knowledge_base_id,
    kb_name: binding.kb_name || `#${binding.knowledge_base_id}`,
    kb_description: binding.kb_description,
    kb_owner_tenant_id: binding.kb_owner_tenant_id,
    kb_owner_tenant_name: binding.kb_owner_tenant_name,
    kb_scope: binding.kb_scope,
  }));
}

export function selectableToDraft(
  item: SelectableKBItem,
): AgentKnowledgeBaseBindingDraftItem {
  return {
    knowledge_base_id: item.id,
    kb_name: item.name,
    kb_description: item.description,
    kb_owner_tenant_id: item.owner_tenant_id,
    kb_owner_tenant_name: item.owner_tenant_name,
    kb_scope: item.scope,
  };
}

export function draftsToBatchPayload(
  drafts: AgentKnowledgeBaseBindingDraftItem[],
): { knowledge_base_ids: number[] } {
  return {
    knowledge_base_ids: drafts.map((draft) => draft.knowledge_base_id),
  };
}

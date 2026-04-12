import type { ComputedRef, Ref } from 'vue';

import type { AgentItem, ChatMessage } from './types';

import { computed, ref } from 'vue';

import { getAgentInputVariables } from './types';

function varsLocalKey(agentId: number): string {
  return `ai-vars:${agentId}`;
}

function saveVarsToStorage(agentId: number, vars: Record<string, string>) {
  try {
    localStorage.setItem(varsLocalKey(agentId), JSON.stringify(vars));
  } catch {
    // quota exceeded or private mode
  }
}

function loadVarsFromStorage(agentId: number): null | Record<string, string> {
  try {
    const raw = localStorage.getItem(varsLocalKey(agentId));
    return raw ? (JSON.parse(raw) as Record<string, string>) : null;
  } catch {
    return null;
  }
}

export function useAIChatVariables(
  agents: Ref<AgentItem[]>,
  chatMessages: Ref<ChatMessage[]>,
): {
  agentsWithVarsInConversation: ComputedRef<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist?: boolean,
  ) => void;
  clearConversationVarsCache: () => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  resetVariables: () => void;
} {
  const allAgentsVariables = ref<Record<number, Record<string, string>>>({});

  function ensureAgentVarsLoaded(agentId: number) {
    if (!(agentId in allAgentsVariables.value)) {
      const stored = loadVarsFromStorage(agentId);
      allAgentsVariables.value[agentId] = stored ?? {};
    }
  }

  function applyVariables(
    agentId: number,
    values: Record<string, string>,
    persist = false,
  ) {
    allAgentsVariables.value[agentId] = { ...values };
    if (persist) {
      saveVarsToStorage(agentId, { ...values });
    }
  }

  function resetVariables() {
    allAgentsVariables.value = {};
  }

  function clearConversationVarsCache() {
    // no-op: variables are persisted by agent.
  }

  const agentsWithVarsInConversation = computed(() => {
    const agentIdsInChat = new Set<number>(
      chatMessages.value.flatMap((message) =>
        message.role === 'assistant' && typeof message.agent_id === 'number'
          ? [message.agent_id]
          : [],
      ),
    );
    return agents.value.filter(
      (agent) =>
        agentIdsInChat.has(agent.id) && getAgentInputVariables(agent).length > 0,
    );
  });

  return {
    agentsWithVarsInConversation,
    allAgentsVariables,
    applyVariables,
    clearConversationVarsCache,
    ensureAgentVarsLoaded,
    resetVariables,
  };
}

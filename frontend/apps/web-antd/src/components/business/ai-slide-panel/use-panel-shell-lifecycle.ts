import type { Ref } from 'vue';

import type { AgentItem } from '#/types/ai-chat';

import { onMounted, onUnmounted, watch, watchEffect } from 'vue';

interface PanelShellLifecycleStore {
  docked: boolean;
  minimized: boolean;
  mode: string;
  panelWidth: number;
  pinnedAgentId: null | number;
  resetConversation: () => void;
  setConversation: (conversationId: number, agentId?: number) => void;
  visible: boolean;
}

interface UsePanelShellLifecycleOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
  cleanup: () => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  loadSavedWidth: () => void;
  manualNewConversationAgentId: Ref<null | number>;
  onDocumentClick: (event: MouseEvent) => void;
  panelStore: PanelShellLifecycleStore;
  selectedAgentId: Ref<null | number>;
}

export function usePanelShellLifecycle(options: UsePanelShellLifecycleOptions) {
  watch(options.selectedAgentId, (agentId) => {
    if (agentId) {
      options.ensureAgentVarsLoaded(agentId);
    }
    if (
      options.manualNewConversationAgentId.value &&
      agentId !== options.manualNewConversationAgentId.value
    ) {
      options.manualNewConversationAgentId.value = null;
    }
  });

  watch(
    [() => options.panelStore.pinnedAgentId, options.agents],
    ([pinnedAgentId, availableAgents]) => {
      if (
        pinnedAgentId &&
        availableAgents.some((agent) => agent.id === pinnedAgentId) &&
        options.selectedAgentId.value !== pinnedAgentId
      ) {
        options.selectedAgentId.value = pinnedAgentId;
      }
    },
    { immediate: true },
  );

  watch(
    [options.activeConversationId, options.selectedAgentId],
    ([conversationId, agentId]) => {
      if (conversationId === null) {
        options.panelStore.resetConversation();
        return;
      }
      options.panelStore.setConversation(conversationId, agentId ?? undefined);
    },
  );

  watchEffect(() => {
    const shouldOffset =
      options.panelStore.visible &&
      !options.panelStore.minimized &&
      options.panelStore.mode === 'panel' &&
      options.panelStore.docked;
    const offset = shouldOffset ? `${options.panelStore.panelWidth}px` : '0px';
    document.documentElement.style.setProperty(
      '--ai-panel-right-offset',
      offset,
    );
  });

  onMounted(() => {
    options.loadSavedWidth();
    document.addEventListener('mousedown', options.onDocumentClick);
  });

  onUnmounted(() => {
    options.cleanup();
    document.removeEventListener('mousedown', options.onDocumentClick);
    document.documentElement.style.removeProperty('--ai-panel-right-offset');
  });
}

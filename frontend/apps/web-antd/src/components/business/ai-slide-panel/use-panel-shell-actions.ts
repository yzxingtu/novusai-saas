import type { Ref } from 'vue';

import { computed, ref } from 'vue';

import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';

interface StarterAgentLike {
  suggested_questions?: null | unknown[];
  welcome_message?: null | string;
}

interface PanelStoreLike {
  close: () => void;
  docked: boolean;
  dynamicWelcomeMessage: null | string;
  minimize: () => void;
  toggleDock: () => void;
  toggleMode: () => void;
  togglePin: (agentId: number, agentName: string) => void;
  visible: boolean;
  welcomeSuggestedActions: string[];
}

interface UsePanelShellActionsOptions {
  aiPanelStore: PanelStoreLike;
  handleSendMessage: () => boolean | Promise<boolean>;
  inputMessage: Ref<string>;
  selectedAgent: Ref<null | StarterAgentLike>;
}

export function usePanelShellActions(options: UsePanelShellActionsOptions) {
  const { aiPanelStore, handleSendMessage, inputMessage, selectedAgent } =
    options;

  const panelRef = ref<HTMLElement | null>(null);

  function handleClose() {
    aiPanelStore.close();
  }

  function handleMinimize() {
    aiPanelStore.minimize();
  }

  function handleToggleMode() {
    aiPanelStore.toggleMode();
  }

  function handleToggleDock() {
    aiPanelStore.toggleDock();
  }

  function onDocumentClick(event: MouseEvent) {
    if (
      !aiPanelStore.docked &&
      aiPanelStore.visible &&
      panelRef.value &&
      !panelRef.value.contains(event.target as Node)
    ) {
      aiPanelStore.close();
    }
  }

  function unpinAgent() {
    aiPanelStore.togglePin(0, '');
  }

  const starterAgent = computed(() => selectedAgent.value ?? null);
  const effectiveWelcomeMessage = computed(
    () =>
      aiPanelStore.dynamicWelcomeMessage ||
      starterAgent.value?.welcome_message ||
      '',
  );
  const effectiveSuggestedQuestions = computed<string[]>(() => {
    // Prefer dynamic suggested actions from store if available
    if (aiPanelStore.welcomeSuggestedActions.length > 0) {
      return aiPanelStore.welcomeSuggestedActions;
    }
    return normalizeStarterQuestions(starterAgent.value?.suggested_questions);
  });

  function askSuggested(question: string) {
    inputMessage.value = question;
    void handleSendMessage();
  }

  return {
    askSuggested,
    effectiveSuggestedQuestions,
    effectiveWelcomeMessage,
    handleClose,
    handleMinimize,
    handleToggleDock,
    handleToggleMode,
    onDocumentClick,
    panelRef,
    starterAgent,
    unpinAgent,
  };
}

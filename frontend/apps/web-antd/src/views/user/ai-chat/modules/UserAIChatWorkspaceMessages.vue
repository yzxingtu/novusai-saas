<script lang="ts" setup>
import AIChatMessageViewport from '#/components/business/ai-slide-panel/AIChatMessageViewport.vue';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const workspace = useUserAIChatWorkspaceContext();
const {
  page: {
    apiPrefix,
    chat,
    effectiveWelcomeMessage,
    effectiveSuggestedQuestions,
  },
} = workspace;
const {
  agents,
  agentKBBindings,
  agentKBBindingsByAgentId,
  agentSkillBindingsByAgentId,
  chatMessages,
  loadAgentKBBindings,
  loadAgentSkillBindings,
  sending,
  selectedAgent,
  messagesContainer,
  showScrollToBottom,
  showScrollToTop,
  streaming,
} = chat;

const setMessagesContainerRef = (element: HTMLDivElement | null) => {
  messagesContainer.value = element as HTMLElement | null;
};

function getPendingOpsForMessage() {
  return [];
}

function getRichTextDraftState() {
  return null;
}
</script>

<template>
  <AIChatMessageViewport
    :api-prefix="apiPrefix"
    :agent-knowledge-bases="agentKBBindings"
    :agent-knowledge-base-map="agentKBBindingsByAgentId"
    :agent-skill-map="agentSkillBindingsByAgentId"
    :agents="agents"
    :chat-messages="chatMessages"
    :compact="false"
    :effective-suggested-questions="effectiveSuggestedQuestions"
    :effective-welcome-message="effectiveWelcomeMessage"
    :ensure-agent-knowledge-bases="loadAgentKBBindings"
    :ensure-agent-skills="loadAgentSkillBindings"
    :get-pending-ops-for-message="getPendingOpsForMessage"
    :get-rich-text-draft-state="getRichTextDraftState"
    :register-container="setMessagesContainerRef"
    :selected-agent="selectedAgent"
    :sending="sending"
    :show-scroll-to-bottom="showScrollToBottom"
    :show-scroll-to-top="showScrollToTop"
    :streaming="streaming"
    @ask-suggested="workspace.askSuggested"
    @copy="workspace.onCopyMessage"
    @confirm="chat.confirmAction"
    @reject="chat.rejectAction"
    @consent-confirm="chat.confirmConsent"
    @consent-reject="chat.rejectConsent"
    @open-url="workspace.openImagePreview"
    @action-click="chat.clickActionButton"
    @regenerate="chat.regenerateMessage"
    @edit="chat.editAndResend"
    @retry="chat.retryLastMessage"
    @scroll="chat.handleMessagesScroll"
    @scroll-to-top="chat.scrollToTop"
    @scroll-to-bottom="chat.scrollToBottom(true)"
  />
</template>

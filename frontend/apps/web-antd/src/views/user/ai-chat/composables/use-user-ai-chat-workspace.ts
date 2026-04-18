import type { UserAIChatWorkspaceContext } from '../modules/user-ai-chat-workspace-context';

import { ref } from 'vue';

import { useUserAIChatContext } from '../modules/ai-chat-context';

export function useUserAIChatWorkspace(): UserAIChatWorkspaceContext {
  const page = useUserAIChatContext();
  const { chat, mobileSidebarOpen } = page;
  const {
    chatMessages,
    inputMessage,
    handleInputKeyDown,
    sendMessage,
    copyMessage,
  } = chat;

  const previewImageUrl = ref('');
  const previewImageVisible = ref(false);

  function openImagePreview(url: string) {
    previewImageUrl.value = url;
    previewImageVisible.value = true;
  }

  function openMobileSidebar() {
    mobileSidebarOpen.value = true;
  }

  async function onCopyMessage(content: string) {
    await copyMessage(content);
  }

  function handleSendClick() {
    sendMessage();
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (handleInputKeyDown(event)) {
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      handleSendClick();
    }
  }

  function askSuggested(question: string) {
    inputMessage.value = question;
    handleSendClick();
  }

  function isAgentSwitch(index: number): boolean {
    const message = chatMessages.value[index];
    if (!message || message.role !== 'assistant' || !message.agent_id) {
      return false;
    }
    for (let currentIndex = index - 1; currentIndex >= 0; currentIndex--) {
      const previousMessage = chatMessages.value[currentIndex];
      if (previousMessage?.role === 'assistant') {
        return previousMessage.agent_id !== message.agent_id;
      }
    }
    return false;
  }

  return {
    page,
    previewImageUrl,
    previewImageVisible,
    openImagePreview,
    openMobileSidebar,
    onCopyMessage,
    handleSendClick,
    handleKeyDown,
    askSuggested,
    isAgentSwitch,
  };
}

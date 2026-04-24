import type { UserAIChatWorkspaceContext } from '../modules/user-ai-chat-workspace-context';

import { ref } from 'vue';

import { useUserAIChatContext } from '../modules/ai-chat-context';

export function useUserAIChatWorkspace(): UserAIChatWorkspaceContext {
  const page = useUserAIChatContext();
  const { chat, mobileSidebarOpen } = page;
  const { inputMessage, handleInputKeyDown, sendMessage, copyMessage } = chat;

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
  };
}

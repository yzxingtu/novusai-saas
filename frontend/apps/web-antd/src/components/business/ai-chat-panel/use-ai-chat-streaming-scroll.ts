import { nextTick, ref } from 'vue';

export function createAIChatStreamingScroll() {
  const messagesContainer = ref<HTMLElement | null>(null);
  const userScrolledUp = ref(false);
  const userNotAtTop = ref(false);

  function isNearBottom(): boolean {
    const element = messagesContainer.value;
    if (!element) return true;
    const threshold = 80;
    return (
      element.scrollHeight - element.scrollTop - element.clientHeight <
      threshold
    );
  }

  function scrollToBottom(force = false) {
    nextTick(() => {
      const element = messagesContainer.value;
      if (!element) return;
      if (force || !userScrolledUp.value) {
        element.scrollTop = element.scrollHeight;
      }
    });
  }

  function scrollToTop() {
    nextTick(() => {
      const element = messagesContainer.value;
      if (!element) return;
      element.scrollTop = 0;
    });
  }

  function handleMessagesScroll() {
    const element = messagesContainer.value;
    if (!element) return;
    userScrolledUp.value = !isNearBottom();
    userNotAtTop.value = element.scrollTop > 80;
  }

  return {
    handleMessagesScroll,
    messagesContainer,
    scrollToBottom,
    scrollToTop,
    userNotAtTop,
    userScrolledUp,
  };
}

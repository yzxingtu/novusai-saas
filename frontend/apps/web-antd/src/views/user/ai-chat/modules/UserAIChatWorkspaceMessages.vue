<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { $t } from '#/locales';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const workspace = useUserAIChatWorkspaceContext();
const {
  page: {
    apiPrefix,
    chat,
    showWorkspaceHero,
    effectiveWelcomeMessage,
    effectiveSuggestedQuestions,
  },
} = workspace;
const {
  agents,
  selectedAgent,
  chatMessages,
  sending,
  streaming,
  messagesContainer,
  handleMessagesScroll,
  showScrollToBottom,
  showScrollToTop,
  scrollToBottom,
  scrollToTop,
  confirmAction,
  rejectAction,
  confirmConsent,
  rejectConsent,
  clickActionButton,
  regenerateMessage,
  editAndResend,
  retryLastMessage,
} = chat;
</script>

<template>
  <div
    :ref="messagesContainer"
    class="flex-1 overflow-y-auto px-4 py-4 sm:px-6"
    @scroll="handleMessagesScroll"
  >
    <div
      v-if="chatMessages.length === 0 && !sending"
      class="flex h-full items-center justify-center"
    >
      <div
        class="w-full"
        :class="showWorkspaceHero ? 'max-w-3xl' : 'max-w-2xl text-center'"
      >
        <template v-if="!showWorkspaceHero">
          <div class="text-base font-semibold text-foreground">
            {{ effectiveWelcomeMessage || $t('user.aiChat.welcomeTitle') }}
          </div>
          <div class="mt-2 text-sm text-muted-foreground">
            {{ $t('user.aiChat.welcomeDesc') }}
          </div>
        </template>

        <div
          v-if="effectiveSuggestedQuestions.length > 0"
          class="flex flex-col gap-2"
          :class="
            showWorkspaceHero
              ? 'mx-auto max-w-2xl rounded-[24px] border border-border/60 bg-background/80 p-4 text-left shadow-sm'
              : 'mt-6'
          "
        >
          <div
            v-if="showWorkspaceHero"
            class="mb-1 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground"
          >
            <IconifyIcon
              icon="lucide:message-circle-more"
              class="size-3.5 text-primary"
            />
            {{ $t('common.globalAiChat.starterQuestions') }}
          </div>
          <button
            v-for="(question, index) in effectiveSuggestedQuestions"
            :key="index"
            class="group/sq flex items-center gap-3 rounded-xl border border-border/30 bg-accent/15 px-4 py-3 text-left text-sm text-foreground transition-all hover:border-primary/30 hover:bg-accent/40 hover:shadow-sm"
            @click="workspace.askSuggested(question)"
          >
            <IconifyIcon
              icon="lucide:message-circle"
              class="size-4 shrink-0 text-primary/50 transition-colors group-hover/sq:text-primary"
            />
            <span class="flex-1 truncate">{{ question }}</span>
            <IconifyIcon
              icon="lucide:arrow-right"
              class="size-3.5 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60"
            />
          </button>
        </div>
      </div>
    </div>

    <div class="mx-auto max-w-3xl space-y-3">
      <ChatMessageItem
        v-for="(msg, index) in chatMessages"
        :key="index"
        :msg="msg"
        :index="index"
        :api-prefix="apiPrefix"
        :agents="agents"
        :selected-agent="selectedAgent"
        :show-agent-switch="workspace.isAgentSwitch(index)"
        @copy="workspace.onCopyMessage"
        @confirm="confirmAction"
        @reject="rejectAction"
        @consent-confirm="confirmConsent"
        @consent-reject="rejectConsent"
        @open-url="workspace.openImagePreview"
        @action-click="clickActionButton"
        @regenerate="regenerateMessage"
        @edit="editAndResend"
        @retry="retryLastMessage"
      />
    </div>

    <div class="sticky bottom-2 z-10 flex justify-center gap-2">
      <Transition name="fade">
        <button
          v-if="showScrollToTop && !streaming"
          class="inline-flex size-8 items-center justify-center rounded-full border border-border/60 bg-background/95 text-muted-foreground shadow-lg backdrop-blur-sm transition-all hover:bg-primary hover:text-white hover:shadow-xl"
          :aria-label="$t('common.globalAiChat.scrollToTop')"
          @click="scrollToTop()"
        >
          <IconifyIcon icon="lucide:arrow-up" class="size-4" />
        </button>
      </Transition>
      <Transition name="fade">
        <button
          v-if="showScrollToBottom && !streaming"
          class="inline-flex size-8 items-center justify-center rounded-full border border-border/60 bg-background/95 text-muted-foreground shadow-lg backdrop-blur-sm transition-all hover:bg-primary hover:text-white hover:shadow-xl"
          @click="scrollToBottom(true)"
        >
          <IconifyIcon icon="lucide:arrow-down" class="size-4" />
        </button>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active {
  transition: opacity 0.2s ease-out;
}

.fade-leave-active {
  transition: opacity 0.3s ease-in;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

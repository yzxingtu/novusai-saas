<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import type { PendingOpDisplayItem } from './use-pending-page-ops';

import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from '#/types/ai-chat';

import { ref, watch } from 'vue';

import AIChatComposer from './AIChatComposer.vue';
import AIChatConversationFooter from './AIChatConversationFooter.vue';
import AIChatHistoryPane from './AIChatHistoryPane.vue';
import AIChatMessageViewport from './AIChatMessageViewport.vue';

interface HistoryConversationItem {
  agent_name?: null | string;
  id: number;
  title?: null | string;
}

interface HistoryConversationGroup {
  items: HistoryConversationItem[];
  label: string;
}

interface ComposerAttachmentItem {
  icon?: string;
  key: string;
  name: string;
  previewUrl?: string;
  type: 'audio' | 'file' | 'image' | 'video';
}

interface ComposerKnowledgeBaseChip {
  id: number;
  label: string;
}

interface ComposerMentionCandidateItem {
  active: boolean;
  id: number;
  kind: 'knowledge_base';
  subtitle?: string;
  title: string;
}

type ComposerSendState = 'idle' | 'routing' | 'sending' | 'streaming';

const props = withDefaults(
  defineProps<{
    activeConversationId?: null | number;
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agents?: AgentItem[];
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
    apiPrefix: string;
    attachDisabled?: boolean;
    attachmentAccept?: string;
    attachmentLimitHint?: string;
    attachments?: ComposerAttachmentItem[];
    boundKnowledgeBases?: ComposerKnowledgeBaseChip[];
    characterCount?: number;
    chatMessages?: ChatMessage[];
    compactMessages?: boolean;
    conversationsCount?: number;
    conversationSearch?: string;
    conversationsLoading?: boolean;
    countdownNow?: number;
    editingConversationId?: null | number;
    editingTitle?: string;
    effectiveSuggestedQuestions?: string[];
    effectiveWelcomeMessage?: string;
    ensureAgentKnowledgeBases?: (agentId: number) => Promise<unknown> | void;
    ensureAgentSkills?: (agentId: number) => Promise<unknown> | void;
    exportMenuItems?: ItemType[];
    forceShowDiagnostics?: boolean;
    getPendingOpsForMessage: (msg: ChatMessage) => PendingOpDisplayItem[];
    getRichTextDraftState: (
      message: ChatMessage,
    ) => null | RichTextDraftRuntimeState;
    groupedConversations?: HistoryConversationGroup[];
    inputMessage?: string;
    mentionCandidates?: ComposerMentionCandidateItem[];
    mentionEmptyHint?: string;
    mentionLoading?: boolean;
    mentionMixedHint?: string;
    mentionOpen?: boolean;
    registerContainer?: (element: HTMLDivElement | null) => void;
    routing?: boolean;
    screenshotDisabled?: boolean;
    screenshotLoading?: boolean;
    selectedAgent?: AgentItem | null;
    selectedKnowledgeBases?: ComposerKnowledgeBaseChip[];
    sendDisabled?: boolean;
    sending?: boolean;
    sendState?: ComposerSendState;
    shiftEnterHint?: string;
    showAttachments?: boolean;
    showHistory?: boolean;
    showScreenshotButton?: boolean;
    showScrollToBottom?: boolean;
    showScrollToTop?: boolean;
    streaming?: boolean;
    totalTokensUsed?: number;
    unassociatedPendingOps?: PendingOpDisplayItem[];
  }>(),
  {
    activeConversationId: null,
    agentKnowledgeBases: null,
    agentKnowledgeBaseMap: null,
    agentSkillMap: null,
    agents: () => [],
    attachDisabled: false,
    attachmentAccept: '',
    attachmentLimitHint: '',
    attachments: () => [],
    boundKnowledgeBases: () => [],
    chatMessages: () => [],
    characterCount: 0,
    compactMessages: true,
    conversationSearch: '',
    conversationsCount: 0,
    conversationsLoading: false,
    countdownNow: 0,
    editingConversationId: null,
    editingTitle: '',
    effectiveSuggestedQuestions: () => [],
    effectiveWelcomeMessage: '',
    exportMenuItems: () => [],
    forceShowDiagnostics: false,
    ensureAgentKnowledgeBases: undefined,
    ensureAgentSkills: undefined,
    groupedConversations: () => [],
    inputMessage: '',
    mentionCandidates: () => [],
    mentionEmptyHint: '',
    mentionLoading: false,
    mentionMixedHint: '',
    mentionOpen: false,
    registerContainer: undefined,
    routing: false,
    screenshotDisabled: false,
    screenshotLoading: false,
    selectedAgent: null,
    selectedKnowledgeBases: () => [],
    sendDisabled: false,
    sendState: 'idle',
    sending: false,
    shiftEnterHint: '',
    showAttachments: true,
    showHistory: false,
    showScrollToBottom: false,
    showScrollToTop: false,
    showScreenshotButton: false,
    streaming: false,
    totalTokensUsed: 0,
    unassociatedPendingOps: () => [],
  },
);

const emit = defineEmits<{
  (e: 'actionClick', index: number, value: string): void;
  (e: 'askSuggested', question: string): void;
  (e: 'cancelEditTitle'): void;
  (e: 'commitEditTitle'): void;
  (e: 'confirm', index: number): void;
  (e: 'consentConfirm', index: number): void;
  (e: 'consentReject', index: number): void;
  (e: 'copy', content: string): void;
  (e: 'deleteConversation', conversationId: number): void;
  (e: 'edit', index: number): void;
  (e: 'newChat'): void;
  (e: 'openUrl', url: string): void;
  (e: 'regenerate', index: number): void;
  (e: 'reject', index: number): void;
  (e: 'resolvePendingOp', invokeId: string, allowed: boolean): void;
  (e: 'retry', index: number): void;
  (
    e: 'richTextApply',
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ): void;
  (e: 'richTextDiscard', index: number): void;
  (e: 'richTextUndo', index: number): void;
  (e: 'registerContainer', element: HTMLDivElement | null): void;
  (e: 'scroll'): void;
  (e: 'scrollToBottom'): void;
  (e: 'scrollToTop'): void;
  (e: 'selectConversation', conversationId: number): void;
  (
    e: 'selectMentionCandidate',
    payload: { id: number; kind: 'knowledge_base' },
  ): void;
  (e: 'send'): void;
  (e: 'stop'): void;
  (e: 'startEditTitle', conversation: HistoryConversationItem): void;
  (e: 'update:conversationSearch', value: string): void;
  (e: 'update:editingTitle', value: string): void;
  (e: 'update:inputMessage', value: string): void;
  (e: 'dragover', event: DragEvent): void;
  (e: 'drop', event: DragEvent): void;
  (e: 'fileSelect', event: Event): void;
  (e: 'keydown', event: KeyboardEvent): void;
  (e: 'paste', event: ClipboardEvent): void;
  (e: 'removeAttachment', index: number): void;
  (e: 'removeSelectedKnowledgeBase', id: number): void;
  (e: 'captureScreenshot'): void;
}>();

const panelBodyRoot = ref<HTMLDivElement | null>(null);

watch(
  () => props.showHistory,
  (showHistory) => {
    if (!showHistory || typeof document === 'undefined') {
      return;
    }
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLElement &&
      panelBodyRoot.value?.contains(activeElement)
    ) {
      activeElement.blur();
    }
  },
);
</script>

<template>
  <div
    ref="panelBodyRoot"
    class="relative flex min-h-0 flex-1 flex-col overflow-hidden"
  >
    <div
      data-testid="transcript-shell"
      class="flex min-h-0 flex-1 flex-col"
      :class="[
        compactMessages ? '' : 'mx-auto w-full max-w-5xl',
        showHistory
          ? 'saturate-75 pointer-events-none select-none opacity-45 blur-[1px]'
          : '',
      ]"
      :aria-hidden="showHistory ? 'true' : 'false'"
      :inert="showHistory || undefined"
    >
      <AIChatMessageViewport
        :api-prefix="apiPrefix"
        :agent-knowledge-bases="agentKnowledgeBases"
        :agent-knowledge-base-map="agentKnowledgeBaseMap"
        :agent-skill-map="agentSkillMap"
        :agents="agents"
        :chat-messages="chatMessages"
        :compact="compactMessages"
        :countdown-now="countdownNow"
        :effective-suggested-questions="effectiveSuggestedQuestions"
        :effective-welcome-message="effectiveWelcomeMessage"
        :force-show-diagnostics="forceShowDiagnostics"
        :get-pending-ops-for-message="getPendingOpsForMessage"
        :get-rich-text-draft-state="getRichTextDraftState"
        :ensure-agent-knowledge-bases="ensureAgentKnowledgeBases"
        :ensure-agent-skills="ensureAgentSkills"
        :register-container="(element) => emit('registerContainer', element)"
        :routing="routing"
        :selected-agent="selectedAgent"
        :sending="sending"
        :show-scroll-to-bottom="showScrollToBottom"
        :show-scroll-to-top="showScrollToTop"
        :streaming="streaming"
        :unassociated-pending-ops="unassociatedPendingOps"
        @ask-suggested="emit('askSuggested', $event)"
        @copy="emit('copy', $event)"
        @confirm="emit('confirm', $event)"
        @reject="emit('reject', $event)"
        @consent-confirm="emit('consentConfirm', $event)"
        @consent-reject="emit('consentReject', $event)"
        @open-url="emit('openUrl', $event)"
        @action-click="(index, value) => emit('actionClick', index, value)"
        @regenerate="emit('regenerate', $event)"
        @edit="emit('edit', $event)"
        @retry="emit('retry', $event)"
        @rich-text-apply="
          (index, target, mode) => emit('richTextApply', index, target, mode)
        "
        @rich-text-discard="emit('richTextDiscard', $event)"
        @rich-text-undo="emit('richTextUndo', $event)"
        @resolve-pending-op="
          (invokeId, allowed) => emit('resolvePendingOp', invokeId, allowed)
        "
        @scroll="emit('scroll')"
        @scroll-to-top="emit('scrollToTop')"
        @scroll-to-bottom="emit('scrollToBottom')"
      />

      <AIChatConversationFooter
        :message-count="chatMessages.length"
        :total-tokens-used="totalTokensUsed"
        :streaming="streaming"
        :export-menu-items="exportMenuItems"
      />

      <AIChatComposer
        :model-value="inputMessage"
        :disabled="agents.length === 0 || sending"
        :max-length="32000"
        :character-count="characterCount"
        :send-state="sendState"
        :send-disabled="sendDisabled"
        :show-attachments="showAttachments"
        :attach-disabled="attachDisabled"
        :attachment-accept="attachmentAccept"
        :attachments="attachments"
        :attachment-limit-hint="attachmentLimitHint"
        :show-screenshot-button="showScreenshotButton"
        :screenshot-disabled="screenshotDisabled"
        :screenshot-loading="screenshotLoading"
        :mention-open="mentionOpen"
        :mention-loading="mentionLoading"
        :mention-mixed-hint="mentionMixedHint"
        :mention-empty-hint="mentionEmptyHint"
        :mention-candidates="mentionCandidates"
        :bound-knowledge-bases="boundKnowledgeBases"
        :selected-knowledge-bases="selectedKnowledgeBases"
        :shift-enter-hint="shiftEnterHint"
        @update:model-value="emit('update:inputMessage', $event)"
        @dragover="emit('dragover', $event)"
        @drop="emit('drop', $event)"
        @file-select="emit('fileSelect', $event)"
        @keydown="emit('keydown', $event)"
        @paste="emit('paste', $event)"
        @capture-screenshot="emit('captureScreenshot')"
        @remove-attachment="emit('removeAttachment', $event)"
        @remove-selected-knowledge-base="
          emit('removeSelectedKnowledgeBase', $event)
        "
        @select-mention-candidate="emit('selectMentionCandidate', $event)"
        @send="emit('send')"
        @stop="emit('stop')"
      />
    </div>

    <Transition name="ai-chat-history-overlay">
      <div
        v-if="showHistory"
        data-testid="history-overlay"
        class="pointer-events-none absolute inset-0 z-10 px-3 py-3"
      >
        <div
          class="absolute inset-0 bg-background/78"
        ></div>
        <div
          data-testid="history-overlay-pane"
          class="ai-chat-history-overlay-pane pointer-events-auto relative flex h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] border"
          :class="compactMessages ? '' : 'mx-auto w-full max-w-5xl'"
        >
          <AIChatHistoryPane
            :active-conversation-id="activeConversationId"
            :conversation-search="conversationSearch"
            :conversations-count="conversationsCount"
            :conversations-loading="conversationsLoading"
            :editing-conversation-id="editingConversationId"
            :editing-title="editingTitle"
            :grouped-conversations="groupedConversations"
            @start-new-chat="emit('newChat')"
            @update:conversation-search="
              emit('update:conversationSearch', $event)
            "
            @select-conversation="emit('selectConversation', $event)"
            @delete-conversation="emit('deleteConversation', $event)"
            @start-edit-title="emit('startEditTitle', $event)"
            @update:editing-title="emit('update:editingTitle', $event)"
            @commit-edit-title="emit('commitEditTitle')"
            @cancel-edit-title="emit('cancelEditTitle')"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ai-chat-history-overlay-pane {
  border-color: hsl(var(--border) / 0.5);
  background: hsl(var(--background));
  box-shadow:
    0 24px 40px -28px hsl(var(--foreground) / 0.16),
    0 0 0 1px hsl(var(--foreground) / 0.04);
}

.ai-chat-history-overlay-enter-active,
.ai-chat-history-overlay-leave-active {
  transition: opacity 0.2s ease;
}

.ai-chat-history-overlay-enter-active .ai-chat-history-overlay-pane,
.ai-chat-history-overlay-leave-active .ai-chat-history-overlay-pane {
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}

.ai-chat-history-overlay-enter-from,
.ai-chat-history-overlay-leave-to {
  opacity: 0;
}

.ai-chat-history-overlay-enter-from .ai-chat-history-overlay-pane,
.ai-chat-history-overlay-leave-to .ai-chat-history-overlay-pane {
  opacity: 0;
  transform: translateY(8px) scale(0.985);
}
</style>

<script lang="ts" setup>
/**
 * AI Chat Panel - Shared Component
 *
 * Supports two modes:
 * - 'page': Full page layout with agent sidebar + conversation history + chat area
 * - 'drawer': Compact layout with agent dropdown + inline history toggle
 *
 * Used by both /admin/ai/chat page and the global AI assistant drawer.
 */
import type { AIChatPanelProps } from './types';

defineOptions({ name: 'AIChatPanel', inheritAttrs: false });

import { computed, onMounted, onUnmounted, ref, toRef, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Input,
  Modal,
  Select,
  Spin,
  Tooltip,
  message,
} from 'ant-design-vue';

import { KbMentionSelector } from '#/components/business/kb-mention-selector';
import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

import ChatMessageItem from './ChatMessageItem.vue';
import { useAIChat } from './use-ai-chat';

const props = withDefaults(defineProps<AIChatPanelProps>(), {
  showKbSelector: false,
  showAttachments: true,
  i18nPrefix: 'common.globalAiChat',
  welcomeMessage: '',
  suggestedQuestions: () => [],
});

const emit = defineEmits<{
  /** Emitted when the selected agent changes */
  'agent-change': [agentId: number];
}>();

const chat = useAIChat({
  apiPrefix: toRef(props, 'apiPrefix'),
  uploadUrl: toRef(props, 'uploadUrl'),
  initialAgentId: toRef(props, 'initialAgentId'),
  onToolCall: props.onToolCall,
  onStreamComplete: props.onStreamComplete,
});

const {
  agents,
  agentsLoading,
  selectedAgentId,
  selectedAgent,
  loadAgents,
  selectAgent,
  conversations,
  conversationsLoading,
  activeConversationId,
  loadConversations,
  startNewConversation,
  deleteConversation,
  loadConversationMessages,
  chatMessages,
  inputMessage,
  selectedKBIds,
  sending,
  streaming,
  messagesContainer, // template ref - used via ref="messagesContainer"
  sendMessage,
  stopGeneration,
  handleMessagesScroll,
  copyMessage,
  handleInputKeyDown,
  cleanup,
  supportsVision,
  pendingAttachments,
  uploading,
  fileInput,
  chatAcceptAttribute,
  handleFileSelect,
  handlePaste,
  handleDrop,
  handleDragOver,
  removePendingAttachment,
  confirmAction,
  rejectAction,
  confirmConsent,
  rejectConsent,
  clickActionButton,
  regenerateMessage,
  editAndResend,
  exportAsMarkdown,
  totalTokensUsed,
} = chat;

// Template ref bindings (used via ref="..." in template)
void messagesContainer;
void fileInput;
void handleMessagesScroll;
void supportsVision;

/**
 * Effective welcome message: props override > agent's welcome_message > default
 */
const effectiveWelcomeMessage = computed(() => {
  if (props.welcomeMessage) return props.welcomeMessage;
  return selectedAgent.value?.welcome_message || '';
});

/**
 * Effective suggested questions: props override > agent's suggested_questions
 */
const effectiveSuggestedQuestions = computed<string[]>(() => {
  if (props.suggestedQuestions.length > 0) return props.suggestedQuestions;
  const raw = selectedAgent.value?.suggested_questions;
  if (!Array.isArray(raw)) return [];
  return raw.filter((q): q is string => typeof q === 'string' && q.trim() !== '');
});

/** Click a suggested question: fill + send */
function askSuggested(question: string) {
  inputMessage.value = question;
  sendMessage();
}

// ============ Conversation search ============

const conversationSearch = ref('');

const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase();
  if (!keyword) return conversations.value;
  return conversations.value.filter(
    (c) => (c.title || '').toLowerCase().includes(keyword),
  );
});

// ============ Image preview lightbox ============

const previewImageUrl = ref('');
const previewImageVisible = ref(false);

function openImagePreview(url: string) {
  previewImageUrl.value = url;
  previewImageVisible.value = true;
}

// ============ Drawer mode: history toggle ============

const showHistory = ref(false);

function toggleHistory() {
  showHistory.value = !showHistory.value;
}

function onStartNewChat() {
  startNewConversation();
  showHistory.value = false;
}

defineExpose({
  showHistory,
  toggleHistory,
  onStartNewChat,
  loadAgents,
  loadConversations,
  selectedAgentId,
});

function onSelectConversation(convId: number) {
  loadConversationMessages(convId);
  showHistory.value = false;
}

function onDeleteConversation(convId: number) {
  Modal.confirm({
    title: $t('common.globalAiChat.confirmDelete'),
    onOk: () => deleteConversation(convId),
  });
}

async function onCopyMessage(content: string) {
  await copyMessage(content);
  message.success($t('common.globalAiChat.copySuccess'));
}

// ============ Avatar helper ============

function agentAvatar(agent: { avatar?: string | null; name: string }) {
  return agent.avatar || null;
}

function agentInitial(agent: { name: string }) {
  return agent.name.charAt(0).toUpperCase();
}

// ============ Lifecycle ============

watch(selectedAgentId, (id) => {
  loadConversations();
  if (id != null) {
    emit('agent-change', id);
  }
});

onMounted(() => {
  loadAgents();
});

onUnmounted(() => {
  cleanup();
});
</script>

<template>
  <!-- ==================== PAGE MODE ==================== -->
  <template v-if="props.mode === 'page'">
    <div class="flex h-full gap-4">
      <!-- Left sidebar: Agent list + Conversations -->
      <Card
        class="w-72 shrink-0 overflow-y-auto"
        :body-style="{ padding: '12px' }"
      >
        <!-- Agent list -->
        <div class="mb-3 text-sm font-medium text-foreground">
          {{ $t('common.globalAiChat.selectAgent') }}
        </div>

        <Spin :spinning="agentsLoading">
          <div
            v-if="agents.length === 0 && !agentsLoading"
            class="py-4 text-center text-sm text-muted-foreground"
          >
            {{ $t('common.globalAiChat.noAgents') }}
          </div>
          <div class="space-y-1.5">
            <div
              v-for="agent in agents"
              :key="agent.id"
              class="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors"
              :class="
                selectedAgentId === agent.id
                  ? 'bg-primary/10 text-primary'
                  : 'hover:bg-accent text-foreground'
              "
              @click="selectAgent(agent.id)"
            >
              <!-- Agent avatar -->
              <div
                class="flex size-8 shrink-0 items-center justify-center rounded-lg text-sm font-medium"
                :class="
                  selectedAgentId === agent.id
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-accent text-muted-foreground'
                "
              >
                <img
                  v-if="agentAvatar(agent)"
                  :src="agentAvatar(agent)!"
                  :alt="agent.name"
                  class="size-full rounded-lg object-cover"
                />
                <span v-else>{{ agentInitial(agent) }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate font-medium">{{ agent.name }}</div>
                <div
                  v-if="agent.description"
                  class="truncate text-xs text-muted-foreground"
                >
                  {{ agent.description }}
                </div>
                <div
                  v-else-if="agent.model_name"
                  class="truncate text-xs text-muted-foreground"
                >
                  {{ agent.model_name }}
                </div>
              </div>
            </div>
          </div>
        </Spin>

        <!-- Divider -->
        <div class="my-3 border-t border-border" />

        <!-- Conversation history -->
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium text-foreground">
            {{ $t('common.globalAiChat.history') }}
          </span>
          <Button size="small" type="text" @click="startNewConversation">
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-3.5" />
            </template>
            {{ $t('common.globalAiChat.newChat') }}
          </Button>
        </div>

        <Input
          v-if="conversations.length > 3"
          v-model:value="conversationSearch"
          :placeholder="$t('common.globalAiChat.searchHistory')"
          size="small"
          allow-clear
          class="mb-2"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="size-3 text-muted-foreground" />
          </template>
        </Input>

        <Spin :spinning="conversationsLoading">
          <div
            v-if="filteredConversations.length === 0 && !conversationsLoading"
            class="py-4 text-center text-sm text-muted-foreground"
          >
            {{ $t('common.globalAiChat.noHistory') }}
          </div>
          <div class="space-y-1">
            <div
              v-for="conv in filteredConversations"
              :key="conv.id"
              class="group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors"
              :class="
                activeConversationId === conv.id
                  ? 'bg-accent text-foreground font-medium'
                  : 'text-muted-foreground hover:bg-accent/50'
              "
              @click="loadConversationMessages(conv.id)"
            >
              <span class="truncate">
                {{ conv.title || `#${conv.id}` }}
              </span>
              <Tooltip :title="$t('common.globalAiChat.deleteConversation')">
                <IconifyIcon
                  icon="lucide:trash-2"
                  class="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  @click.stop="onDeleteConversation(conv.id)"
                />
              </Tooltip>
            </div>
          </div>
        </Spin>
      </Card>

      <!-- Right: Chat area -->
      <Card
        class="flex flex-1 flex-col overflow-hidden"
        :body-style="{
          padding: '0',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
        }"
      >
        <!-- Header: Current agent info -->
        <div
          v-if="selectedAgent"
          class="flex items-center gap-3 border-b border-border px-4 py-3"
        >
          <div
            class="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-sm font-medium text-primary"
          >
            <img
              v-if="agentAvatar(selectedAgent)"
              :src="agentAvatar(selectedAgent)!"
              :alt="selectedAgent.name"
              class="size-full rounded-lg object-cover"
            />
            <span v-else>{{ agentInitial(selectedAgent) }}</span>
          </div>
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ selectedAgent.name }}
            </div>
            <div
              v-if="selectedAgent.model_name"
              class="max-w-md truncate text-xs text-muted-foreground"
            >
              {{ selectedAgent.model_name }}
            </div>
          </div>
        </div>

        <!-- Messages -->
        <div
          ref="messagesContainer"
          class="flex-1 overflow-y-auto px-4 py-4"
          @scroll="handleMessagesScroll"
        >
          <!-- Empty state -->
          <div
            v-if="chatMessages.length === 0 && !sending"
            class="flex h-full items-center justify-center"
          >
            <div class="max-w-md text-center">
              <div
                class="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-lg font-semibold text-primary"
              >
                <img
                  v-if="selectedAgent && agentAvatar(selectedAgent)"
                  :src="agentAvatar(selectedAgent)!"
                  :alt="selectedAgent.name"
                  class="size-full rounded-2xl object-cover"
                />
                <span v-else-if="selectedAgent">{{ agentInitial(selectedAgent) }}</span>
                <IconifyIcon
                  v-else
                  icon="lucide:bot"
                  class="size-7 text-primary"
                />
              </div>
              <div class="text-base font-medium text-foreground">
                {{ effectiveWelcomeMessage || $t('common.globalAiChat.welcomeTitle') }}
              </div>
              <div v-if="!effectiveWelcomeMessage" class="mt-1 text-sm text-muted-foreground">
                {{ $t('common.globalAiChat.welcomeDesc') }}
              </div>
              <!-- Suggested questions -->
              <div
                v-if="effectiveSuggestedQuestions.length > 0"
                class="mt-5 flex flex-wrap justify-center gap-2"
              >
                <Button
                  v-for="(q, qi) in effectiveSuggestedQuestions"
                  :key="qi"
                  size="small"
                  class="max-w-[220px] truncate"
                  @click="askSuggested(q)"
                >
                  {{ q }}
                </Button>
              </div>
            </div>
          </div>

          <!-- Message list -->
          <div class="space-y-4">
            <ChatMessageItem
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              :msg="msg"
              :index="idx"
              :selected-agent="selectedAgent"
              @copy="onCopyMessage"
              @confirm="confirmAction"
              @reject="rejectAction"
              @consent-confirm="confirmConsent"
              @consent-reject="rejectConsent"
              @open-url="openImagePreview"
              @action-click="clickActionButton"
              @regenerate="regenerateMessage"
              @edit="editAndResend"
            />
          </div>
        </div>

        <!-- Token usage indicator -->
        <div
          v-if="totalTokensUsed > 0 && !streaming"
          class="flex items-center justify-center gap-1.5 border-t border-border/50 px-4 py-1 text-[11px] text-muted-foreground"
        >
          <IconifyIcon icon="lucide:activity" class="size-3" />
          <span>{{ chatMessages.length }} {{ $t('common.globalAiChat.messages') }} · {{ totalTokensUsed.toLocaleString() }} {{ $t('common.globalAiChat.tokens') }}</span>
          <span class="text-border">|</span>
          <button class="hover:text-foreground" @click="exportAsMarkdown">
            <IconifyIcon icon="lucide:download" class="size-3" />
          </button>
        </div>

        <!-- Input area -->
        <div
          class="border-t border-border px-4 py-3"
          @dragover="handleDragOver"
          @drop="handleDrop"
        >
          <!-- Stop button -->
          <div v-if="streaming" class="mb-2 flex justify-center">
            <Button size="small" danger @click="stopGeneration">
              <template #icon>
                <IconifyIcon icon="lucide:square" class="size-3.5" />
              </template>
              {{ $t('common.globalAiChat.stop') }}
            </Button>
          </div>

          <!-- Pending attachments preview -->
          <TransitionGroup
            v-if="props.showAttachments && pendingAttachments.length > 0"
            name="att-pop"
            tag="div"
            class="mb-2 flex flex-wrap gap-2"
          >
            <div
              v-for="(att, ai) in pendingAttachments"
              :key="att.url || ai"
              class="group relative"
            >
              <div
                v-if="att.type === 'image'"
                class="relative size-16 overflow-hidden rounded-lg border border-border"
              >
                <img
                  :src="att.preview || att.url"
                  :alt="att.name || ''"
                  class="size-full object-cover"
                />
                <button
                  class="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
                  @click="removePendingAttachment(ai)"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                </button>
              </div>
              <div
                v-else
                class="flex items-center gap-1.5 rounded-lg border border-border bg-accent/50 px-2 py-1.5"
              >
                <IconifyIcon
                  :icon="getFileIcon(att.name || '', att.mime_type)"
                  class="size-4 text-muted-foreground"
                />
                <span
                  class="max-w-[120px] truncate text-xs text-foreground"
                >
                  {{ att.name }}
                </span>
                <button
                  class="flex size-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
                  @click="removePendingAttachment(ai)"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                </button>
              </div>
            </div>
            <div
              v-if="uploading"
              class="flex size-16 items-center justify-center rounded-lg border border-dashed border-border"
            >
              <Spin size="small" />
            </div>
          </TransitionGroup>

          <!-- KB mention selector -->
          <KbMentionSelector
            v-if="props.showKbSelector && props.fetchKbApi"
            v-model:selected-ids="selectedKBIds"
            :fetch-api="props.fetchKbApi"
            class="mb-2"
          />

          <!-- Input row -->
          <div class="flex gap-2">
            <Tooltip
              v-if="props.showAttachments"
              :title="$t('common.globalAiChat.addAttachment')"
            >
              <Button
                :disabled="!selectedAgentId || sending"
                @click="fileInput?.click()"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:paperclip" class="size-4" />
                </template>
              </Button>
            </Tooltip>
            <input
              ref="fileInput"
              type="file"
              multiple
              :accept="chatAcceptAttribute"
              class="hidden"
              @change="handleFileSelect"
            />
            <Input.TextArea
              v-model:value="inputMessage"
              :placeholder="$t('common.globalAiChat.inputPlaceholder')"
              :auto-size="{ minRows: 1, maxRows: 4 }"
              :disabled="!selectedAgentId || sending"
              class="flex-1"
              @keydown="handleInputKeyDown"
              @paste="handlePaste"
            />
            <Button
              type="primary"
              :disabled="
                (!inputMessage.trim() && pendingAttachments.length === 0) ||
                !selectedAgentId ||
                sending
              "
              :loading="sending"
              @click="() => sendMessage()"
            >
              <template #icon>
                <IconifyIcon icon="lucide:send" class="size-3.5" />
              </template>
            </Button>
          </div>
        </div>
      </Card>
    </div>
  </template>

  <!-- ==================== DRAWER MODE ==================== -->
  <template v-else>
    <div class="flex h-full flex-col overflow-hidden">
      <!-- Agent selector bar -->
      <div class="shrink-0 border-b border-border px-3 py-2">
        <Select
          :value="selectedAgentId ?? undefined"
          :loading="agentsLoading"
          :placeholder="$t('common.globalAiChat.selectAgent')"
          class="w-full"
          size="small"
          @change="(v: unknown) => selectAgent(v as number)"
        >
          <Select.Option
            v-for="agent in agents"
            :key="agent.id"
            :value="agent.id"
          >
            <div class="flex items-center gap-2">
              <div
                class="flex size-5 shrink-0 items-center justify-center rounded text-[10px] font-medium"
                :class="
                  agentAvatar(agent)
                    ? ''
                    : 'bg-primary/10 text-primary'
                "
              >
                <img
                  v-if="agentAvatar(agent)"
                  :src="agentAvatar(agent)!"
                  :alt="agent.name"
                  class="size-full rounded object-cover"
                />
                <span v-else>{{ agentInitial(agent) }}</span>
              </div>
              <span>{{ agent.name }}</span>
            </div>
          </Select.Option>
        </Select>
        <!-- Agent description + model name -->
        <div
          v-if="selectedAgent && (selectedAgent.description || selectedAgent.model_name)"
          class="mt-1.5 space-y-0.5 px-0.5"
        >
          <div
            v-if="selectedAgent.description"
            class="truncate text-[11px] text-muted-foreground"
            :title="selectedAgent.description"
          >
            {{ selectedAgent.description }}
          </div>
          <div
            v-if="selectedAgent.model_name"
            class="truncate text-[11px] text-muted-foreground/60"
          >
            {{ selectedAgent.model_name }}
          </div>
        </div>
      </div>

      <!-- History panel (overlay) -->
      <div v-if="showHistory" class="flex-1 overflow-y-auto px-3 py-2">
        <Spin :spinning="conversationsLoading">
          <div
            v-if="conversations.length === 0 && !conversationsLoading"
            class="py-6 text-center text-sm text-muted-foreground"
          >
            {{ $t('common.globalAiChat.noHistory') }}
          </div>
          <div class="space-y-1">
            <div
              v-for="conv in conversations"
              :key="conv.id"
              class="group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors"
              :class="
                activeConversationId === conv.id
                  ? 'bg-accent font-medium'
                  : 'hover:bg-accent/50 text-muted-foreground'
              "
              @click="onSelectConversation(conv.id)"
            >
              <span class="truncate">
                {{ conv.title || `#${conv.id}` }}
              </span>
              <IconifyIcon
                icon="lucide:trash-2"
                class="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                @click.stop="onDeleteConversation(conv.id)"
              />
            </div>
          </div>
        </Spin>
      </div>

      <!-- Chat area (when not showing history) -->
      <template v-if="!showHistory">
        <!-- Messages -->
        <div
          ref="messagesContainer"
          class="flex-1 overflow-y-auto px-3 py-3"
          @scroll="handleMessagesScroll"
        >
          <!-- Empty state -->
          <div
            v-if="chatMessages.length === 0 && !sending"
            class="flex h-full items-center justify-center"
          >
            <div class="max-w-xs text-center">
              <div
                v-if="selectedAgent"
                class="mx-auto mb-2 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-sm font-medium text-primary"
              >
                <img
                  v-if="agentAvatar(selectedAgent)"
                  :src="agentAvatar(selectedAgent)!"
                  :alt="selectedAgent.name"
                  class="size-full rounded-xl object-cover"
                />
                <span v-else>{{ agentInitial(selectedAgent) }}</span>
              </div>
              <IconifyIcon
                v-else
                icon="lucide:bot"
                class="mx-auto mb-2 size-10 text-primary/30"
              />
              <div class="text-sm font-medium text-foreground">
                {{ effectiveWelcomeMessage || $t('common.globalAiChat.welcomeDesc') }}
              </div>
              <div
                v-if="selectedAgent?.description && !effectiveWelcomeMessage"
                class="mt-1 text-xs text-muted-foreground"
              >
                {{ selectedAgent.description }}
              </div>
              <!-- Suggested questions (drawer) -->
              <div
                v-if="effectiveSuggestedQuestions.length > 0"
                class="mt-3 flex flex-wrap justify-center gap-1.5"
              >
                <Button
                  v-for="(q, qi) in effectiveSuggestedQuestions"
                  :key="qi"
                  size="small"
                  class="max-w-[180px] truncate !text-xs"
                  @click="askSuggested(q)"
                >
                  {{ q }}
                </Button>
              </div>
            </div>
          </div>

          <!-- Message list -->
          <div class="space-y-3">
            <ChatMessageItem
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              :msg="msg"
              :index="idx"
              compact
              @copy="onCopyMessage"
              @confirm="confirmAction"
              @reject="rejectAction"
              @consent-confirm="confirmConsent"
              @consent-reject="rejectConsent"
              @open-url="openImagePreview"
              @action-click="clickActionButton"
              @regenerate="regenerateMessage"
              @edit="editAndResend"
            />
          </div>
        </div>

        <!-- Input area -->
        <div
          class="shrink-0 border-t border-border px-3 py-2"
          @dragover="handleDragOver"
          @drop="handleDrop"
        >
          <div v-if="streaming" class="mb-1.5 flex justify-center">
            <Button size="small" danger @click="stopGeneration">
              <template #icon>
                <IconifyIcon icon="lucide:square" class="size-3" />
              </template>
              {{ $t('common.globalAiChat.stop') }}
            </Button>
          </div>
          <!-- Pending attachments -->
          <TransitionGroup
            v-if="props.showAttachments && pendingAttachments.length > 0"
            name="att-pop"
            tag="div"
            class="mb-1.5 flex flex-wrap gap-1.5"
          >
            <div
              v-for="(att, ai) in pendingAttachments"
              :key="att.url || ai"
              class="group relative"
            >
              <div
                v-if="att.type === 'image'"
                class="relative size-12 overflow-hidden rounded border border-border"
              >
                <img
                  :src="att.preview || att.url"
                  class="size-full object-cover"
                />
                <button
                  class="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
                  @click="removePendingAttachment(ai)"
                >
                  <IconifyIcon icon="lucide:x" class="size-2.5" />
                </button>
              </div>
              <div
                v-else
                class="flex items-center gap-1 rounded border border-border bg-accent/50 px-1.5 py-1"
              >
                <IconifyIcon
                  :icon="getFileIcon(att.name || '', att.mime_type)"
                  class="size-3.5 shrink-0 text-muted-foreground"
                />
                <span
                  class="max-w-[80px] truncate text-[11px] text-foreground"
                >
                  {{ att.name }}
                </span>
                <button
                  class="flex size-3.5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
                  @click="removePendingAttachment(ai)"
                >
                  <IconifyIcon icon="lucide:x" class="size-2.5" />
                </button>
              </div>
            </div>
          </TransitionGroup>
          <!-- KB mention selector (drawer) -->
          <KbMentionSelector
            v-if="props.showKbSelector && props.fetchKbApi"
            v-model:selected-ids="selectedKBIds"
            :fetch-api="props.fetchKbApi"
            class="mb-1.5"
          />

          <div class="flex gap-2">
            <Tooltip
              v-if="props.showAttachments"
              :title="$t('common.globalAiChat.addAttachment')"
            >
              <Button
                size="small"
                :disabled="!selectedAgentId || sending"
                @click="fileInput?.click()"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:paperclip" class="size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <input
              ref="fileInput"
              type="file"
              multiple
              :accept="chatAcceptAttribute"
              class="hidden"
              @change="handleFileSelect"
            />
            <Input.TextArea
              v-model:value="inputMessage"
              :placeholder="$t('common.globalAiChat.inputPlaceholder')"
              :auto-size="{ minRows: 1, maxRows: 3 }"
              :disabled="!selectedAgentId || sending"
              class="flex-1 !text-sm"
              @keydown="handleInputKeyDown"
              @paste="handlePaste"
            />
            <Button
              type="primary"
              size="small"
              :disabled="
                (!inputMessage.trim() && pendingAttachments.length === 0) ||
                !selectedAgentId ||
                sending
              "
              :loading="sending"
              @click="() => sendMessage()"
            >
              <template #icon>
                <IconifyIcon icon="lucide:send" class="size-3.5" />
              </template>
            </Button>
          </div>
        </div>
      </template>
    </div>
  </template>

  <!-- Image preview lightbox -->
  <Modal
    v-model:open="previewImageVisible"
    :footer="null"
    :width="'auto'"
    :style="{ maxWidth: '90vw' }"
    centered
    destroy-on-close
  >
    <img
      :src="previewImageUrl"
      alt=""
      class="max-h-[80vh] max-w-full object-contain"
    />
  </Modal>
</template>

<style scoped>
.att-pop-enter-active {
  animation: att-in 0.25s ease-out;
}
.att-pop-leave-active {
  animation: att-in 0.15s ease-in reverse;
}
@keyframes att-in {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
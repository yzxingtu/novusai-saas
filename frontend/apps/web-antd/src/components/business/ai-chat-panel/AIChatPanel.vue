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
import { toAvatarDisplayUrl } from '#/utils/image';

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

interface ConversationGroup {
  label: string;
  items: typeof conversations.value;
}

const groupedConversations = computed<ConversationGroup[]>(() => {
  const list = filteredConversations.value;
  if (list.length === 0) return [];

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;

  const today: typeof list = [];
  const yesterday: typeof list = [];
  const earlier: typeof list = [];

  for (const c of list) {
    const t = new Date(c.created_at).getTime();
    if (t >= todayStart) today.push(c);
    else if (t >= yesterdayStart) yesterday.push(c);
    else earlier.push(c);
  }

  const groups: ConversationGroup[] = [];
  if (today.length) groups.push({ label: $t('common.globalAiChat.today'), items: today });
  if (yesterday.length) groups.push({ label: $t('common.globalAiChat.yesterday'), items: yesterday });
  if (earlier.length) groups.push({ label: $t('common.globalAiChat.earlier'), items: earlier });
  return groups;
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
  return agent.avatar ? toAvatarDisplayUrl(agent.avatar) : null;
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
      <div class="flex w-72 shrink-0 flex-col overflow-hidden rounded-2xl border border-border/50 bg-card">
        <div class="flex-1 overflow-y-auto p-3">
          <!-- Agent list -->
          <div class="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {{ $t('common.globalAiChat.selectAgent') }}
          </div>

          <Spin :spinning="agentsLoading">
            <div
              v-if="agents.length === 0 && !agentsLoading"
              class="py-6 text-center text-sm text-muted-foreground"
            >
              {{ $t('common.globalAiChat.noAgents') }}
            </div>
            <div class="space-y-1">
              <div
                v-for="agent in agents"
                :key="agent.id"
                class="flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-all duration-200"
                :class="
                  selectedAgentId === agent.id
                    ? 'bg-primary/10 text-primary shadow-sm'
                    : 'hover:bg-muted text-foreground'
                "
                @click="selectAgent(agent.id)"
              >
                <div
                  class="flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-medium shadow-sm"
                  :class="
                    selectedAgentId === agent.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground'
                  "
                >
                  <img
                    v-if="agentAvatar(agent)"
                    :src="agentAvatar(agent)!"
                    :alt="agent.name"
                    class="size-full rounded-xl object-cover"
                  />
                  <span v-else>{{ agentInitial(agent) }}</span>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="truncate font-medium">{{ agent.name }}</div>
                  <div
                    v-if="agent.description"
                    class="truncate text-xs text-muted-foreground/70"
                  >
                    {{ agent.description }}
                  </div>
                  <div
                    v-else-if="agent.model_name"
                    class="truncate text-xs text-muted-foreground/70"
                  >
                    {{ agent.model_name }}
                  </div>
                </div>
              </div>
            </div>
          </Spin>

          <!-- Divider -->
          <div class="my-3 border-t border-border/40" />

          <!-- Conversation history -->
          <div class="mb-2 flex items-center justify-between px-1">
            <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {{ $t('common.globalAiChat.history') }}
            </span>
            <button
              class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-primary transition-colors hover:bg-primary/10"
              @click="startNewConversation"
            >
              <IconifyIcon icon="lucide:plus" class="size-3" />
              {{ $t('common.globalAiChat.newChat') }}
            </button>
          </div>

          <Input
            v-if="conversations.length > 3"
            v-model:value="conversationSearch"
            :placeholder="$t('common.globalAiChat.searchHistory')"
            size="small"
            allow-clear
            class="mb-2 !rounded-lg"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="size-3 text-muted-foreground" />
            </template>
          </Input>

          <Spin :spinning="conversationsLoading">
            <div
              v-if="groupedConversations.length === 0 && !conversationsLoading"
              class="py-6 text-center text-sm text-muted-foreground"
            >
              {{ $t('common.globalAiChat.noHistory') }}
            </div>
            <div v-for="group in groupedConversations" :key="group.label" class="mb-2">
              <div class="mb-1 px-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                {{ group.label }}
              </div>
              <div class="space-y-0.5">
                <div
                  v-for="conv in group.items"
                  :key="conv.id"
                  class="group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition-all duration-150"
                  :class="
                    activeConversationId === conv.id
                      ? 'bg-accent text-foreground font-medium'
                      : 'text-muted-foreground hover:bg-accent/50'
                  "
                  @click="loadConversationMessages(conv.id)"
                >
                  <div class="flex min-w-0 items-center gap-2">
                    <IconifyIcon icon="lucide:message-square" class="size-3.5 shrink-0 opacity-50" />
                    <span class="truncate">
                      {{ conv.title || `#${conv.id}` }}
                    </span>
                  </div>
                  <Tooltip :title="$t('common.globalAiChat.deleteConversation')">
                    <IconifyIcon
                      icon="lucide:trash-2"
                      class="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                      @click.stop="onDeleteConversation(conv.id)"
                    />
                  </Tooltip>
                </div>
              </div>
            </div>
          </Spin>
        </div>
      </div>

      <!-- Right: Chat area -->
      <div class="flex flex-1 flex-col overflow-hidden rounded-2xl border border-border/50 bg-card">
        <!-- Header: Current agent info -->
        <div
          v-if="selectedAgent"
          class="flex items-center justify-between border-b border-border/40 px-5 py-3"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 text-sm font-medium text-primary shadow-sm"
            >
              <img
                v-if="agentAvatar(selectedAgent)"
                :src="agentAvatar(selectedAgent)!"
                :alt="selectedAgent.name"
                class="size-full rounded-xl object-cover"
              />
              <span v-else>{{ agentInitial(selectedAgent) }}</span>
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ selectedAgent.name }}
              </div>
              <div
                v-if="selectedAgent.model_name"
                class="max-w-md truncate text-xs text-muted-foreground/70"
              >
                {{ selectedAgent.model_name }}
              </div>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <Tooltip :title="$t('common.globalAiChat.newChat')">
              <button
                class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                @click="startNewConversation"
              >
                <IconifyIcon icon="lucide:plus" class="size-4" />
              </button>
            </Tooltip>
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
            <div class="max-w-lg text-center">
              <div
                class="mx-auto mb-5 flex size-20 animate-float items-center justify-center rounded-3xl bg-gradient-to-br from-primary/20 to-primary/5 text-xl font-semibold text-primary shadow-xl shadow-primary/10 ring-1 ring-primary/10"
              >
                <img
                  v-if="selectedAgent && agentAvatar(selectedAgent)"
                  :src="agentAvatar(selectedAgent)!"
                  :alt="selectedAgent.name"
                  class="size-full rounded-3xl object-cover"
                />
                <span v-else-if="selectedAgent">{{ agentInitial(selectedAgent) }}</span>
                <IconifyIcon
                  v-else
                  icon="lucide:sparkles"
                  class="size-8 text-primary"
                />
              </div>
              <div class="text-xl font-semibold text-foreground">
                {{ effectiveWelcomeMessage || $t('common.globalAiChat.welcomeTitle') }}
              </div>
              <div v-if="!effectiveWelcomeMessage" class="mt-2 text-sm text-muted-foreground">
                {{ $t('common.globalAiChat.welcomeDesc') }}
              </div>
              <!-- Suggested questions -->
              <div
                v-if="effectiveSuggestedQuestions.length > 0"
                class="mt-8 grid gap-2"
                :class="effectiveSuggestedQuestions.length <= 2 ? 'grid-cols-1 mx-auto max-w-sm' : 'grid-cols-2'"
              >
                <button
                  v-for="(q, qi) in effectiveSuggestedQuestions"
                  :key="qi"
                  class="flex items-center gap-2.5 rounded-xl border border-border/50 bg-card px-4 py-3 text-left text-sm text-foreground shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
                  @click="askSuggested(q)"
                >
                  <IconifyIcon icon="lucide:message-circle" class="size-4 shrink-0 text-primary/60" />
                  <span class="line-clamp-2">{{ q }}</span>
                </button>
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
          class="border-t border-border/30 px-5 py-3"
          @dragover="handleDragOver"
          @drop="handleDrop"
        >
          <!-- Stop button -->
          <div v-if="streaming" class="mb-2 flex justify-center">
            <button
              class="flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/5 px-4 py-1.5 text-xs font-medium text-destructive shadow-sm transition-all hover:bg-destructive/15 hover:shadow-md"
              @click="stopGeneration"
            >
              <IconifyIcon icon="lucide:square" class="size-3" />
              {{ $t('common.globalAiChat.stop') }}
            </button>
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
          <div class="flex items-end gap-2 rounded-2xl border border-border/40 bg-muted/20 px-3 py-2 transition-colors focus-within:border-primary/40 focus-within:bg-background">
            <Tooltip
              v-if="props.showAttachments"
              :title="$t('common.globalAiChat.addAttachment')"
            >
              <button
                class="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                :disabled="!selectedAgentId || sending"
                @click="fileInput?.click()"
              >
                <IconifyIcon icon="lucide:paperclip" class="size-4" />
              </button>
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
              class="flex-1 !border-0 !bg-transparent !shadow-none !outline-none !ring-0"
              @keydown="handleInputKeyDown"
              @paste="handlePaste"
            />
            <button
              class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition-all hover:shadow-md disabled:opacity-40"
              :disabled="
                (!inputMessage.trim() && pendingAttachments.length === 0) ||
                !selectedAgentId ||
                sending
              "
              @click="() => sendMessage()"
            >
              <Spin v-if="sending" size="small" />
              <IconifyIcon v-else icon="lucide:arrow-up" class="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </template>

  <!-- ==================== DRAWER MODE ==================== -->
  <template v-else>
    <div class="flex h-full flex-col overflow-hidden">
      <!-- Agent selector bar -->
      <div class="shrink-0 border-b border-border/40 bg-muted/20 px-3 py-2.5">
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
                class="flex size-5 shrink-0 items-center justify-center rounded-md text-[10px] font-medium"
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
                  class="size-full rounded-md object-cover"
                />
                <span v-else>{{ agentInitial(agent) }}</span>
              </div>
              <span>{{ agent.name }}</span>
            </div>
          </Select.Option>
        </Select>
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
            class="flex items-center gap-1 truncate text-[11px] text-muted-foreground/60"
          >
            <IconifyIcon icon="lucide:cpu" class="size-2.5" />
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
                class="mx-auto mb-3 flex size-12 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 text-sm font-medium text-primary shadow-md shadow-primary/10"
              >
                <img
                  v-if="agentAvatar(selectedAgent)"
                  :src="agentAvatar(selectedAgent)!"
                  :alt="selectedAgent.name"
                  class="size-full rounded-2xl object-cover"
                />
                <span v-else>{{ agentInitial(selectedAgent) }}</span>
              </div>
              <div
                v-else
                class="mx-auto mb-3 flex size-12 items-center justify-center rounded-2xl bg-muted"
              >
                <IconifyIcon icon="lucide:sparkles" class="size-6 text-muted-foreground/40" />
              </div>
              <div class="text-sm font-semibold text-foreground">
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
                class="mt-4 flex flex-wrap justify-center gap-1.5"
              >
                <button
                  v-for="(q, qi) in effectiveSuggestedQuestions"
                  :key="qi"
                  class="max-w-[180px] truncate rounded-full border border-border/60 px-3 py-1.5 text-xs text-foreground transition-all hover:border-primary/30 hover:shadow-sm"
                  @click="askSuggested(q)"
                >
                  {{ q }}
                </button>
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

          <div class="flex items-end gap-1.5 rounded-xl border border-border/40 bg-muted/20 px-2 py-1.5 transition-colors focus-within:border-primary/40 focus-within:bg-background">
            <Tooltip
              v-if="props.showAttachments"
              :title="$t('common.globalAiChat.addAttachment')"
            >
              <button
                class="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                :disabled="!selectedAgentId || sending"
                @click="fileInput?.click()"
              >
                <IconifyIcon icon="lucide:paperclip" class="size-3.5" />
              </button>
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
              class="flex-1 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
              @keydown="handleInputKeyDown"
              @paste="handlePaste"
            />
            <button
              class="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition-all hover:shadow-md disabled:opacity-40"
              :disabled="
                (!inputMessage.trim() && pendingAttachments.length === 0) ||
                !selectedAgentId ||
                sending
              "
              @click="() => sendMessage()"
            >
              <Spin v-if="sending" size="small" />
              <IconifyIcon v-else icon="lucide:arrow-up" class="size-3.5" />
            </button>
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

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-6px);
  }
}

.animate-float {
  animation: float 3s ease-in-out infinite;
}
</style>
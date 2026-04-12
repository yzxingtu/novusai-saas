<script lang="ts" setup>
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Dropdown, Input, Menu, Modal, Spin, Tooltip } from 'ant-design-vue';

import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { formatKnowledgeBaseName } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

import { useUserAIChatContext } from './ai-chat-context';

const {
  apiPrefix,
  chat,
  mobileSidebarOpen,
  showWorkspaceHero,
  chatHeaderSubtitle,
  selectedAgentHasVariables,
  selectedAgentVarsConfigured,
  showMemoryPanel,
  onToggleMemory,
  onClearMemory,
  onStartNewChat,
  openSelectedAgentVarsModal,
  effectiveWelcomeMessage,
  effectiveSuggestedQuestions,
  exportMenuItems,
} = useUserAIChatContext();

const {
  agents,
  agentsLoading,
  selectedAgent,
  activeConversationId,
  chatMessages,
  inputMessage,
  mentionOpen,
  mentionCandidates,
  mentionActiveIndex,
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
  pendingAttachments,
  uploading,
  fileInput,
  chatAcceptAttribute,
  handleFileSelect,
  handlePaste,
  handleDrop,
  handleDragOver,
  removePendingAttachment,
  selectMentionKnowledgeBase,
  removeSelectedKnowledgeBase,
  selectedKBIds,
  agentKBBindings,
  memoryState,
  memoryLoading,
  clearingMemory,
  lastMemoryUpdated,
  totalTokensUsed,
  handleInputKeyDown,
  sendMessage,
  stopGeneration,
  copyMessage,
} = chat;

const previewImageUrl = ref('');
const previewImageVisible = ref(false);

void messagesContainer;
void fileInput;
void handleMessagesScroll;
void showScrollToBottom;
void showScrollToTop;
void scrollToBottom;
void scrollToTop;

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

function handleKeyDown(e: KeyboardEvent) {
  if (handleInputKeyDown(e)) {
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    handleSendClick();
  }
}

function askSuggested(question: string) {
  inputMessage.value = question;
  handleSendClick();
}

function isAgentSwitch(idx: number): boolean {
  const msg = chatMessages.value[idx];
  if (!msg || msg.role !== 'assistant' || !msg.agent_id) return false;
  for (let i = idx - 1; i >= 0; i--) {
    const prev = chatMessages.value[i];
    if (prev?.role === 'assistant') {
      return prev.agent_id !== msg.agent_id;
    }
  }
  return false;
}
</script>

<template>
  <div class="flex flex-1 flex-col overflow-hidden">
    <!-- Chat Header -->
    <div
      class="flex shrink-0 items-start justify-between gap-3 border-b border-border/40 px-4 py-3"
    >
      <div class="flex min-w-0 items-start gap-3">
        <!-- Mobile sidebar toggle -->
        <button
          class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
          @click="openMobileSidebar"
        >
          <IconifyIcon icon="lucide:panel-left" class="size-4" />
        </button>
        <div
          v-if="!showWorkspaceHero && selectedAgent"
          class="flex min-w-0 items-center gap-3"
        >
          <div
            class="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-xs font-medium text-primary"
          >
            <img
              v-if="selectedAgent.avatar"
              :src="selectedAgent.avatar"
              :alt="selectedAgent.name"
              class="size-9 rounded-xl object-cover"
            />
            <span v-else>{{ selectedAgent.name.charAt(0).toUpperCase() }}</span>
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-foreground">
              {{ selectedAgent.name }}
            </div>
            <div
              v-if="chatHeaderSubtitle"
              class="truncate text-[11px] text-muted-foreground"
            >
              {{ chatHeaderSubtitle }}
            </div>
          </div>
        </div>
        <div v-else class="min-w-0">
          <div class="text-sm font-semibold text-foreground">
            {{ $t('user.aiChat.title') }}
          </div>
          <div
            v-if="chatHeaderSubtitle"
            class="truncate text-[11px] text-muted-foreground"
          >
            {{ chatHeaderSubtitle }}
          </div>
        </div>
      </div>

      <!-- Right actions -->
      <div class="flex shrink-0 items-center gap-1">
        <Tooltip
          v-if="selectedAgentHasVariables"
          :title="$t('user.aiChat.varsModal.editVars')"
        >
          <button
            class="flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-medium text-primary transition-colors hover:bg-primary/8"
            @click="openSelectedAgentVarsModal"
          >
            <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
            <span class="hidden sm:inline">{{
              $t('user.aiChat.varsModal.editVars')
            }}</span>
            <span
              v-if="selectedAgentVarsConfigured"
              class="size-1.5 rounded-full bg-green-500"
            ></span>
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.newChat')">
          <button
            class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </button>
        </Tooltip>
        <Tooltip
          v-if="activeConversationId"
          :title="$t('common.globalAiChat.memoryUpdated')"
        >
          <button
            class="flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-muted disabled:opacity-40"
            :class="
              showMemoryPanel
                ? 'bg-primary/10 text-primary'
                : lastMemoryUpdated
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
            "
            :disabled="clearingMemory"
            @click="onToggleMemory"
          >
            <Spin v-if="memoryLoading" size="small" />
            <IconifyIcon v-else icon="lucide:brain" class="size-4" />
          </button>
        </Tooltip>
      </div>
    </div>

    <!-- Streaming progress bar -->
    <div v-if="streaming" class="h-0.5 w-full overflow-hidden bg-primary/10">
      <div class="streaming-bar h-full bg-primary/60"></div>
    </div>

    <!-- Memory panel -->
    <Transition name="fade">
      <div
        v-if="showMemoryPanel"
        class="shrink-0 border-b border-border/30 bg-muted/5 px-4 py-3"
      >
        <div class="mb-2.5 flex items-center justify-between">
          <div class="flex items-center gap-1.5 text-xs font-medium text-foreground">
            <IconifyIcon icon="lucide:brain" class="size-3.5 text-primary" />
            {{ $t('common.globalAiChat.memoryUpdated') }}
          </div>
          <Tooltip :title="$t('common.globalAiChat.clearMemory')">
            <button
              class="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
              :disabled="clearingMemory"
              @click="onClearMemory"
            >
              <Spin v-if="clearingMemory" size="small" />
              <IconifyIcon v-else icon="lucide:eraser" class="size-3" />
              {{ $t('common.globalAiChat.clearMemory') }}
            </button>
          </Tooltip>
        </div>
        <div v-if="memoryLoading" class="py-3 text-center">
          <Spin size="small" />
        </div>
        <div
          v-else-if="
            !memoryState ||
            (memoryState.preferences.length === 0 &&
              memoryState.constraints.length === 0 &&
              memoryState.task_states.length === 0 &&
              memoryState.verified_facts.length === 0)
          "
          class="py-2 text-center text-xs text-muted-foreground"
        >
          {{ $t('common.globalAiChat.clearMemoryEmpty') }}
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="section in [
              {
                key: 'preferences',
                icon: 'lucide:heart',
                label: $t('common.globalAiChat.memoryPreferences'),
                items: memoryState.preferences,
              },
              {
                key: 'constraints',
                icon: 'lucide:shield',
                label: $t('common.globalAiChat.memoryConstraints'),
                items: memoryState.constraints,
              },
              {
                key: 'task_states',
                icon: 'lucide:list-checks',
                label: $t('common.globalAiChat.memoryTaskStates'),
                items: memoryState.task_states,
              },
              {
                key: 'verified_facts',
                icon: 'lucide:check-circle',
                label: $t('common.globalAiChat.memoryVerifiedFacts'),
                items: memoryState.verified_facts,
              },
            ].filter((s) => s.items.length > 0)"
            :key="section.key"
            class="rounded-lg bg-background/60 px-2.5 py-2"
          >
            <div
              class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground"
            >
              <IconifyIcon :icon="section.icon" class="size-3" />
              {{ section.label }}
            </div>
            <ul class="space-y-0.5 text-[11px] text-foreground/80">
              <li
                v-for="(item, ii) in section.items"
                :key="ii"
                class="flex items-start gap-1.5 pl-1"
              >
                <span
                  class="mt-1.5 size-1 shrink-0 rounded-full bg-primary/40"
                ></span>
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Messages -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto px-4 py-4 sm:px-6"
      @scroll="handleMessagesScroll"
    >
      <!-- Empty state -->
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
              v-for="(q, qi) in effectiveSuggestedQuestions"
              :key="qi"
              class="group/sq flex items-center gap-3 rounded-xl border border-border/30 bg-accent/15 px-4 py-3 text-left text-sm text-foreground transition-all hover:border-primary/30 hover:bg-accent/40 hover:shadow-sm"
              @click="askSuggested(q)"
            >
              <IconifyIcon
                icon="lucide:message-circle"
                class="size-4 shrink-0 text-primary/50 transition-colors group-hover/sq:text-primary"
              />
              <span class="flex-1 truncate">{{ q }}</span>
              <IconifyIcon
                icon="lucide:arrow-right"
                class="size-3.5 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60"
              />
            </button>
          </div>
        </div>
      </div>

      <!-- Message list -->
      <div class="mx-auto max-w-3xl space-y-3">
        <ChatMessageItem
          v-for="(msg, idx) in chatMessages"
          :key="idx"
          :msg="msg"
          :index="idx"
          :api-prefix="apiPrefix"
          :agents="agents"
          :selected-agent="selectedAgent"
          :show-agent-switch="isAgentSwitch(idx)"
          @copy="onCopyMessage"
          @confirm="confirmAction"
          @reject="rejectAction"
          @consent-confirm="confirmConsent"
          @consent-reject="rejectConsent"
          @open-url="openImagePreview"
          @action-click="clickActionButton"
          @regenerate="regenerateMessage"
          @edit="editAndResend"
          @retry="retryLastMessage"
        />
      </div>

      <!-- Floating action buttons (scroll-to-top + scroll-to-bottom) -->
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

    <!-- Token usage -->
    <div
      v-if="totalTokensUsed > 0 && !streaming"
      class="flex items-center justify-center gap-1.5 border-t border-border/50 px-4 py-1 text-[11px] text-muted-foreground"
    >
      <IconifyIcon icon="lucide:activity" class="size-3" />
      <span>
        {{ chatMessages.length }}
        {{ $t('common.globalAiChat.messages') }} ·
        {{ totalTokensUsed.toLocaleString() }}
        {{ $t('common.globalAiChat.tokens') }}
      </span>
      <span class="text-border">|</span>
      <Dropdown :trigger="['click']" placement="bottomRight">
        <button class="hover:text-foreground" type="button">
          <IconifyIcon icon="lucide:download" class="size-3" />
        </button>
        <template #overlay>
          <Menu :items="exportMenuItems" />
        </template>
      </Dropdown>
    </div>

    <!-- Input area -->
    <div
      class="shrink-0 border-t border-border px-4 py-3 sm:px-6"
      @dragover="handleDragOver"
      @drop="handleDrop"
    >
      <!-- Pending attachments -->
      <TransitionGroup
        v-if="pendingAttachments.length > 0"
        name="att-pop"
        tag="div"
        class="mb-2 flex flex-wrap gap-1.5"
      >
        <div v-for="(att, ai) in pendingAttachments" :key="att.url || ai" class="group relative">
          <div
            v-if="att.type === 'image'"
            class="relative size-14 overflow-hidden rounded-lg border border-border"
          >
            <img :src="att.preview || att.url" class="size-full object-cover" />
            <button
              class="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
              @click="removePendingAttachment(ai)"
            >
              <IconifyIcon icon="lucide:x" class="size-2.5" />
            </button>
          </div>
          <div
            v-else
            class="flex items-center gap-1.5 rounded-lg border border-border bg-accent/50 px-2 py-1.5"
          >
            <IconifyIcon
              :icon="getFileIcon(att.name || '', att.mime_type)"
              class="size-4 shrink-0 text-muted-foreground"
            />
            <span class="max-w-[100px] truncate text-xs text-foreground">
              {{ att.name }}
            </span>
            <button
              class="flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
              @click="removePendingAttachment(ai)"
            >
              <IconifyIcon icon="lucide:x" class="size-3" />
            </button>
          </div>
        </div>
        <div
          v-if="uploading"
          class="flex size-14 items-center justify-center rounded-lg border border-dashed border-border"
        >
          <Spin size="small" />
        </div>
      </TransitionGroup>
      <div
        v-if="pendingAttachments.length > 0"
        class="mb-1 text-[10px] text-muted-foreground/70"
      >
        {{
          $t('common.globalAiChat.attachmentCount', {
            count: pendingAttachments.length,
            max: 5,
          })
        }}
      </div>

      <!-- Trust session toggle -->
      <div
        v-if="chatMessages.length > 0"
        class="mb-1.5 flex items-center justify-between"
      >
        <span class="text-[11px] text-muted-foreground/40">
          {{ $t('common.globalAiChat.shiftEnterHint') }}
        </span>
      </div>

      <!-- Bound KB indicator -->
      <div
        v-if="agentKBBindings.length > 0"
        class="mb-1.5 flex flex-wrap items-center gap-1"
      >
        <IconifyIcon
          icon="lucide:book-open"
          class="size-3 shrink-0 text-muted-foreground/50"
        />
        <span
          v-for="kb in agentKBBindings"
          :key="kb.knowledge_base_id"
          class="inline-flex items-center rounded-full bg-primary/8 px-1.5 py-0.5 text-[10px] leading-tight text-primary/70"
        >
          {{ formatKnowledgeBaseName(kb.kb_name, kb.knowledge_base_id) }}
        </span>
      </div>
      <div
        v-if="selectedKBIds.length > 0"
        class="mb-1.5 flex flex-wrap items-center gap-1"
      >
        <span class="text-[10px] text-muted-foreground/70">{{
          $t('common.globalAiChat.selectedKbForTurn')
        }}</span>
        <span
          v-for="kid in selectedKBIds"
          :key="kid"
          class="inline-flex items-center gap-0.5 rounded-full border border-primary/25 bg-background px-1.5 py-0.5 text-[10px] text-primary"
        >
          {{
            formatKnowledgeBaseName(
              agentKBBindings.find((b) => b.knowledge_base_id === kid)?.kb_name,
              kid,
            )
          }}
          <button
            type="button"
            class="rounded p-0 leading-none text-muted-foreground hover:text-destructive"
            :aria-label="$t('common.globalAiChat.removeKbFromTurn')"
            @click="removeSelectedKnowledgeBase(kid)"
          >
            <IconifyIcon icon="lucide:x" class="size-2.5" />
          </button>
        </span>
      </div>

      <!-- Input row -->
      <div
        class="overflow-hidden rounded-xl border border-border/40 bg-muted/20 transition-all focus-within:border-primary/40 focus-within:bg-background focus-within:shadow-sm focus-within:shadow-primary/5"
      >
        <Transition name="mention-panel">
          <div
            v-if="mentionOpen"
            class="border-b border-border/30 bg-background/70 px-2 py-1.5"
          >
            <div
              class="mb-1 flex items-center gap-1 text-[10px] text-muted-foreground/70"
            >
              <IconifyIcon icon="lucide:at-sign" class="size-3" />
              <span>{{ $t('common.globalAiChat.mentionMixedHint') }}</span>
            </div>
            <div v-if="agentsLoading" class="flex items-center gap-2 px-1 py-2">
              <Spin size="small" />
              <span class="text-[11px] text-muted-foreground">
                {{ $t('common.globalAiChat.mentionAgentLoading') }}
              </span>
            </div>
            <div
              v-else-if="mentionCandidates.length === 0"
              class="space-y-1 px-1 py-2 text-[11px] text-muted-foreground"
            >
              <p>{{ $t('common.globalAiChat.mentionAgentEmpty') }}</p>
              <p
                v-if="agentKBBindings.length === 0 && !agentsLoading"
                class="text-[10px] text-muted-foreground/80"
              >
                {{ $t('common.globalAiChat.mentionKbNoneBound') }}
              </p>
            </div>
            <div v-else class="max-h-48 space-y-2 overflow-y-auto">
              <template
                v-for="(c, candidateIndex) in mentionCandidates"
                :key="`kb-${c.binding.knowledge_base_id}`"
              >
                <div
                  v-if="
                    candidateIndex === 0 ||
                    mentionCandidates[candidateIndex - 1]!.kind !== c.kind
                  "
                  class="px-0.5 pt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60"
                >
                  {{ $t('common.globalAiChat.mentionSectionKbs') }}
                </div>
                <button
                  class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors"
                  :class="
                    candidateIndex === mentionActiveIndex
                      ? 'bg-primary/10 text-foreground'
                      : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground'
                  "
                  @mousedown.prevent
                  @click="selectMentionKnowledgeBase(c.binding)"
                >
                  <div
                    class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-700 dark:text-amber-400"
                  >
                    <IconifyIcon icon="lucide:library" class="size-4" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-[12px] font-medium">
                      {{
                        formatKnowledgeBaseName(
                          c.binding.kb_name,
                          c.binding.knowledge_base_id,
                        )
                      }}
                    </div>
                    <div class="truncate text-[10px] text-muted-foreground/70">
                      {{ $t('common.globalAiChat.mentionKbPickHint') }}
                    </div>
                  </div>
                </button>
              </template>
            </div>
          </div>
        </Transition>
        <div class="flex min-h-[2.75rem] items-end gap-2 px-3 py-2">
          <Tooltip :title="$t('common.globalAiChat.addAttachment')">
            <button
              class="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
              :disabled="agents.length === 0 || sending"
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
            :placeholder="$t('user.aiChat.inputPlaceholder')"
            :auto-size="{ minRows: 2, maxRows: 6 }"
            :maxlength="32000"
            :disabled="agents.length === 0 || sending"
            class="ai-chat-textarea min-w-0 flex-1 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
            @keydown="handleKeyDown"
            @paste="handlePaste"
          />
          <button
            class="flex size-8 shrink-0 items-center justify-center rounded-full shadow-sm transition-all hover:scale-110 hover:shadow-md active:scale-95 disabled:opacity-40 disabled:hover:scale-100"
            :class="[
              streaming
                ? 'bg-destructive text-destructive-foreground'
                : 'bg-primary text-primary-foreground',
            ]"
            :aria-label="
              streaming ? $t('common.globalAiChat.stop') : $t('common.commandBar.send')
            "
            :disabled="
              !streaming &&
              ((!inputMessage.trim() && pendingAttachments.length === 0) ||
                agents.length === 0 ||
                sending)
            "
            @click="streaming ? stopGeneration() : handleSendClick()"
          >
            <Spin v-if="!streaming && sending" size="small" />
            <IconifyIcon
              v-else
              :icon="streaming ? 'lucide:square' : 'lucide:arrow-up'"
              class="size-4"
            />
          </button>
        </div>
        <div class="flex justify-end px-2 pb-1">
          <span class="text-[10px] text-muted-foreground/60">
            {{ inputMessage.length }} / 32000
          </span>
        </div>
      </div>
    </div>

    <!-- Image preview lightbox -->
    <Modal
      v-model:open="previewImageVisible"
      :footer="null"
      width="auto"
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
  </div>
</template>

<style scoped>
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

@keyframes streaming-slide {
  0% {
    transform: translateX(-100%);
  }

  50% {
    transform: translateX(233%);
  }

  100% {
    transform: translateX(-100%);
  }
}

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

/* Mention dropdown transition / @ 智能体下拉过渡 */
.mention-panel-enter-active,
.mention-panel-leave-active {
  overflow: hidden;
  transition:
    opacity 0.2s ease,
    max-height 0.24s ease,
    transform 0.24s ease;
}

.mention-panel-enter-from,
.mention-panel-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-6px);
}

.mention-panel-enter-to,
.mention-panel-leave-from {
  max-height: 240px;
  opacity: 1;
  transform: translateY(0);
}

/* Attachment pop transition */
.att-pop-enter-active {
  animation: att-in 0.25s ease-out;
}

.att-pop-leave-active {
  animation: att-in 0.15s ease-in reverse;
}

/* 输入框多行文本域：保证与图标垂直对齐 */
.ai-chat-textarea :deep(.ant-input) {
  resize: none;
}

/* Streaming progress bar / 流式进度条 */
.streaming-bar {
  width: 30%;
  background: linear-gradient(
    90deg,
    transparent,
    hsl(var(--primary) / 60%),
    hsl(var(--primary)),
    hsl(var(--primary) / 60%),
    transparent
  );
  border-radius: 9999px;
  animation: streaming-slide 1.5s ease-in-out infinite;
}
</style>

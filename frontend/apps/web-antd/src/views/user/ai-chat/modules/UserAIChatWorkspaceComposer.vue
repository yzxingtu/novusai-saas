<script lang="ts" setup>
import type { VNodeRef } from 'vue';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Input, Spin, Tooltip } from 'ant-design-vue';

import { formatKnowledgeBaseName } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const workspace = useUserAIChatWorkspaceContext();
const { page, handleKeyDown, handleSendClick } = workspace;
const { chat } = page;
const {
  agents,
  agentsLoading,
  chatMessages,
  inputMessage,
  mentionOpen,
  mentionCandidates,
  mentionActiveIndex,
  sending,
  streaming,
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
  stopGeneration,
} = chat;

const canSend = computed(
  () =>
    streaming.value ||
    !(
      (!inputMessage.value.trim() && pendingAttachments.value.length === 0) ||
      agents.value.length === 0 ||
      sending.value
    ),
);

function resolveSelectedKbName(knowledgeBaseId: number) {
  return formatKnowledgeBaseName(
    agentKBBindings.value.find(
      (binding) => binding.knowledge_base_id === knowledgeBaseId,
    )?.kb_name,
    knowledgeBaseId,
  );
}

const setFileInputRef: VNodeRef = (element) => {
  fileInput.value = element as HTMLInputElement | null;
};
</script>

<template>
  <div
    class="shrink-0 border-t border-border px-4 py-3 sm:px-6"
    @dragover="handleDragOver"
    @drop="handleDrop"
  >
    <TransitionGroup
      v-if="pendingAttachments.length > 0"
      name="att-pop"
      tag="div"
      class="mb-2 flex flex-wrap gap-1.5"
    >
      <div
        v-for="(attachment, index) in pendingAttachments"
        :key="attachment.url || index"
        class="group relative"
      >
        <div
          v-if="attachment.type === 'image'"
          class="relative size-14 overflow-hidden rounded-lg border border-border"
        >
          <img
            :src="attachment.preview || attachment.url"
            class="size-full object-cover"
          />
          <button
            class="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
            @click="removePendingAttachment(index)"
          >
            <IconifyIcon icon="lucide:x" class="size-2.5" />
          </button>
        </div>

        <div
          v-else
          class="flex items-center gap-1.5 rounded-lg border border-border bg-accent/50 px-2 py-1.5"
        >
          <IconifyIcon
            :icon="getFileIcon(attachment.name || '', attachment.mime_type)"
            class="size-4 shrink-0 text-muted-foreground"
          />
          <span class="max-w-[100px] truncate text-xs text-foreground">
            {{ attachment.name }}
          </span>
          <button
            class="flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
            @click="removePendingAttachment(index)"
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

    <div
      v-if="chatMessages.length > 0"
      class="mb-1.5 flex items-center justify-between"
    >
      <span class="text-[11px] text-muted-foreground/40">
        {{ $t('common.globalAiChat.shiftEnterHint') }}
      </span>
    </div>

    <div
      v-if="agentKBBindings.length > 0"
      class="mb-1.5 flex flex-wrap items-center gap-1"
    >
      <IconifyIcon
        icon="lucide:book-open"
        class="size-3 shrink-0 text-muted-foreground/50"
      />
      <span
        v-for="binding in agentKBBindings"
        :key="binding.knowledge_base_id"
        class="inline-flex items-center rounded-full bg-primary/8 px-1.5 py-0.5 text-[10px] leading-tight text-primary/70"
      >
        {{
          formatKnowledgeBaseName(binding.kb_name, binding.knowledge_base_id)
        }}
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
        v-for="knowledgeBaseId in selectedKBIds"
        :key="knowledgeBaseId"
        class="inline-flex items-center gap-0.5 rounded-full border border-primary/25 bg-background px-1.5 py-0.5 text-[10px] text-primary"
      >
        {{ resolveSelectedKbName(knowledgeBaseId) }}
        <button
          type="button"
          class="rounded p-0 leading-none text-muted-foreground hover:text-destructive"
          :aria-label="$t('common.globalAiChat.removeKbFromTurn')"
          @click="removeSelectedKnowledgeBase(knowledgeBaseId)"
        >
          <IconifyIcon icon="lucide:x" class="size-2.5" />
        </button>
      </span>
    </div>

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
              v-for="(candidate, candidateIndex) in mentionCandidates"
              :key="`kb-${candidate.binding.knowledge_base_id}`"
            >
                <div
                  v-if="
                    candidateIndex === 0 ||
                    mentionCandidates[candidateIndex - 1]?.kind !== candidate.kind
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
                @click="selectMentionKnowledgeBase(candidate.binding)"
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
                        candidate.binding.kb_name,
                        candidate.binding.knowledge_base_id,
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
          :ref="setFileInputRef"
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
          :class="
            streaming
              ? 'bg-destructive text-destructive-foreground'
              : 'bg-primary text-primary-foreground'
          "
          :aria-label="
            streaming
              ? $t('common.globalAiChat.stop')
              : $t('common.commandBar.send')
          "
          :disabled="!canSend"
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

.att-pop-enter-active {
  animation: att-in 0.25s ease-out;
}

.att-pop-leave-active {
  animation: att-in 0.15s ease-in reverse;
}

.ai-chat-textarea :deep(.ant-input) {
  resize: none;
}
</style>

<script lang="ts" setup>
import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Input, Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

type ComposerSendState = 'idle' | 'routing' | 'sending' | 'streaming';

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

interface ComposerSkillPackageChip {
  id: string;
  label: string;
  value: string;
}

interface ComposerMentionCandidateItem {
  active: boolean;
  id: number;
  kind: 'knowledge_base' | 'skill_package';
  subtitle?: string;
  title: string;
}

const props = withDefaults(
  defineProps<{
    attachDisabled?: boolean;
    attachmentAccept?: string;
    attachmentLimitHint?: string;
    attachments?: ComposerAttachmentItem[];
    boundKnowledgeBases?: ComposerKnowledgeBaseChip[];
    characterCount?: number;
    disabled?: boolean;
    maxLength?: number;
    mentionCandidates?: ComposerMentionCandidateItem[];
    mentionEmptyHint?: string;
    mentionLoading?: boolean;
    mentionMixedHint?: string;
    mentionOpen?: boolean;
    modelValue?: string;
    selectedKnowledgeBases?: ComposerKnowledgeBaseChip[];
    selectedSkillPackages?: ComposerSkillPackageChip[];
    sendDisabled?: boolean;
    sendState?: ComposerSendState;
    shiftEnterHint?: string;
    showAttachments?: boolean;
  }>(),
  {
    attachDisabled: false,
    attachmentAccept: '',
    attachmentLimitHint: '',
    attachments: () => [],
    boundKnowledgeBases: () => [],
    characterCount: 0,
    disabled: false,
    maxLength: 32_000,
    mentionCandidates: () => [],
    mentionEmptyHint: '',
    mentionLoading: false,
    mentionMixedHint: '',
    mentionOpen: false,
    modelValue: '',
    sendDisabled: false,
    selectedKnowledgeBases: () => [],
    selectedSkillPackages: () => [],
    sendState: 'idle',
    shiftEnterHint: '',
    showAttachments: true,
  },
);

const emit = defineEmits<{
  (e: 'dragover', event: DragEvent): void;
  (e: 'drop', event: DragEvent): void;
  (e: 'fileSelect', event: Event): void;
  (e: 'keydown', event: KeyboardEvent): void;
  (e: 'paste', event: ClipboardEvent): void;
  (e: 'removeAttachment', index: number): void;
  (e: 'removeSelectedKnowledgeBase', id: number): void;
  (
    e: 'selectMentionCandidate',
    payload: { id: number; kind: 'knowledge_base' | 'skill_package' },
  ): void;
  (e: 'removeSelectedSkillPackage', value: string): void;
  (e: 'send'): void;
  (e: 'stop'): void;
  (e: 'update:modelValue', value: string): void;
}>();

const fileInputEl = ref<HTMLInputElement | null>(null);
const inputModel = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

function openFilePicker() {
  fileInputEl.value?.click();
}

function onSendClick() {
  if (props.sendState === 'streaming') {
    emit('stop');
    return;
  }
  emit('send');
}
</script>

<template>
  <div
    class="shrink-0 border-t border-border px-3 py-2"
    @dragover="emit('dragover', $event)"
    @drop="emit('drop', $event)"
  >
    <TransitionGroup
      v-if="showAttachments && attachments.length > 0"
      name="att-pop"
      tag="div"
      class="mb-1.5 flex flex-wrap gap-1.5"
    >
      <div
        v-for="(attachment, attachmentIndex) in attachments"
        :key="attachment.key"
        class="group relative"
      >
        <div
          v-if="attachment.type === 'image'"
          class="relative size-12 overflow-hidden rounded border border-border"
        >
          <img :src="attachment.previewUrl" class="size-full object-cover" />
          <button
            class="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
            @click="emit('removeAttachment', attachmentIndex)"
          >
            <IconifyIcon icon="lucide:x" class="size-2.5" />
          </button>
        </div>
        <div
          v-else
          class="flex items-center gap-1 rounded border border-border bg-accent/50 px-1.5 py-1"
        >
          <IconifyIcon
            :icon="attachment.icon || 'lucide:file'"
            class="size-3.5 shrink-0 text-muted-foreground"
          />
          <span class="max-w-[80px] truncate text-[11px] text-foreground">
            {{ attachment.name }}
          </span>
          <button
            class="flex size-3.5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
            @click="emit('removeAttachment', attachmentIndex)"
          >
            <IconifyIcon icon="lucide:x" class="size-2.5" />
          </button>
        </div>
      </div>

      <div
        v-if="sendState === 'sending'"
        key="composer-uploading-indicator"
        class="flex size-12 items-center justify-center rounded border border-dashed border-border"
      >
        <Spin size="small" />
      </div>
    </TransitionGroup>

    <div
      v-if="showAttachments && attachmentLimitHint"
      class="mb-1 text-[10px] text-muted-foreground/70"
    >
      {{ attachmentLimitHint }}
    </div>

    <div
      v-if="boundKnowledgeBases.length > 0"
      class="mb-1 flex flex-wrap items-center gap-1"
    >
      <IconifyIcon
        icon="lucide:book-open"
        class="size-3 shrink-0 text-muted-foreground/50"
      />
      <span
        v-for="knowledgeBase in boundKnowledgeBases"
        :key="knowledgeBase.id"
        class="bg-primary/8 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] leading-tight text-primary/70"
      >
        {{ knowledgeBase.label }}
      </span>
    </div>

    <div
      v-if="
        selectedKnowledgeBases.length > 0 || selectedSkillPackages.length > 0
      "
      class="mb-1 flex flex-wrap items-center gap-1"
    >
      <span
        v-if="selectedKnowledgeBases.length > 0"
        class="text-[10px] text-muted-foreground/70"
      >
        {{ $t('common.globalAiChat.selectedKbForTurn') }}
      </span>
      <span
        v-for="knowledgeBase in selectedKnowledgeBases"
        :key="knowledgeBase.id"
        class="inline-flex items-center gap-0.5 rounded-full border border-primary/25 bg-background px-1.5 py-0.5 text-[10px] text-primary"
      >
        {{ knowledgeBase.label }}
        <button
          type="button"
          class="rounded p-0 leading-none text-muted-foreground hover:text-destructive"
          :aria-label="$t('common.globalAiChat.removeKbFromTurn')"
          @click="emit('removeSelectedKnowledgeBase', knowledgeBase.id)"
        >
          <IconifyIcon icon="lucide:x" class="size-2.5" />
        </button>
      </span>
      <span
        v-if="selectedSkillPackages.length > 0"
        class="text-[10px] text-muted-foreground/70"
      >
        {{ $t('common.globalAiChat.selectedSkillForTurn') }}
      </span>
      <span
        v-for="skillPackage in selectedSkillPackages"
        :key="skillPackage.id"
        class="inline-flex items-center gap-0.5 rounded-full border border-emerald-500/25 bg-background px-1.5 py-0.5 text-[10px] text-emerald-700 dark:text-emerald-300"
      >
        {{ skillPackage.label }}
        <button
          type="button"
          class="rounded p-0 leading-none text-muted-foreground hover:text-destructive"
          :aria-label="$t('common.globalAiChat.removeSkillFromTurn')"
          @click="emit('removeSelectedSkillPackage', skillPackage.value)"
        >
          <IconifyIcon icon="lucide:x" class="size-2.5" />
        </button>
      </span>
    </div>

    <div
      class="ai-composer-shell overflow-hidden rounded-[18px] border transition-all"
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
            <span>{{ mentionMixedHint }}</span>
          </div>
          <div v-if="mentionLoading" class="flex items-center gap-2 px-1 py-2">
            <Spin size="small" />
            <span class="text-[11px] text-muted-foreground">
              {{ $t('common.globalAiChat.mentionAgentLoading') }}
            </span>
          </div>
          <div
            v-else-if="mentionCandidates.length === 0"
            class="space-y-1 px-1 py-2 text-[11px] text-muted-foreground"
          >
            <p>{{ mentionEmptyHint }}</p>
          </div>
          <div v-else class="max-h-48 space-y-2 overflow-y-auto">
            <template
              v-for="(candidate, candidateIndex) in mentionCandidates"
              :key="`${candidate.kind}-${candidate.id}`"
            >
              <div
                v-if="
                  candidateIndex === 0 ||
                  mentionCandidates[candidateIndex - 1]!.kind !== candidate.kind
                "
                class="px-0.5 pt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60"
              >
                {{
                  candidate.kind === 'skill_package'
                    ? $t('common.globalAiChat.mentionSectionSkills')
                    : $t('common.globalAiChat.mentionSectionKbs')
                }}
              </div>
              <button
                class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors"
                :class="
                  candidate.active
                    ? 'bg-primary/10 text-foreground'
                    : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground'
                "
                @mousedown.prevent
                @click="
                  emit('selectMentionCandidate', {
                    id: candidate.id,
                    kind: candidate.kind,
                  })
                "
              >
                <div
                  class="flex size-7 shrink-0 items-center justify-center rounded-lg"
                  :class="
                    candidate.kind === 'skill_package'
                      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                      : 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
                  "
                >
                  <IconifyIcon
                    :icon="
                      candidate.kind === 'skill_package'
                        ? 'lucide:package-check'
                        : 'lucide:library'
                    "
                    class="size-4"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-[12px] font-medium">
                    {{ candidate.title }}
                  </div>
                  <div
                    v-if="candidate.subtitle"
                    class="truncate text-[10px] text-muted-foreground/70"
                  >
                    {{ candidate.subtitle }}
                  </div>
                </div>
              </button>
            </template>
          </div>
        </div>
      </Transition>

      <div class="flex min-h-[2.75rem] items-end gap-1.5 px-3 py-2.5">
        <Tooltip
          v-if="showAttachments"
          :title="$t('common.globalAiChat.addAttachment')"
        >
          <button
            class="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
            :disabled="attachDisabled"
            @click="openFilePicker"
          >
            <IconifyIcon icon="lucide:paperclip" class="size-3.5" />
          </button>
        </Tooltip>
        <input
          ref="fileInputEl"
          type="file"
          multiple
          :accept="attachmentAccept"
          class="hidden"
          @change="emit('fileSelect', $event)"
        />
        <Input.TextArea
          v-model:value="inputModel"
          :placeholder="$t('common.globalAiChat.inputPlaceholder')"
          :auto-size="{ minRows: 2, maxRows: 6 }"
          :maxlength="maxLength"
          :disabled="disabled"
          data-testid="ai-chat-input"
          class="ai-chat-textarea min-w-0 flex-1 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
          @keydown="emit('keydown', $event)"
          @paste="emit('paste', $event)"
        />
        <button
          type="button"
          class="send-btn flex size-8 shrink-0 items-center justify-center rounded-xl transition-colors disabled:opacity-40"
          :class="
            sendState === 'streaming'
              ? 'bg-destructive text-destructive-foreground'
              : 'hover:bg-foreground/88 bg-foreground text-background'
          "
          :aria-label="
            sendState === 'streaming'
              ? $t('common.globalAiChat.stop')
              : $t('common.commandBar.send')
          "
          :disabled="sendState !== 'streaming' && sendDisabled"
          @click="onSendClick"
        >
          <Spin
            v-if="
              sendState !== 'streaming' &&
              (sendState === 'sending' || sendState === 'routing')
            "
            size="small"
          />
          <span
            v-else-if="sendState === 'streaming'"
            aria-hidden="true"
            class="block size-3 rounded-[2px] bg-current"
          ></span>
          <svg
            v-else
            viewBox="0 0 16 16"
            aria-hidden="true"
            class="size-4"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.7"
          >
            <path d="M8 12V4" />
            <path d="M4.75 7.25 8 4l3.25 3.25" />
          </svg>
        </button>
      </div>

      <div class="flex justify-end px-1 pb-0.5">
        <span class="text-[10px] text-muted-foreground/60">
          {{ shiftEnterHint }} · {{ characterCount }} / {{ maxLength }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-composer-shell {
  background: hsl(var(--background) / 98%);
  border-color: hsl(var(--border) / 34%);
  box-shadow: 0 12px 24px -24px hsl(var(--foreground) / 10%);
}

.ai-composer-shell:focus-within {
  background: hsl(var(--background));
  border-color: hsl(var(--foreground) / 18%);
  box-shadow:
    0 14px 28px -24px hsl(var(--foreground) / 12%),
    0 0 0 3px hsl(var(--foreground) / 4%);
}

.ai-chat-textarea :deep(.ant-input) {
  resize: none;
}
</style>

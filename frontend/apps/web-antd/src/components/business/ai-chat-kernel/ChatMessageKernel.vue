<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { prepareMessageContent } from '#/components/business/ai-chat-panel/chat-message-display-preparation';
import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';
import { $t } from '#/locales';

import ActionConsentGate from './ActionConsentGate.vue';
import EvidenceCard from './EvidenceCard.vue';
import { buildTurnFlowState } from './TurnFlowState';
import TurnTimeline from './TurnTimeline.vue';
import { getProcessHeadlineForStage } from './turn-stage-presentation';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
    state?: null | TurnFlowState;
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    pendingOps: () => [],
    state: null,
  },
);

const emit = defineEmits<{
  confirm: [];
  consentConfirm: [];
  consentReject: [];
  copy: [content: string];
  reject: [];
}>();

const resolvedState = computed(
  () => props.state ?? buildTurnFlowState(props.msg, props.pendingOps),
);
const preparedDigestBody = computed(() => {
  if (resolvedState.value.timeline.length > 0) {
    return '';
  }
  const prepared = prepareMessageContent(props.msg);
  if (prepared.suppressed) {
    return '';
  }
  return prepared.bodyMarkdown.trim();
});
const hasDigestCard = computed(
  () =>
    Boolean(resolvedState.value.answerCard?.summary) ||
    (resolvedState.value.answerCard?.sections?.length ?? 0) > 0 ||
    resolvedState.value.selectedEvidence.length > 0 ||
    Boolean(preparedDigestBody.value) ||
    (props.msg.streaming === true &&
      resolvedState.value.timeline.some(
        (stage) =>
          stage.type === 'answer_assembly' &&
          stage.status !== 'error' &&
          stage.status !== 'skipped',
      )),
);
const visibleKernelTimeline = computed(() =>
  resolvedState.value.timeline.filter((stage) => {
    if (stage.type === 'completed') {
      return false;
    }
    if (
      stage.type === 'answer_assembly' &&
      stage.status === 'completed' &&
      Boolean(
        resolvedState.value.answerCard ||
          normalizeMergedTextPart(props.msg.content),
      )
    ) {
      return false;
    }
    if (
      stage.status === 'skipped' &&
      (stage.type === 'tool_selection' ||
        stage.type === 'tool_execution' ||
        stage.type === 'retrieval')
    ) {
      return false;
    }
    return true;
  }),
);
const hasTimeline = computed(() => visibleKernelTimeline.value.length > 0);
const hasRunningTimelineStage = computed(() =>
  visibleKernelTimeline.value.some((stage) => stage.status === 'running'),
);
const hasDigestContent = computed(
  () => hasTimeline.value || hasDigestCard.value,
);
const canCollapseKernel = computed(
  () =>
    hasDigestContent.value &&
    props.msg.streaming !== true &&
    !hasRunningTimelineStage.value,
);

function normalizeText(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeIdentityPart(value: unknown): string | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return normalizeOptionalString(value);
}

function hashIdentityParts(parts: string[]): string {
  let hash = 2_166_136_261;
  const joined = parts.join('\u001F');
  for (let index = 0; index < joined.length; index += 1) {
    hash ^= joined.codePointAt(index) ?? 0;
    hash = Math.imul(hash, 16_777_619);
  }
  return (hash >>> 0).toString(36);
}

function resolveMessageIdentity(msg: ChatMessage): string {
  const messageRecord = msg as unknown as Record<string, unknown>;
  const persistedId = [
    messageRecord.message_id,
    messageRecord.messageId,
    messageRecord.id,
  ]
    .map((value) => normalizeIdentityPart(value))
    .find(Boolean);
  if (persistedId) {
    return `persisted:${persistedId}`;
  }

  const normalizedClientKey = normalizeOptionalString(msg.clientKey);
  if (normalizedClientKey) {
    return `client:${normalizedClientKey}`;
  }

  const content = normalizeMergedTextPart(msg.content) || msg.content;
  return `fallback:${hashIdentityParts([
    msg.role,
    normalizeOptionalString(msg.created_at) ?? '',
    String(content.length),
    content.slice(0, 256),
  ])}`;
}

function truncatePreview(value: string, limit: number) {
  return value.length > limit ? `${value.slice(0, limit - 1).trimEnd()}…` : value;
}

const messageIdentity = computed(() => resolveMessageIdentity(props.msg));
const isKernelExpanded = ref(false);
const showKernelBody = computed(
  () => !canCollapseKernel.value || isKernelExpanded.value,
);
const digestPreviewText = computed(() => {
  const summary = normalizeText(resolvedState.value.answerCard?.summary);
  if (summary) {
    return truncatePreview(summary, 64);
  }

  const firstSection = resolvedState.value.answerCard?.sections?.find(
    (section) =>
      normalizeText(section.title) ||
      normalizeText(section.body) ||
      normalizeText(section.content),
  );
  const sectionPreview = normalizeText(
    firstSection?.title || firstSection?.body || firstSection?.content,
  );
  if (sectionPreview) {
    return truncatePreview(sectionPreview, 64);
  }

  const evidencePreview = normalizeText(
    resolvedState.value.selectedEvidence[0]?.label,
  );
  if (evidencePreview) {
    return truncatePreview(evidencePreview, 64);
  }

  const preparedPreview = normalizeText(preparedDigestBody.value);
  if (preparedPreview) {
    return truncatePreview(preparedPreview, 64);
  }

  return '';
});
const digestOverviewLabelKey = computed(() =>
  Boolean(resolvedState.value.answerCard?.summary) ||
  (resolvedState.value.answerCard?.sections?.length ?? 0) > 0 ||
  Boolean(preparedDigestBody.value)
    ? 'common.globalAiChat.turnAnswerCardTitle'
    : 'common.globalAiChat.turnEvidenceTitle',
);
const visibleProcessStages = computed(() => {
  const stages = visibleKernelTimeline.value;
  return stages.length > 0 ? stages : resolvedState.value.timeline;
});
const processStageCount = computed(() => visibleProcessStages.value.length);
const processPreviewText = computed(() => {
  const errorMessage =
    normalizeText(resolvedState.value.flow.errorSurface?.message) ||
    normalizeText(resolvedState.value.flow.errorSurface?.summary);
  if (errorMessage) {
    return truncatePreview(errorMessage, 38);
  }

  for (let index = visibleProcessStages.value.length - 1; index >= 0; index -= 1) {
    const stage = visibleProcessStages.value[index];
    if (!stage) {
      continue;
    }
    const preview = normalizeText(
      getProcessHeadlineForStage(stage, {
        errorSurface: resolvedState.value.flow.errorSurface,
      }),
    );
    if (preview) {
      return truncatePreview(preview, 38);
    }
  }

  return '';
});

function syncKernelExpanded(nextExpanded: boolean) {
  if (isKernelExpanded.value === nextExpanded) {
    return;
  }
  isKernelExpanded.value = nextExpanded;
}

function toggleKernelExpanded() {
  if (!canCollapseKernel.value) {
    return;
  }
  syncKernelExpanded(!isKernelExpanded.value);
}

watch(
  messageIdentity,
  () => {
    syncKernelExpanded(props.msg.streaming === true);
  },
  { immediate: true },
);

watch(
  () => props.msg.streaming === true,
  (isStreaming, wasStreaming) => {
    if (isStreaming === wasStreaming) {
      return;
    }
    syncKernelExpanded(isStreaming);
  },
);

function handleApprove() {
  if (resolvedState.value.pendingAction?.kind === 'confirmation') {
    emit('confirm');
    return;
  }
  emit('consentConfirm');
}

function handleReject() {
  if (resolvedState.value.pendingAction?.kind === 'confirmation') {
    emit('reject');
    return;
  }
  emit('consentReject');
}
</script>

<template>
  <div class="space-y-1.5">
    <div
      v-if="hasDigestContent"
      data-testid="chat-message-kernel-header"
      class="chat-message-kernel-shell overflow-hidden rounded-[16px] border"
    >
      <button
        v-if="canCollapseKernel"
        type="button"
        data-testid="chat-message-kernel-overview-toggle"
        class="chat-message-kernel-overview flex w-full min-w-0 items-center gap-2 text-left"
        :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'"
        :aria-expanded="isKernelExpanded"
        @click="toggleKernelExpanded"
      >
        <div class="min-w-0 flex flex-1 items-stretch gap-2">
          <div
            v-if="hasDigestCard"
            class="kernel-overview-group min-w-0 flex flex-1 items-center gap-1.5"
          >
            <span class="kernel-overview-pill shrink-0">
              {{ $t(digestOverviewLabelKey) }}
            </span>
            <span
              v-if="digestPreviewText"
              class="kernel-overview-copy min-w-0 flex-1 truncate"
            >
              {{ digestPreviewText }}
            </span>
          </div>

          <span
            v-if="hasDigestCard && hasTimeline"
            class="kernel-overview-divider shrink-0"
          ></span>

          <div
            v-if="hasTimeline"
            class="kernel-overview-group min-w-0 flex flex-1 items-center gap-1.5"
          >
            <span class="kernel-overview-pill shrink-0">
              {{ $t('common.globalAiChat.turnTimeline') }}
            </span>
            <span
              v-if="processPreviewText"
              class="kernel-overview-copy min-w-0 flex-1 truncate"
            >
              {{ processPreviewText }}
            </span>
            <span class="kernel-overview-count shrink-0">
              {{
                $t('common.globalAiChat.turnStageCount', {
                  count: processStageCount,
                })
              }}
            </span>
          </div>
        </div>

        <span
          class="kernel-overview-chevron inline-flex shrink-0 items-center justify-center rounded-full p-1"
        >
          <IconifyIcon
            icon="lucide:chevron-down"
            class="size-3 transition-transform duration-200"
            :style="{
              transform: isKernelExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            }"
          />
        </span>
      </button>

      <Transition name="chat-message-kernel-body">
        <div
          v-if="showKernelBody"
          data-testid="chat-message-kernel-body"
          class="space-y-1"
          :class="[
            compact ? 'px-2.5 py-1.5' : 'px-3 py-2',
            canCollapseKernel ? 'border-t border-border/10' : '',
          ]"
        >
          <EvidenceCard
            v-if="hasDigestCard"
            :compact="compact"
            :msg="msg"
            :state="resolvedState"
          />

          <div
            v-if="hasTimeline"
            :class="hasDigestCard ? 'border-t border-border/10 pt-1.5' : ''"
          >
            <TurnTimeline
              :compact="compact"
              :countdown-now="countdownNow"
              :msg="msg"
              :pending-ops="pendingOps"
              :state="resolvedState"
              @copy="(content) => emit('copy', content)"
            />
          </div>
        </div>
      </Transition>
    </div>

    <ActionConsentGate
      :action="resolvedState.pendingAction"
      :compact="compact"
      @approve="handleApprove"
      @reject="handleReject"
    />
    <slot name="diagnostics"></slot>
  </div>
</template>

<style scoped>
.chat-message-kernel-shell {
  border-color: hsl(var(--border) / 0.15);
  background:
    linear-gradient(
      180deg,
      hsl(var(--primary) / 0.02) 0%,
      hsl(var(--background) / 0.988) 42%,
      hsl(var(--muted) / 0.03) 100%
    );
  box-shadow: 0 16px 26px -32px hsl(var(--foreground) / 0.12);
}

.chat-message-kernel-overview {
  transition:
    background-color 160ms ease,
    border-color 160ms ease;
}

.chat-message-kernel-overview:hover {
  background: hsl(var(--primary) / 0.03);
}

.kernel-overview-group {
  min-width: 0;
  padding: 0.55rem 0.65rem;
  border: 1px solid hsl(var(--border) / 0.16);
  border-radius: 16px;
  background: hsl(var(--background) / 0.82);
}

.kernel-overview-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0.16rem 0.55rem;
  color: hsl(var(--primary) / 0.76);
  border: 1px solid hsl(var(--primary) / 0.12);
  background: hsl(var(--primary) / 0.05);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.kernel-overview-copy {
  color: hsl(var(--foreground) / 0.72);
  font-size: 0.7rem;
  line-height: 1rem;
}

.kernel-overview-count {
  color: hsl(var(--muted-foreground) / 0.56);
  border: 1px solid hsl(var(--border) / 0.14);
  background: hsl(var(--muted) / 0.32);
  border-radius: 9999px;
  padding: 0.16rem 0.45rem;
  font-size: 0.62rem;
  line-height: 0.9rem;
}

.kernel-overview-divider {
  width: 1px;
  align-self: stretch;
  background: hsl(var(--border) / 0.1);
}

.kernel-overview-chevron {
  color: hsl(var(--muted-foreground) / 0.44);
  border: 1px solid hsl(var(--border) / 0.14);
  background: hsl(var(--background) / 0.84);
}

.chat-message-kernel-overview:hover .kernel-overview-chevron {
  color: hsl(var(--primary) / 0.76);
  border-color: hsl(var(--primary) / 0.14);
}

.chat-message-kernel-body-enter-active,
.chat-message-kernel-body-leave-active {
  overflow: hidden;
  transition:
    max-height 180ms ease,
    opacity 160ms ease;
}

.chat-message-kernel-body-enter-from,
.chat-message-kernel-body-leave-to {
  max-height: 0;
  opacity: 0;
}

.chat-message-kernel-body-enter-to,
.chat-message-kernel-body-leave-from {
  max-height: 28rem;
  opacity: 1;
}
</style>

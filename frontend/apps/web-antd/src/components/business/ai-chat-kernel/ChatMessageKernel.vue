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
const hasKernelFailure = computed(
  () =>
    Boolean(resolvedState.value.flow.errorSurface?.message) ||
    Boolean(resolvedState.value.flow.errorSurface?.summary) ||
    Boolean(props.msg.error) ||
    props.msg.requestFailedRetry === true,
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
  return value.length > limit
    ? `${value.slice(0, limit - 1).trimEnd()}…`
    : value;
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

  for (
    let index = visibleProcessStages.value.length - 1;
    index >= 0;
    index -= 1
  ) {
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
const kernelStatusLabelKey = computed(() => {
  if (props.msg.streaming || hasRunningTimelineStage.value) {
    return 'common.globalAiChat.processing';
  }
  if (hasKernelFailure.value) {
    return 'common.globalAiChat.turnStageStatus.error';
  }
  return 'common.globalAiChat.turnStageStatus.completed';
});
const kernelStatusIcon = computed(() => {
  if (props.msg.streaming || hasRunningTimelineStage.value) {
    return 'lucide:loader-circle';
  }
  if (hasKernelFailure.value) {
    return 'lucide:triangle-alert';
  }
  return 'lucide:check';
});
const kernelStatusClass = computed(() => {
  if (props.msg.streaming || hasRunningTimelineStage.value) {
    return 'kernel-status-running';
  }
  if (hasKernelFailure.value) {
    return 'kernel-status-error';
  }
  return 'kernel-status-completed';
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
      class="chat-message-kernel-shell overflow-hidden rounded-[18px] border"
    >
      <button
        v-if="canCollapseKernel"
        type="button"
        data-testid="chat-message-kernel-overview-toggle"
        class="chat-message-kernel-overview flex w-full min-w-0 items-center gap-2.5 text-left"
        :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'"
        :aria-expanded="isKernelExpanded"
        @click="toggleKernelExpanded"
      >
        <div class="flex min-w-0 flex-1 flex-wrap items-stretch gap-2">
          <div
            v-if="hasDigestCard"
            class="kernel-overview-group flex min-w-0 flex-1 items-center gap-2"
          >
            <span class="kernel-overview-icon shrink-0">
              <IconifyIcon icon="lucide:sparkles" class="size-3" />
            </span>
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="kernel-overview-label">
                {{ $t(digestOverviewLabelKey) }}
              </span>
              <span
                v-if="digestPreviewText"
                class="kernel-overview-copy min-w-0 truncate"
              >
                {{ digestPreviewText }}
              </span>
            </span>
          </div>

          <div
            v-if="hasTimeline"
            class="kernel-overview-group flex min-w-0 flex-1 items-center gap-2"
          >
            <span class="kernel-overview-icon shrink-0">
              <IconifyIcon icon="lucide:list-todo" class="size-3" />
            </span>
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="kernel-overview-label">
                {{ $t('common.globalAiChat.turnTimeline') }}
              </span>
              <span
                v-if="processPreviewText"
                class="kernel-overview-copy min-w-0 truncate"
              >
                {{ processPreviewText }}
              </span>
            </span>
            <span class="kernel-overview-meta shrink-0">
              {{
                $t('common.globalAiChat.turnStageCount', {
                  count: processStageCount,
                })
              }}
            </span>
          </div>
        </div>

        <span :class="['kernel-status-chip shrink-0', kernelStatusClass]">
          <IconifyIcon
            :icon="kernelStatusIcon"
            class="kernel-status-icon size-3"
            :class="
              props.msg.streaming || hasRunningTimelineStage
                ? 'kernel-status-spin'
                : ''
            "
          />
          <span class="truncate">{{ $t(kernelStatusLabelKey) }}</span>
        </span>

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
          class="space-y-2"
          :class="[
            compact ? 'px-2.5 pb-2.5 pt-2' : 'px-3 pb-3 pt-2.5',
            canCollapseKernel ? 'border-t border-border/12' : '',
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
  position: relative;
  border-color: hsl(var(--border) / 0.14);
  background:
    radial-gradient(
      circle at top right,
      hsl(var(--primary) / 0.08),
      transparent 24%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.985) 0%,
      hsl(var(--background) / 0.965) 100%
    );
  box-shadow: 0 18px 38px -36px hsl(var(--foreground) / 0.16);
}

.chat-message-kernel-overview {
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    transform 180ms ease;
}

.chat-message-kernel-overview:hover {
  background: hsl(var(--muted) / 0.18);
  transform: translateY(-1px);
}

.kernel-overview-group {
  min-width: 0;
  padding: 0.48rem 0.62rem;
  border: 1px solid hsl(var(--border) / 0.1);
  border-radius: 14px;
  background: hsl(var(--background) / 0.88);
  box-shadow: inset 0 1px 0 hsl(var(--background) / 0.6);
}

.kernel-overview-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 9999px;
  color: hsl(var(--primary) / 0.76);
  border: 1px solid hsl(var(--primary) / 0.12);
  background: hsl(var(--primary) / 0.05);
}

.kernel-overview-label {
  color: hsl(var(--muted-foreground) / 0.6);
  font-size: 0.52rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  line-height: 0.75rem;
}

.kernel-overview-copy {
  color: hsl(var(--foreground) / 0.74);
  font-size: 0.68rem;
  line-height: 0.98rem;
}

.kernel-overview-meta {
  color: hsl(var(--muted-foreground) / 0.56);
  border: 1px solid hsl(var(--border) / 0.08);
  background: hsl(var(--muted) / 0.18);
  border-radius: 9999px;
  padding: 0.1rem 0.36rem;
  font-size: 0.55rem;
  line-height: 0.82rem;
}

.kernel-status-chip {
  display: inline-flex;
  max-width: 9.5rem;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.52rem;
  border-radius: 9999px;
  border: 1px solid hsl(var(--border) / 0.1);
  font-size: 0.58rem;
  font-weight: 600;
  line-height: 0.8rem;
}

.kernel-status-running {
  color: hsl(var(--primary) / 0.82);
  border-color: hsl(var(--primary) / 0.16);
  background: hsl(var(--primary) / 0.08);
}

.kernel-status-completed {
  color: rgb(4 120 87 / 0.92);
  border-color: rgb(16 185 129 / 0.16);
  background: rgb(16 185 129 / 0.08);
}

.kernel-status-error {
  color: rgb(220 38 38 / 0.88);
  border-color: rgb(239 68 68 / 0.16);
  background: rgb(239 68 68 / 0.08);
}

.kernel-status-icon {
  flex-shrink: 0;
}

.kernel-status-spin {
  animation: kernel-status-spin 1.1s linear infinite;
}

.kernel-overview-chevron {
  color: hsl(var(--muted-foreground) / 0.44);
  border: 1px solid hsl(var(--border) / 0.1);
  background: hsl(var(--background) / 0.9);
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

@keyframes kernel-status-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>

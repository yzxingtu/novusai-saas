<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { ChatMessage } from '#/types/ai-chat';

import { computed, onBeforeUnmount, ref, watch } from 'vue';

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
import {
  getSafeErrorSurfaceMessage,
  getProcessHeadlineForStage,
  isTechnicalProcessErrorCopy,
  isNoopSkippedStage,
} from './turn-stage-presentation';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
    state?: null | TurnFlowState;
  }>(),
  {
    compact: false,
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

const KERNEL_AUTO_COLLAPSE_DELAY_MS = 220;

const resolvedState = computed(
  () => props.state ?? buildTurnFlowState(props.msg),
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
    if (isNoopSkippedStage(stage)) {
      return false;
    }
    if (
      stage.type === 'failed' &&
      isRecoverableProcessFailure(props.msg, resolvedState.value.flow)
    ) {
      return false;
    }
    if (
      stage.type === 'answer_assembly' &&
      (stage.status === 'completed' ||
        (stage.status === 'error' &&
          isRecoverableProcessFailure(props.msg, resolvedState.value.flow))) &&
      Boolean(
        resolvedState.value.answerCard ||
          hasReadableAnswerText(props.msg),
      )
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
const hasFinalAnswerText = computed(() => hasReadableAnswerText(props.msg));

function isFailureToken(value: unknown) {
  const normalized = normalizeOptionalString(value)?.toLocaleLowerCase();
  if (!normalized) {
    return false;
  }
  return (
    normalized === 'failed' ||
    normalized === 'error' ||
    normalized === 'untrusted_final_output_source' ||
    normalized.startsWith('provider_') ||
    normalized.startsWith('stream_execution_error') ||
    normalized.includes('failed') ||
    normalized.includes('error')
  );
}

function hasTerminalFailureState(
  msg: ChatMessage,
  flow: TurnFlowState['flow'],
) {
  if (
    msg.error ||
    msg.requestFailedRetry === true ||
    flow.finalStageStatus === 'error'
  ) {
    return true;
  }
  const turnOutcome = normalizeOptionalString(flow.turnOutcome)
    ?.toLocaleLowerCase();
  const failureKind = normalizeOptionalString(flow.failureKind);
  if (turnOutcome === 'failed') {
    return true;
  }
  if (turnOutcome === 'partial' && failureKind) {
    return true;
  }
  return [
    failureKind,
    flow.completionReason,
    flow.errorSurface?.errorType,
    flow.errorSurface?.message,
    flow.errorSurface?.summary,
  ].some((candidate) => isFailureToken(candidate));
}

const hasKernelFailure = computed(
  () =>
    hasTerminalFailureState(props.msg, resolvedState.value.flow) ||
    visibleKernelTimeline.value.some(
      (stage) =>
        stage.status === 'error' ||
        stage.status === 'interrupted' ||
        stage.type === 'failed',
    ),
);
const hasDigestContent = computed(() => hasDigestCard.value);
const kernelBodyLayout = computed(() =>
  !props.compact && hasDigestCard.value && hasTimeline.value
    ? 'split'
    : 'stacked',
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

function hasReadableAnswerText(msg: ChatMessage) {
  return Boolean(
    normalizeText(normalizeMergedTextPart(msg.content) || msg.content),
  );
}

function isRecoverableProcessFailure(
  msg: ChatMessage,
  flow: TurnFlowState['flow'],
) {
  if (!hasReadableAnswerText(msg) || msg.error || msg.streaming) {
    return false;
  }
  const messageRecord = msg as unknown as Record<string, unknown>;
  const candidates = [
    flow.failureKind,
    flow.completionReason,
    flow.errorSurface?.errorType,
    flow.errorSurface?.message,
    flow.errorSurface?.summary,
    messageRecord.failure_kind,
    messageRecord.failureKind,
    msg.completionReason,
    msg.terminationReason,
  ];
  return candidates.some((candidate) => isTechnicalProcessErrorCopy(candidate));
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
let kernelAutoCollapseTimer: ReturnType<typeof globalThis.setTimeout> | undefined;
const showKernelBody = computed(
  () => !canCollapseKernel.value || isKernelExpanded.value,
);
const digestPreviewText = computed(() => {
  const summary = normalizeText(resolvedState.value.answerCard?.summary);
  if (summary) {
    return truncatePreview(summary, 96);
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
    return truncatePreview(sectionPreview, 96);
  }

  const evidencePreview = normalizeText(
    resolvedState.value.selectedEvidence[0]?.label,
  );
  if (evidencePreview) {
    return truncatePreview(evidencePreview, 96);
  }

  const preparedPreview = normalizeText(preparedDigestBody.value);
  if (preparedPreview) {
    return truncatePreview(preparedPreview, 96);
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
const visibleProcessStages = computed(() => visibleKernelTimeline.value);
const processStageCount = computed(() => visibleProcessStages.value.length);
const processPreviewText = computed(() => {
  const errorMessage = normalizeText(
    getSafeErrorSurfaceMessage(resolvedState.value.flow.errorSurface),
  );
  if (errorMessage) {
    return truncatePreview(errorMessage, 64);
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
      return truncatePreview(preview, 64);
    }
  }

  return '';
});
const preferProcessOverview = computed(
  () => hasTimeline.value && hasFinalAnswerText.value && !props.msg.streaming,
);
const showProcessSubcopy = computed(
  () =>
    !preferProcessOverview.value &&
    Boolean(digestPreviewText.value) &&
    Boolean(processPreviewText.value),
);
const kernelHeadline = computed(
  () =>
    (preferProcessOverview.value
      ? processPreviewText.value || $t('common.globalAiChat.turnTimeline')
      : digestPreviewText.value) ||
    processPreviewText.value ||
    $t('common.globalAiChat.processing'),
);
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
const kernelEvidenceCount = computed(() =>
  hasKernelFailure.value ? 0 : resolvedState.value.selectedEvidence.length,
);

function syncKernelExpanded(nextExpanded: boolean) {
  if (isKernelExpanded.value === nextExpanded) {
    return;
  }
  isKernelExpanded.value = nextExpanded;
}

function clearKernelAutoCollapseTimer() {
  if (kernelAutoCollapseTimer === undefined) {
    return;
  }
  globalThis.clearTimeout(kernelAutoCollapseTimer);
  kernelAutoCollapseTimer = undefined;
}

function scheduleKernelAutoCollapse() {
  clearKernelAutoCollapseTimer();
  if (!canCollapseKernel.value) {
    return;
  }
  kernelAutoCollapseTimer = globalThis.setTimeout(() => {
    kernelAutoCollapseTimer = undefined;
    syncKernelExpanded(false);
  }, KERNEL_AUTO_COLLAPSE_DELAY_MS);
}

function toggleKernelExpanded() {
  clearKernelAutoCollapseTimer();
  if (!canCollapseKernel.value) {
    return;
  }
  syncKernelExpanded(!isKernelExpanded.value);
}

watch(
  messageIdentity,
  () => {
    clearKernelAutoCollapseTimer();
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
    if (isStreaming) {
      clearKernelAutoCollapseTimer();
      syncKernelExpanded(true);
      return;
    }
    scheduleKernelAutoCollapse();
  },
);

watch(canCollapseKernel, (collapsible) => {
  if (collapsible) {
    return;
  }
  clearKernelAutoCollapseTimer();
});

onBeforeUnmount(() => {
  clearKernelAutoCollapseTimer();
});

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
      v-if="hasDigestCard"
      data-testid="chat-message-kernel-header"
      class="chat-message-kernel-shell overflow-hidden rounded-[12px] border"
    >
      <button
        type="button"
        data-testid="chat-message-kernel-overview-toggle"
        class="chat-message-kernel-overview flex w-full min-w-0 items-start justify-between gap-2 text-left"
        :class="compact ? 'px-2 py-1.5' : 'px-2.5 py-2'"
        :aria-expanded="isKernelExpanded"
        @click="toggleKernelExpanded"
      >
        <div class="min-w-0 flex-1">
          <div class="flex min-w-0 flex-wrap items-center gap-1.5">
            <span
              v-if="hasDigestCard"
              class="kernel-overview-pill kernel-overview-pill-primary"
            >
              {{ $t(digestOverviewLabelKey) }}
            </span>
            <span v-if="hasTimeline" class="kernel-overview-pill">
              {{ $t('common.globalAiChat.turnTimeline') }}
            </span>
          </div>

          <div
            class="kernel-overview-headline mt-1 min-w-0 truncate"
            :class="
              compact
                ? 'text-[10px] leading-[1rem]'
                : 'text-[10.5px] leading-[1.08rem]'
            "
          >
            {{ kernelHeadline }}
          </div>

          <div class="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <span
              v-if="processStageCount > 0"
              class="kernel-overview-meta-chip shrink-0"
            >
              {{
                $t('common.globalAiChat.turnStageCount', {
                  count: processStageCount,
                })
              }}
            </span>
            <span
              v-if="kernelEvidenceCount > 0"
              class="kernel-overview-meta-chip shrink-0"
            >
              {{
                $t('common.globalAiChat.turnRetrievalSummary', {
                  count: kernelEvidenceCount,
                })
              }}
            </span>
            <span
              v-if="showProcessSubcopy"
              class="kernel-overview-subcopy truncate"
            >
              {{ processPreviewText }}
            </span>
          </div>
        </div>

        <div class="flex shrink-0 items-start gap-1.5">
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
            v-if="canCollapseKernel"
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
        </div>
      </button>

      <Transition name="chat-message-kernel-body">
        <div
          v-if="showKernelBody"
          data-testid="chat-message-kernel-body"
          class="kernel-body-layout"
          :data-layout="kernelBodyLayout"
          :class="[
            compact ? 'px-2.5 pb-2.5 pt-2' : 'px-3.5 pb-3.5 pt-2.5',
            canCollapseKernel ? 'border-t border-border/12' : '',
            kernelBodyLayout === 'split'
              ? 'kernel-body-layout-split'
              : 'space-y-2.5',
          ]"
        >
          <div
            v-if="hasDigestCard"
            data-testid="chat-message-kernel-digest-panel"
            class="space-y-1.5"
            :class="[
              kernelBodyLayout === 'split'
                ? 'kernel-detail-panel kernel-detail-panel-raised'
                : '',
            ]"
          >
            <div class="kernel-section-caption">
              {{ $t(digestOverviewLabelKey) }}
            </div>
            <EvidenceCard
              :compact="compact"
              :msg="msg"
              :state="resolvedState"
            />
          </div>

          <div
            v-if="hasTimeline"
            data-testid="chat-message-kernel-timeline-panel"
            class="space-y-1.5"
            :class="[
              kernelBodyLayout === 'split'
                ? 'kernel-detail-panel kernel-detail-panel-raised'
                : '',
              hasDigestCard && kernelBodyLayout !== 'split'
                ? 'border-t border-border/10 pt-2'
                : '',
            ]"
          >
            <div class="kernel-section-caption">
              {{ $t('common.globalAiChat.turnTimeline') }}
            </div>
            <TurnTimeline
              :compact="compact"
              inline
              :msg="msg"
              :state="resolvedState"
              @copy="(content) => emit('copy', content)"
            />
          </div>
        </div>
      </Transition>
    </div>

    <div
      v-else-if="hasTimeline"
      data-testid="chat-message-kernel-header"
      class="chat-message-kernel-standalone"
    >
      <TurnTimeline
        :compact="compact"
        :msg="msg"
        :state="resolvedState"
        @copy="(content) => emit('copy', content)"
      />
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
  border-color: hsl(var(--border) / 0.1);
  background: hsl(var(--muted) / 0.045);
  box-shadow: none;
}

.chat-message-kernel-standalone {
  min-width: 0;
  padding: 0.05rem 0;
}

.chat-message-kernel-overview {
  transition:
    background-color 160ms ease,
    border-color 160ms ease;
}

.chat-message-kernel-overview:hover {
  background: hsl(var(--muted) / 0.1);
}

.kernel-overview-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border-radius: 9999px;
  border: 0;
  background: transparent;
  color: hsl(var(--muted-foreground) / 0.62);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}

.kernel-overview-pill-primary {
  color: hsl(var(--primary) / 0.78);
}

.kernel-overview-headline {
  color: hsl(var(--foreground) / 0.76);
  font-weight: 500;
  letter-spacing: 0;
}

.kernel-overview-meta-chip {
  color: hsl(var(--muted-foreground) / 0.56);
  border: 0;
  background: transparent;
  border-radius: 9999px;
  padding: 0;
  font-size: 0.55rem;
  line-height: 0.8rem;
}

.kernel-overview-subcopy {
  min-width: 0;
  color: hsl(var(--muted-foreground) / 0.58);
  font-size: 0.6rem;
  line-height: 0.85rem;
}

.kernel-status-chip {
  display: inline-flex;
  max-width: 9rem;
  align-items: center;
  gap: 0.35rem;
  padding: 0.22rem 0.46rem;
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
  color: hsl(var(--muted-foreground) / 0.46);
  border: 0;
  background: transparent;
}

.kernel-section-caption {
  color: hsl(var(--muted-foreground) / 0.54);
  font-size: 0.55rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.kernel-body-layout-split {
  display: grid;
  grid-template-columns: minmax(0, 1.02fr) minmax(0, 0.98fr);
  gap: 0.65rem;
  align-items: start;
}

.kernel-detail-panel {
  min-width: 0;
}

.kernel-detail-panel-raised {
  padding: 0.62rem 0.68rem 0.68rem;
  border: 1px solid hsl(var(--border) / 0.08);
  border-radius: 12px;
  background: hsl(var(--background) / 0.72);
  box-shadow: none;
}

.chat-message-kernel-body-enter-active,
.chat-message-kernel-body-leave-active {
  transition: all 200ms ease;
}

.chat-message-kernel-body-enter-from,
.chat-message-kernel-body-leave-to {
  opacity: 0;
  transform: translateY(-3px);
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

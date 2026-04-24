<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed } from 'vue';

import { prepareMessageContent } from '#/components/business/ai-chat-panel/chat-message-display-preparation';

import ActionConsentGate from './ActionConsentGate.vue';
import EvidenceCard from './EvidenceCard.vue';
import { buildTurnFlowState } from './TurnFlowState';
import TurnTimeline from './TurnTimeline.vue';

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
const hasTimeline = computed(() => resolvedState.value.timeline.length > 0);
const hasDigestContent = computed(
  () => hasTimeline.value || hasDigestCard.value,
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
  <div class="space-y-2">
    <div
      v-if="hasDigestContent"
      data-testid="chat-message-kernel-header"
      class="chat-message-kernel-shell overflow-hidden rounded-[16px] border"
    >
      <div
        class="space-y-1"
        :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'"
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
  border-color: hsl(var(--border) / 0.18);
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.98) 0%,
    hsl(var(--muted) / 0.05) 100%
  );
  box-shadow: 0 14px 24px -32px hsl(var(--foreground) / 0.14);
}
</style>

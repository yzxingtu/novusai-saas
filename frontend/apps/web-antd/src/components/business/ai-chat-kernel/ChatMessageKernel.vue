<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed } from 'vue';

import ActionConsentGate from './ActionConsentGate.vue';
import EvidenceCard from './EvidenceCard.vue';
import { buildTurnFlowState } from './TurnFlowState';
import TurnTimeline from './TurnTimeline.vue';

const props = withDefaults(
  defineProps<{
    adminMode?: boolean;
    compact?: boolean;
    countdownNow?: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
    state?: null | TurnFlowState;
  }>(),
  {
    adminMode: false,
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
const hasDigestContent = computed(
  () =>
    resolvedState.value.timeline.length > 0 ||
    Boolean(resolvedState.value.answerCard?.summary) ||
    (resolvedState.value.answerCard?.sections?.length ?? 0) > 0 ||
    resolvedState.value.selectedEvidence.length > 0,
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
  <div class="space-y-2.5">
    <div
      v-if="hasDigestContent"
      data-testid="chat-message-kernel-header"
      class="chat-message-kernel-card overflow-hidden rounded-[16px] border border-border/24"
    >
      <div
        class="chat-message-kernel-stack space-y-1.5"
        :class="compact ? 'px-3 py-2.5' : 'px-3.5 py-3'"
      >
        <EvidenceCard
          :compact="compact"
          :msg="msg"
          :state="resolvedState"
        />
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

    <ActionConsentGate
      :action="resolvedState.pendingAction"
      :compact="compact"
      @approve="handleApprove"
      @reject="handleReject"
    />
    <slot v-if="adminMode" name="diagnostics"></slot>
  </div>
</template>

<style scoped>
.chat-message-kernel-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.94) 0%,
    hsl(var(--muted) / 0.08) 100%
  );
  box-shadow: 0 14px 32px -34px hsl(var(--foreground) / 0.18);
}
</style>

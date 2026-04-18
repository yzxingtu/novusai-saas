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
  <TurnTimeline
    :compact="compact"
    :countdown-now="countdownNow"
    :msg="msg"
    :pending-ops="pendingOps"
    :state="resolvedState"
    @copy="(content) => emit('copy', content)"
  />
  <EvidenceCard :compact="compact" :msg="msg" :state="resolvedState" />
  <ActionConsentGate
    :action="resolvedState.pendingAction"
    :compact="compact"
    @approve="handleApprove"
    @reject="handleReject"
  />
  <slot v-if="adminMode" name="diagnostics"></slot>
</template>

<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed } from 'vue';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

function normalizeDiagnosticText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

const BENIGN_TURN_OUTCOMES = new Set(['partial', 'success']);
const BENIGN_TERMINATION_REASONS = new Set([
  'budget_exit',
  'completed',
  'consent_pause',
  'interrupted',
  'stop',
]);

interface ContextSourceDisplayItem {
  active: boolean;
  key: string;
  label: string;
}

function formatContextSourceLabel(source: {
  kind?: string;
  metadata?: Record<string, unknown>;
  name?: string;
}) {
  const kind = normalizeDiagnosticText(source.kind);
  const name = normalizeDiagnosticText(source.name);
  if (kind && name) {
    return `${kind}:${name}`;
  }
  if (name) {
    return name;
  }
  if (kind) {
    return kind;
  }
  const metadata = source.metadata ?? {};
  const metadataName =
    normalizeDiagnosticText(metadata.name) ||
    normalizeDiagnosticText(metadata.title) ||
    normalizeDiagnosticText(metadata.knowledge_base_name) ||
    normalizeDiagnosticText(metadata.source);
  return metadataName;
}

const diagnosticTurnOutcome = computed(() =>
  normalizeDiagnosticText(props.msg.turnOutcome),
);
const diagnosticTerminationReason = computed(() => {
  return (
    normalizeDiagnosticText(props.msg.terminationReason) ||
    normalizeDiagnosticText(props.msg.completionReason)
  );
});
const diagnosticProtocolPath = computed(() =>
  normalizeDiagnosticText(props.msg.protocolPath),
);
const diagnosticSelectedTools = computed(() => {
  return (props.msg.selectedToolNames ?? [])
    .map((item) => normalizeDiagnosticText(item))
    .filter((item) => item.length > 0);
});
const diagnosticSelectedSkills = computed(() => {
  return (props.msg.selectedSkillNames ?? [])
    .map((item) => normalizeDiagnosticText(item))
    .filter((item) => item.length > 0);
});
const diagnosticContextSources = computed<ContextSourceDisplayItem[]>(() => {
  const list = props.msg.contextSources ?? [];
  return list
    .map((source, index) => {
      const label = formatContextSourceLabel(source);
      const key = `${source.kind || ''}-${source.name || ''}-${index}`;
      return {
        key,
        label: label || `#${index + 1}`,
        active: source.active !== false,
      };
    })
    .filter((item) => item.label.length > 0 && item.active);
});
const hasTurnDiagnostics = computed(() => {
  return Boolean(
    diagnosticTurnOutcome.value ||
    diagnosticTerminationReason.value ||
    diagnosticProtocolPath.value ||
    diagnosticSelectedTools.value.length > 0 ||
    diagnosticSelectedSkills.value.length > 0 ||
    diagnosticContextSources.value.length > 0,
  );
});
const shouldShowTurnDiagnostics = computed(() => {
  if (!hasTurnDiagnostics.value) {
    return false;
  }

  if (props.msg.error) {
    return false;
  }

  if (props.msg.requestFailedRetry) {
    return true;
  }

  const normalizedOutcome = diagnosticTurnOutcome.value.toLowerCase();
  if (normalizedOutcome && !BENIGN_TURN_OUTCOMES.has(normalizedOutcome)) {
    return true;
  }

  const normalizedTerminationReason =
    diagnosticTerminationReason.value.toLowerCase();
  if (
    normalizedTerminationReason &&
    !BENIGN_TERMINATION_REASONS.has(normalizedTerminationReason)
  ) {
    return true;
  }

  return false;
});
</script>

<template>
  <div
    v-if="shouldShowTurnDiagnostics"
    class="rounded-xl border border-border/30 bg-accent/10"
    :class="
      compact ? 'mb-1 space-y-1 px-2 py-1.5' : 'mb-2 space-y-1.5 px-3 py-2'
    "
  >
    <div class="flex flex-wrap items-center gap-1.5">
      <span
        v-if="diagnosticTurnOutcome"
        class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
      >
        <span class="font-mono text-[10px] text-muted-foreground">{{
          $t('common.globalAiChat.diagnosticTurnOutcomeLabel')
        }}</span>
        <span class="font-medium text-foreground">{{
          diagnosticTurnOutcome
        }}</span>
      </span>
      <span
        v-if="diagnosticTerminationReason"
        class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
      >
        <span class="font-mono text-[10px] text-muted-foreground">{{
          $t('common.globalAiChat.diagnosticTerminationReasonLabel')
        }}</span>
        <span class="font-medium text-foreground">{{
          diagnosticTerminationReason
        }}</span>
      </span>
      <span
        v-if="diagnosticProtocolPath"
        class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
      >
        <span class="font-mono text-[10px] text-muted-foreground">{{
          $t('common.globalAiChat.diagnosticProtocolPathLabel')
        }}</span>
        <span class="font-medium text-foreground">{{
          diagnosticProtocolPath
        }}</span>
      </span>
    </div>
    <div
      v-if="diagnosticSelectedTools.length > 0"
      class="flex flex-wrap items-center gap-1.5"
    >
      <span class="font-mono text-[10px] text-muted-foreground">{{
        $t('common.globalAiChat.diagnosticSelectedToolsLabel')
      }}</span>
      <span
        v-for="toolName in diagnosticSelectedTools"
        :key="toolName"
        class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
      >
        {{ toolName }}
      </span>
    </div>
    <div
      v-if="diagnosticSelectedSkills.length > 0"
      class="flex flex-wrap items-center gap-1.5"
    >
      <span class="font-mono text-[10px] text-muted-foreground">{{
        $t('common.globalAiChat.diagnosticSelectedSkillsLabel')
      }}</span>
      <span
        v-for="skillName in diagnosticSelectedSkills"
        :key="skillName"
        class="inline-flex items-center rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-600 dark:text-sky-300"
      >
        {{ skillName }}
      </span>
    </div>
    <div
      v-if="diagnosticContextSources.length > 0"
      class="flex flex-wrap items-center gap-1.5"
    >
      <span class="font-mono text-[10px] text-muted-foreground">{{
        $t('common.globalAiChat.diagnosticContextSourcesLabel')
      }}</span>
      <span
        v-for="source in diagnosticContextSources"
        :key="source.key"
        class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px]"
        :class="
          source.active
            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
            : 'bg-muted text-muted-foreground'
        "
      >
        {{ source.label }}
      </span>
    </div>
  </div>
</template>

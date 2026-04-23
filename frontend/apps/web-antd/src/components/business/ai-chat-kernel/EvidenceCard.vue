<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type {
  TurnAnswerCard,
  TurnAnswerCardSection,
} from '#/components/business/ai-chat-panel/types';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
    state: TurnFlowState;
  }>(),
  {
    compact: false,
  },
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

function isLikelyRawUrl(value: string) {
  return /^https?:\/\//i.test(value);
}

function extractHostLabel(url?: string) {
  const href = normalizeText(url);
  if (!href) {
    return '';
  }
  try {
    const parsed = new URL(href);
    return parsed.hostname.trim().replace(/^www\./i, '');
  } catch {
    return '';
  }
}

const preparedEvidence = computed(() => {
  const seen = new Set<string>();
  return props.state.selectedEvidence
    .filter((item) => {
      const dedupeKey = item.href || item.id;
      if (!dedupeKey || seen.has(dedupeKey)) {
        return false;
      }
      seen.add(dedupeKey);
      return true;
    })
    .map((item) => {
      const hostLabel =
        normalizeText(item.hostLabel) || extractHostLabel(item.href);
      const normalizedLabel = normalizeText(item.label);
      const label =
        normalizedLabel && !isLikelyRawUrl(normalizedLabel)
          ? normalizedLabel
          : hostLabel || $t('common.globalAiChat.turnEvidenceTitle');
      return {
        ...item,
        hostLabel: hostLabel && hostLabel !== label ? hostLabel : '',
        label,
      };
    });
});

function normalizeAnswerSections(
  sections: TurnAnswerCardSection[] | undefined,
): TurnAnswerCardSection[] {
  return (sections ?? [])
    .map((section, index): null | TurnAnswerCardSection => {
      const title = normalizeText(section.title);
      const body =
        normalizeText(section.body) || normalizeText(section.content);
      if (!title && !body) {
        return null;
      }
      return {
        ...(body ? { body, content: body } : {}),
        ...(section.id
          ? { id: section.id }
          : { id: `answer-section-${index}` }),
        ...(title ? { title } : {}),
      };
    })
    .filter((section): section is TurnAnswerCardSection => section !== null);
}

function getAnswerAssemblyStage(): TurnFlowStageForDisplay | undefined {
  for (let index = props.state.timeline.length - 1; index >= 0; index -= 1) {
    const stage = props.state.timeline[index];
    if (!stage || stage.type !== 'answer_assembly') {
      continue;
    }
    if (stage.status === 'error' || stage.status === 'skipped') {
      continue;
    }
    return stage;
  }
  return undefined;
}

function buildProvisionalAnswerCard(
  stage: TurnFlowStageForDisplay | undefined,
): TurnAnswerCard | undefined {
  if (!stage) {
    return undefined;
  }
  const summary = normalizeText(stage.summary);
  const detailLines = (stage.detailLines ?? [])
    .map((line) => normalizeText(line))
    .filter((line) => line.length > 0 && line !== summary);
  const sections = detailLines.map((line, index) => ({
    body: line,
    content: line,
    id: `provisional-answer-section-${stage.id}-${index}`,
  }));
  if (!summary && sections.length === 0) {
    return undefined;
  }
  return {
    ...(summary ? { summary } : {}),
    ...(sections.length > 0 ? { sections } : {}),
  };
}

const messageIdentity = computed(() => resolveMessageIdentity(props.msg));
const stickyProvisionalAnswerCard = ref<TurnAnswerCard | undefined>(undefined);
const provisionalAnswerStage = computed(() => getAnswerAssemblyStage());
const liveProvisionalAnswerCandidate = computed(() => {
  if (!props.msg.streaming) {
    return undefined;
  }
  if (!provisionalAnswerStage.value) {
    return undefined;
  }
  return buildProvisionalAnswerCard(provisionalAnswerStage.value);
});

watch(
  messageIdentity,
  () => {
    stickyProvisionalAnswerCard.value = undefined;
  },
  { immediate: true },
);

const displayAnswerCard = computed(
  () =>
    props.state.answerCard ??
    liveProvisionalAnswerCandidate.value ??
    stickyProvisionalAnswerCard.value,
);
const displayAnswerSummary = computed(() =>
  normalizeText(displayAnswerCard.value?.summary),
);
const displayAnswerSections = computed(() =>
  normalizeAnswerSections(displayAnswerCard.value?.sections),
);
const normalizedMessageBody = computed(() =>
  normalizeText(
    normalizeMergedTextPart(props.msg.content) || props.msg.content,
  ),
);
watch(
  [
    () => props.state.answerCard,
    liveProvisionalAnswerCandidate,
    normalizedMessageBody,
    () => props.msg.streaming,
  ],
  ([canonicalAnswerCard, candidate, messageBody, isStreaming]) => {
    if (canonicalAnswerCard) {
      stickyProvisionalAnswerCard.value = undefined;
      return;
    }
    if (candidate) {
      stickyProvisionalAnswerCard.value = candidate;
      return;
    }
    if (!isStreaming && messageBody) {
      stickyProvisionalAnswerCard.value = undefined;
    }
  },
  { immediate: true },
);
const isProvisionalAnswerCard = computed(
  () =>
    !props.state.answerCard &&
    Boolean(
      liveProvisionalAnswerCandidate.value ?? stickyProvisionalAnswerCard.value,
    ),
);
const hasAnswerSummary = computed(() => Boolean(displayAnswerSummary.value));
const hasAnswerSections = computed(
  () => displayAnswerSections.value.length > 0,
);
const hasEvidence = computed(() => preparedEvidence.value.length > 0);
const digestLabelKey = computed(() =>
  hasAnswerSummary.value || hasAnswerSections.value
    ? 'common.globalAiChat.turnAnswerCardTitle'
    : 'common.globalAiChat.turnEvidenceTitle',
);
const isRedundantAnswerCard = computed(() => {
  if (props.msg.streaming || hasEvidence.value) {
    return false;
  }
  const messageBody = normalizedMessageBody.value;
  if (!messageBody) {
    return false;
  }

  const summaryMatches =
    !displayAnswerSummary.value || displayAnswerSummary.value === messageBody;
  if (!summaryMatches) {
    return false;
  }

  if (displayAnswerSections.value.length === 0) {
    return Boolean(displayAnswerSummary.value);
  }

  return displayAnswerSections.value.every((section) => {
    const sectionBody =
      normalizeText(section.body) || normalizeText(section.content);
    return sectionBody === messageBody;
  });
});
const shouldShow = computed(
  () =>
    !isRedundantAnswerCard.value &&
    (hasAnswerSummary.value || hasAnswerSections.value || hasEvidence.value),
);
const provisionalStatusLabelKey = computed(() =>
  props.msg.streaming
    ? 'common.globalAiChat.turnStageStatus.running'
    : 'common.globalAiChat.turnStageStatus.completed',
);

function getEvidenceIcon(kind: string) {
  if (kind === 'knowledge_base') {
    return 'lucide:library';
  }
  if (kind === 'web') {
    return 'lucide:globe';
  }
  if (kind === 'page') {
    return 'lucide:monitor';
  }
  if (kind === 'memory') {
    return 'lucide:brain';
  }
  return 'lucide:wrench';
}
</script>

<template>
  <div
    v-if="shouldShow"
    data-testid="chat-message-kernel-evidence"
    class="min-w-0"
  >
    <div
      class="flex min-w-0 flex-wrap items-center gap-1.5"
      :class="compact ? 'text-[10px]' : 'text-[10px]'"
    >
      <span class="font-medium uppercase tracking-[0.1em] text-muted-foreground/60">
        {{ $t(digestLabelKey) }}
      </span>
      <span
        v-if="isProvisionalAnswerCard"
        data-testid="chat-message-kernel-evidence-live-state"
        class="inline-flex items-center rounded-full border border-primary/16 bg-primary/[0.08] px-1.5 py-0.5 text-[9px] font-medium text-primary"
        :class="msg.streaming ? 'tc-pill-pulse' : ''"
      >
        {{ $t(provisionalStatusLabelKey) }}
      </span>
    </div>

    <p
      v-if="displayAnswerSummary"
      class="mt-1 line-clamp-2 text-foreground/84"
      :class="compact ? 'text-[11px] leading-5' : 'text-[11px] leading-5'"
    >
      {{ displayAnswerSummary }}
    </p>

    <div
      v-else-if="displayAnswerSections.length > 0"
      class="mt-1 space-y-1"
    >
      <div
        v-for="section in displayAnswerSections.slice(0, 2)"
        :key="section.id || section.title || section.body || section.content"
      >
        <p
          v-if="section.title"
          class="text-[10px] font-medium text-foreground/72"
        >
          {{ section.title }}
        </p>
        <p
          class="line-clamp-2 text-muted-foreground/72"
          :class="compact ? 'text-[10px] leading-5' : 'text-[10px] leading-5'"
        >
          {{ section.body || section.content }}
        </p>
      </div>
    </div>

    <div v-if="hasEvidence" class="mt-1.5 flex flex-wrap gap-1">
      <component
        v-for="item in preparedEvidence"
        :key="item.id"
        :is="item.href ? 'a' : 'span'"
        :href="item.href || undefined"
        :target="item.href ? '_blank' : undefined"
        :rel="item.href ? 'noopener noreferrer' : undefined"
        :title="item.label"
        class="inline-flex max-w-full items-center gap-1 rounded-full border border-border/18 bg-background/80 text-foreground/70 transition-colors"
        :class="[
          compact ? 'px-2 py-0.5 text-[9px]' : 'px-2 py-0.5 text-[10px]',
          item.href ? 'hover:border-primary/22 hover:bg-primary/[0.06] hover:text-primary' : '',
        ]"
      >
        <IconifyIcon
          :icon="getEvidenceIcon(item.kind)"
          class="shrink-0 text-primary/72"
          :class="compact ? 'size-2.5' : 'size-2.5'"
        />
        <span class="min-w-0 truncate">{{ item.label }}</span>
      </component>
      <span
        v-if="state.hiddenEvidenceCount > 0"
        class="inline-flex items-center rounded-full border border-dashed border-border/28 bg-background/72 px-2 py-0.5 text-[9px] text-muted-foreground"
      >
        +{{ state.hiddenEvidenceCount }}
      </span>
    </div>
  </div>
</template>

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
      const body = normalizeText(section.body) || normalizeText(section.content);
      if (!title && !body) {
        return null;
      }
      return {
        ...(body ? { body, content: body } : {}),
        ...(section.id ? { id: section.id } : { id: `answer-section-${index}` }),
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

watch(
  [() => props.state.answerCard, liveProvisionalAnswerCandidate],
  ([canonicalAnswerCard, candidate]) => {
    if (canonicalAnswerCard) {
      stickyProvisionalAnswerCard.value = undefined;
      return;
    }
    if (candidate) {
      stickyProvisionalAnswerCard.value = candidate;
    }
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
const isProvisionalAnswerCard = computed(
  () =>
    !props.state.answerCard &&
    Boolean(
      liveProvisionalAnswerCandidate.value ?? stickyProvisionalAnswerCard.value,
    ),
);
const hasAnswerSummary = computed(() => Boolean(displayAnswerSummary.value));
const hasAnswerSections = computed(() => displayAnswerSections.value.length > 0);
const hasEvidence = computed(() => preparedEvidence.value.length > 0);
const shouldShow = computed(
  () => hasAnswerSummary.value || hasAnswerSections.value || hasEvidence.value,
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
    class="overflow-hidden rounded-xl border border-border/25 bg-background/70"
    :class="compact ? 'mb-1.5' : 'mb-2'"
  >
    <div
      class="flex items-center gap-1.5 border-b border-border/20 text-muted-foreground/80"
      :class="compact ? 'px-2.5 py-1.5 text-[11px]' : 'px-3 py-2 text-xs'"
    >
      <IconifyIcon
        icon="lucide:file-check-2"
        :class="compact ? 'size-3' : 'size-3.5'"
      />
      <span class="font-medium">{{
        $t('common.globalAiChat.turnAnswerCardTitle')
      }}</span>
      <span
        v-if="isProvisionalAnswerCard"
        data-testid="chat-message-kernel-evidence-live-state"
        class="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-[1px] font-medium text-primary"
        :class="[
          compact ? 'text-[9px]' : 'text-[10px]',
          msg.streaming ? 'tc-pill-pulse' : '',
        ]"
      >
        {{ $t(provisionalStatusLabelKey) }}
      </span>
    </div>

    <div class="space-y-2" :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'">
      <p
        v-if="displayAnswerSummary"
        class="leading-relaxed text-foreground/90"
        :class="compact ? 'text-[11px]' : 'text-xs'"
      >
        {{ displayAnswerSummary }}
      </p>

      <div v-if="displayAnswerSections.length" class="space-y-1.5">
        <div
          v-for="section in displayAnswerSections"
          :key="section.id || section.title || section.body || section.content"
          class="rounded-lg border border-border/20 bg-accent/20"
          :class="compact ? 'px-2 py-1.5' : 'px-2.5 py-2'"
        >
          <p
            v-if="section.title"
            class="font-medium text-foreground/90"
            :class="compact ? 'text-[11px]' : 'text-xs'"
          >
            {{ section.title }}
          </p>
          <p
            class="text-muted-foreground/90"
            :class="compact ? 'text-[11px]' : 'text-xs'"
          >
            {{ section.body || section.content }}
          </p>
        </div>
      </div>

      <div v-if="hasEvidence" class="space-y-1.5">
        <p
          class="text-muted-foreground/75"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          {{ $t('common.globalAiChat.turnEvidenceTitle') }}
        </p>
        <div class="flex flex-wrap gap-1.5">
          <component
            v-for="item in preparedEvidence"
            :key="item.id"
            :is="item.href ? 'a' : 'span'"
            :href="item.href || undefined"
            :target="item.href ? '_blank' : undefined"
            :rel="item.href ? 'noopener noreferrer' : undefined"
            :title="item.label"
            class="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border/30 bg-accent/20 text-foreground/85 shadow-sm transition-colors"
            :class="[
              compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]',
              item.href ? 'hover:bg-accent/45 hover:text-primary' : '',
            ]"
          >
            <IconifyIcon
              :icon="getEvidenceIcon(item.kind)"
              class="shrink-0 text-muted-foreground/70"
              :class="compact ? 'size-2.5' : 'size-3'"
            />
            <span class="min-w-0 truncate font-medium">{{ item.label }}</span>
            <span
              v-if="item.hostLabel"
              class="inline-flex shrink-0 items-center rounded-full bg-background/85 px-1.5 py-[1px] text-[9px] text-muted-foreground/90"
            >
              {{ item.hostLabel }}
            </span>
            <IconifyIcon
              v-if="item.href"
              icon="lucide:external-link"
              class="shrink-0 text-muted-foreground/55"
              :class="compact ? 'size-2.5' : 'size-3'"
            />
          </component>
          <span
            v-if="state.hiddenEvidenceCount > 0"
            class="inline-flex items-center rounded-full border border-dashed border-border/40 bg-background/70 text-muted-foreground"
            :class="
              compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]'
            "
          >
            +{{ state.hiddenEvidenceCount }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

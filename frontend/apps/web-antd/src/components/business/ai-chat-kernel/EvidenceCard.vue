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

import { prepareMessageContent } from '#/components/business/ai-chat-panel/chat-message-display-preparation';
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

function normalizeComparableAnswerText(value: string) {
  return value.normalize('NFKC').replaceAll(/\s+/gu, ' ').trim();
}

function normalizeCompactAnswerText(value: string) {
  return value.normalize('NFKC').replaceAll(/\s+/gu, '');
}

function isSameAnswerText(left: string, right: string) {
  return (
    normalizeComparableAnswerText(left) ===
      normalizeComparableAnswerText(right) ||
    normalizeCompactAnswerText(left) === normalizeCompactAnswerText(right)
  );
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
const digestExpanded = ref(false);
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
const preparedTranscriptDigest = computed(() => {
  if (props.state.timeline.length > 0) {
    return '';
  }
  const prepared = prepareMessageContent(props.msg);
  if (prepared.suppressed) {
    return '';
  }
  return normalizeText(prepared.bodyMarkdown);
});
const fallbackAnswerSummary = computed(() => {
  if (
    props.msg.streaming ||
    displayAnswerSummary.value ||
    displayAnswerSections.value.length > 0 ||
    hasEvidence.value
  ) {
    return '';
  }
  const safeBody = preparedTranscriptDigest.value;
  if (!safeBody) {
    return '';
  }
  return safeBody.length > 180
    ? `${safeBody.slice(0, 179).trimEnd()}…`
    : safeBody;
});
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
const hasAnswerSummary = computed(() =>
  Boolean(displayAnswerSummary.value || fallbackAnswerSummary.value),
);
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
  if (fallbackAnswerSummary.value) {
    return false;
  }
  if (hasEvidence.value) {
    return false;
  }
  const messageBody = normalizedMessageBody.value;
  if (!messageBody) {
    return false;
  }

  const summaryMatches =
    !displayAnswerSummary.value ||
    isSameAnswerText(displayAnswerSummary.value, messageBody);
  if (!summaryMatches) {
    return false;
  }

  if (displayAnswerSections.value.length === 0) {
    return Boolean(displayAnswerSummary.value);
  }

  return displayAnswerSections.value.every((section) => {
    const sectionBody =
      normalizeText(section.body) || normalizeText(section.content);
    return isSameAnswerText(sectionBody, messageBody);
  });
});
const shouldShow = computed(
  () =>
    !isRedundantAnswerCard.value &&
    (hasAnswerSummary.value || hasAnswerSections.value || hasEvidence.value),
);
const isLiveDigest = computed(
  () => props.msg.streaming === true || isProvisionalAnswerCard.value,
);
const digestPreviewText = computed(() => {
  const summary = displayAnswerSummary.value || fallbackAnswerSummary.value;
  if (summary) {
    return summary;
  }

  const firstSection = displayAnswerSections.value[0];
  if (firstSection) {
    const sectionPreview =
      normalizeText(firstSection.title) ||
      normalizeText(firstSection.body) ||
      normalizeText(firstSection.content);
    if (sectionPreview) {
      return sectionPreview;
    }
  }

  return preparedEvidence.value[0]?.label ?? '';
});
const canToggleDigest = computed(() => shouldShow.value && !isLiveDigest.value);
const showDigestBody = computed(
  () => !canToggleDigest.value || digestExpanded.value,
);
const provisionalStatusLabelKey = computed(() =>
  props.msg.streaming
    ? 'common.globalAiChat.turnStageStatus.running'
    : 'common.globalAiChat.turnStageStatus.completed',
);

function syncDigestExpanded(nextExpanded: boolean) {
  if (digestExpanded.value === nextExpanded) {
    return;
  }
  digestExpanded.value = nextExpanded;
}

function toggleDigestExpanded() {
  if (!canToggleDigest.value) {
    return;
  }
  syncDigestExpanded(!digestExpanded.value);
}

watch(
  messageIdentity,
  () => {
    syncDigestExpanded(isLiveDigest.value);
  },
  { immediate: true },
);

watch(isLiveDigest, (liveDigest, previousLiveDigest) => {
  if (liveDigest === previousLiveDigest) {
    return;
  }
  syncDigestExpanded(liveDigest);
});

function getEvidenceIcon(kind: string) {
  if (kind === 'knowledge_base') {
    return 'lucide:library';
  }
  if (kind === 'document') {
    return 'lucide:link';
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
    <button
      v-if="canToggleDigest"
      type="button"
      data-testid="turn-digest-toggle"
      class="turn-digest-toggle flex w-full min-w-0 items-center gap-2 rounded-[14px] px-1.5 py-1.5 text-left"
      :aria-expanded="digestExpanded"
      @click="toggleDigestExpanded"
    >
      <span
        class="digest-label inline-flex items-center rounded-full px-1.5 py-0.5 font-medium uppercase tracking-[0.12em]"
        :class="compact ? 'text-[9px]' : 'text-[9.5px]'"
      >
        {{ $t(digestLabelKey) }}
      </span>
      <span
        v-if="digestPreviewText"
        class="text-foreground/72 min-w-0 flex-1 truncate"
        :class="compact ? 'text-[10.5px]' : 'text-[11px]'"
      >
        {{ digestPreviewText }}
      </span>
      <span
        v-if="hasEvidence"
        class="digest-evidence-count inline-flex items-center rounded-full px-1.5 py-0.5 text-[9.5px]"
      >
        {{ preparedEvidence.length + state.hiddenEvidenceCount }}
      </span>
      <span
        class="digest-chevron inline-flex shrink-0 items-center justify-center rounded-full p-1"
      >
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-3 transition-transform duration-200"
          :style="{
            transform: digestExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }"
        />
      </span>
    </button>

    <div
      v-else
      class="flex min-w-0 flex-wrap items-center gap-1.5"
      :class="compact ? 'text-[9px]' : 'text-[9.5px]'"
    >
      <span
        class="digest-label inline-flex items-center rounded-full px-1.5 py-0.5 font-medium uppercase tracking-[0.12em]"
      >
        {{ $t(digestLabelKey) }}
      </span>
      <span
        v-if="isProvisionalAnswerCard"
        data-testid="chat-message-kernel-evidence-live-state"
        class="digest-live-state inline-flex items-center rounded-full border px-1.5 py-0.5 text-[9px] font-medium text-primary"
        :class="msg.streaming ? 'tc-pill-pulse' : ''"
      >
        {{ $t(provisionalStatusLabelKey) }}
      </span>
    </div>

    <Transition name="turn-digest-body">
      <div
        v-if="showDigestBody"
        data-testid="turn-digest-body"
        class="turn-digest-body min-w-0 space-y-1.5"
      >
        <p
          v-if="displayAnswerSummary || fallbackAnswerSummary"
          class="digest-summary line-clamp-2"
          :class="
            compact
              ? 'text-[10.5px] leading-[1.18rem]'
              : 'text-[11px] leading-[1.24rem]'
          "
        >
          {{ displayAnswerSummary || fallbackAnswerSummary }}
        </p>

        <div v-else-if="displayAnswerSections.length > 0" class="space-y-1">
          <div
            v-for="section in displayAnswerSections.slice(0, 2)"
            :key="
              section.id || section.title || section.body || section.content
            "
          >
            <p
              v-if="section.title"
              class="text-foreground/56 text-[9.5px] font-medium"
            >
              {{ section.title }}
            </p>
            <p
              class="digest-section-copy line-clamp-2"
              :class="
                compact
                  ? 'text-[10px] leading-[1.14rem]'
                  : 'text-[10.5px] leading-[1.2rem]'
              "
            >
              {{ section.body || section.content }}
            </p>
          </div>
        </div>

        <div v-if="hasEvidence" class="flex flex-wrap gap-1">
          <component
            v-for="item in preparedEvidence"
            :key="item.id"
            :is="item.href ? 'a' : 'span'"
            :href="item.href || undefined"
            :target="item.href ? '_blank' : undefined"
            :rel="item.href ? 'noopener noreferrer' : undefined"
            :title="item.label"
            class="digest-evidence-chip inline-flex max-w-full items-center gap-1 rounded-full border transition-colors"
            :class="[
              compact ? 'px-2 py-0.5 text-[9.5px]' : 'px-2 py-0.5 text-[10px]',
              item.href
                ? 'hover:border-primary/20 hover:bg-primary/[0.05] hover:text-primary'
                : '',
            ]"
          >
            <IconifyIcon
              :icon="getEvidenceIcon(item.kind)"
              class="text-primary/66 size-2.5 shrink-0"
            />
            <span class="min-w-0 truncate">{{ item.label }}</span>
          </component>
          <span
            v-if="state.hiddenEvidenceCount > 0"
            class="digest-evidence-more inline-flex items-center rounded-full border border-dashed px-2 py-0.5 text-[9.5px]"
          >
            +{{ state.hiddenEvidenceCount }}
          </span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.turn-digest-toggle {
  border: 1px solid transparent;
  background: transparent;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    color 160ms ease;
}

.turn-digest-toggle:hover {
  border-color: hsl(var(--border) / 0.08);
  background: hsl(var(--muted) / 0.14);
}

.digest-label {
  color: hsl(var(--muted-foreground) / 0.58);
  border: 1px solid hsl(var(--primary) / 0.12);
  background: hsl(var(--primary) / 0.05);
}

.digest-live-state {
  border-color: hsl(var(--primary) / 0.16);
  background: hsl(var(--primary) / 0.08);
}

.digest-evidence-count {
  color: hsl(var(--muted-foreground) / 0.54);
  border: 1px solid hsl(var(--border) / 0.08);
  background: hsl(var(--muted) / 0.18);
}

.digest-chevron {
  color: hsl(var(--muted-foreground) / 0.46);
  border: 1px solid hsl(var(--border) / 0.1);
  background: hsl(var(--background) / 0.88);
}

.turn-digest-toggle:hover .digest-chevron {
  color: hsl(var(--primary) / 0.76);
  border-color: hsl(var(--primary) / 0.16);
}

.turn-digest-body {
  margin-top: 0.3rem;
  padding-left: 0.15rem;
}

.turn-digest-body-enter-active,
.turn-digest-body-leave-active {
  overflow: hidden;
  transition:
    max-height 180ms ease,
    opacity 160ms ease,
    transform 180ms ease,
    margin-top 180ms ease;
}

.turn-digest-body-enter-from,
.turn-digest-body-leave-to {
  max-height: 0;
  opacity: 0;
  margin-top: 0;
  transform: translateY(-3px);
}

.turn-digest-body-enter-to,
.turn-digest-body-leave-from {
  max-height: 14rem;
  opacity: 1;
  margin-top: 0.3rem;
  transform: translateY(0);
}

.digest-summary {
  color: hsl(var(--foreground) / 0.82);
}

.digest-section-copy {
  color: hsl(var(--muted-foreground) / 0.64);
}

.digest-evidence-chip {
  border-color: hsl(var(--border) / 0.12);
  color: hsl(var(--foreground) / 0.68);
  background: hsl(var(--background) / 0.86);
}

.digest-evidence-more {
  border-color: hsl(var(--border) / 0.16);
  color: hsl(var(--muted-foreground) / 0.72);
  background: hsl(var(--background) / 0.9);
}
</style>

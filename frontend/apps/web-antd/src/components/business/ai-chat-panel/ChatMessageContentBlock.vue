<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

import { prepareMessageContent } from './chat-message-display-preparation';
import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    index: number;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

/** Long message fold: keep very long replies readable without feeling truncated / 长消息折叠阈值 */
const COLLAPSE_THRESHOLD = 1600;
const SOURCE_HEADER_LABELS = new Set([
  'links',
  'reference',
  'references',
  'sources',
  '参考',
  '来源',
  '资料来源',
  '链接',
]);

function asRecord(value: unknown): null | Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function pickPreparedContentBody(msg: ChatMessage): string | undefined {
  const messageRecord = msg as unknown as Record<string, unknown>;
  const directPreparedFields = [
    messageRecord.preparedContentBody,
    messageRecord.prepared_content_body,
    messageRecord.preparedContent,
    messageRecord.prepared_content,
    messageRecord.contentBody,
    messageRecord.content_body,
  ];
  for (const candidate of directPreparedFields) {
    const normalized = normalizeOptionalString(candidate);
    if (normalized) {
      return normalized;
    }
  }

  const metadata = asRecord(messageRecord.metadata);
  if (metadata) {
    const metadataPreparedFields = [
      metadata.prepared_content_body,
      metadata.preparedContentBody,
      metadata.prepared_content,
      metadata.preparedContent,
      metadata.content_body,
      metadata.contentBody,
    ];
    for (const candidate of metadataPreparedFields) {
      const normalized = normalizeOptionalString(candidate);
      if (normalized) {
        return normalized;
      }
    }
  }

  return undefined;
}

function stripListPrefix(line: string): string {
  const trimmedStart = line.trimStart();
  if (
    (trimmedStart.startsWith('-') || trimmedStart.startsWith('*')) &&
    /\s/u.test(trimmedStart[1] ?? '')
  ) {
    return trimmedStart.slice(2).trimStart();
  }
  return trimmedStart;
}

function stripTrailingColon(value: string): string {
  let normalized = value.trimEnd();
  while (normalized.endsWith(':') || normalized.endsWith('：')) {
    normalized = normalized.slice(0, -1).trimEnd();
  }
  return normalized;
}

function isSourceHeaderLine(line: string): boolean {
  const normalized = stripTrailingColon(stripListPrefix(line))
    .trim()
    .toLocaleLowerCase();
  return SOURCE_HEADER_LABELS.has(normalized);
}

function isReferenceLine(line: string): boolean {
  const candidate = stripListPrefix(line).trim();
  return candidate.includes('http://') || candidate.includes('https://');
}

function stripTrailingSourceBlock(content: string) {
  const normalized = content.replaceAll('\r\n', '\n').trimEnd();
  if (!normalized) {
    return normalized;
  }

  const lines = normalized.split('\n');
  const removableIndexes = new Set<number>();
  let tailEnd = lines.length - 1;
  while (tailEnd >= 0 && lines[tailEnd]?.trim() === '') {
    tailEnd -= 1;
  }

  let foundReference = false;
  for (let index = tailEnd; index >= 0; index -= 1) {
    const line = lines[index] ?? '';
    if (line.trim() === '') {
      if (foundReference) {
        removableIndexes.add(index);
      }
      continue;
    }
    if (isReferenceLine(line)) {
      foundReference = true;
      removableIndexes.add(index);
      continue;
    }
    if (foundReference && isSourceHeaderLine(line)) {
      removableIndexes.add(index);
    }
    break;
  }

  if (!foundReference) {
    return normalized;
  }

  return lines
    .filter((_, index) => !removableIndexes.has(index))
    .join('\n')
    .trimEnd();
}

const preparedMessageContent = computed(() => prepareMessageContent(props.msg));

const preparedContentBody = computed(() => {
  if (preparedMessageContent.value.suppressed) {
    return '';
  }
  const normalizedPreparedBody = stripTrailingSourceBlock(
    preparedMessageContent.value.bodyMarkdown,
  );
  if (
    preparedMessageContent.value.references.length > 0 ||
    normalizedPreparedBody
  ) {
    return normalizedPreparedBody;
  }
  const preparedBody = pickPreparedContentBody(props.msg);
  if (preparedBody) {
    return stripTrailingSourceBlock(preparedBody);
  }
  return stripTrailingSourceBlock(
    normalizeMergedTextPart(props.msg.content) || props.msg.content,
  );
});

const hasContentBody = computed(() => Boolean(preparedContentBody.value));
const canCollapse = computed(
  () =>
    hasContentBody.value &&
    !props.msg.streaming &&
    preparedContentBody.value.length > COLLAPSE_THRESHOLD,
);

function normalizeDiagnosticText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

const diagnosticTerminationReason = computed(() => {
  return (
    normalizeDiagnosticText(props.msg.terminationReason) ||
    normalizeDiagnosticText(props.msg.completionReason)
  );
});

const isTruncatedByLength = computed(() => {
  return (
    !props.msg.streaming &&
    diagnosticTerminationReason.value.toLowerCase() === 'length'
  );
});

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

const messageIdentity = computed(() => resolveMessageIdentity(props.msg));
const expanded = ref(false);

watch(messageIdentity, () => {
  expanded.value = false;
});

function toggleExpand() {
  expanded.value = !expanded.value;
}
</script>

<template>
  <div
    v-if="hasContentBody"
    class="assistant-content-block relative"
    :class="compact ? 'text-[14px]' : 'text-[15px]'"
  >
    <div
      class="assistant-content-body transition-[max-height] duration-200"
      :class="[
        compact ? 'leading-[1.82]' : 'leading-[1.86]',
        canCollapse && !expanded
          ? 'relative max-h-[300px] overflow-hidden'
          : '',
      ]"
    >
      <MarkdownRender
        :content="preparedContentBody"
        :streaming="!!msg.streaming"
      />
      <span v-if="msg.streaming" class="streaming-cursor"></span>
      <span
        v-if="msg.stoppedByUser && !msg.streaming"
        class="ml-1 text-muted-foreground/70"
      >
        {{ $t('common.globalAiChat.generationStopped') }}
      </span>
      <span
        v-else-if="msg.interrupted && !msg.streaming"
        class="ml-1 text-muted-foreground/70"
      >
        {{ $t('common.globalAiChat.generationInterrupted') }}
      </span>
      <span
        v-else-if="msg.partial && !msg.streaming"
        class="ml-1 text-muted-foreground/70"
      >
        {{ $t('common.globalAiChat.generationIncomplete') }}
      </span>
      <div
        v-if="canCollapse && !expanded"
        class="via-card/92 pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-card to-transparent"
      ></div>
    </div>
    <button
      v-if="canCollapse && !msg.streaming"
      type="button"
      class="hover:border-primary/22 mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-border/30 bg-background/80 px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-primary/[0.05] hover:text-primary"
      @click="toggleExpand"
    >
      {{
        expanded
          ? $t('common.globalAiChat.collapseMessage')
          : $t('common.globalAiChat.expandMore')
      }}
    </button>
    <p
      v-if="canCollapse && !expanded && !msg.streaming"
      data-testid="collapsed-message-hint"
      class="text-muted-foreground/68 mt-1.5 text-[11px] leading-5"
    >
      {{ $t('common.globalAiChat.collapsedMessageHint') }}
    </p>
    <div
      v-if="isTruncatedByLength"
      data-testid="truncation-warning"
      class="border-amber-500/18 mt-2 flex items-center gap-1.5 rounded-xl border bg-amber-500/[0.08] px-2.5 py-2 text-[12px] text-amber-700 dark:text-amber-300"
    >
      <IconifyIcon icon="lucide:triangle-alert" class="size-3.5 shrink-0" />
      <span>{{ $t('common.globalAiChat.responseTruncated') }}</span>
    </div>
  </div>
</template>

<style scoped>
.assistant-content-body {
  color: hsl(var(--foreground) / 0.88);
}

.assistant-content-block :deep(.markdown-render) {
  font-size: inherit;
  line-height: inherit;
  color: inherit;
}

.assistant-content-block :deep(.markdown-render h1),
.assistant-content-block :deep(.markdown-render h2),
.assistant-content-block :deep(.markdown-render h3),
.assistant-content-block :deep(.markdown-render h4) {
  margin: 1em 0 0.5em;
  font-weight: 600;
  line-height: 1.35;
  color: hsl(var(--foreground) / 0.94);
}

.assistant-content-block :deep(.markdown-render h1) {
  font-size: 1.15em;
}

.assistant-content-block :deep(.markdown-render h2) {
  font-size: 1.08em;
}

.assistant-content-block :deep(.markdown-render h3),
.assistant-content-block :deep(.markdown-render h4) {
  font-size: 1.04em;
}

.assistant-content-block :deep(.markdown-render p) {
  margin: 0.55em 0;
}

.assistant-content-block :deep(.markdown-render ul),
.assistant-content-block :deep(.markdown-render ol) {
  margin: 0.6em 0;
  padding-left: 1.35em;
}

.assistant-content-block :deep(.markdown-render li + li) {
  margin-top: 0.28em;
}

.assistant-content-block :deep(.markdown-render hr) {
  margin: 1em 0;
  border-color: hsl(var(--border) / 0.55);
}

.assistant-content-block :deep(.markdown-render blockquote) {
  margin: 0.85em 0;
  padding: 0.75em 0.95em;
  color: hsl(var(--muted-foreground) / 0.96);
  border-left-width: 2px;
  border-left-color: hsl(var(--primary) / 0.24);
  border-radius: 0 12px 12px 0;
  background: hsl(var(--muted) / 0.2);
}

.assistant-content-block :deep(.markdown-render a) {
  font-weight: 500;
  box-shadow: inset 0 -1px 0 hsl(var(--primary) / 0.22);
}

.assistant-content-block :deep(.md-code-block) {
  border-color: hsl(var(--border) / 0.42);
  border-radius: 14px;
  background: hsl(var(--muted) / 0.1);
}

.assistant-content-block :deep(.md-code-header) {
  padding: 0.42rem 0.8rem;
  background: hsl(var(--muted) / 0.28);
}

.assistant-content-block :deep(.md-code-block pre.hljs) {
  padding: 0.95rem 1rem;
  background: hsl(var(--background) / 0.94);
}

.assistant-content-block :deep(.markdown-render code:not(.hljs code)) {
  padding: 0.15rem 0.38rem;
  border-radius: 6px;
  background: hsl(var(--muted) / 0.45);
}

.assistant-content-block :deep(.markdown-render table) {
  margin: 0.75em 0;
}

.assistant-content-block :deep(.markdown-render th) {
  background: hsl(var(--muted) / 0.42);
}
</style>

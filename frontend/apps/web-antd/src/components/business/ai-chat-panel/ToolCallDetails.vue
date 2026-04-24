<script setup lang="ts">
import type { ToolDisplayItem } from './tool-call-utils';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { getPageOpErrorHintKey } from '#/components/business/ai-chat-panel/pageOpErrorHints';
import { $t } from '#/locales';

import {
  getSearchFallbackNotice,
  getSearchProviderLabel,
  getSearchStatusLabel,
} from './tool-call-utils';

interface DetailFieldLine {
  key: string;
  value: string;
}

interface DetailField {
  key: string;
  lines: string[];
  metaLines: DetailFieldLine[];
  multiline: boolean;
  overflowCount: number;
  text?: string;
}

interface DetailPreview {
  lines: string[];
  multiline: boolean;
  overflowCount: number;
  text?: string;
}

const DETAIL_FIELD_LIMIT = 4;
const DETAIL_ITEM_LIMIT = 4;
const INLINE_VALUE_LIMIT = 160;
const BLOCK_VALUE_LIMIT = 600;
const OBJECT_TITLE_KEYS = [
  'title',
  'name',
  'label',
  'id',
  'status',
  'message',
  'summary',
  'url',
  'href',
] as const;

const props = defineProps<{
  compact: boolean;
  rawExpanded: boolean;
  toolItem: ToolDisplayItem;
}>();

const emit = defineEmits<{
  copy: [content: string];
  toggleRaw: [];
}>();

const searchFallbackNotice = computed(() =>
  props.toolItem.searchSummary
    ? getSearchFallbackNotice(props.toolItem.searchSummary)
    : null,
);

const errorHintKey = computed(() =>
  getPageOpErrorHintKey(props.toolItem.tc.errorType),
);

const hasSearchTechnicalDetails = computed(() => {
  const summary = props.toolItem.searchSummary;
  if (!summary) return false;
  return Boolean(
    summary.provider ||
    summary.selectedBackend ||
    summary.fallbackReason ||
    summary.nativeFailureKind ||
    summary.providerChain?.length,
  );
});

const argumentFields = computed(() =>
  buildDetailFields(props.toolItem.tc.arguments),
);

const parsedRawOutput = computed<unknown>(() => {
  const raw = props.toolItem.structuredOutput.raw;
  if (!raw?.trim()) {
    return undefined;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
});

const outputFields = computed(() =>
  isRecord(parsedRawOutput.value)
    ? buildDetailFields(parsedRawOutput.value)
    : [],
);

const outputPreview = computed<DetailPreview | null>(() => {
  const value = parsedRawOutput.value;
  if (!hasMeaningfulValue(value) || isRecord(value)) {
    return null;
  }
  return buildDetailPreview(value);
});

const hasStructuredOutputPreview = computed(
  () => outputFields.value.length > 0 || outputPreview.value !== null,
);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value))
    return value.some((item) => hasMeaningfulValue(item));
  if (isRecord(value))
    return Object.values(value).some((item) => hasMeaningfulValue(item));
  return true;
}

function normalizeInlineWhitespace(text: string): string {
  return text.replaceAll(/\s+/g, ' ').trim();
}

function truncateText(text: string, limit: number): string {
  return text.length > limit ? `${text.slice(0, limit - 1)}...` : text;
}

function safeJsonStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? '';
  } catch {
    return String(value);
  }
}

function formatBlockValue(value: unknown): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return truncateText(trimmed, BLOCK_VALUE_LIMIT);
  }
  return truncateText(String(value), BLOCK_VALUE_LIMIT);
}

function formatInlineValue(value: unknown, depth = 0): string {
  if (value === null || value === undefined) return '';

  if (typeof value === 'string') {
    const trimmed = normalizeInlineWhitespace(value);
    return trimmed ? truncateText(trimmed, INLINE_VALUE_LIMIT) : '';
  }

  if (
    typeof value === 'boolean' ||
    typeof value === 'bigint' ||
    typeof value === 'number'
  ) {
    return String(value);
  }

  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    const visibleItems = items
      .slice(0, Math.max(2, DETAIL_ITEM_LIMIT - 1))
      .map((item) => formatInlineValue(item, depth + 1))
      .filter(Boolean);
    const joined = visibleItems.join(' | ');
    if (items.length > visibleItems.length) {
      return joined
        ? `${joined} +${items.length - visibleItems.length}`
        : `+${items.length - visibleItems.length}`;
    }
    return joined;
  }

  if (isRecord(value)) {
    if (depth >= 2) {
      return truncateText(safeJsonStringify(value), INLINE_VALUE_LIMIT);
    }

    const entries = Object.entries(value).filter(([, entryValue]) =>
      hasMeaningfulValue(entryValue),
    );
    const titleKey = OBJECT_TITLE_KEYS.find((candidate) =>
      hasMeaningfulValue(value[candidate]),
    );

    const parts: string[] = [];
    if (titleKey) {
      const title = formatInlineValue(value[titleKey], depth + 1);
      if (title) {
        parts.push(title);
      }
    }

    for (const [entryKey, entryValue] of entries) {
      if (titleKey && entryKey === titleKey) {
        continue;
      }
      const formatted = formatInlineValue(entryValue, depth + 1);
      if (!formatted) {
        continue;
      }
      parts.push(`${entryKey}: ${formatted}`);
      if (parts.length >= (titleKey ? 3 : 2)) {
        break;
      }
    }

    return truncateText(
      parts.join(' | ') || safeJsonStringify(value),
      INLINE_VALUE_LIMIT,
    );
  }

  return truncateText(String(value), INLINE_VALUE_LIMIT);
}

function buildDetailField(key: string, value: unknown): DetailField {
  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    return {
      key,
      lines: items
        .slice(0, DETAIL_ITEM_LIMIT)
        .map((item) => formatInlineValue(item))
        .filter(Boolean),
      metaLines: [],
      multiline: false,
      overflowCount: Math.max(items.length - DETAIL_ITEM_LIMIT, 0),
    };
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, entryValue]) =>
      hasMeaningfulValue(entryValue),
    );
    return {
      key,
      lines: [],
      metaLines: entries
        .slice(0, DETAIL_FIELD_LIMIT)
        .map(([entryKey, entryValue]) => ({
          key: entryKey,
          value:
            formatInlineValue(entryValue) ||
            truncateText(safeJsonStringify(entryValue), INLINE_VALUE_LIMIT),
        })),
      multiline: false,
      overflowCount: Math.max(entries.length - DETAIL_FIELD_LIMIT, 0),
    };
  }

  return {
    key,
    lines: [],
    metaLines: [],
    multiline:
      typeof value === 'string' &&
      (value.includes('\n') || value.trim().length > 80),
    overflowCount: 0,
    text: formatBlockValue(value),
  };
}

function buildDetailFields(value?: Record<string, unknown>): DetailField[] {
  if (!value) {
    return [];
  }
  return Object.entries(value)
    .filter(([, fieldValue]) => hasMeaningfulValue(fieldValue))
    .map(([key, fieldValue]) => buildDetailField(key, fieldValue));
}

function buildDetailPreview(value: unknown): DetailPreview | null {
  if (!hasMeaningfulValue(value)) {
    return null;
  }
  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    return {
      lines: items
        .slice(0, DETAIL_ITEM_LIMIT)
        .map((item) => formatInlineValue(item))
        .filter(Boolean),
      multiline: false,
      overflowCount: Math.max(items.length - DETAIL_ITEM_LIMIT, 0),
    };
  }

  return {
    lines: [],
    multiline:
      typeof value === 'string' &&
      (value.includes('\n') || value.trim().length > 80),
    overflowCount: 0,
    text: formatBlockValue(value),
  };
}

function getSearchResultDomain(url: string): string {
  const normalized = url.trim();
  if (!normalized) return '';
  try {
    const hostname = new URL(normalized).hostname.replace(/^www\./iu, '');
    return hostname || normalized;
  } catch {
    const fallbackDomain = normalized
      .replace(/^https?:\/\//iu, '')
      .split(/[/?#]/u)[0]
      ?.trim();
    return fallbackDomain || normalized;
  }
}
</script>

<template>
  <div
    :class="
      compact
        ? 'space-y-1.5 px-2 py-1 text-[9.75px]'
        : 'space-y-2 px-2.5 py-1.5 text-[10px]'
    "
  >
    <section
      v-if="argumentFields.length > 0"
      class="tool-detail-section px-2 py-1.5"
    >
      <div class="tool-detail-label">
        {{ $t('common.globalAiChat.toolInputParameters') }}
      </div>
      <div class="mt-1.5 space-y-1">
        <div
          v-for="(field, fieldIndex) in argumentFields"
          :key="`arg-${field.key}-${fieldIndex}`"
          :data-testid="`tool-arg-field-${fieldIndex}`"
          class="tool-detail-card px-2 py-1.5"
        >
          <div class="flex items-start gap-2">
            <code
              class="text-foreground/74 shrink-0 rounded bg-accent/45 px-1.5 py-px text-[9px]"
            >
              {{ field.key }}
            </code>
            <div class="min-w-0 flex-1 space-y-1">
              <p
                v-if="field.text"
                class="text-foreground/84 break-words leading-4"
                :class="field.multiline ? 'whitespace-pre-wrap' : ''"
              >
                {{ field.text }}
              </p>
              <ul v-if="field.lines.length > 0" class="space-y-1">
                <li
                  v-for="(line, lineIndex) in field.lines"
                  :key="`${field.key}-line-${lineIndex}`"
                  class="rounded-[10px] bg-accent/18 px-1.5 py-1 leading-4 text-foreground/80"
                >
                  {{ line }}
                </li>
              </ul>
              <dl v-if="field.metaLines.length > 0" class="space-y-1">
                <div
                  v-for="entry in field.metaLines"
                  :key="`${field.key}-${entry.key}`"
                  class="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5"
                >
                  <dt>
                    <code class="text-muted-foreground/62 text-[9px]">
                      {{ entry.key }}
                    </code>
                  </dt>
                  <dd class="text-foreground/78 min-w-0 break-words leading-4">
                    {{ entry.value }}
                  </dd>
                </div>
              </dl>
              <div
                v-if="field.overflowCount > 0"
                class="text-muted-foreground/56 text-[9px]"
              >
                +{{ field.overflowCount }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="toolItem.searchSummary"
      class="tool-detail-section px-2 py-1.5 text-foreground/80"
    >
      <div class="tool-detail-label flex flex-wrap items-center gap-2">
        <span class="font-medium">{{
          $t('common.globalAiChat.toolSearchResults')
        }}</span>
        <span
          v-if="toolItem.searchSummary.status"
          class="normal-case tracking-normal"
        >
          {{ getSearchStatusLabel(toolItem.searchSummary.status) }}
        </span>
        <span
          v-if="toolItem.searchSummary.resultCount !== undefined"
          data-testid="tool-search-result-count"
          class="rounded bg-accent/30 px-1.5 py-px font-mono text-[9px] normal-case tracking-normal text-foreground/80"
        >
          {{ toolItem.searchSummary.resultCount }}
        </span>
      </div>
      <div
        v-if="searchFallbackNotice"
        class="mt-1.5 rounded-[12px] border border-amber-500/18 bg-amber-500/8 px-1.5 py-1 leading-4 text-amber-700 dark:text-amber-200"
      >
        {{ searchFallbackNotice }}
      </div>
      <div
        v-if="hasSearchTechnicalDetails"
        class="tool-detail-card mt-1.5 px-1.5 py-1"
      >
        <details>
          <summary class="tool-detail-label cursor-pointer select-none">
            {{ $t('common.globalAiChat.toolSearchTechnicalDetails') }}
          </summary>
          <div class="mt-1.5 space-y-1 text-[10px] text-muted-foreground">
            <div v-if="toolItem.searchSummary.provider">
              <span class="font-medium">{{
                $t('common.globalAiChat.toolSearchProvider')
              }}</span>
              <code class="ml-1 break-all">{{
                getSearchProviderLabel(toolItem.searchSummary.provider)
              }}</code>
            </div>
            <div v-if="toolItem.searchSummary.selectedBackend">
              <span class="font-medium">{{
                $t('common.globalAiChat.toolSearchBackend')
              }}</span>
              <code class="ml-1 break-all">{{
                toolItem.searchSummary.selectedBackend
              }}</code>
            </div>
            <div v-if="toolItem.searchSummary.providerChain?.length">
              <span class="font-medium">{{
                $t('common.globalAiChat.toolSearchProviderChain')
              }}</span>
              <code class="ml-1 break-all">{{
                toolItem.searchSummary.providerChain.join(' -> ')
              }}</code>
            </div>
            <div v-if="toolItem.searchSummary.nativeFailureKind">
              <span class="font-medium">{{
                $t('common.globalAiChat.toolSearchNativeFailure')
              }}</span>
              <code class="ml-1 break-all">{{
                toolItem.searchSummary.nativeFailureKind
              }}</code>
            </div>
            <div v-if="toolItem.searchSummary.fallbackReason">
              <span class="font-medium">{{
                $t('common.globalAiChat.toolSearchFallbackReason')
              }}</span>
              <code class="ml-1 break-all">{{
                toolItem.searchSummary.fallbackReason
              }}</code>
            </div>
          </div>
        </details>
      </div>
      <div
        v-if="toolItem.searchSummary.failureReason"
        class="mt-1.5 whitespace-pre-wrap break-words leading-4 text-muted-foreground"
      >
        {{ toolItem.searchSummary.failureReason }}
      </div>
      <ul
        v-else-if="toolItem.searchSummary.items.length > 0"
        class="mt-1.5 space-y-1"
      >
        <li
          v-for="(searchItem, searchIndex) in toolItem.searchSummary.items"
          :key="`${toolItem.index}-${searchIndex}-${searchItem.url}`"
          class="tool-detail-card px-1.5 py-1.5"
        >
          <a
            :href="searchItem.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block hover:text-primary"
            :data-testid="`tool-search-result-link-${toolItem.index}-${searchIndex}`"
          >
            <div class="text-[10px] font-medium leading-4 text-foreground">
              {{ searchItem.title }}
            </div>
            <div
              class="mt-0.5 flex items-center gap-1 text-[9px] text-muted-foreground"
            >
              <IconifyIcon icon="lucide:globe" class="size-2.5 shrink-0" />
              <span class="truncate">{{
                getSearchResultDomain(searchItem.url)
              }}</span>
            </div>
          </a>
          <div
            v-if="searchItem.snippet"
            class="mt-1 whitespace-pre-wrap break-words leading-4 text-foreground/75"
          >
            {{ searchItem.snippet }}
          </div>
        </li>
      </ul>
    </section>

    <section
      v-if="toolItem.structuredOutput.explanation"
      class="tool-detail-section px-2 py-1.5 text-foreground/80"
    >
      <div class="tool-detail-label">
        {{ $t('common.globalAiChat.toolExplanation') }}
      </div>
      <div class="mt-1 whitespace-pre-wrap break-words leading-4">
        {{ toolItem.structuredOutput.explanation }}
      </div>
    </section>

    <section
      v-if="toolItem.structuredOutput.sql"
      class="rounded-[14px] bg-slate-950/95 px-2 py-1.5 font-mono text-[10px] text-slate-100"
    >
      <div class="flex items-center gap-2">
        <span
          class="text-[9px] font-medium uppercase tracking-[0.08em] text-slate-300"
          >{{ $t('common.globalAiChat.toolSql') }}</span
        >
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-full border border-slate-700/80 px-1.5 py-px text-[9px] text-slate-300 transition-colors hover:border-slate-500 hover:text-white"
          @click.stop="emit('copy', toolItem.structuredOutput.sql || '')"
        >
          <IconifyIcon icon="lucide:copy" class="size-2.5" />
          {{ $t('common.globalAiChat.copySql') }}
        </button>
      </div>
      <pre
        class="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap break-all leading-4"
        >{{ toolItem.structuredOutput.sql }}</pre
      >
    </section>

    <section
      v-if="hasStructuredOutputPreview"
      class="tool-detail-section px-2 py-1.5 text-muted-foreground"
    >
      <div class="tool-detail-label">
        {{ $t('common.globalAiChat.toolReturnValue') }}
      </div>

      <div
        v-if="outputPreview?.text"
        data-testid="tool-output-preview"
        class="text-foreground/82 mt-1.5 break-words leading-4"
        :class="outputPreview.multiline ? 'whitespace-pre-wrap' : ''"
      >
        {{ outputPreview.text }}
      </div>

      <ul
        v-if="outputPreview?.lines.length"
        data-testid="tool-output-preview"
        class="mt-1.5 space-y-1"
      >
        <li
          v-for="(line, lineIndex) in outputPreview.lines"
          :key="`output-preview-line-${lineIndex}`"
          class="tool-detail-card px-1.5 py-1 leading-4 text-foreground/80"
        >
          {{ line }}
        </li>
      </ul>

      <div v-if="outputFields.length > 0" class="mt-1.5 space-y-1">
        <div
          v-for="(field, fieldIndex) in outputFields"
          :key="`output-${field.key}-${fieldIndex}`"
          :data-testid="`tool-output-field-${fieldIndex}`"
          class="tool-detail-card px-2 py-1.5"
        >
          <div class="flex items-start gap-2">
            <code
              class="text-foreground/74 shrink-0 rounded bg-accent/45 px-1.5 py-px text-[9px]"
            >
              {{ field.key }}
            </code>
            <div class="min-w-0 flex-1 space-y-1">
              <p
                v-if="field.text"
                class="text-foreground/84 break-words leading-4"
                :class="field.multiline ? 'whitespace-pre-wrap' : ''"
              >
                {{ field.text }}
              </p>
              <ul v-if="field.lines.length > 0" class="space-y-1">
                <li
                  v-for="(line, lineIndex) in field.lines"
                  :key="`${field.key}-line-${lineIndex}`"
                  class="rounded-[10px] bg-accent/18 px-1.5 py-1 leading-4 text-foreground/80"
                >
                  {{ line }}
                </li>
              </ul>
              <dl v-if="field.metaLines.length > 0" class="space-y-1">
                <div
                  v-for="entry in field.metaLines"
                  :key="`${field.key}-${entry.key}`"
                  class="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5"
                >
                  <dt>
                    <code class="text-muted-foreground/62 text-[9px]">
                      {{ entry.key }}
                    </code>
                  </dt>
                  <dd class="text-foreground/78 min-w-0 break-words leading-4">
                    {{ entry.value }}
                  </dd>
                </div>
              </dl>
              <div
                v-if="field.overflowCount > 0"
                class="text-muted-foreground/56 text-[9px]"
              >
                +{{ field.overflowCount }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="(outputPreview?.overflowCount ?? 0) > 0"
        class="text-muted-foreground/56 mt-1.5 text-[9px]"
      >
        +{{ outputPreview?.overflowCount }}
      </div>
    </section>

    <section
      v-if="toolItem.structuredOutput.raw"
      class="tool-detail-section overflow-hidden px-0 py-0 text-muted-foreground"
    >
      <button
        type="button"
        class="hover:bg-accent/16 flex w-full items-center gap-1 px-2 py-1.5 text-left transition-colors"
        :title="
          $t(
            rawExpanded
              ? 'common.globalAiChat.rawResultCollapse'
              : 'common.globalAiChat.rawResultExpand',
          )
        "
        @click="emit('toggleRaw')"
      >
        <IconifyIcon icon="lucide:braces" class="size-3 shrink-0" />
        <span class="tool-detail-label flex-1">
          {{ $t('common.globalAiChat.rawResult') }}
        </span>
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-2.5 transition-transform duration-200"
          :style="{
            transform: rawExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }"
        />
      </button>
      <div
        class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
        :style="{
          gridTemplateRows: rawExpanded ? '1fr' : '0fr',
          opacity: rawExpanded ? 1 : 0,
        }"
      >
        <div class="border-border/12 min-h-0 overflow-hidden border-t">
          <pre
            class="text-foreground/78 overflow-y-auto whitespace-pre-wrap break-all bg-background/72 px-2 py-1.5 font-mono leading-4"
            :class="[compact ? 'max-h-32 text-[10px]' : 'max-h-40 text-[11px]']"
            >{{ toolItem.structuredOutput.raw }}</pre
          >
        </div>
      </div>
    </section>

    <section
      v-if="toolItem.tc.error"
      class="rounded-[14px] border border-red-500/16 bg-red-50/75 px-2 py-1.5 text-red-600 dark:bg-red-950/24 dark:text-red-200"
    >
      <div class="whitespace-pre-wrap break-all leading-4">
        {{ toolItem.tc.error }}
      </div>
      <p
        v-if="toolItem.tc.status === 'error' && errorHintKey"
        class="mt-1 text-[10px] leading-4 text-red-500/90 dark:text-red-200/90"
      >
        {{ $t(errorHintKey) }}
      </p>
    </section>

    <a
      v-if="toolItem.tc.resultLink && toolItem.tc.status === 'success'"
      :href="toolItem.tc.resultLink"
      target="_blank"
      rel="noopener noreferrer"
      class="inline-flex items-center gap-1 rounded-full border border-border/16 bg-background/64 px-2 py-1 text-[10px] text-primary transition-colors hover:border-primary/18 hover:bg-background/76 hover:underline"
    >
      <IconifyIcon icon="lucide:external-link" class="size-2.5" />
      {{ $t('common.globalAiChat.viewResult') }}
    </a>
  </div>
</template>

<style scoped>
.tool-detail-section {
  background:
    radial-gradient(
      circle at top left,
      hsl(var(--primary) / 0.03),
      transparent 34%
    ),
    hsl(var(--background) / 0.62);
  border: 1px solid hsl(var(--border) / 0.1);
  border-radius: 0.95rem;
}

.tool-detail-card {
  background: hsl(var(--muted) / 0.12);
  border: 1px solid hsl(var(--border) / 0.1);
  border-radius: 0.8rem;
}

.tool-detail-label {
  color: hsl(var(--muted-foreground) / 0.58);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
</style>

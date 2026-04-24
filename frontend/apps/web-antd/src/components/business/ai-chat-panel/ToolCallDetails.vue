<script setup lang="ts">
import type { ToolDisplayItem } from './tool-call-utils';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

import {
  buildToolCallDetailsViewModel,
} from './chat-message-tool-call-details-helpers';

const props = defineProps<{
  compact: boolean;
  rawExpanded: boolean;
  toolItem: ToolDisplayItem;
}>();

const emit = defineEmits<{
  copy: [content: string];
  toggleRaw: [];
}>();

const detailView = computed(() => buildToolCallDetailsViewModel(props.toolItem));
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
      v-if="detailView.argumentFields.length > 0"
      class="tool-detail-section px-2 py-1.5"
    >
      <div class="tool-detail-label">
        {{ $t('common.globalAiChat.toolInputParameters') }}
      </div>
      <div class="mt-1.5 space-y-1">
        <div
          v-for="(field, fieldIndex) in detailView.argumentFields"
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
      v-if="detailView.toolSearchSummaryExists"
      class="tool-detail-section px-2 py-1.5 text-foreground/80"
    >
      <div class="tool-detail-label flex flex-wrap items-center gap-2">
        <span class="font-medium">{{
          $t('common.globalAiChat.toolSearchResults')
        }}</span>
        <span
          v-if="detailView.searchStatusLabel"
          class="normal-case tracking-normal"
        >
          {{ detailView.searchStatusLabel }}
        </span>
        <span
          v-if="detailView.searchResultCount !== undefined"
          data-testid="tool-search-result-count"
          class="rounded bg-accent/30 px-1.5 py-px font-mono text-[9px] normal-case tracking-normal text-foreground/80"
        >
          {{ detailView.searchResultCount }}
        </span>
      </div>
      <div
        v-if="detailView.searchFallbackNotice"
        class="mt-1.5 rounded-[12px] border border-amber-500/18 bg-amber-500/8 px-1.5 py-1 leading-4 text-amber-700 dark:text-amber-200"
      >
        {{ detailView.searchFallbackNotice }}
      </div>
      <div
        v-if="detailView.hasSearchTechnicalDetails"
        class="tool-detail-card mt-1.5 px-1.5 py-1"
      >
        <details>
          <summary class="tool-detail-label cursor-pointer select-none">
            {{ $t('common.globalAiChat.toolSearchTechnicalDetails') }}
          </summary>
          <dl class="mt-1.5 space-y-1 text-[10px] text-muted-foreground">
            <div
              v-for="detail in detailView.searchTechnicalDetails"
              :key="detail.key"
              class="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5"
            >
              <dt class="font-medium">{{ detail.label }}</dt>
              <dd><code class="break-all">{{ detail.value }}</code></dd>
            </div>
          </dl>
        </details>
      </div>
      <div
        v-if="detailView.searchFailureReason"
        class="mt-1.5 whitespace-pre-wrap break-words leading-4 text-muted-foreground"
      >
        {{ detailView.searchFailureReason }}
      </div>
      <ul
        v-else-if="detailView.searchResults.length > 0"
        class="mt-1.5 space-y-1"
      >
        <li
          v-for="(searchItem, searchIndex) in detailView.searchResults"
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
              <span class="truncate">{{ searchItem.domain }}</span>
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
      v-if="detailView.hasStructuredOutputPreview"
      class="tool-detail-section px-2 py-1.5 text-muted-foreground"
    >
      <div class="tool-detail-label">
        {{ $t('common.globalAiChat.toolReturnValue') }}
      </div>

      <div
        v-if="detailView.outputPreview?.text"
        data-testid="tool-output-preview"
        class="text-foreground/82 mt-1.5 break-words leading-4"
        :class="detailView.outputPreview.multiline ? 'whitespace-pre-wrap' : ''"
      >
        {{ detailView.outputPreview.text }}
      </div>

      <ul
        v-if="detailView.outputPreview?.lines.length"
        data-testid="tool-output-preview"
        class="mt-1.5 space-y-1"
      >
        <li
          v-for="(line, lineIndex) in detailView.outputPreview.lines"
          :key="`output-preview-line-${lineIndex}`"
          class="tool-detail-card px-1.5 py-1 leading-4 text-foreground/80"
        >
          {{ line }}
        </li>
      </ul>

      <div v-if="detailView.outputFields.length > 0" class="mt-1.5 space-y-1">
        <div
          v-for="(field, fieldIndex) in detailView.outputFields"
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
        v-if="(detailView.outputPreview?.overflowCount ?? 0) > 0"
        class="text-muted-foreground/56 mt-1.5 text-[9px]"
      >
        +{{ detailView.outputPreview?.overflowCount }}
      </div>
    </section>

    <section
      v-if="detailView.rawOutput"
      class="tool-detail-section overflow-hidden px-0 py-0 text-muted-foreground"
    >
      <button
        type="button"
        class="hover:bg-accent/16 flex w-full items-center gap-1 px-2 py-1.5 text-left transition-colors"
        :title="
          $t(
            props.rawExpanded
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
            transform: props.rawExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }"
        />
      </button>
      <div
        class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
        :style="{
          gridTemplateRows: props.rawExpanded ? '1fr' : '0fr',
          opacity: props.rawExpanded ? 1 : 0,
        }"
      >
        <div class="border-border/12 min-h-0 overflow-hidden border-t">
          <pre
            class="text-foreground/78 overflow-y-auto whitespace-pre-wrap break-all bg-background/72 px-2 py-1.5 font-mono leading-4"
            :class="[compact ? 'max-h-32 text-[10px]' : 'max-h-40 text-[11px]']"
            >{{ detailView.rawOutput }}</pre
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
        v-if="toolItem.tc.status === 'error' && detailView.errorHintKey"
        class="mt-1 text-[10px] leading-4 text-red-500/90 dark:text-red-200/90"
      >
        {{ $t(detailView.errorHintKey) }}
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

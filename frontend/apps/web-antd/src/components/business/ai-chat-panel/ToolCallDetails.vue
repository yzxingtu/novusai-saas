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
  <div :class="compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-[11px]'">
    <div
      v-if="
        toolItem.tc.arguments && Object.keys(toolItem.tc.arguments).length > 0
      "
      class="mb-1"
    >
      <span class="font-medium text-muted-foreground/60">{{
        $t('common.globalAiChat.args')
      }}</span>
      <code
        class="ml-1 rounded bg-accent/50 px-1 py-px text-[10px] text-muted-foreground"
      >
        {{ JSON.stringify(toolItem.tc.arguments) }}
      </code>
    </div>
    <div
      v-if="toolItem.searchSummary"
      class="mb-1 rounded bg-background/70 px-1.5 py-1 text-foreground/80"
    >
      <div
        class="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground"
      >
        <span class="font-medium">{{
          $t('common.globalAiChat.toolSearchResults')
        }}</span>
        <span v-if="toolItem.searchSummary.status">{{
          getSearchStatusLabel(toolItem.searchSummary.status)
        }}</span>
        <span
          v-if="toolItem.searchSummary.resultCount !== undefined"
          data-testid="tool-search-result-count"
        >
          {{ toolItem.searchSummary.resultCount }}
        </span>
      </div>
      <div
        v-if="searchFallbackNotice"
        class="mt-1 rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-1 text-[10px] text-amber-700 dark:text-amber-200"
      >
        {{ searchFallbackNotice }}
      </div>
      <div
        v-if="hasSearchTechnicalDetails"
        class="mt-1 rounded border border-border/30 bg-accent/10 px-1.5 py-1"
      >
        <details>
          <summary
            class="cursor-pointer select-none text-[10px] font-medium text-muted-foreground"
          >
            {{ $t('common.globalAiChat.toolSearchTechnicalDetails') }}
          </summary>
          <div class="mt-1 space-y-0.5 text-[10px] text-muted-foreground">
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
        class="mt-1 whitespace-pre-wrap break-words text-muted-foreground"
      >
        {{ toolItem.searchSummary.failureReason }}
      </div>
      <ul
        v-else-if="toolItem.searchSummary.items.length > 0"
        class="mt-1 space-y-1"
      >
        <li
          v-for="(searchItem, searchIndex) in toolItem.searchSummary.items"
          :key="`${toolItem.index}-${searchIndex}-${searchItem.url}`"
          class="rounded border border-border/20 bg-accent/20 px-1.5 py-1"
        >
          <a
            :href="searchItem.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block hover:text-primary"
            :data-testid="`tool-search-result-link-${toolItem.index}-${searchIndex}`"
          >
            <div class="text-[11px] font-medium text-foreground">
              {{ searchItem.title }}
            </div>
            <div
              class="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground"
            >
              <IconifyIcon icon="lucide:globe" class="size-2.5 shrink-0" />
              <span class="truncate">{{
                getSearchResultDomain(searchItem.url)
              }}</span>
            </div>
          </a>
          <div
            v-if="searchItem.snippet"
            class="mt-0.5 whitespace-pre-wrap break-words text-[10px] text-foreground/75"
          >
            {{ searchItem.snippet }}
          </div>
        </li>
      </ul>
    </div>
    <div
      v-if="toolItem.structuredOutput.explanation"
      class="mb-1 rounded bg-background/70 px-1.5 py-1 text-foreground/80"
    >
      <span class="font-medium text-muted-foreground/60">{{
        $t('common.globalAiChat.toolExplanation')
      }}</span>
      <div class="mt-0.5 whitespace-pre-wrap break-words">
        {{ toolItem.structuredOutput.explanation }}
      </div>
    </div>
    <div
      v-if="toolItem.structuredOutput.sql"
      class="mb-1 rounded bg-slate-950/95 px-1.5 py-1 font-mono text-[10px] text-slate-100"
    >
      <div class="flex items-center gap-2">
        <span class="font-medium text-slate-300">{{
          $t('common.globalAiChat.toolSql')
        }}</span>
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded border border-slate-700/80 px-1.5 py-px text-[10px] text-slate-300 transition-colors hover:border-slate-500 hover:text-white"
          @click.stop="emit('copy', toolItem.structuredOutput.sql || '')"
        >
          <IconifyIcon icon="lucide:copy" class="size-2.5" />
          {{ $t('common.globalAiChat.copySql') }}
        </button>
      </div>
      <pre
        class="mt-0.5 max-h-40 overflow-y-auto whitespace-pre-wrap break-all"
        >{{ toolItem.structuredOutput.sql }}</pre
      >
    </div>
    <div
      v-if="toolItem.structuredOutput.raw"
      class="rounded bg-accent/20 text-muted-foreground"
    >
      <button
        type="button"
        class="flex w-full items-center gap-1 px-1.5 py-1 text-left transition-colors hover:bg-accent/30"
        @click="emit('toggleRaw')"
      >
        <IconifyIcon icon="lucide:braces" class="size-3 shrink-0" />
        <span class="flex-1 text-[10px] font-medium">
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
        <div class="min-h-0 overflow-hidden border-t border-border/20">
          <pre
            class="overflow-y-auto whitespace-pre-wrap break-all px-1.5 py-1"
            :class="[compact ? 'max-h-32 text-[10px]' : 'max-h-40 text-[11px]']"
            >{{ toolItem.structuredOutput.raw }}</pre
          >
        </div>
      </div>
    </div>
    <div
      v-if="toolItem.tc.error"
      class="whitespace-pre-wrap break-all rounded bg-red-50 px-1.5 py-1 text-red-500 dark:bg-red-950/30"
    >
      {{ toolItem.tc.error }}
    </div>
    <p
      v-if="
        toolItem.tc.status === 'error' &&
        getPageOpErrorHintKey(toolItem.tc.errorType)
      "
      class="mt-1 text-[10px] text-muted-foreground"
    >
      {{ $t(getPageOpErrorHintKey(toolItem.tc.errorType)) }}
    </p>
    <a
      v-if="toolItem.tc.resultLink && toolItem.tc.status === 'success'"
      :href="toolItem.tc.resultLink"
      target="_blank"
      rel="noopener noreferrer"
      class="mt-1 inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
    >
      <IconifyIcon icon="lucide:external-link" class="size-2.5" />
      {{ $t('common.globalAiChat.viewResult') }}
    </a>
  </div>
</template>

<script lang="ts" setup>
import type { ChatMessage } from './types';
import type { PendingPageOpForDisplay } from './pending-page-op';

import { computed, onUnmounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { formatDurationSeconds } from '#/components/business/ai-chat-panel/display-formatters';
import { getPageOpErrorHintKey } from '#/components/business/ai-chat-panel/pageOpErrorHints';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    index: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    pendingOps: () => [],
  },
);

const emit = defineEmits<{
  copy: [content: string];
}>();

const aiPanelStore = useAIPanelStore();

interface ToolTargetBadge {
  labelKey: string;
  value: string;
}

interface StructuredToolOutput {
  explanation?: string;
  raw?: string;
  sql?: string;
}

interface SearchResultItem {
  snippet?: string;
  title: string;
  url: string;
}

interface SearchSummary {
  fallbackReason?: string;
  failureReason?: string;
  items: SearchResultItem[];
  provider?: string;
  providerChain?: string[];
  resultCount?: number;
  selectedBackend?: string;
  status?: string;
  nativeFailureKind?: string;
}

interface ToolDisplayItem {
  expanded: boolean;
  hasDetails: boolean;
  headlineSummary: null | string;
  index: number;
  searchSummary: null | SearchSummary;
  structuredOutput: StructuredToolOutput;
  targetBadges: ToolTargetBadge[];
  tc: NonNullable<ChatMessage['toolCalls']>[number];
}

const toolExpandedMap = ref<Record<number, boolean>>({});
const toolRawExpandedMap = ref<Record<number, boolean>>({});
const pendingOpExpandedMap = ref<Record<string, boolean>>({});

function hasToolCardDetails(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'arguments' | 'error' | 'output' | 'summaryPayload'
  >,
) {
  return Boolean(
    tc.output ||
      tc.error ||
      tc.summaryPayload ||
      (tc.arguments && Object.keys(tc.arguments).length > 0),
  );
}

function isToolExpanded(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'status' | 'summaryPayload'
  >,
  idx: number,
) {
  const existing = toolExpandedMap.value[idx];
  if (existing !== undefined) {
    return existing;
  }
  return tc.status === 'error';
}

function toggleToolExpand(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'arguments' | 'error' | 'output' | 'status' | 'summaryPayload'
  >,
  idx: number,
) {
  if (!hasToolCardDetails(tc)) return;
  toolExpandedMap.value = {
    ...toolExpandedMap.value,
    [idx]: !isToolExpanded(tc, idx),
  };
}

function isToolRawExpanded(idx: number) {
  return Boolean(toolRawExpandedMap.value[idx]);
}

function toggleToolRawExpand(idx: number) {
  toolRawExpandedMap.value = {
    ...toolRawExpandedMap.value,
    [idx]: !toolRawExpandedMap.value[idx],
  };
}

function hasPendingOpArgs(params?: Record<string, unknown>) {
  return Boolean(params && Object.keys(params).length > 0);
}

function isPendingOpExpanded(invokeId: string) {
  return Boolean(pendingOpExpandedMap.value[invokeId]);
}

function togglePendingOpExpand(invokeId: string) {
  pendingOpExpandedMap.value = {
    ...pendingOpExpandedMap.value,
    [invokeId]: !pendingOpExpandedMap.value[invokeId],
  };
}

const TOOL_SUMMARY_LIMIT = 56;

function compactValueText(text: string) {
  return text.length > TOOL_SUMMARY_LIMIT
    ? `${text.slice(0, TOOL_SUMMARY_LIMIT - 1)}...`
    : text;
}

function formatToolTargetValue(value: unknown): null | string {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) {
    const parts = value
      .map((item) => formatToolTargetValue(item))
      .filter(Boolean);
    if (parts.length === 0) return null;
    const visible = parts.slice(0, 3).join(', ');
    return parts.length > 3 ? `${visible} +${parts.length - 3}` : visible;
  }
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const named =
      formatToolTargetValue(record.name) ??
      formatToolTargetValue(record.label) ??
      formatToolTargetValue(record.id);
    return named ? compactValueText(named) : null;
  }
  const text = String(value).trim();
  return text ? compactValueText(text) : null;
}

function readFirstArg(
  args: Record<string, unknown> | undefined,
  keys: string[],
): unknown {
  if (!args) return undefined;
  for (const key of keys) {
    if (args[key] !== null && args[key] !== undefined) {
      return args[key];
    }
  }
  return undefined;
}

function parseSqlTableNames(text: string): string[] {
  const matches = [
    ...text.matchAll(/\b(?:from|join|into|update)\s+([\w."]+)/gi),
  ];
  const out: string[] = [];
  for (const match of matches) {
    const raw = (match[1] ?? '').replaceAll('"', '').trim();
    if (!raw) continue;
    const normalized = raw.split(/\s+/)[0] ?? raw;
    if (normalized && !out.includes(normalized)) {
      out.push(normalized);
    }
  }
  return out;
}

function parseSqlSelectClause(text: string): string {
  const selectMatch = /\bselect\b/i.exec(text);
  if (!selectMatch) return '';

  const selectStart = selectMatch.index + selectMatch[0].length;
  const fromMatch = /\bfrom\b/i.exec(text.slice(selectStart));
  if (!fromMatch) return '';

  return text.slice(selectStart, selectStart + fromMatch.index).trim();
}

function parseSqlMetrics(text: string): string[] {
  const selectClause = parseSqlSelectClause(text);
  if (!selectClause) return [];
  const matches = [
    ...selectClause.matchAll(
      /\b(count|sum|avg|min|max)\s*\(([\s\S]*?)\)/gi,
    ),
  ];
  const out: string[] = [];
  for (const match of matches) {
    const fnName = (match[1] ?? '').toUpperCase();
    const arg = (match[2] ?? '').replaceAll(/\s+/g, ' ').trim();
    if (!fnName || !arg) continue;
    const formatted = `${fnName}(${arg})`;
    if (!out.includes(formatted)) {
      out.push(formatted);
    }
  }
  return out;
}

function parseSqlGroupByColumns(text: string): string[] {
  const match = text.match(
    /\bgroup\s+by\b([\s\S]*?)(?:\border\s+by\b|\blimit\b|$)/i,
  );
  if (!match?.[1]) return [];
  return match[1]
    .split(',')
    .map((item) => item.trim().replaceAll(/\s+/g, ' '))
    .filter(Boolean)
    .slice(0, 4);
}

function parseSqlFilterHints(text: string): string[] {
  const normalized = text.toLowerCase();
  const hints: string[] = [];

  if (
    normalized.includes("interval '7 day'") ||
    normalized.includes("interval '7 days'")
  ) {
    hints.push($t('common.globalAiChat.toolFilterLast7Days'));
  } else if (
    normalized.includes("interval '30 day'") ||
    normalized.includes("interval '30 days'")
  ) {
    hints.push($t('common.globalAiChat.toolFilterLast30Days'));
  } else if (
    normalized.includes('current_date') ||
    normalized.includes("date_trunc('day'") ||
    normalized.includes("date_trunc('day'")
  ) {
    hints.push($t('common.globalAiChat.toolFilterToday'));
  }

  return hints;
}

function parseToolOutputPayload(
  output?: string,
): null | Record<string, unknown> {
  if (!output) return null;
  try {
    const parsed = JSON.parse(output);
    return parsed && typeof parsed === 'object'
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function getSummaryPayload(
  tc: Pick<NonNullable<ChatMessage['toolCalls']>[number], 'summaryPayload'>,
) {
  return tc.summaryPayload && typeof tc.summaryPayload === 'object'
    ? tc.summaryPayload
    : null;
}

function toSearchResultItems(value: unknown): SearchResultItem[] {
  if (!Array.isArray(value)) return [];
  const items: SearchResultItem[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const title = typeof item.title === 'string' ? item.title.trim() : '';
    const url = typeof item.url === 'string' ? item.url.trim() : '';
    const snippet = typeof item.snippet === 'string' ? item.snippet.trim() : '';
    if (!title || !url) continue;
    items.push({
      title,
      url,
      snippet: snippet || undefined,
    });
  }
  return items;
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

function getSearchSummary(
  tc: Pick<NonNullable<ChatMessage['toolCalls']>[number], 'summaryPayload'>,
): null | SearchSummary {
  const summaryPayload = getSummaryPayload(tc);
  if (!summaryPayload) return null;

  const provider =
    typeof summaryPayload.provider === 'string'
      ? summaryPayload.provider.trim()
      : '';
  const status =
    typeof summaryPayload.status === 'string' ? summaryPayload.status.trim() : '';
  const failureReason =
    typeof summaryPayload.failure_reason === 'string'
      ? summaryPayload.failure_reason.trim()
      : '';
  const fallbackReason =
    typeof summaryPayload.fallback_reason === 'string'
      ? summaryPayload.fallback_reason.trim()
      : '';
  const selectedBackend =
    typeof summaryPayload.selected_backend === 'string'
      ? summaryPayload.selected_backend.trim()
      : '';
  const nativeFailureKind =
    typeof summaryPayload.native_failure_kind === 'string'
      ? summaryPayload.native_failure_kind.trim()
      : '';
  const providerChain = toStringList(summaryPayload.provider_chain);
  const items = toSearchResultItems(summaryPayload.items);
  const resultCount =
    typeof summaryPayload.result_count === 'number'
      ? summaryPayload.result_count
      : items.length > 0
        ? items.length
        : undefined;

  if (
    !provider &&
    !status &&
    !failureReason &&
    !fallbackReason &&
    !selectedBackend &&
    !nativeFailureKind &&
    providerChain.length === 0 &&
    items.length === 0
  ) {
    return null;
  }

  return {
    fallbackReason: fallbackReason || undefined,
    provider: provider || undefined,
    providerChain: providerChain.length > 0 ? providerChain : undefined,
    status: status || undefined,
    resultCount,
    items,
    failureReason: failureReason || undefined,
    selectedBackend: selectedBackend || undefined,
    nativeFailureKind: nativeFailureKind || undefined,
  };
}

function getSearchFallbackNotice(summary: SearchSummary): null | string {
  const fallbackReason = summary.fallbackReason ?? '';
  if (!fallbackReason) {
    return null;
  }
  if (
    fallbackReason.includes('default_verified_target_unavailable') ||
    fallbackReason.includes('untrusted_openai_compatible_runtime_target')
  ) {
    return $t('common.globalAiChat.toolSearchFallbackNeedVerifiedNativeTarget');
  }
  if (
    summary.nativeFailureKind === 'unsupported' &&
    summary.selectedBackend?.startsWith('public:')
  ) {
    return $t('common.globalAiChat.toolSearchFallbackNativeUnsupported');
  }
  return null;
}

function getSearchProviderLabel(provider?: string) {
  switch (provider) {
    case 'native_hosted': {
      return $t('common.globalAiChat.toolSearchSourceNative');
    }
    case 'baidu_public': {
      return $t('common.globalAiChat.toolSearchSourceBaidu');
    }
    case 'so360_public': {
      return $t('common.globalAiChat.toolSearchSource360');
    }
    default: {
      return provider || '';
    }
  }
}

function getSearchStatusLabel(status?: string) {
  switch (status) {
    case 'no_results': {
      return $t('common.globalAiChat.toolSearchStatusNoResults');
    }
    case 'source_blocked': {
      return $t('common.globalAiChat.toolSearchStatusBlocked');
    }
    case 'source_challenged': {
      return $t('common.globalAiChat.toolSearchStatusChallenged');
    }
    case 'source_unavailable': {
      return $t('common.globalAiChat.toolSearchStatusUnavailable');
    }
    case 'success': {
      return $t('common.globalAiChat.toolSearchStatusSuccess');
    }
    default: {
      return status || '';
    }
  }
}

function getStructuredToolOutput(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'output' | 'summaryPayload'
  >,
): StructuredToolOutput {
  const summaryPayload = getSummaryPayload(tc);
  const payloadExplanation =
    typeof summaryPayload?.explanation === 'string'
      ? summaryPayload.explanation.trim()
      : '';
  const payloadSql =
    typeof summaryPayload?.sql === 'string' ? summaryPayload.sql.trim() : '';

  if (!tc.output) {
    return {
      explanation: payloadExplanation || undefined,
      sql: payloadSql || undefined,
    };
  }

  const parsed = parseToolOutputPayload(tc.output);
  if (!parsed) {
    return {
      explanation: payloadExplanation || undefined,
      raw: tc.output,
      sql: payloadSql || undefined,
    };
  }

  const explanation =
    payloadExplanation ||
    (typeof parsed.explanation === 'string' ? parsed.explanation.trim() : '');
  const sql =
    payloadSql || (typeof parsed.sql === 'string' ? parsed.sql.trim() : '');

  const rest = { ...parsed };
  delete rest.explanation;
  delete rest.sql;

  const hasMeaningfulRest = Object.entries(rest).some(([, value]) => {
    if (value === null || value === undefined) return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === 'string') return value.trim().length > 0;
    return true;
  });

  return {
    explanation: explanation || undefined,
    raw: hasMeaningfulRest ? JSON.stringify(rest, null, 2) : undefined,
    sql: sql || undefined,
  };
}

function getToolHeadlineSummary(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'output' | 'status' | 'summary' | 'summaryPayload'
  >,
): null | string {
  if (tc.summary?.trim()) {
    return tc.summary.trim();
  }
  if (tc.status !== 'success') return null;
  const structured = getStructuredToolOutput(tc);
  if (!structured.explanation) return null;
  return compactValueText(structured.explanation.replaceAll(/\s+/g, ' '));
}

function getToolTargetBadges(
  tc: Pick<
    NonNullable<ChatMessage['toolCalls']>[number],
    'arguments' | 'output' | 'summaryPayload'
  >,
): ToolTargetBadge[] {
  const args = tc.arguments;
  const summaryPayload = getSummaryPayload(tc);
  const badges: ToolTargetBadge[] = [];
  const pushBadge = (labelKey: string, value: unknown) => {
    const formatted = formatToolTargetValue(value);
    if (!formatted) return;
    if (
      badges.some(
        (badge) => badge.labelKey === labelKey && badge.value === formatted,
      )
    ) {
      return;
    }
    badges.push({ labelKey, value: formatted });
  };

  pushBadge(
    'common.globalAiChat.toolTargetAction',
    readFirstArg(args, ['action', 'operation', 'operation_name', 'command']),
  );
  pushBadge(
    'common.globalAiChat.toolTargetTables',
    readFirstArg(args, [
      'table',
      'tables',
      'table_name',
      'table_names',
      'resource',
      'resources',
      'resource_name',
    ]),
  );
  pushBadge(
    'common.globalAiChat.toolTargetFields',
    readFirstArg(args, [
      'field',
      'fields',
      'field_name',
      'field_names',
      'column',
      'columns',
    ]),
  );
  pushBadge(
    'common.globalAiChat.toolTargetRecords',
    readFirstArg(args, ['record_id', 'record_ids', 'id', 'ids']),
  );
  pushBadge(
    'common.globalAiChat.toolTargetQuery',
    readFirstArg(args, ['question', 'query', 'keyword', 'prompt']),
  );

  const parsedOutput = parseToolOutputPayload(tc.output);
  let sqlText = '';
  if (typeof parsedOutput?.sql === 'string') {
    sqlText = parsedOutput.sql;
  } else if (typeof tc.output === 'string') {
    sqlText = tc.output;
  }
  const sqlTables = parseSqlTableNames(sqlText);
  if (
    sqlTables.length > 0 &&
    !badges.some(
      (badge) => badge.labelKey === 'common.globalAiChat.toolTargetTables',
    )
  ) {
    pushBadge('common.globalAiChat.toolTargetTables', sqlTables);
  }

  const sqlMetrics = parseSqlMetrics(sqlText);
  if (sqlMetrics.length > 0) {
    pushBadge('common.globalAiChat.toolTargetMetrics', sqlMetrics);
  }

  const sqlGroups = parseSqlGroupByColumns(sqlText);
  if (sqlGroups.length > 0) {
    pushBadge('common.globalAiChat.toolTargetGrouping', sqlGroups);
  }

  const sqlFilters = parseSqlFilterHints(sqlText);
  if (sqlFilters.length > 0) {
    pushBadge('common.globalAiChat.toolTargetFilter', sqlFilters);
  }

  if (Array.isArray(summaryPayload?.tables)) {
    pushBadge('common.globalAiChat.toolTargetTables', summaryPayload.tables);
  }
  if (Array.isArray(summaryPayload?.metrics)) {
    pushBadge('common.globalAiChat.toolTargetMetrics', summaryPayload.metrics);
  }
  if (Array.isArray(summaryPayload?.group_by)) {
    pushBadge('common.globalAiChat.toolTargetGrouping', summaryPayload.group_by);
  }
  if (Array.isArray(summaryPayload?.filters)) {
    const normalizedFilters = summaryPayload.filters.map((item) => {
      switch (item) {
        case 'last_7_days': {
          return $t('common.globalAiChat.toolFilterLast7Days');
        }
        case 'last_30_days': {
          return $t('common.globalAiChat.toolFilterLast30Days');
        }
        case 'today': {
          return $t('common.globalAiChat.toolFilterToday');
        }
        default: {
          return String(item);
        }
      }
    });
    pushBadge('common.globalAiChat.toolTargetFilter', normalizedFilters);
  }

  return badges.slice(0, 6);
}

const toolDisplayItems = computed<ToolDisplayItem[]>(() =>
  (props.msg.toolCalls ?? []).map((tc, idx) => {
    const hasDetails = hasToolCardDetails(tc);
    const structuredOutput = getStructuredToolOutput(tc);
    const searchSummary = getSearchSummary(tc);
    return {
      index: idx,
      tc,
      hasDetails,
      expanded: hasDetails ? isToolExpanded(tc, idx) : false,
      headlineSummary: getToolHeadlineSummary(tc),
      searchSummary,
      structuredOutput,
      targetBadges: getToolTargetBadges(tc),
    };
  }),
);

const RUNTIME_PAGE_TOOL_NAMES = new Set([
  'capture_screenshot',
  'clear_search',
  'create_record',
  'edit_record',
  'fill_form',
  'get_form_options',
  'get_form_state',
  'go_to_page',
  'list_available_menus',
  'navigate_menu',
  'next_page',
  'prev_page',
  'read_row_detail',
  'read_visible_rows',
  'refresh_list',
  'search',
  'set_page_size',
  'submit_form',
]);

function isRuntimePageToolName(name: string): boolean {
  return name.startsWith('ui_') || RUNTIME_PAGE_TOOL_NAMES.has(name);
}

/** Whether this tool call has a pending confirmation (inline) / 该工具调用是否有待确认（内联） */
function hasPendingForToolCall(tc: {
  id?: string;
  name: string;
  status: string;
}): boolean {
  if (tc.status !== 'running') return false;
  if (!isRuntimePageToolName(tc.name)) return false;
  if (!props.pendingOps?.length) return false;
  // Prefer toolCallId match when available / 有 toolCallId 时精确匹配
  const matched = props.pendingOps.some(
    (op) => op.toolCallId && op.toolCallId === tc.id && !op.resolved,
  );
  if (matched) return true;
  // Fallback: legacy ops without toolCallId, any unresolved = waiting / 兜底：无 toolCallId 的旧数据，存在未解决则显示待确认 */
  return props.pendingOps.some((op) => !op.toolCallId && !op.resolved);
}

/** Display sub-state for running tools: waiting_confirm vs executing / 运行中工具的展示子状态 */
function getToolDisplayState(tc: {
  id?: string;
  name: string;
  status: string;
}): 'executing' | 'waiting_confirm' {
  if (tc.status !== 'running') return 'executing';
  if (hasPendingForToolCall(tc)) return 'waiting_confirm';
  return 'executing';
}

/** Ticking now for "still running" countdown (8s+) / 用于“仍在执行”提示的计时 */
const now = ref(Date.now());
const hasRunningTool = computed(
  () => props.msg.toolCalls?.some((tc) => tc.status === 'running') ?? false,
);
let tickInterval: null | ReturnType<typeof setInterval> = null;
function startTick() {
  if (tickInterval) return;
  tickInterval = setInterval(() => {
    now.value = Date.now();
  }, 1000);
}
function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval);
    tickInterval = null;
  }
}
watch(
  hasRunningTool,
  (running) => {
    if (running) startTick();
    else stopTick();
  },
  { immediate: true },
);
onUnmounted(stopTick);

const toolGroupExpandedMap = ref<Record<number, boolean>>({});

const toolGroupSummary = computed(() => {
  const tools = props.msg.toolCalls;
  if (!tools?.length) return null;
  const total = tools.length;
  const success = tools.filter((tc) => tc.status === 'success').length;
  const error = tools.filter((tc) => tc.status === 'error').length;
  const running = tools.filter((tc) => tc.status === 'running').length;
  return { total, success, error, running };
});

function isToolGroupExpanded(idx: number): boolean {
  const explicit = toolGroupExpandedMap.value[idx];
  if (explicit !== undefined) return explicit;
  return hasRunningTool.value || !!props.msg.streaming;
}

function toggleToolGroupExpand(idx: number) {
  toolGroupExpandedMap.value = {
    ...toolGroupExpandedMap.value,
    [idx]: !isToolGroupExpanded(idx),
  };
}

/** Auto-collapse tool group when all tools finish or streaming ends. */
watch(
  () => [hasRunningTool.value, props.msg.streaming, props.index] as const,
  ([running, streaming, idx], oldVal) => {
    const wasRunning = oldVal?.[0];
    const wasStreaming = oldVal?.[1];
    if (
      typeof idx === 'number' &&
      ((wasRunning === true && running === false) ||
        (wasStreaming === true && streaming === false && !running))
    ) {
      toolGroupExpandedMap.value = {
        ...toolGroupExpandedMap.value,
        [idx]: false,
      };
    }
  },
);
</script>

<template>
  <!-- Generating indicator (tool calls running but no content yet) -->
  <div
    v-if="msg.streaming && !msg.content && msg.toolCalls?.length"
    class="flex items-center gap-1.5 px-2 py-0.5 text-muted-foreground"
    :class="compact ? 'text-[11px]' : 'text-xs'"
  >
    <span class="typing-dots"><span></span><span></span><span></span></span>
    <span>{{ $t('common.globalAiChat.generating') }}</span>
  </div>

  <!-- Tool calls - collapsible group card -->
  <div
    v-if="msg.toolCalls?.length"
    class="overflow-hidden rounded-lg border border-border/25 bg-accent/10"
    :class="compact ? 'mt-1' : 'mt-1.5'"
  >
    <button
      type="button"
      class="flex w-full cursor-pointer select-none items-center text-left transition-colors hover:bg-accent/20"
      :class="
        compact ? 'gap-1 px-2 py-1 text-[11px]' : 'gap-1.5 px-2.5 py-1.5 text-xs'
      "
      data-testid="tool-group-toggle"
      @click="toggleToolGroupExpand(index)"
    >
      <IconifyIcon
        icon="lucide:wrench"
        class="shrink-0 text-muted-foreground/60"
        :class="[
          compact ? 'size-3' : 'size-3.5',
          toolGroupSummary?.running ? 'tc-pill-pulse' : '',
        ]"
      />
      <span class="flex-1 font-medium text-muted-foreground">
        <template v-if="toolGroupSummary?.running">
          {{
            $t('common.globalAiChat.toolGroupRunning', {
              count: toolGroupSummary.total,
            })
          }}
        </template>
        <template v-else>
          {{
            $t('common.globalAiChat.toolGroupSummary', {
              count: toolGroupSummary?.total ?? 0,
            })
          }}
        </template>
      </span>
      <span
        v-if="toolGroupSummary && !toolGroupSummary.running"
        class="flex items-center gap-1.5 text-[10px]"
      >
        <span
          v-if="toolGroupSummary.success"
          class="flex items-center gap-0.5 text-green-600 dark:text-green-400"
        >
          <IconifyIcon icon="lucide:check" class="size-2.5" />
          {{ toolGroupSummary.success }}
        </span>
        <span v-if="toolGroupSummary.error" class="flex items-center gap-0.5 text-red-500">
          <IconifyIcon icon="lucide:x" class="size-2.5" />
          {{ toolGroupSummary.error }}
        </span>
      </span>
      <IconifyIcon
        icon="lucide:chevron-down"
        class="shrink-0 text-muted-foreground/30 transition-transform duration-300"
        style="transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1)"
        :class="compact ? 'size-2.5' : 'size-3'"
        :style="{
          transform: isToolGroupExpanded(index) ? 'rotate(180deg)' : 'rotate(0deg)',
        }"
      />
    </button>

    <div
      class="grid"
      :style="{
        gridTemplateRows: isToolGroupExpanded(index) ? '1fr' : '0fr',
        opacity: isToolGroupExpanded(index) ? 1 : 0,
        transition:
          'grid-template-rows 350ms cubic-bezier(0.4,0,0.2,1), opacity 200ms ease',
      }"
      data-testid="tool-group-body"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="border-t border-border/20 transition-opacity duration-200"
          :style="{ opacity: isToolGroupExpanded(index) ? 1 : 0 }"
        ></div>
        <div class="tc-timeline relative" :class="compact ? 'px-2 py-1 pl-5' : 'px-2.5 py-1.5 pl-6'">
          <!-- Timeline vertical line -->
          <div
            v-if="msg.toolCalls.length > 1"
            class="absolute w-px bg-border/40"
            :class="compact ? 'bottom-1 left-[8px] top-1' : 'bottom-1.5 left-[9px] top-1.5'"
          ></div>

          <div
            v-for="toolItem in toolDisplayItems"
            :key="toolItem.index"
            class="relative"
            :class="toolItem.index > 0 ? (compact ? 'mt-0.5' : 'mt-1') : ''"
          >
            <!-- Timeline dot -->
            <div class="absolute z-[1]" :class="compact ? '-left-3 top-[5px]' : '-left-4 top-[7px]'">
              <span
                v-if="toolItem.tc.status === 'running'"
                class="tc-dot-pulse block rounded-full bg-primary"
                :class="compact ? 'size-[7px]' : 'size-2'"
              ></span>
              <span
                v-else-if="toolItem.tc.status === 'success'"
                class="block rounded-full bg-green-500"
                :class="compact ? 'size-[7px]' : 'size-2'"
              ></span>
              <span
                v-else
                class="block rounded-full bg-red-500"
                :class="compact ? 'size-[7px]' : 'size-2'"
              ></span>
            </div>

            <!-- Tool call card -->
            <div
              class="group/tc overflow-hidden rounded-lg border border-border/20 bg-accent/15 backdrop-blur-sm transition-colors hover:bg-accent/25"
            >
              <button
                type="button"
                class="flex w-full select-none items-center text-left"
                :class="[
                  compact ? 'gap-1 px-2 py-[3px] text-[11px]' : 'gap-1.5 px-2.5 py-1 text-xs',
                  toolItem.hasDetails ? 'cursor-pointer' : 'cursor-default',
                ]"
                :data-testid="`tool-call-toggle-${toolItem.index}`"
                @click="toggleToolExpand(toolItem.tc, toolItem.index)"
              >
                <!-- Status pill -->
                <span
                  class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px text-[10px] font-medium leading-tight"
                  :class="
                    toolItem.tc.status === 'running'
                      ? getToolDisplayState(toolItem.tc) === 'waiting_confirm'
                        ? 'tc-pill-pulse bg-warning/10 text-warning'
                        : 'tc-pill-pulse bg-primary/10 text-primary'
                      : toolItem.tc.status === 'success'
                        ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                        : 'bg-red-500/10 text-red-500'
                  "
                >
                  <IconifyIcon
                    v-if="toolItem.tc.status !== 'running'"
                    :icon="toolItem.tc.status === 'success' ? 'lucide:check' : 'lucide:x'"
                    class="size-2.5"
                  />
                  <span v-else class="tc-dot-pulse mr-0.5 inline-block size-1.5 rounded-full bg-current"></span>
                  {{
                    toolItem.tc.status === 'running'
                      ? getToolDisplayState(toolItem.tc) === 'waiting_confirm'
                        ? $t('common.globalAiChat.toolWaitingConfirm')
                        : $t('common.globalAiChat.toolExecuting')
                      : toolItem.tc.status === 'success'
                        ? $t('common.globalAiChat.toolStatusOk')
                        : $t('common.globalAiChat.toolStatusErr')
                  }}
                </span>

                <!-- Tool name -->
                <span class="min-w-0 flex-1 text-muted-foreground">
                  <span class="block truncate">
                    <template v-if="toolItem.tc.skillName">
                      <span class="font-medium text-foreground/60">{{ toolItem.tc.skillName }}</span>
                      <span class="mx-0.5 text-muted-foreground/30">›</span>
                    </template>
                    <span class="text-foreground/70">{{
                      toolItem.tc.displayName || toolItem.tc.name
                    }}</span>
                    <span
                      v-if="toolItem.headlineSummary && toolItem.tc.status === 'success'"
                      class="ml-1 text-muted-foreground/50"
                      >— {{ toolItem.headlineSummary }}</span
                    >
                  </span>
                  <span
                    v-if="toolItem.targetBadges.length > 0"
                    class="mt-1 flex flex-wrap items-center gap-1"
                    :class="compact ? 'text-[9px]' : 'text-[10px]'"
                  >
                    <span class="text-muted-foreground/45">
                      {{ $t('common.globalAiChat.toolTouched') }}
                    </span>
                    <span
                      v-for="badge in toolItem.targetBadges"
                      :key="`${badge.labelKey}-${badge.value}`"
                      class="inline-flex max-w-full items-center gap-1 rounded-full border border-border/30 bg-background/70 px-1.5 py-px"
                    >
                      <span class="shrink-0 text-muted-foreground/55">{{ $t(badge.labelKey) }}</span>
                      <span class="truncate text-foreground/75">{{ badge.value }}</span>
                    </span>
                  </span>
                </span>

                <!-- Duration -->
                <span
                  v-if="toolItem.tc.durationMs"
                  class="text-[10px] tabular-nums text-muted-foreground/40"
                >
                  {{ formatDurationSeconds(toolItem.tc.durationMs) }}
                </span>

                <!-- Expand chevron -->
                <IconifyIcon
                  v-if="toolItem.hasDetails"
                  icon="lucide:chevron-down"
                  class="shrink-0 text-muted-foreground/30 transition-transform duration-200"
                  :class="compact ? 'size-2.5' : 'size-3'"
                  :style="{ transform: toolItem.expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
              </button>

              <!-- Expanded details -->
              <div
                v-if="toolItem.hasDetails"
                class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                :style="{
                  gridTemplateRows: toolItem.expanded ? '1fr' : '0fr',
                  opacity: toolItem.expanded ? 1 : 0,
                }"
                :data-testid="`tool-call-details-${toolItem.index}`"
              >
                <div class="min-h-0 overflow-hidden border-t border-border/20">
                  <div :class="compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-[11px]'">
                    <div
                      v-if="toolItem.tc.arguments && Object.keys(toolItem.tc.arguments).length > 0"
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
                      <div class="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                        <span class="font-medium">{{
                          $t('common.globalAiChat.toolSearchResults')
                        }}</span>
                        <span v-if="toolItem.searchSummary.provider">{{
                          getSearchProviderLabel(toolItem.searchSummary.provider)
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
                        v-if="getSearchFallbackNotice(toolItem.searchSummary)"
                        class="mt-1 rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-1 text-[10px] text-amber-700 dark:text-amber-200"
                      >
                        {{ getSearchFallbackNotice(toolItem.searchSummary) }}
                      </div>
                      <div
                        v-if="
                          toolItem.searchSummary.selectedBackend ||
                          toolItem.searchSummary.fallbackReason ||
                          toolItem.searchSummary.nativeFailureKind ||
                          toolItem.searchSummary.providerChain?.length
                        "
                        class="mt-1 space-y-0.5 text-[10px] text-muted-foreground"
                      >
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
                      <div
                        v-if="toolItem.searchSummary.failureReason"
                        class="mt-1 whitespace-pre-wrap break-words text-muted-foreground"
                      >
                        {{ toolItem.searchSummary.failureReason }}
                      </div>
                      <ul v-else-if="toolItem.searchSummary.items.length > 0" class="mt-1 space-y-1">
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
                            <div class="mt-0.5 break-all text-[10px] text-muted-foreground">
                              {{ searchItem.url }}
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
                      <pre class="mt-0.5 max-h-40 overflow-y-auto whitespace-pre-wrap break-all">{{
                        toolItem.structuredOutput.sql
                      }}</pre>
                    </div>
                    <div v-if="toolItem.structuredOutput.raw" class="rounded bg-accent/20 text-muted-foreground">
                      <button
                        type="button"
                        class="flex w-full items-center gap-1 px-1.5 py-1 text-left transition-colors hover:bg-accent/30"
                        @click="toggleToolRawExpand(toolItem.index)"
                      >
                        <IconifyIcon icon="lucide:braces" class="size-3 shrink-0" />
                        <span class="flex-1 text-[10px] font-medium">
                          {{ $t('common.globalAiChat.rawResult') }}
                        </span>
                        <IconifyIcon
                          icon="lucide:chevron-down"
                          class="size-2.5 transition-transform duration-200"
                          :style="{
                            transform: isToolRawExpanded(toolItem.index) ? 'rotate(180deg)' : 'rotate(0deg)',
                          }"
                        />
                      </button>
                      <div
                        class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                        :style="{
                          gridTemplateRows: isToolRawExpanded(toolItem.index) ? '1fr' : '0fr',
                          opacity: isToolRawExpanded(toolItem.index) ? 1 : 0,
                        }"
                      >
                        <div class="min-h-0 overflow-hidden border-t border-border/20">
                          <pre
                            class="overflow-y-auto whitespace-pre-wrap break-all px-1.5 py-1"
                            :class="[
                              compact ? 'max-h-32 text-[10px]' : 'max-h-40 text-[11px]',
                            ]"
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
                </div>
              </div>
            </div>

            <!-- Inline confirmation card (for this tool call) / 内联确认卡片（对应本工具调用） -->
            <div
              v-for="op in (pendingOps || []).filter((o) => o.toolCallId === toolItem.tc.id)"
              :key="op.invokeId"
              class="mt-1 overflow-hidden rounded-lg border"
              :class="op.resolved ? 'border-border/20 bg-accent/10' : 'border-warning/30 bg-warning/5'"
            >
              <!-- Resolved state -->
              <div
                v-if="op.resolved"
                class="flex items-center gap-1.5 px-2.5 py-1.5"
                :class="compact ? 'text-[10px]' : 'text-[11px]'"
              >
                <IconifyIcon
                  :icon="op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'"
                  class="size-3 shrink-0"
                  :class="op.allowed ? 'text-green-600' : 'text-red-500'"
                />
                <span class="truncate text-muted-foreground">
                  <span class="font-medium text-foreground/60">{{ op.operationLabel }}</span>
                  <span v-if="op.operationDescription" class="ml-1 text-muted-foreground/60"
                    >{{ op.operationDescription }}</span
                  >
                </span>
                <span
                  class="ml-auto shrink-0 rounded-full px-1.5 py-px font-medium"
                  :class="[
                    compact ? 'text-[9px]' : 'text-[10px]',
                    op.allowed
                      ? 'bg-green-50 text-green-600 dark:bg-green-950/30'
                      : 'bg-red-50 text-red-600 dark:bg-red-950/30',
                  ]"
                >
                  {{
                    op.allowed
                      ? $t('shared.pageOperation.confirmOk')
                      : $t('shared.pageOperation.confirmCancel')
                  }}
                </span>
              </div>
              <!-- Pending state -->
              <template v-else>
                <div class="flex items-center gap-1.5 px-2.5 py-1.5" :class="compact ? 'text-[10px]' : 'text-[11px]'">
                  <IconifyIcon icon="lucide:shield-alert" class="size-3.5 shrink-0 text-warning" />
                  <div class="min-w-0 flex-1">
                    <div class="truncate font-medium text-foreground/80">
                      {{ op.operationLabel }}
                    </div>
                    <div v-if="op.operationDescription" class="truncate text-muted-foreground/60">
                      {{ op.operationDescription }}
                    </div>
                    <div
                      class="mt-0.5 text-muted-foreground/50"
                      :class="compact ? 'text-[9px]' : 'text-[10px]'"
                    >
                      {{
                        $t('shared.pageOperation.confirmCountdown', {
                          seconds: Math.max(
                            0,
                            60 -
                              Math.floor(
                                ((countdownNow ?? now) - (op.startedAt || 0)) /
                                  1000,
                              ),
                          ),
                        })
                      }}
                    </div>
                  </div>
                  <div class="flex shrink-0 items-center gap-1">
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, true)"
                    >
                      <IconifyIcon icon="lucide:check" class="size-3" />
                      {{ $t('shared.pageOperation.confirmOk') }}
                    </button>
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, false)"
                    >
                      <IconifyIcon icon="lucide:x" class="size-3" />
                      {{ $t('shared.pageOperation.confirmCancel') }}
                    </button>
                  </div>
                </div>
                <div v-if="hasPendingOpArgs(op.params)" class="border-t border-border/20">
                  <button
                    type="button"
                    class="flex w-full cursor-pointer items-center gap-1 px-2.5 py-0.5 text-left text-muted-foreground/60 transition-colors hover:text-muted-foreground"
                    :class="compact ? 'text-[9px]' : 'text-[10px]'"
                    @click="togglePendingOpExpand(op.invokeId)"
                  >
                    <IconifyIcon icon="lucide:code" class="size-2.5" />
                    {{ $t('common.globalAiChat.args') }}
                    <IconifyIcon
                      icon="lucide:chevron-down"
                      class="size-2.5 transition-transform duration-200"
                      :style="{ transform: isPendingOpExpanded(op.invokeId) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                    />
                  </button>
                  <div
                    class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                    :style="{
                      gridTemplateRows: isPendingOpExpanded(op.invokeId) ? '1fr' : '0fr',
                      opacity: isPendingOpExpanded(op.invokeId) ? 1 : 0,
                    }"
                  >
                    <div class="min-h-0 overflow-hidden border-t border-border/20">
                      <div class="px-2.5 py-1">
                        <pre
                          class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-muted-foreground"
                          :class="compact ? 'text-[9px]' : 'text-[10px]'"
                          >{{ JSON.stringify(op.params, null, 2) }}</pre
                        >
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>

            <!-- Still running hint (8s+) - outside details so always visible / 执行超 8s 的提示 -->
            <p
              v-if="
                toolItem.tc.status === 'running' &&
                toolItem.tc.startedAt &&
                now - toolItem.tc.startedAt >= 8000
              "
              class="mt-0.5 pl-1 text-[10px] text-muted-foreground"
            >
              {{ $t('common.globalAiChat.toolStillRunningHint') }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

import type { ChatMessage } from './types';

import { $t } from '#/locales';

export interface ToolTargetBadge {
  labelKey: string;
  value: string;
}

export interface StructuredToolOutput {
  explanation?: string;
  raw?: string;
  sql?: string;
}

export interface SearchResultItem {
  snippet?: string;
  title: string;
  url: string;
}

export interface SearchSummary {
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

export interface ToolDisplayItem {
  expanded: boolean;
  hasDetails: boolean;
  headlineSummary: null | string;
  index: number;
  searchSummary: null | SearchSummary;
  structuredOutput: StructuredToolOutput;
  targetBadges: ToolTargetBadge[];
  tc: NonNullable<ChatMessage['toolCalls']>[number];
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
    ...selectClause.matchAll(/\b(count|sum|avg|min|max)\s*\(([\s\S]*?)\)/gi),
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

export function getSearchSummary(
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

export function getSearchFallbackNotice(summary: SearchSummary): null | string {
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

export function getSearchProviderLabel(provider?: string) {
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

export function getSearchStatusLabel(status?: string) {
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

export function getStructuredToolOutput(
  tc: Pick<NonNullable<ChatMessage['toolCalls']>[number], 'output' | 'summaryPayload'>,
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

export function getToolHeadlineSummary(
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

export function getToolTargetBadges(
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

export function hasToolCardDetails(
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

export function isRuntimePageToolName(name: string): boolean {
  return name.startsWith('ui_') || RUNTIME_PAGE_TOOL_NAMES.has(name);
}

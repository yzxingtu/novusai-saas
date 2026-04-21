import type { SearchSummary } from './tool-call-search-utils';
import type { ToolCallEvent } from './types';

import { $t } from '#/locales';

import { getToolCallSummaryPayload } from './tool-call-search-utils';

export type { SearchResultItem, SearchSummary } from './tool-call-search-utils';
export {
  getSearchFallbackNotice,
  getSearchProviderLabel,
  getSearchStatusLabel,
  getSearchSummary,
  getToolCallSummaryPayload,
} from './tool-call-search-utils';

export interface ToolTargetBadge {
  labelKey: string;
  value: string;
}

export interface StructuredToolOutput {
  explanation?: string;
  raw?: string;
  sql?: string;
}

export interface ToolDisplayItem {
  expanded: boolean;
  hasDetails: boolean;
  headlineSummary: null | string;
  index: number;
  searchSummary: null | SearchSummary;
  structuredOutput: StructuredToolOutput;
  targetBadges: ToolTargetBadge[];
  tc: ToolCallEvent;
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

export function getStructuredToolOutput(
  tc: Pick<ToolCallEvent, 'output' | 'summaryPayload'>,
): StructuredToolOutput {
  const summaryPayload = getToolCallSummaryPayload(tc);
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
  tc: Pick<ToolCallEvent, 'output' | 'status' | 'summary' | 'summaryPayload'>,
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
  tc: Pick<ToolCallEvent, 'arguments' | 'output' | 'summaryPayload'>,
): ToolTargetBadge[] {
  const args = tc.arguments;
  const summaryPayload = getToolCallSummaryPayload(tc);
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
    pushBadge(
      'common.globalAiChat.toolTargetGrouping',
      summaryPayload.group_by,
    );
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
  tc: Pick<ToolCallEvent, 'arguments' | 'error' | 'output' | 'summaryPayload'>,
) {
  return Boolean(
    tc.output ||
    tc.error ||
    tc.summaryPayload ||
    (tc.arguments && Object.keys(tc.arguments).length > 0),
  );
}

export function isRuntimePageToolName(name: string): boolean {
  return name.startsWith('ui_');
}

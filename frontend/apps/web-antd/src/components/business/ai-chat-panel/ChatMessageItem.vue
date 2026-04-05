<script lang="ts" setup>
/**
 * Chat Message Item - Renders a single chat message (assistant or user).
 * 单条聊天消息项 — 渲染一条助手或用户消息。
 *
 * Supports two visual densities via `compact` prop:
 * 通过 compact 支持两种展示密度：
 * - false (default): Full page layout with avatar, Tag status, RAG sources
 * - true: Compact drawer layout with smaller sizes, no avatar/Tag/RAG
 */
import type {
  AgentItem,
  ChatAttachment,
  ChatMessage,
  RagSource,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Modal, Tooltip } from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import { getPageOpErrorHintKey } from '#/components/business/ai-chat-panel/pageOpErrorHints';
import RichTextDraftCard from '#/components/business/ai-chat-panel/RichTextDraftCard.vue';
import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { formatTimeOnly } from '#/utils/common';
import { getFileIcon } from '#/utils/file';
import { isDevErrorMode } from '#/utils/request';

/** Pending page op for inline confirmation card / 待确认的页面操作（内联卡片） */
export interface PendingPageOpForDisplay {
  invokeId: string;
  operationLabel: string;
  operationDescription: string;
  params: Record<string, unknown>;
  resolved: boolean;
  allowed?: boolean;
  startedAt: number;
  toolCallId?: string;
}

const props = withDefaults(
  defineProps<{
    /** Agents list for resolving avatar/name by msg.agent_id (fix avatar mismatch) / 智能体列表，按 msg.agent_id 解析头像 */
    agents?: AgentItem[];
    apiPrefix?: string;
    compact?: boolean;
    /** Current timestamp for 60s countdown display (fallback: local now) / 用于 60s 倒计时的当前时间戳 */
    countdownNow?: number;
    index: number;
    msg: ChatMessage;
    /** Pending page ops for this message (filtered by toolCallId) / 本消息关联的待确认操作 */
    pendingOps?: PendingPageOpForDisplay[];
    richTextState?: null | RichTextDraftRuntimeState;
    selectedAgent?: AgentItem | null;
    /** Whether to show an agent-switch separator above this message / 是否在本条消息上方显示智能体切换分隔 */
    showAgentSwitch?: boolean;
  }>(),
  {
    apiPrefix: '',
    agents: () => [],
    compact: false,
    countdownNow: undefined,
    selectedAgent: null,
    showAgentSwitch: false,
    pendingOps: () => [],
    richTextState: null,
  },
);

const emit = defineEmits<{
  actionClick: [index: number, value: string];
  confirm: [index: number];
  consentConfirm: [index: number];
  consentReject: [index: number];
  copy: [content: string];
  edit: [index: number];
  openUrl: [url: string];
  regenerate: [index: number];
  reject: [index: number];
  retry: [index: number];
  richTextApply: [
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ];
  richTextDiscard: [index: number];
  richTextUndo: [index: number];
}>();

/** Agent resolved by msg.agent_id from agents list (fix avatar mismatch when msg.agent_avatar is null) */
const resolvedAgent = computed(() => {
  if (props.msg.agent_id && props.agents?.length) {
    return props.agents.find((a) => a.id === props.msg.agent_id) ?? null;
  }
  return null;
});

/** Avatar: msg > agents[agent_id] > selectedAgent (avoid wrong agent avatar in history) */
const resolvedAvatar = computed(
  () =>
    props.msg.agent_avatar ??
    resolvedAgent.value?.avatar ??
    props.selectedAgent?.avatar ??
    null,
);
/** Resolve agent display info: prefer message-level, then agents by id, fallback to selectedAgent */
const msgAgentName = computed(
  () =>
    props.msg.agent_name ??
    resolvedAgent.value?.name ??
    props.selectedAgent?.name ??
    null,
);
const msgAgentDescription = computed(
  () =>
    props.msg.agent_description ??
    resolvedAgent.value?.description ??
    props.selectedAgent?.description ??
    null,
);
const msgModelName = computed(
  () =>
    props.msg.model_name ??
    resolvedAgent.value?.model_name ??
    props.selectedAgent?.model_name ??
    null,
);
const isMentionRoute = computed(() => props.msg.routeSource === 'mention');
const showRouteBadge = computed(
  () =>
    props.msg.role === 'assistant' &&
    !!msgAgentName.value &&
    (props.showAgentSwitch || isMentionRoute.value),
);

const ragDetailOpen = ref(false);
const ragDetailItem = ref<null | RagSource>(null);
function openRagDetail(s: RagSource) {
  ragDetailItem.value = s;
  ragDetailOpen.value = true;
}

/** Group RAG hits by knowledge base for display / 按知识库分组展示引用 */
const ragGroups = computed(() => {
  const list = props.msg.ragSources ?? [];
  const groups = new Map<string, { items: RagSource[]; label: string }>();
  for (const s of list) {
    const label =
      s.knowledge_base_name ||
      (s.knowledge_base_id === null || s.knowledge_base_id === undefined
        ? '—'
        : `KB#${s.knowledge_base_id}`);
    const key = String(s.knowledge_base_id ?? label);
    if (!groups.has(key)) {
      groups.set(key, { label, items: [] });
    }
    groups.get(key)!.items.push(s);
  }
  return [...groups.values()];
});

/** 用户消息图片：blob 预览失效时改用 url；仍失败则隐藏避免破图 / Image load error fallback */
function onUserAttachmentImageError(event: Event, att: ChatAttachment) {
  const el = event.target as HTMLImageElement;
  if (!el) return;
  if (att.preview && el.src.startsWith('blob:') && att.url) {
    el.src = att.url;
    return;
  }
  el.classList.add('hidden');
}

function pickRichTextDraftCopyContent(
  ...values: Array<null | string | undefined>
) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return '';
}

function getRichTextDraftCopyContent(mode: RichTextAIApplyMode) {
  const task = props.msg.richTextAI;
  if (!task) {
    return props.msg.content;
  }
  if (mode === 'plain') {
    return pickRichTextDraftCopyContent(
      task.draft.plainText,
      task.draft.markdown,
      props.msg.content,
      task.draft.html,
    );
  }
  return pickRichTextDraftCopyContent(
    task.draft.markdown,
    task.draft.plainText,
    props.msg.content,
    task.draft.html,
  );
}

const aiPanelStore = useAIPanelStore();

/** Long message fold: content exceeds 1000 chars and not streaming / 长消息折叠阈值 */
const COLLAPSE_THRESHOLD = 1000;
const canCollapse = computed(
  () =>
    !!props.msg.content &&
    !props.msg.streaming &&
    props.msg.content.length > COLLAPSE_THRESHOLD,
);
const showDebugError = computed(
  () => isDevErrorMode() && !!props.msg.error?.debugMessage,
);

function normalizeDiagnosticText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

interface ContextSourceDisplayItem {
  active: boolean;
  key: string;
  label: string;
}

function formatContextSourceLabel(source: {
  kind?: string;
  metadata?: Record<string, unknown>;
  name?: string;
}) {
  const kind = normalizeDiagnosticText(source.kind);
  const name = normalizeDiagnosticText(source.name);
  if (kind && name) {
    return `${kind}:${name}`;
  }
  if (name) {
    return name;
  }
  if (kind) {
    return kind;
  }
  const metadata = source.metadata ?? {};
  const metadataName =
    normalizeDiagnosticText(metadata.name) ||
    normalizeDiagnosticText(metadata.title) ||
    normalizeDiagnosticText(metadata.knowledge_base_name) ||
    normalizeDiagnosticText(metadata.source);
  return metadataName;
}

const diagnosticTurnOutcome = computed(() =>
  normalizeDiagnosticText(props.msg.turnOutcome),
);
const diagnosticTerminationReason = computed(() => {
  return (
    normalizeDiagnosticText(props.msg.terminationReason) ||
    normalizeDiagnosticText(props.msg.completionReason)
  );
});
const diagnosticProtocolPath = computed(() =>
  normalizeDiagnosticText(props.msg.protocolPath),
);
const diagnosticSelectedTools = computed(() => {
  return (props.msg.selectedToolNames ?? [])
    .map((item) => normalizeDiagnosticText(item))
    .filter((item) => item.length > 0);
});
const diagnosticSelectedSkills = computed(() => {
  return (props.msg.selectedSkillNames ?? [])
    .map((item) => normalizeDiagnosticText(item))
    .filter((item) => item.length > 0);
});
const diagnosticContextSources = computed<ContextSourceDisplayItem[]>(() => {
  const list = props.msg.contextSources ?? [];
  return list
    .map((source, index) => {
      const label = formatContextSourceLabel(source);
      const key = `${source.kind || ''}-${source.name || ''}-${index}`;
      return {
        key,
        label: label || `#${index + 1}`,
        active: source.active !== false,
      };
    })
    .filter((item) => item.label.length > 0);
});
const hasTurnDiagnostics = computed(() => {
  return Boolean(
    diagnosticTurnOutcome.value ||
    diagnosticTerminationReason.value ||
    diagnosticProtocolPath.value ||
    diagnosticSelectedTools.value.length > 0 ||
    diagnosticSelectedSkills.value.length > 0 ||
    diagnosticContextSources.value.length > 0,
  );
});

const expandedMap = ref<Record<number, boolean>>({});
function toggleExpand(idx: number) {
  expandedMap.value = { ...expandedMap.value, [idx]: !expandedMap.value[idx] };
}

/** Thinking block: expanded during streaming, collapsed by default when done. User can toggle. */
const thinkingExpandedMap = ref<Record<number, boolean>>({});

function isThinkingExpanded(idx: number) {
  return Boolean(
    (props.msg.streaming && props.msg.thinkingContent) ||
    thinkingExpandedMap.value[idx],
  );
}

function toggleThinkingExpand(idx: number) {
  thinkingExpandedMap.value = {
    ...thinkingExpandedMap.value,
    [idx]: !thinkingExpandedMap.value[idx],
  };
}

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
  failureReason?: string;
  items: SearchResultItem[];
  provider?: string;
  resultCount: number;
  status?: string;
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
    typeof summaryPayload.status === 'string'
      ? summaryPayload.status.trim()
      : '';
  const failureReason =
    typeof summaryPayload.failure_reason === 'string'
      ? summaryPayload.failure_reason.trim()
      : '';
  const items = toSearchResultItems(summaryPayload.items);
  const resultCount =
    typeof summaryPayload.result_count === 'number'
      ? summaryPayload.result_count
      : items.length;

  if (!provider && !status && !failureReason && items.length === 0) {
    return null;
  }

  return {
    provider: provider || undefined,
    status: status || undefined,
    resultCount,
    items,
    failureReason: failureReason || undefined,
  };
}

function getSearchProviderLabel(provider?: string) {
  switch (provider) {
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

/** Whether this tool call has a pending confirmation (inline) / 该工具调用是否有待确认（内联） */
function hasPendingForToolCall(tc: {
  id?: string;
  name: string;
  status: string;
}): boolean {
  if (tc.status !== 'running') return false;
  if (tc.name !== 'invoke_page_operation' && !tc.name.startsWith('pageop_'))
    return false;
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

/** Auto-collapse thinking block when streaming ends. */
watch(
  () => [props.msg.streaming, props.index] as const,
  ([streaming, idx], oldVal) => {
    const prevStreaming = oldVal?.[0];
    if (
      prevStreaming === true &&
      streaming === false &&
      typeof idx === 'number'
    ) {
      thinkingExpandedMap.value = {
        ...thinkingExpandedMap.value,
        [idx]: false,
      };
    }
  },
);

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
  <!-- Agent switch separator -->
  <div
    v-if="showRouteBadge"
    class="flex items-center gap-2 py-1"
    :class="compact ? 'mb-1' : 'mb-2'"
  >
    <div class="h-px flex-1 bg-border/40"></div>
    <div
      class="flex items-center gap-1 rounded-full bg-muted/60 px-2.5 py-0.5 text-muted-foreground"
      :class="compact ? 'text-[10px]' : 'text-xs'"
    >
      <IconifyIcon
        :icon="isMentionRoute ? 'lucide:at-sign' : 'lucide:arrow-right'"
        class="size-3"
      />
      <span>{{ isMentionRoute ? `@ ${msgAgentName}` : msgAgentName }}</span>
    </div>
    <div class="h-px flex-1 bg-border/40"></div>
  </div>

  <div
    class="flex"
    :class="[
      msg.role === 'user' ? 'justify-end' : 'justify-start',
      compact ? 'gap-2' : 'gap-3',
    ]"
  >
    <!-- ===== Assistant message ===== -->
    <div
      v-if="msg.role === 'assistant'"
      class="group flex"
      :class="compact ? 'max-w-[90%] gap-1.5' : 'max-w-[80%] gap-2'"
    >
      <!-- Avatar with profile card popover -->
      <AgentProfilePopover
        :agent-id="msg.agent_id ?? selectedAgent?.id"
        :agent-avatar="resolvedAvatar"
        :agent-name="msgAgentName"
        :agent-description="msgAgentDescription"
        :model-name="msgModelName"
        :api-prefix="apiPrefix"
        :size="compact ? 'sm' : 'md'"
      />

      <div class="min-w-0">
        <!-- Agent name + model label -->
        <div
          v-if="msgAgentName && msg.agent_id"
          :class="compact ? 'mb-0.5' : 'mb-1'"
        >
          <span
            :class="compact ? 'text-[10px]' : 'text-xs'"
            class="font-medium text-muted-foreground"
          >
            {{ msgAgentName }}
          </span>
          <span
            v-if="!compact && msgModelName"
            class="ml-1.5 rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground/60"
          >
            {{ msgModelName }}
          </span>
        </div>

        <!-- Thinking (no tool calls yet) - skeleton pulse -->
        <div
          v-if="
            msg.streaming &&
            !msg.content &&
            !msg.toolCalls?.length &&
            !msg.thinkingContent
          "
          class="thinking-skeleton space-y-2 rounded-xl border border-border/20 bg-accent/30 px-3 py-3"
        >
          <div class="flex items-center gap-2">
            <div
              class="thinking-glow relative flex size-5 items-center justify-center rounded-full bg-primary/10"
            >
              <span class="typing-dots"
                ><span></span><span></span><span></span
              ></span>
            </div>
            <span class="text-xs font-medium text-muted-foreground">{{
              $t('common.globalAiChat.processing')
            }}</span>
          </div>
          <div class="space-y-2">
            <div
              class="skeleton-line h-2 w-[90%] rounded-full bg-muted/50"
            ></div>
            <div
              class="skeleton-line h-2 w-[72%] rounded-full bg-muted/50"
              style="animation-delay: 0.15s"
            ></div>
            <div
              class="skeleton-line h-2 w-[55%] rounded-full bg-muted/50"
              style="animation-delay: 0.3s"
            ></div>
          </div>
        </div>

        <!-- Thinking content (streamed separately from final answer). Less prominent; auto-collapse when done; expandable. -->
        <div
          v-if="msg.thinkingContent"
          class="relative"
          :class="compact ? 'mb-1.5' : 'mb-2'"
        >
          <button
            :aria-expanded="isThinkingExpanded(index)"
            data-testid="thinking-toggle"
            type="button"
            class="thinking-chip hover:border-primary/18 flex max-w-full cursor-pointer items-center gap-2 border-0 bg-transparent text-left transition-all duration-200 hover:text-foreground"
            :class="compact ? 'px-2.5 py-1.5' : 'px-3 py-1.5'"
            @click="toggleThinkingExpand(index)"
          >
            <span
              class="thinking-chip-icon relative flex shrink-0 items-center justify-center rounded-full"
              :class="compact ? 'size-6' : 'size-7'"
            >
              <IconifyIcon
                icon="lucide:brain"
                class="size-3.5 text-muted-foreground/80"
                :class="msg.streaming ? 'thinking-glow text-primary/70' : ''"
              />
            </span>

            <span class="flex min-w-0 flex-1 items-center gap-1.5">
              <span class="text-foreground/84 truncate text-xs font-medium">
                {{
                  msg.streaming
                    ? $t('common.globalAiChat.thinking')
                    : $t('common.globalAiChat.thinkingCollapsed')
                }}
              </span>

              <span
                v-if="msg.streaming"
                class="typing-dots thinking-status-dots shrink-0"
                ><span></span><span></span><span></span
              ></span>
              <span
                v-else
                aria-hidden="true"
                class="size-1.5 shrink-0 rounded-full bg-primary/35"
              >
              </span>
            </span>

            <span
              class="ml-auto flex shrink-0 items-center text-muted-foreground/60"
            >
              <IconifyIcon
                icon="lucide:chevron-down"
                class="size-3.5 transition-transform duration-200"
                :class="
                  isThinkingExpanded(index) ? 'rotate-180 text-primary/80' : ''
                "
              />
            </span>
          </button>
          <div
            data-testid="thinking-body"
            class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
            :style="{
              gridTemplateRows: isThinkingExpanded(index) ? '1fr' : '0fr',
              opacity: isThinkingExpanded(index) ? 1 : 0,
            }"
          >
            <div class="min-h-0 overflow-hidden">
              <div
                class="thinking-sheet-card mt-2 transition-transform duration-200"
                :class="compact ? 'ml-1.5 px-3 py-2.5' : 'ml-2 px-3.5 py-3'"
                :style="{
                  transform: isThinkingExpanded(index)
                    ? 'translateY(0)'
                    : 'translateY(-6px)',
                }"
              >
                <div
                  class="thinking-markdown leading-5.5 text-muted-foreground/82 text-xs"
                >
                  <MarkdownRender
                    :content="msg.thinkingContent"
                    :streaming="!!msg.streaming && !msg.content"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Optimizing tools indicator -->
        <div
          v-if="msg.optimizingTools"
          class="flex items-center rounded-lg bg-accent/50 text-muted-foreground"
          :class="
            compact
              ? 'mb-1 gap-1.5 px-2 py-1 text-[11px]'
              : 'mb-2 gap-2 px-3 py-1.5 text-xs'
          "
        >
          <span
            class="text-primary"
            :class="
              compact
                ? 'icon-[lucide--sparkles] h-3 w-3'
                : 'icon-[lucide--sparkles] h-3.5 w-3.5'
            "
          ></span>
          <span>{{
            $t('common.globalAiChat.optimizingTools', {
              total: msg.optimizingTools.total,
              selected: msg.optimizingTools.selected,
            })
          }}</span>
        </div>

        <!-- Structured error panel -->
        <div
          v-if="msg.error"
          class="rounded-xl border border-destructive/40 bg-destructive/5"
          :class="
            compact ? 'mb-1 px-2.5 py-2 text-xs' : 'mb-2 px-3 py-2.5 text-sm'
          "
        >
          <div class="flex items-start gap-2">
            <IconifyIcon
              icon="lucide:alert-triangle"
              class="mt-0.5 size-4 shrink-0 text-destructive"
            />
            <div class="min-w-0 flex-1">
              <p class="break-words text-foreground">{{ msg.error.message }}</p>
              <p
                v-if="msg.error.traceId"
                class="mt-1 font-mono text-[11px] text-muted-foreground"
              >
                {{ `${$t('common.http.traceId')}: ${msg.error.traceId}` }}
              </p>
              <pre
                v-if="showDebugError"
                class="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-black/5 p-2 text-[11px] text-red-500"
                >{{ msg.error?.debugMessage }}</pre
              >
            </div>
          </div>
        </div>

        <div
          v-if="hasTurnDiagnostics"
          class="rounded-xl border border-border/30 bg-accent/10"
          :class="
            compact
              ? 'mb-1 space-y-1 px-2 py-1.5'
              : 'mb-2 space-y-1.5 px-3 py-2'
          "
        >
          <div class="flex flex-wrap items-center gap-1.5">
            <span
              v-if="diagnosticTurnOutcome"
              class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
            >
              <span class="font-mono text-[10px] text-muted-foreground"
                >turn_outcome</span
              >
              <span class="font-medium text-foreground">{{
                diagnosticTurnOutcome
              }}</span>
            </span>
            <span
              v-if="diagnosticTerminationReason"
              class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
            >
              <span class="font-mono text-[10px] text-muted-foreground"
                >termination_reason</span
              >
              <span class="font-medium text-foreground">{{
                diagnosticTerminationReason
              }}</span>
            </span>
            <span
              v-if="diagnosticProtocolPath"
              class="inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-0.5 text-[11px]"
            >
              <span class="font-mono text-[10px] text-muted-foreground"
                >protocol_path</span
              >
              <span class="font-medium text-foreground">{{
                diagnosticProtocolPath
              }}</span>
            </span>
          </div>
          <div
            v-if="diagnosticSelectedTools.length > 0"
            class="flex flex-wrap items-center gap-1.5"
          >
            <span class="font-mono text-[10px] text-muted-foreground"
              >selected_tools</span
            >
            <span
              v-for="toolName in diagnosticSelectedTools"
              :key="toolName"
              class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
            >
              {{ toolName }}
            </span>
          </div>
          <div
            v-if="diagnosticSelectedSkills.length > 0"
            class="flex flex-wrap items-center gap-1.5"
          >
            <span class="font-mono text-[10px] text-muted-foreground"
              >selected_skills</span
            >
            <span
              v-for="skillName in diagnosticSelectedSkills"
              :key="skillName"
              class="inline-flex items-center rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-600 dark:text-sky-300"
            >
              {{ skillName }}
            </span>
          </div>
          <div
            v-if="diagnosticContextSources.length > 0"
            class="flex flex-wrap items-center gap-1.5"
          >
            <span class="font-mono text-[10px] text-muted-foreground"
              >context_sources</span
            >
            <span
              v-for="source in diagnosticContextSources"
              :key="source.key"
              class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px]"
              :class="
                source.active
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : 'bg-muted text-muted-foreground'
              "
            >
              {{ source.label }}
            </span>
          </div>
        </div>

        <!-- Markdown content -->
        <div
          v-if="msg.content"
          class="overflow-hidden rounded-2xl border border-border/30 bg-gradient-to-br from-muted/40 to-muted/20 shadow-sm"
          :class="compact ? 'px-2.5 py-1.5 text-sm' : 'px-4 py-3'"
        >
          <div
            class="transition-[max-height] duration-200"
            :class="[
              canCollapse && !expandedMap[index]
                ? 'relative max-h-[300px] overflow-hidden'
                : '',
            ]"
          >
            <MarkdownRender
              :content="msg.content"
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
              v-if="canCollapse && !expandedMap[index]"
              class="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-muted/90 to-transparent"
            ></div>
          </div>
          <button
            v-if="canCollapse && !msg.streaming"
            type="button"
            class="mt-1 flex w-full items-center justify-center gap-1 rounded py-1 text-xs text-primary transition-colors hover:underline"
            @click="toggleExpand(index)"
          >
            {{
              expandedMap[index]
                ? $t('common.globalAiChat.collapseMessage')
                : $t('common.globalAiChat.expandMore')
            }}
          </button>
        </div>
        <!-- SSE error retry -->
        <div
          v-if="msg.requestFailedRetry"
          class="mt-1 flex items-center gap-1.5"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          <Button
            type="link"
            size="small"
            class="!p-0 !text-primary"
            @click="emit('retry', index)"
          >
            {{ $t('common.globalAiChat.retry') }}
          </Button>
        </div>

        <!-- Generating indicator (tool calls running but no content yet) -->
        <div
          v-if="msg.streaming && !msg.content && msg.toolCalls?.length"
          class="flex items-center gap-1.5 px-2 py-0.5 text-muted-foreground"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          <span class="typing-dots"
            ><span></span><span></span><span></span
          ></span>
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
              compact
                ? 'gap-1 px-2 py-1 text-[11px]'
                : 'gap-1.5 px-2.5 py-1.5 text-xs'
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
              <span
                v-if="toolGroupSummary.error"
                class="flex items-center gap-0.5 text-red-500"
              >
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
                transform: isToolGroupExpanded(index)
                  ? 'rotate(180deg)'
                  : 'rotate(0deg)',
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
              <div
                class="tc-timeline relative"
                :class="compact ? 'px-2 py-1 pl-5' : 'px-2.5 py-1.5 pl-6'"
              >
                <!-- Timeline vertical line -->
                <div
                  v-if="msg.toolCalls.length > 1"
                  class="absolute w-px bg-border/40"
                  :class="
                    compact
                      ? 'bottom-1 left-[8px] top-1'
                      : 'bottom-1.5 left-[9px] top-1.5'
                  "
                ></div>

                <div
                  v-for="toolItem in toolDisplayItems"
                  :key="toolItem.index"
                  class="relative"
                  :class="
                    toolItem.index > 0 ? (compact ? 'mt-0.5' : 'mt-1') : ''
                  "
                >
                  <!-- Timeline dot -->
                  <div
                    class="absolute z-[1]"
                    :class="compact ? '-left-3 top-[5px]' : '-left-4 top-[7px]'"
                  >
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
                        compact
                          ? 'gap-1 px-2 py-[3px] text-[11px]'
                          : 'gap-1.5 px-2.5 py-1 text-xs',
                        toolItem.hasDetails
                          ? 'cursor-pointer'
                          : 'cursor-default',
                      ]"
                      :data-testid="`tool-call-toggle-${toolItem.index}`"
                      @click="toggleToolExpand(toolItem.tc, toolItem.index)"
                    >
                      <!-- Status pill -->
                      <span
                        class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px text-[10px] font-medium leading-tight"
                        :class="
                          toolItem.tc.status === 'running'
                            ? getToolDisplayState(toolItem.tc) ===
                              'waiting_confirm'
                              ? 'tc-pill-pulse bg-warning/10 text-warning'
                              : 'tc-pill-pulse bg-primary/10 text-primary'
                            : toolItem.tc.status === 'success'
                              ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                              : 'bg-red-500/10 text-red-500'
                        "
                      >
                        <IconifyIcon
                          v-if="toolItem.tc.status !== 'running'"
                          :icon="
                            toolItem.tc.status === 'success'
                              ? 'lucide:check'
                              : 'lucide:x'
                          "
                          class="size-2.5"
                        />
                        <span
                          v-else
                          class="tc-dot-pulse mr-0.5 inline-block size-1.5 rounded-full bg-current"
                        ></span>
                        {{
                          toolItem.tc.status === 'running'
                            ? getToolDisplayState(toolItem.tc) ===
                              'waiting_confirm'
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
                            <span class="font-medium text-foreground/60">{{
                              toolItem.tc.skillName
                            }}</span>
                            <span class="mx-0.5 text-muted-foreground/30"
                              >›</span
                            >
                          </template>
                          <span class="text-foreground/70">{{
                            toolItem.tc.displayName || toolItem.tc.name
                          }}</span>
                          <span
                            v-if="
                              toolItem.headlineSummary &&
                              toolItem.tc.status === 'success'
                            "
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
                            <span class="shrink-0 text-muted-foreground/55">
                              {{ $t(badge.labelKey) }}
                            </span>
                            <span class="truncate text-foreground/75">{{
                              badge.value
                            }}</span>
                          </span>
                        </span>
                      </span>

                      <!-- Duration -->
                      <span
                        v-if="toolItem.tc.durationMs"
                        class="text-[10px] tabular-nums text-muted-foreground/40"
                      >
                        {{ (toolItem.tc.durationMs / 1000).toFixed(1) }}s
                      </span>

                      <!-- Expand chevron -->
                      <IconifyIcon
                        v-if="toolItem.hasDetails"
                        icon="lucide:chevron-down"
                        class="shrink-0 text-muted-foreground/30 transition-transform duration-200"
                        :class="compact ? 'size-2.5' : 'size-3'"
                        :style="{
                          transform: toolItem.expanded
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                        }"
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
                      <div
                        class="min-h-0 overflow-hidden border-t border-border/20"
                      >
                        <div
                          :class="
                            compact
                              ? 'px-2 py-1 text-[10px]'
                              : 'px-2.5 py-1.5 text-[11px]'
                          "
                        >
                          <div
                            v-if="
                              toolItem.tc.arguments &&
                              Object.keys(toolItem.tc.arguments).length > 0
                            "
                            class="mb-1"
                          >
                            <span
                              class="font-medium text-muted-foreground/60"
                              >{{ $t('common.globalAiChat.args') }}</span
                            >
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
                              <span v-if="toolItem.searchSummary.provider">
                                {{
                                  getSearchProviderLabel(
                                    toolItem.searchSummary.provider,
                                  )
                                }}
                              </span>
                              <span v-if="toolItem.searchSummary.status">
                                {{
                                  getSearchStatusLabel(
                                    toolItem.searchSummary.status,
                                  )
                                }}
                              </span>
                              <span>
                                {{ toolItem.searchSummary.resultCount }}
                              </span>
                            </div>
                            <div
                              v-if="toolItem.searchSummary.failureReason"
                              class="mt-1 whitespace-pre-wrap break-words text-muted-foreground"
                            >
                              {{ toolItem.searchSummary.failureReason }}
                            </div>
                            <ul
                              v-else-if="
                                toolItem.searchSummary.items.length > 0
                              "
                              class="mt-1 space-y-1"
                            >
                              <li
                                v-for="(searchItem, searchIndex) in toolItem
                                  .searchSummary.items"
                                :key="`${toolItem.index}-${searchIndex}-${searchItem.url}`"
                                class="rounded border border-border/20 bg-accent/20 px-1.5 py-1"
                              >
                                <button
                                  type="button"
                                  class="w-full text-left text-[11px] font-medium text-foreground hover:text-primary"
                                  @click.stop="emit('openUrl', searchItem.url)"
                                >
                                  {{ searchItem.title }}
                                </button>
                                <div
                                  class="mt-0.5 break-all text-[10px] text-muted-foreground"
                                >
                                  {{ searchItem.url }}
                                </div>
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
                            <span
                              class="font-medium text-muted-foreground/60"
                              >{{
                                $t('common.globalAiChat.toolExplanation')
                              }}</span
                            >
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
                                @click.stop="
                                  emit(
                                    'copy',
                                    toolItem.structuredOutput.sql || '',
                                  )
                                "
                              >
                                <IconifyIcon
                                  icon="lucide:copy"
                                  class="size-2.5"
                                />
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
                              @click="toggleToolRawExpand(toolItem.index)"
                            >
                              <IconifyIcon
                                icon="lucide:braces"
                                class="size-3 shrink-0"
                              />
                              <span class="flex-1 text-[10px] font-medium">
                                {{ $t('common.globalAiChat.rawResult') }}
                              </span>
                              <IconifyIcon
                                icon="lucide:chevron-down"
                                class="size-2.5 transition-transform duration-200"
                                :style="{
                                  transform: isToolRawExpanded(toolItem.index)
                                    ? 'rotate(180deg)'
                                    : 'rotate(0deg)',
                                }"
                              />
                            </button>
                            <div
                              class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                              :style="{
                                gridTemplateRows: isToolRawExpanded(
                                  toolItem.index,
                                )
                                  ? '1fr'
                                  : '0fr',
                                opacity: isToolRawExpanded(toolItem.index)
                                  ? 1
                                  : 0,
                              }"
                            >
                              <div
                                class="min-h-0 overflow-hidden border-t border-border/20"
                              >
                                <pre
                                  class="overflow-y-auto whitespace-pre-wrap break-all px-1.5 py-1"
                                  :class="[
                                    compact
                                      ? 'max-h-32 text-[10px]'
                                      : 'max-h-40 text-[11px]',
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
                            {{
                              $t(getPageOpErrorHintKey(toolItem.tc.errorType))
                            }}
                          </p>
                          <a
                            v-if="
                              toolItem.tc.resultLink &&
                              toolItem.tc.status === 'success'
                            "
                            :href="toolItem.tc.resultLink"
                            target="_blank"
                            class="mt-1 inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
                          >
                            <IconifyIcon
                              icon="lucide:external-link"
                              class="size-2.5"
                            />
                            {{ $t('common.globalAiChat.viewResult') }}
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Inline confirmation card (for this tool call) / 内联确认卡片（对应本工具调用） -->
                  <div
                    v-for="op in (pendingOps || []).filter(
                      (o) => o.toolCallId === toolItem.tc.id,
                    )"
                    :key="op.invokeId"
                    class="mt-1 overflow-hidden rounded-lg border"
                    :class="
                      op.resolved
                        ? 'border-border/20 bg-accent/10'
                        : 'border-warning/30 bg-warning/5'
                    "
                  >
                    <!-- Resolved state -->
                    <div
                      v-if="op.resolved"
                      class="flex items-center gap-1.5 px-2.5 py-1.5"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                    >
                      <IconifyIcon
                        :icon="
                          op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'
                        "
                        class="size-3 shrink-0"
                        :class="op.allowed ? 'text-green-600' : 'text-red-500'"
                      />
                      <span class="truncate text-muted-foreground">
                        <span class="font-medium text-foreground/60">{{
                          op.operationLabel
                        }}</span>
                        <span
                          v-if="op.operationDescription"
                          class="ml-1 text-muted-foreground/60"
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
                      <div
                        class="flex items-center gap-1.5 px-2.5 py-1.5"
                        :class="compact ? 'text-[10px]' : 'text-[11px]'"
                      >
                        <IconifyIcon
                          icon="lucide:shield-alert"
                          class="size-3.5 shrink-0 text-warning"
                        />
                        <div class="min-w-0 flex-1">
                          <div class="truncate font-medium text-foreground/80">
                            {{ op.operationLabel }}
                          </div>
                          <div
                            v-if="op.operationDescription"
                            class="truncate text-muted-foreground/60"
                          >
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
                                      ((countdownNow ?? now) -
                                        (op.startedAt || 0)) /
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
                            @click="
                              aiPanelStore.resolvePageOp(op.invokeId, true)
                            "
                          >
                            <IconifyIcon icon="lucide:check" class="size-3" />
                            {{ $t('shared.pageOperation.confirmOk') }}
                          </button>
                          <button
                            class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                            :class="compact ? 'text-[10px]' : 'text-[11px]'"
                            @click="
                              aiPanelStore.resolvePageOp(op.invokeId, false)
                            "
                          >
                            <IconifyIcon icon="lucide:x" class="size-3" />
                            {{ $t('shared.pageOperation.confirmCancel') }}
                          </button>
                        </div>
                      </div>
                      <div
                        v-if="hasPendingOpArgs(op.params)"
                        class="border-t border-border/20"
                      >
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
                            :style="{
                              transform: isPendingOpExpanded(op.invokeId)
                                ? 'rotate(180deg)'
                                : 'rotate(0deg)',
                            }"
                          />
                        </button>
                        <div
                          class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                          :style="{
                            gridTemplateRows: isPendingOpExpanded(op.invokeId)
                              ? '1fr'
                              : '0fr',
                            opacity: isPendingOpExpanded(op.invokeId) ? 1 : 0,
                          }"
                        >
                          <div
                            class="min-h-0 overflow-hidden border-t border-border/20"
                          >
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

        <!-- Generated images -->
        <div
          v-if="msg.imageResults && msg.imageResults.length > 0"
          class="flex flex-wrap"
          :class="compact ? 'mt-1.5 gap-2' : 'mt-2 gap-3'"
        >
          <div
            v-for="(img, ii) in msg.imageResults"
            :key="ii"
            class="group/img relative overflow-hidden rounded-lg border border-border"
          >
            <img
              :src="img.isBase64 ? `data:image/png;base64,${img.url}` : img.url"
              :alt="
                img.revisedPrompt || $t('common.globalAiChat.generatedImage')
              "
              class="cursor-pointer object-cover transition-transform hover:scale-105"
              :class="compact ? 'max-h-48 max-w-56' : 'max-h-64 max-w-72'"
              @click="
                emit(
                  'openUrl',
                  img.isBase64 ? `data:image/png;base64,${img.url}` : img.url,
                )
              "
            />
            <a
              :href="
                img.isBase64 ? `data:image/png;base64,${img.url}` : img.url
              "
              :download="img.isBase64 ? 'generated-image.png' : undefined"
              target="_blank"
              class="absolute bottom-2 right-2 flex size-7 items-center justify-center rounded-full bg-black/50 text-white opacity-0 transition-opacity hover:bg-black/70 group-hover/img:opacity-100"
              :title="$t('common.globalAiChat.downloadImage')"
            >
              <IconifyIcon icon="lucide:download" class="size-3.5" />
            </a>
            <div
              v-if="img.revisedPrompt"
              class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-2 pb-1.5 pt-4 text-white opacity-0 transition-opacity group-hover/img:opacity-100"
              :class="compact ? 'text-[10px]' : 'text-xs'"
            >
              <span class="line-clamp-2">{{ img.revisedPrompt }}</span>
            </div>
          </div>
        </div>

        <RichTextDraftCard
          v-if="
            msg.source === 'rich_text_ai' &&
            msg.richTextAI &&
            !msg.streaming &&
            !richTextState?.discarded
          "
          :task="msg.richTextAI"
          :state="richTextState"
          :compact="compact"
          @apply="
            (target, mode) => emit('richTextApply', props.index, target, mode)
          "
          @copy="(mode) => emit('copy', getRichTextDraftCopyContent(mode))"
          @discard="emit('richTextDiscard', props.index)"
          @undo="emit('richTextUndo', props.index)"
        />

        <!-- Confirmation card -->
        <div
          v-if="msg.pendingConfirmation && !msg.streaming"
          class="rounded-lg border border-warning/40 bg-warning/5"
          :class="compact ? 'mt-1.5 px-3 py-2' : 'mt-2 px-4 py-3'"
        >
          <div
            class="flex items-center font-medium text-foreground"
            :class="compact ? 'mb-1.5 gap-1.5 text-xs' : 'mb-2 gap-2 text-sm'"
          >
            <IconifyIcon
              icon="lucide:shield-question"
              class="size-4 text-warning"
            />
            <span>{{ $t('common.globalAiChat.confirmationTitle') }}</span>
          </div>
          <div
            v-if="msg.pendingConfirmation.preview"
            class="overflow-y-auto rounded-md bg-accent/50"
            :class="
              compact
                ? 'mb-2 max-h-32 px-2 py-1.5 text-[10px]'
                : 'mb-3 max-h-40 px-3 py-2 text-xs'
            "
          >
            <table class="w-full text-left">
              <tr
                v-for="(val, key) in msg.pendingConfirmation.preview"
                :key="String(key)"
                class="border-b border-border/30 last:border-0"
              >
                <td
                  class="whitespace-nowrap py-0.5 pr-3 font-medium text-foreground/70"
                >
                  {{ key }}
                </td>
                <td class="break-all py-0.5 text-muted-foreground">
                  {{ typeof val === 'object' ? JSON.stringify(val) : val }}
                </td>
              </tr>
            </table>
          </div>
          <div
            v-if="!msg.pendingConfirmation.resolved"
            class="flex items-center gap-2"
          >
            <Button
              type="primary"
              size="small"
              @click="emit('confirm', props.index)"
            >
              <template #icon>
                <IconifyIcon
                  icon="lucide:check"
                  :class="compact ? 'size-3' : 'size-3.5'"
                />
              </template>
              {{ $t('common.globalAiChat.confirmBtn') }}
            </Button>
            <Button size="small" danger @click="emit('reject', props.index)">
              <template #icon>
                <IconifyIcon
                  icon="lucide:x"
                  :class="compact ? 'size-3' : 'size-3.5'"
                />
              </template>
              {{ $t('common.globalAiChat.rejectBtn') }}
            </Button>
          </div>
          <div
            v-else
            :class="compact ? 'text-[11px]' : 'text-xs'"
            class="text-muted-foreground"
          >
            <IconifyIcon
              icon="lucide:check-circle"
              class="mr-1 inline text-success"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            {{ $t('common.globalAiChat.confirmationResolved') }}
          </div>
        </div>

        <!-- Tool consent card -->
        <div
          v-if="msg.pendingConsent && !msg.streaming"
          class="overflow-hidden rounded-lg border"
          :class="[
            compact ? 'mt-1' : 'mt-1.5',
            msg.pendingConsent.resolved
              ? 'border-border/20 bg-accent/10'
              : 'border-warning/30 bg-warning/5',
          ]"
        >
          <!-- Resolved state: compact single line -->
          <div
            v-if="msg.pendingConsent.resolved"
            class="flex items-center gap-1.5 px-2.5 py-1 text-[11px]"
          >
            <IconifyIcon
              :icon="
                msg.pendingConsent.rejected
                  ? 'lucide:x-circle'
                  : msg.pendingConsent.autoApproved
                    ? 'lucide:shield-check'
                    : 'lucide:check-circle'
              "
              class="size-3 shrink-0"
              :class="
                msg.pendingConsent.rejected ? 'text-red-500' : 'text-green-600'
              "
            />
            <span class="truncate text-muted-foreground">
              <span
                v-if="msg.pendingConsent.skillName"
                class="font-medium text-foreground/60"
                >{{ msg.pendingConsent.skillName }} ›</span
              >
              <code class="text-[10px]">{{ msg.pendingConsent.toolName }}</code>
            </span>
            <span
              class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
              :class="
                msg.pendingConsent.rejected
                  ? 'bg-red-50 text-red-600 dark:bg-red-950/30'
                  : msg.pendingConsent.autoApproved
                    ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/30'
                    : 'bg-green-50 text-green-600 dark:bg-green-950/30'
              "
            >
              {{
                msg.pendingConsent.rejected
                  ? $t('common.globalAiChat.consentRejected')
                  : msg.pendingConsent.autoApproved
                    ? $t('common.globalAiChat.consentAutoApproved')
                    : $t('common.globalAiChat.consentApproved')
              }}
            </span>
          </div>

          <!-- Pending state: inline with actions -->
          <template v-else>
            <p
              class="border-b border-border/20 px-2.5 py-1 text-[10px] text-muted-foreground"
            >
              {{ $t('common.globalAiChat.consentFirstTimeHint') }}
            </p>
            <div class="flex items-center gap-1.5 px-2.5 py-1.5">
              <IconifyIcon
                icon="lucide:shield-alert"
                class="size-3.5 shrink-0 text-warning"
              />
              <span class="flex-1 truncate text-[11px] text-muted-foreground">
                <span
                  v-if="msg.pendingConsent.skillName"
                  class="font-medium text-foreground/70"
                  >{{ msg.pendingConsent.skillName }} ›</span
                >
                <code class="text-[10px] font-semibold">{{
                  msg.pendingConsent.toolName
                }}</code>
              </span>
              <div class="flex shrink-0 items-center gap-1">
                <button
                  class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                  @click="emit('consentConfirm', props.index)"
                >
                  <IconifyIcon icon="lucide:check" class="size-3" />
                  {{ $t('common.globalAiChat.consentAllow') }}
                </button>
                <button
                  class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                  @click="emit('consentReject', props.index)"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                  {{ $t('common.globalAiChat.consentDeny') }}
                </button>
              </div>
            </div>
            <!-- Collapsible args -->
            <details
              v-if="
                msg.pendingConsent.arguments &&
                Object.keys(msg.pendingConsent.arguments).length > 0
              "
              class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
            >
              <summary
                class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
              >
                <IconifyIcon icon="lucide:code" class="size-2.5" />
                {{ $t('common.globalAiChat.consentShowArgs') }}
                <IconifyIcon
                  icon="lucide:chevron-down"
                  class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180"
                />
              </summary>
              <div class="border-t border-border/20 px-2.5 py-1">
                <pre
                  class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
                  >{{
                    JSON.stringify(msg.pendingConsent.arguments, null, 2)
                  }}</pre
                >
              </div>
            </details>
          </template>
        </div>

        <!-- RAG sources -->
        <div
          v-if="msg.ragSources && msg.ragSources.length > 0 && !msg.streaming"
          :class="compact ? 'mt-1' : 'mt-1.5'"
        >
          <details class="group">
            <summary
              class="flex cursor-pointer items-center text-muted-foreground hover:text-foreground"
              :class="compact ? 'gap-1 text-[11px]' : 'gap-1.5 text-xs'"
            >
              <IconifyIcon
                icon="lucide:book-open"
                :class="compact ? 'size-3' : 'size-3.5'"
              />
              <span
                >{{ $t('common.globalAiChat.ragSources') }} ({{
                  msg.ragSources.length
                }})</span
              >
            </summary>
            <div
              :class="
                compact ? 'mt-1 space-y-2 pl-4' : 'mt-1.5 space-y-2.5 pl-5'
              "
            >
              <div
                v-for="(grp, gi) in ragGroups"
                :key="gi"
                class="rounded-md border border-border/30 bg-accent/40"
                :class="compact ? 'p-1.5' : 'p-2'"
              >
                <div
                  class="mb-1 flex items-center gap-1 font-medium text-primary/80"
                  :class="compact ? 'text-[10px]' : 'text-xs'"
                >
                  <IconifyIcon icon="lucide:library" class="size-3 shrink-0" />
                  {{ grp.label }}
                </div>
                <button
                  v-for="(src, si) in grp.items"
                  :key="si"
                  type="button"
                  class="block w-full rounded-md bg-accent/50 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  :class="
                    compact
                      ? 'mb-1 px-2 py-1 text-[11px]'
                      : 'mb-1 px-2.5 py-1.5 text-xs'
                  "
                  @click="openRagDetail(src)"
                >
                  <div class="font-medium text-foreground">
                    {{ src.doc_name }}
                  </div>
                  <div
                    :class="
                      compact ? 'mt-0.5 line-clamp-2' : 'mt-0.5 line-clamp-2'
                    "
                  >
                    {{ src.snippet }}
                  </div>
                  <div class="mt-0.5 text-[10px] text-primary/70">
                    {{ $t('common.globalAiChat.ragClickForDetail') }}
                  </div>
                </button>
              </div>
            </div>
          </details>
        </div>

        <Modal
          v-model:open="ragDetailOpen"
          :title="$t('common.globalAiChat.ragSourceDetailTitle')"
          :footer="null"
          :width="compact ? '90vw' : 560"
          destroy-on-close
        >
          <div v-if="ragDetailItem" class="space-y-2 text-sm">
            <div
              v-if="
                ragDetailItem.knowledge_base_name ||
                ragDetailItem.knowledge_base_id != null
              "
            >
              <span class="text-muted-foreground"
                >{{ $t('common.globalAiChat.ragKbLabel') }}:</span
              >
              {{
                ragDetailItem.knowledge_base_name ||
                `KB#${ragDetailItem.knowledge_base_id}`
              }}
            </div>
            <div>
              <span class="text-muted-foreground"
                >{{ $t('common.globalAiChat.ragDocLabel') }}:</span
              >
              {{ ragDetailItem.doc_name }}
            </div>
            <div
              v-if="ragDetailItem.page != null || ragDetailItem.heading"
              class="text-xs text-muted-foreground"
            >
              <template v-if="ragDetailItem.page != null">
                {{
                  $t('common.globalAiChat.ragPageLabel', {
                    page: ragDetailItem.page,
                  })
                }}
              </template>
              <template v-if="ragDetailItem.heading">
                · {{ ragDetailItem.heading }}
              </template>
            </div>
            <div
              class="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-foreground"
            >
              {{ ragDetailItem.snippet }}
            </div>
          </div>
        </Modal>

        <!-- Action Buttons -->
        <div
          v-if="
            msg.actionButtons && msg.actionButtons.length > 0 && !msg.streaming
          "
          class="flex flex-wrap"
          :class="compact ? 'mt-1.5 gap-1.5' : 'mt-2 gap-2'"
        >
          <Button
            v-for="(btn, bi) in msg.actionButtons"
            :key="bi"
            size="small"
            :type="
              btn.style === 'primary'
                ? 'primary'
                : btn.style === 'danger'
                  ? 'default'
                  : 'default'
            "
            :danger="btn.style === 'danger'"
            :disabled="!!msg.actionButtonsUsed"
            :class="compact ? '!text-xs' : ''"
            @click="emit('actionClick', props.index, btn.value)"
          >
            {{ btn.label }}
          </Button>
        </div>

        <!-- Stats + Copy + Regenerate -->
        <div
          v-if="msg.content && !msg.streaming"
          class="flex items-center text-muted-foreground/70 transition-opacity duration-200 group-hover:opacity-100"
          :class="[
            compact ? 'mt-0.5 gap-0.5 text-[11px]' : 'mt-1 gap-1 text-xs',
            compact ? 'opacity-100' : 'opacity-60 hover:opacity-100',
          ]"
        >
          <span
            v-if="msg.created_at"
            class="mr-0.5 text-[10px] tabular-nums text-muted-foreground/40"
          >
            {{ formatTimeOnly(msg.created_at) }}
          </span>
          <span v-if="msg.tokenUsage" class="mr-0.5 tabular-nums"
            >{{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}</span
          >
          <span v-if="msg.durationMs" class="mr-0.5 tabular-nums"
            >· {{ (msg.durationMs / 1000).toFixed(1) }}s</span
          >
          <Tooltip
            v-if="msg.memoryUpdated"
            :title="$t('common.globalAiChat.memoryUpdated')"
          >
            <span
              class="mr-0.5 inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
            >
              <IconifyIcon icon="lucide:brain" class="size-2.5" />
            </span>
          </Tooltip>
          <span class="mx-0.5 text-border">·</span>
          <Tooltip :title="$t('common.globalAiChat.copy')">
            <button
              class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
              :class="compact ? 'size-5' : 'size-5'"
              @click="emit('copy', msg.content)"
            >
              <IconifyIcon
                icon="lucide:copy"
                :class="compact ? 'size-2.5' : 'size-3'"
              />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.globalAiChat.regenerate')">
            <button
              class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
              :class="compact ? 'size-5' : 'size-5'"
              @click="emit('regenerate', props.index)"
            >
              <IconifyIcon
                icon="lucide:refresh-cw"
                :class="compact ? 'size-2.5' : 'size-3'"
              />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <!-- ===== User message ===== -->
    <div v-else class="group" :class="compact ? 'max-w-[85%]' : 'max-w-[75%]'">
      <!-- Attachments -->
      <div
        v-if="msg.attachments?.length"
        class="flex flex-wrap justify-end"
        :class="compact ? 'mb-1 gap-1' : 'mb-1.5 gap-1.5'"
      >
        <template
          v-for="(att, ati) in msg.attachments"
          :key="`${ati}-${att.url}`"
        >
          <img
            v-if="att.type === 'image'"
            :src="att.preview || att.url"
            :alt="att.name || ''"
            class="cursor-pointer rounded-lg object-contain"
            :class="
              compact
                ? 'max-h-32 max-w-40'
                : 'max-h-48 max-w-60 border border-white/20'
            "
            @error="onUserAttachmentImageError($event, att)"
            @click="emit('openUrl', att.url)"
          />
          <audio
            v-else-if="att.type === 'audio'"
            controls
            :src="att.url"
            class="max-w-full rounded-lg"
            :class="compact ? 'max-w-48' : 'max-w-64'"
          ></audio>
          <video
            v-else-if="att.type === 'video'"
            controls
            :src="att.url"
            class="max-w-full rounded-lg object-contain"
            :class="
              compact
                ? 'max-h-32 max-w-40'
                : 'max-h-48 max-w-60 border border-white/20'
            "
          ></video>
          <a
            v-else
            :href="att.url"
            target="_blank"
            class="flex items-center rounded-lg bg-primary-foreground/10 text-primary-foreground hover:bg-primary-foreground/20"
            :class="
              compact
                ? 'gap-1 px-1.5 py-0.5 text-[11px]'
                : 'gap-1.5 px-2 py-1 text-xs'
            "
          >
            <IconifyIcon
              :icon="getFileIcon(att.name || '', att.mime_type)"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            <span
              :class="compact ? 'max-w-[80px]' : 'max-w-[120px]'"
              class="truncate"
            >
              {{ att.name || $t('common.globalAiChat.file') }}
            </span>
          </a>
        </template>
      </div>
      <div
        v-if="msg.content"
        class="whitespace-pre-wrap rounded-2xl rounded-br-md bg-gradient-to-br from-primary to-primary/85 px-4 py-2.5 text-sm text-primary-foreground shadow-md shadow-primary/15"
      >
        {{ msg.content }}
      </div>
      <!-- User message toolbar (timestamp + copy + edit) -->
      <div
        class="mt-0.5 flex items-center justify-end gap-0.5 transition-opacity duration-200"
        :class="compact ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
      >
        <span
          v-if="msg.created_at"
          class="mr-0.5 text-[10px] tabular-nums text-muted-foreground/40"
        >
          {{ formatTimeOnly(msg.created_at) }}
        </span>
        <Tooltip :title="$t('common.globalAiChat.copy')">
          <button
            class="flex size-5 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
            @click="emit('copy', msg.content)"
          >
            <IconifyIcon icon="lucide:copy" class="size-2.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.editResend')">
          <button
            class="flex size-5 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
            @click="emit('edit', props.index)"
          >
            <IconifyIcon icon="lucide:pencil" class="size-2.5" />
          </button>
        </Tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0;
  }
}

@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 0.4;
  }

  50% {
    opacity: 0.8;
  }
}

@keyframes glow-pulse {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@keyframes tc-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 hsl(var(--primary) / 40%);
    opacity: 0.6;
  }

  50% {
    box-shadow: 0 0 0 3px hsl(var(--primary) / 0%);
    opacity: 1;
  }
}

@keyframes tc-pill-glow {
  0%,
  100% {
    opacity: 0.7;
  }

  50% {
    opacity: 1;
  }
}

.streaming-cursor::after {
  display: inline;
  font-weight: bold;
  color: hsl(var(--primary));
  content: '▍';
  animation: blink 0.8s step-end infinite;
}

/* Skeleton line pulse animation / 骨架线脉冲动画 */
.skeleton-line {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

/* Thinking glow ring / 思考光环 */
.thinking-glow::before {
  position: absolute;
  inset: -2px;
  content: '';
  background: radial-gradient(
    circle,
    hsl(var(--primary) / 20%),
    transparent 70%
  );
  border-radius: 50%;
  animation: glow-pulse 2s ease-in-out infinite;
}

.thinking-chip {
  width: fit-content;
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 96%),
    hsl(var(--accent) / 42%)
  );
  border: 1px solid hsl(var(--border) / 28%);
  border-radius: 999px;
  box-shadow:
    inset 0 1px 0 hsl(var(--background) / 84%),
    0 12px 28px -30px hsl(var(--primary) / 55%);
}

.thinking-chip-icon {
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 9%),
    hsl(var(--primary) / 4%)
  );
}

.thinking-status-dots span {
  width: 3px;
  height: 3px;
}

.thinking-sheet-card {
  position: relative;
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 95%),
    hsl(var(--accent) / 18%)
  );
  border: 1px solid hsl(var(--border) / 18%);
  border-radius: 18px;
  box-shadow:
    inset 0 1px 0 hsl(var(--background) / 82%),
    0 18px 42px -36px hsl(var(--foreground) / 35%);
  backdrop-filter: blur(12px);
}

.thinking-sheet-card::before {
  position: absolute;
  top: 14px;
  bottom: 14px;
  left: 0;
  width: 2px;
  content: '';
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 46%),
    hsl(var(--primary) / 0%)
  );
  border-radius: 999px;
}

.thinking-markdown :deep(p + p) {
  margin-top: 0.65rem;
}

.thinking-markdown :deep(pre) {
  margin: 0.75rem 0;
}

/* Typing dots animation / 打字点点动画 */
.typing-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}

.typing-dots span {
  display: inline-block;
  width: 4px;
  height: 4px;
  background-color: hsl(var(--primary));
  border-radius: 50%;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

/* Tool call timeline dot pulse (running state) / 工具调用时间线点脉冲 */
.tc-dot-pulse {
  box-shadow: 0 0 0 0 hsl(var(--primary) / 40%);
  animation: tc-pulse 1.5s ease-in-out infinite;
}

/* Tool call pill pulse (running status badge) / 工具调用药丸脉冲 */
.tc-pill-pulse {
  animation: tc-pill-glow 2s ease-in-out infinite;
}
</style>

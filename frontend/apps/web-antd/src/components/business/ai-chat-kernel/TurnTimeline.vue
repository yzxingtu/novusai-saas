<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  getOptimizingToolsForDisplay,
  getRagSourcesForDisplay,
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
} from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import ChatMessageThinkingBlock from '#/components/business/ai-chat-panel/ChatMessageThinkingBlock.vue';
import ChatMessageToolCalls from '#/components/business/ai-chat-panel/ChatMessageToolCalls.vue';
import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';
import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    index?: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
    state: TurnFlowState;
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    index: 0,
    pendingOps: () => [],
  },
);

const emit = defineEmits<{
  copy: [content: string];
}>();

const timeline = computed(() => props.state.timeline);
const isLiveMessage = computed(() => props.msg.streaming === true);
const isProcessExpanded = ref(false);
const liveProcessStatusLabel = computed(() =>
  $t('common.globalAiChat.turnStageStatus.running'),
);
const processTerminalStage = computed(() => visibleTimeline.value.at(-1));
const processStatusLabel = computed(() => {
  if (isLiveMessage.value) {
    return liveProcessStatusLabel.value;
  }
  const stage = processTerminalStage.value;
  if (!stage) {
    return undefined;
  }
  return getStageStatusLabel(stage);
});
const displayOptimizingTools = computed(() =>
  getOptimizingToolsForDisplay(props.msg),
);
const displayThinkingContent = computed(() =>
  getThinkingContentForDisplay(props.msg),
);
const displayToolCalls = computed(
  () => getToolCallsForDisplay(props.msg) ?? [],
);
const displayRagSources = computed(
  () => getRagSourcesForDisplay(props.msg) ?? [],
);

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

const GENERIC_STAGE_STATUS_TOKENS = new Set([
  'completed',
  'error',
  'failed',
  'in progress',
  'interrupted',
  'running',
  'skipped',
]);

const GENERIC_STAGE_COPY_BY_TYPE: Record<
  TurnFlowStageForDisplay['type'],
  readonly string[]
> = {
  answer_assembly: [
    'answer assembly',
    'assembling answer',
    'assembling the final answer',
    'final answer assembly',
    'response assembly',
  ],
  completed: [
    'complete',
    'completed',
    'done',
    'process complete',
    'process completed',
    'turn complete',
    'turn completed',
    'workflow complete',
    'workflow completed',
  ],
  failed: [
    'error',
    'errored',
    'failed',
    'failure',
    'process failed',
    'turn failed',
    'workflow failed',
  ],
  retrieval: [
    'evidence retrieval',
    'information retrieval',
    'no evidence retrieved',
    'retrieval',
    'source retrieval',
  ],
  thinking: ['analysis', 'reasoning', 'thinking'],
  tool_execution: [
    'executing tools',
    'no tools executed',
    'tool call execution',
    'tool calls',
    'tool execution',
  ],
  tool_selection: [
    'select tools',
    'selecting tools',
    'tool filtering',
    'tool selection',
  ],
};

const GENERIC_STAGE_COPY_PATTERNS: Record<
  TurnFlowStageForDisplay['type'],
  readonly RegExp[]
> = {
  answer_assembly: [/^assembling (the )?(final )?answer$/],
  completed: [/^(process|turn|workflow) completed$/],
  failed: [/^(process|turn|workflow) failed$/],
  retrieval: [
    /^(found|retrieved|retrieving) \d+ (sources?|results?|items?|documents?|evidence)( .*)?$/,
  ],
  thinking: [
    /^(completed )?(analysis|reasoning|thinking)( and planning)?$/,
    /^(analysis|reasoning|thinking) complete$/,
  ],
  tool_execution: [
    /^(executed|executing) \d+ tool calls?$/,
    /^tool calls? executed \d+$/,
  ],
  tool_selection: [
    /^(selected|selecting) \d+ of \d+ tools?$/,
    /^\d+ of \d+ tools? selected$/,
  ],
};

const TRANSCRIPT_COPY_MEANINGFUL_CHAR_RE = /[\p{L}\p{N}]/u;
const TRANSCRIPT_COPY_SYMBOL_ONLY_RE = /^[\p{P}\p{S}\s]+$/u;

const GENERIC_STAGE_DETAIL_COPY_BY_TYPE: Record<
  TurnFlowStageForDisplay['type'],
  readonly string[]
> = {
  answer_assembly: [
    'answer assembly',
    'answer assembled',
    '答案整理',
    '整理答案',
  ],
  completed: [
    'completed',
    'complete',
    'done',
    '本轮完成',
    '本轮结束',
    '已完成',
  ],
  failed: ['failed', 'failure', 'error', '执行失败', '本轮失败', '处理失败'],
  retrieval: [
    'retrieval',
    'information retrieval',
    'source retrieval',
    'evidence retrieval',
    '查找来源',
    '检索来源',
    '来源检索',
    '证据检索',
  ],
  thinking: [
    'thinking',
    'analysis',
    'reasoning',
    '思考',
    '思考过程',
    '思考与规划',
    '已完成思考',
    '已完成思考与规划',
    '完成思考',
    '完成思考与规划',
  ],
  tool_execution: [
    'tool execution',
    'tool calls',
    'tool call execution',
    'executing tools',
    '工具执行',
    '执行工具',
  ],
  tool_selection: [
    'tool selection',
    'selecting tools',
    'select tools',
    '工具选择',
    '选择工具',
    '工具筛选',
  ],
};

const GENERIC_STAGE_DETAIL_COPY_PATTERNS: Record<
  TurnFlowStageForDisplay['type'],
  readonly RegExp[]
> = {
  answer_assembly: [/^已?完成答案整理$/u, /^正在(组织|整理)答案$/u],
  completed: [/^本轮(完成|结束)$/u, /^completed$/iu],
  failed: [/^(执行|处理)?失败$/u, /^failed$/iu],
  retrieval: [
    /^未?(检索|获取|找到)到(任何)?(证据|来源|结果)$/u,
    /^查找来源$/u,
    /^retrieval$/iu,
  ],
  thinking: [
    /^思考(过程)?$/u,
    /^已?完成思考(与规划)?$/u,
    /^正在思考(与规划)?$/u,
    /^(analysis|reasoning|thinking)( and planning)?$/iu,
  ],
  tool_execution: [
    /^no tools executed$/iu,
    /^executed \d+ tool calls?$/iu,
    /^执行了?\d+个工具调用$/u,
  ],
  tool_selection: [
    /^selected \d+ of \d+ tools?$/iu,
    /^\d+ of \d+ tools? selected$/iu,
    /^筛选了?\d+个工具$/u,
  ],
};

function normalizeMeaningfulTranscriptCopy(value: unknown): string | undefined {
  const normalized = normalizeOptionalString(value);
  if (
    !normalized ||
    TRANSCRIPT_COPY_SYMBOL_ONLY_RE.test(normalized) ||
    !TRANSCRIPT_COPY_MEANINGFUL_CHAR_RE.test(normalized)
  ) {
    return undefined;
  }
  return normalized;
}

function normalizeComparableStageCopy(value: string): string {
  return value
    .normalize('NFKC')
    .toLocaleLowerCase()
    .replaceAll(/[_-]+/g, ' ')
    .replaceAll(/[\p{P}\p{S}]+/gu, ' ')
    .replaceAll(/\s+/gu, ' ')
    .trim();
}

function normalizeAsciiStageCopy(value: unknown): string | undefined {
  const normalized = normalizeOptionalString(value);
  const containsNonAscii = [...(normalized ?? '')].some(
    (character) => (character.codePointAt(0) ?? 0) > 127,
  );
  if (!normalized || containsNonAscii || !/[A-Z]/i.test(normalized)) {
    return undefined;
  }
  const collapsed = normalized
    .toLowerCase()
    .replaceAll(/[_-]+/g, ' ')
    .replaceAll(/[^a-z0-9 ]+/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim();
  return collapsed.length > 0 ? collapsed : undefined;
}

function isGenericBackendStageCopy(
  stage: TurnFlowStageForDisplay,
  value: unknown,
) {
  const normalized = normalizeAsciiStageCopy(value);
  if (!normalized) {
    return false;
  }
  const normalizedType = stage.type.replaceAll('_', ' ');
  const normalizedStatus = stage.status.replaceAll('_', ' ');
  return (
    GENERIC_STAGE_STATUS_TOKENS.has(normalized) ||
    GENERIC_STAGE_COPY_BY_TYPE[stage.type].includes(normalized) ||
    GENERIC_STAGE_COPY_PATTERNS[stage.type].some((pattern) =>
      pattern.test(normalized),
    ) ||
    normalized === normalizedType ||
    normalized === `${normalizedType} ${normalizedStatus}` ||
    normalized === `${normalizedStatus} ${normalizedType}`
  );
}

function getMeaningfulStageTitle(stage: TurnFlowStageForDisplay) {
  const title = normalizeMeaningfulTranscriptCopy(stage.title);
  if (!title || isGenericBackendStageCopy(stage, title)) {
    return undefined;
  }
  return title;
}

function getMeaningfulStageSummary(stage: TurnFlowStageForDisplay) {
  const summary = normalizeMeaningfulTranscriptCopy(stage.summary);
  if (!summary || isGenericBackendStageCopy(stage, summary)) {
    return undefined;
  }
  return summary === getMeaningfulStageTitle(stage) ? undefined : summary;
}

function getStageKey(stage: TurnFlowStageForDisplay, index: number) {
  return `${messageIdentity.value}:${stage.id}-${index}`;
}

function getStageTypeLabel(stage: TurnFlowStageForDisplay) {
  const stageTitle = getMeaningfulStageTitle(stage);
  if (stageTitle) {
    return stageTitle;
  }
  return $t(`common.globalAiChat.turnStageType.${stage.type}`);
}

function getStageStatusLabel(stage: TurnFlowStageForDisplay) {
  return $t(`common.globalAiChat.turnStageStatus.${stage.status}`);
}

function normalizeMetricNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function readMetricNumber(
  metrics: Record<string, number | string>,
  keys: string[],
): number | undefined {
  for (const key of keys) {
    const normalized = normalizeMetricNumber(metrics[key]);
    if (normalized !== undefined) {
      return normalized;
    }
  }
  return undefined;
}

function readMetricText(
  metrics: Record<string, number | string>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const normalized = normalizeOptionalString(metrics[key]);
    if (normalized) {
      return normalized;
    }
  }
  return undefined;
}

function getMetricSummaryForStage(
  stage: TurnFlowStageForDisplay,
): string | undefined {
  const metrics = stage.metrics ?? {};
  if (stage.type === 'tool_selection') {
    const selected = readMetricNumber(metrics, [
      'selected',
      'candidate_tools_count',
      'candidateToolsCount',
      'selected_count',
      'selectedCount',
    ]);
    const total = Math.max(
      selected ?? 0,
      readMetricNumber(metrics, [
        'total',
        'all_tools_count',
        'allToolsCount',
        'total_tools_count',
        'totalToolsCount',
        'candidate_count',
        'candidateCount',
      ]) ?? 0,
    );
    if (total > 0) {
      return $t('common.globalAiChat.optimizingTools', {
        total,
        selected: selected ?? 0,
      });
    }
  }

  if (stage.type === 'tool_execution') {
    const total = Math.max(
      readMetricNumber(metrics, ['total', 'tool_rounds', 'tool_call_count']) ??
        0,
      (readMetricNumber(metrics, ['completed_tool_calls']) ?? 0) +
        (readMetricNumber(metrics, ['failed_tool_calls']) ?? 0),
    );
    if (total > 0) {
      return stage.status === 'running'
        ? $t('common.globalAiChat.toolGroupRunning', { count: total })
        : $t('common.globalAiChat.toolGroupSummary', { count: total });
    }
  }

  if (stage.type === 'retrieval') {
    const count = readMetricNumber(metrics, [
      'count',
      'source_count',
      'sourceCount',
      'result_count',
      'resultCount',
      'evidence_count',
      'evidenceCount',
      'total',
    ]);
    if (count !== undefined && count > 0) {
      return $t('common.globalAiChat.turnRetrievalSummary', { count });
    }
  }

  return undefined;
}

function getStageSummary(stage: TurnFlowStageForDisplay) {
  const stageSummary = getMeaningfulStageSummary(stage);
  if (stageSummary) {
    return stageSummary;
  }

  if (stage.type === 'failed') {
    const errorSurface = props.state.flow.errorSurface;
    const errorMessage =
      (typeof errorSurface?.message === 'string' &&
        errorSurface.message.trim()) ||
      (typeof errorSurface?.summary === 'string' &&
        errorSurface.summary.trim()) ||
      undefined;
    if (errorMessage) {
      return errorMessage;
    }
  }

  const metricSummary = getMetricSummaryForStage(stage);
  if (metricSummary) {
    return metricSummary;
  }

  const metrics = stage.metrics ?? {};
  if (stage.type === 'tool_execution' && stage.status === 'running') {
    const provider =
      readMetricText(metrics, [
        'provider',
        'selected_backend',
        'selectedBackend',
        'provider_name',
        'providerName',
      ]) ?? readMetricText(metrics, ['provider_chain', 'providerChain']);
    if (provider) {
      return `${$t('common.globalAiChat.toolSearchProvider')}: ${provider}`;
    }
  }

  if (stage.status === 'running') {
    return $t(`common.globalAiChat.turnStageSummary.${stage.type}`);
  }

  return `${getStageTypeLabel(stage)} · ${getStageStatusLabel(stage)}`;
}

function getProcessHeadlineForStage(stage: TurnFlowStageForDisplay) {
  const stageSummary = getMeaningfulStageSummary(stage);
  if (stageSummary) {
    return stageSummary;
  }

  const metricSummary = getMetricSummaryForStage(stage);
  if (metricSummary) {
    return metricSummary;
  }

  return stage.status === 'completed'
    ? getStageTypeLabel(stage)
    : getStageSummary(stage);
}

function getStageStatusClass(stage: TurnFlowStageForDisplay) {
  if (stage.status === 'running') {
    return 'border-primary/18 bg-primary/[0.08] text-primary';
  }
  if (stage.status === 'interrupted') {
    return 'border-amber-500/16 bg-amber-500/[0.10] text-amber-700 dark:text-amber-300';
  }
  if (stage.status === 'completed') {
    return 'border-emerald-500/16 bg-emerald-500/[0.10] text-emerald-700 dark:text-emerald-300';
  }
  return 'border-red-500/16 bg-red-500/[0.10] text-red-500';
}

function shouldShowStageStatus(stage: TurnFlowStageForDisplay) {
  return (
    stage.status === 'running' ||
    stage.status === 'error' ||
    stage.status === 'interrupted'
  );
}

function getProcessStatusClass() {
  const stage = processTerminalStage.value;
  if (isLiveMessage.value) {
    return 'border-primary/16 bg-primary/[0.08] text-primary';
  }
  if (stage?.status === 'error') {
    return 'border-red-500/16 bg-red-500/[0.10] text-red-500';
  }
  if (stage?.status === 'interrupted') {
    return 'border-amber-500/16 bg-amber-500/[0.10] text-amber-700 dark:text-amber-300';
  }
  return 'border-emerald-500/16 bg-emerald-500/[0.10] text-emerald-700 dark:text-emerald-300';
}

function getThinkingDetailText(stage: TurnFlowStageForDisplay) {
  return getFilteredStageDetailLines(stage).join('\n\n');
}

function getFilteredStageDetailLines(stage: TurnFlowStageForDisplay) {
  const seen = new Set<string>();
  const titleKey = normalizeComparableStageCopy(
    getMeaningfulStageTitle(stage) ?? '',
  );
  const summaryKey = normalizeComparableStageCopy(
    getMeaningfulStageSummary(stage) ?? '',
  );

  return (stage.detailLines ?? [])
    .flatMap((line) => {
      const normalized = normalizeMeaningfulTranscriptCopy(line);
      return normalized ? [normalized] : [];
    })
    .filter((line) => {
      const comparable = normalizeComparableStageCopy(line);
      if (!comparable) {
        return false;
      }
      if (
        (titleKey && comparable === titleKey) ||
        (summaryKey && comparable === summaryKey)
      ) {
        return false;
      }
      if (
        GENERIC_STAGE_DETAIL_COPY_BY_TYPE[stage.type].includes(comparable) ||
        GENERIC_STAGE_DETAIL_COPY_PATTERNS[stage.type].some((pattern) =>
          pattern.test(line),
        )
      ) {
        return false;
      }
      if (seen.has(comparable)) {
        return false;
      }
      seen.add(comparable);
      return true;
    });
}

function getThinkingBodyContent(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'thinking') {
    return undefined;
  }
  const detailText = getThinkingDetailText(stage);
  if (detailText) {
    return detailText;
  }
  if (
    stage.id === lastThinkingStageId.value &&
    normalizeOptionalString(displayThinkingContent.value)
  ) {
    return displayThinkingContent.value;
  }
  return getMeaningfulStageSummary(stage);
}

const lastThinkingStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'thinking')?.id,
);
const lastToolSelectionStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'tool_selection')?.id,
);
const lastToolExecutionStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'tool_execution')?.id,
);
const lastRetrievalStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'retrieval')?.id,
);

function hasThinkingBody(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'thinking') {
    return false;
  }
  const bodyContent = normalizeOptionalString(getThinkingBodyContent(stage));
  if (!bodyContent) {
    return false;
  }
  const summary = getMeaningfulStageSummary(stage);
  if (!summary || bodyContent !== summary) {
    return true;
  }
  return (
    stage.id === lastThinkingStageId.value &&
    (isLiveMessage.value || stage.status === 'running')
  );
}

function isEmbeddedThinkingStage(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'thinking' &&
    stage.id === lastThinkingStageId.value &&
    Boolean(normalizeOptionalString(displayThinkingContent.value)) &&
    hasThinkingBody(stage)
  );
}

function hasToolSelectionBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_selection' &&
    stage.id === lastToolSelectionStageId.value &&
    (displayOptimizingTools.value?.selected ?? 0) > 0 &&
    (displayOptimizingTools.value?.total ?? 0) > 0
  );
}

function hasToolExecutionBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_execution' &&
    stage.id === lastToolExecutionStageId.value &&
    displayToolCalls.value.length > 0
  );
}

function hasRetrievalBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'retrieval' &&
    stage.id === lastRetrievalStageId.value &&
    displayRagSources.value.length > 0
  );
}

function hasStageBody(stage: TurnFlowStageForDisplay) {
  return (
    hasThinkingBody(stage) ||
    hasToolSelectionBody(stage) ||
    hasToolExecutionBody(stage) ||
    hasRetrievalBody(stage)
  );
}

function shouldHideCompletedAnswerAssembly(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'answer_assembly' &&
    stage.status === 'completed' &&
    Boolean(
      props.state.answerCard || normalizeMergedTextPart(props.msg.content),
    )
  );
}

function shouldHideSkippedToolSelection(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_selection' &&
    stage.status === 'skipped' &&
    (displayOptimizingTools.value?.selected ?? 0) === 0
  );
}

function shouldHideNoopToolExecution(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'tool_execution' || displayToolCalls.value.length > 0) {
    return false;
  }
  const metrics = stage.metrics ?? {};
  const total =
    readMetricNumber(metrics, ['total', 'tool_rounds', 'tool_call_count']) ?? 0;
  return (
    total <= 0 &&
    stage.status !== 'running' &&
    getFilteredStageDetailLines(stage).length === 0
  );
}

function shouldHideNoopRetrieval(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'retrieval' || displayRagSources.value.length > 0) {
    return false;
  }
  const metrics = stage.metrics ?? {};
  const total =
    readMetricNumber(metrics, [
      'count',
      'source_count',
      'sourceCount',
      'result_count',
      'resultCount',
      'evidence_count',
      'evidenceCount',
      'total',
    ]) ?? 0;
  return (
    total <= 0 &&
    stage.status !== 'running' &&
    getFilteredStageDetailLines(stage).length === 0
  );
}

function shouldRenderStage(stage: TurnFlowStageForDisplay) {
  if (stage.type === 'completed') {
    return false;
  }
  if (shouldHideCompletedAnswerAssembly(stage)) {
    return false;
  }
  if (shouldHideSkippedToolSelection(stage)) {
    return false;
  }
  if (shouldHideNoopToolExecution(stage)) {
    return false;
  }
  if (shouldHideNoopRetrieval(stage)) {
    return false;
  }
  if (stage.type === 'thinking') {
    return Boolean(
      normalizeOptionalString(stage.summary) ||
      normalizeOptionalString(stage.title) ||
      hasThinkingBody(stage),
    );
  }
  return true;
}

const visibleTimeline = computed(() =>
  timeline.value.filter((stage) => shouldRenderStage(stage)),
);

const processHeadline = computed(() => {
  const liveStage = visibleTimeline.value.findLast(
    (stage) => stage.status === 'running',
  );
  const stage = liveStage ?? visibleTimeline.value.at(-1);
  return stage ? getProcessHeadlineForStage(stage) : undefined;
});

function syncProcessExpanded(nextExpanded: boolean) {
  if (isProcessExpanded.value === nextExpanded) {
    return;
  }
  isProcessExpanded.value = nextExpanded;
}

function toggleProcessExpanded() {
  syncProcessExpanded(!isProcessExpanded.value);
}

watch(
  messageIdentity,
  () => {
    syncProcessExpanded(isLiveMessage.value);
  },
  { immediate: true },
);

watch(
  () => props.msg.streaming === true,
  (isStreaming, wasStreaming) => {
    if (isStreaming && !wasStreaming) {
      syncProcessExpanded(true);
    } else if (!isStreaming && wasStreaming) {
      syncProcessExpanded(false);
    }
  },
);
</script>

<template>
  <div
    v-if="visibleTimeline.length > 0"
    data-testid="chat-message-kernel-timeline"
    class="min-w-0"
  >
    <button
      type="button"
      :aria-expanded="isProcessExpanded"
      data-testid="turn-process-toggle"
      :title="
        isProcessExpanded
          ? $t('common.globalAiChat.turnTimelineCollapse')
          : $t('common.globalAiChat.turnTimelineExpand')
      "
      class="turn-process-toggle group flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left"
      @click="toggleProcessExpanded"
    >
      <span
        class="turn-process-pill inline-flex shrink-0 items-center rounded-full px-1.5 py-0.5 text-[8px] font-medium uppercase tracking-[0.14em]"
      >
        {{ $t('common.globalAiChat.turnTimeline') }}
      </span>

      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 flex-wrap items-center gap-1.5">
          <p
            class="text-foreground/74 min-w-0 flex-1 truncate font-medium"
            :class="
              compact
                ? 'text-[9.75px] leading-[1.05rem]'
                : 'text-[10.25px] leading-[1.1rem]'
            "
          >
            {{
              processHeadline ||
              $t('common.globalAiChat.turnStageSummary.answer_assembly')
            }}
          </p>
          <span
            v-if="processStatusLabel"
            class="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[8.5px] font-medium"
            :class="getProcessStatusClass()"
          >
            {{ processStatusLabel }}
          </span>
          <span
            class="turn-process-count inline-flex items-center rounded-full px-1.5 py-0.5 text-[8.5px]"
          >
            {{
              $t('common.globalAiChat.turnStageCount', {
                count: visibleTimeline.length,
              })
            }}
          </span>
        </div>
      </div>

      <span
        class="turn-process-chevron inline-flex shrink-0 items-center justify-center rounded-full p-1 transition-colors"
      >
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-3 transition-transform duration-200"
          :style="{
            transform: isProcessExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }"
        />
      </span>
    </button>

    <div
      data-testid="turn-process-body"
      class="grid overflow-hidden transition-[grid-template-rows,opacity] duration-180 ease-out"
      :style="{
        gridTemplateRows: isProcessExpanded ? '1fr' : '0fr',
        opacity: isProcessExpanded ? 1 : 0,
      }"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="turn-process-track relative mt-1.5 border-l"
          :class="compact ? 'space-y-1.5 pl-2.5' : 'space-y-1.5 pl-3'"
        >
          <div
            v-for="(stage, stageIndex) in visibleTimeline"
            :key="getStageKey(stage, stageIndex)"
            class="relative min-w-0"
            :class="compact ? 'pl-2' : 'pl-2.5'"
            :data-testid="`turn-stage-${stageIndex}`"
          >
            <div
              class="absolute top-[7px] flex size-3 items-center justify-center rounded-full bg-background shadow-[0_0_0_3px_hsl(var(--background)/0.94)]"
              :class="compact ? 'left-[-13px]' : 'left-[-15px]'"
            >
              <span
                class="block rounded-full"
                :class="[
                  compact ? 'size-[6px]' : 'size-[6px]',
                  stage.status === 'running'
                    ? 'bg-primary'
                    : stage.status === 'completed'
                      ? 'bg-emerald-500'
                      : stage.status === 'interrupted'
                        ? 'bg-amber-500'
                        : stage.status === 'skipped'
                          ? 'bg-muted-foreground/35'
                          : 'bg-red-500',
                  stage.status === 'running' ? 'tc-dot-pulse' : '',
                ]"
              ></span>
            </div>

            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                <span
                  class="text-foreground/72 truncate font-medium"
                  :class="compact ? 'text-[9.5px]' : 'text-[10px]'"
                >
                  {{ getStageTypeLabel(stage) }}
                </span>
                <span
                  v-if="shouldShowStageStatus(stage)"
                  class="inline-flex shrink-0 items-center rounded-full border px-1.5 py-0.5 text-[8.5px] font-medium"
                  :class="getStageStatusClass(stage)"
                >
                  {{ getStageStatusLabel(stage) }}
                </span>
              </div>
              <p
                class="text-muted-foreground/58 mt-0.5"
                :class="
                  compact
                    ? 'text-[8.75px] leading-[1rem]'
                    : 'text-[9.25px] leading-[1.05rem]'
                "
              >
                {{ getStageSummary(stage) }}
              </p>

              <div
                v-if="hasStageBody(stage)"
                class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                :data-testid="`turn-stage-body-${stageIndex}`"
                :style="{
                  gridTemplateRows: isProcessExpanded ? '1fr' : '0fr',
                  opacity: isProcessExpanded ? 1 : 0,
                }"
              >
                <div class="min-h-0 overflow-hidden">
                  <div
                    class="mt-1 min-w-0"
                    :class="compact ? 'pl-0.5' : 'pl-1'"
                  >
                    <div
                      class="turn-stage-detail-surface min-w-0 rounded-xl border"
                      :class="compact ? 'px-2.5 py-1.5' : 'px-2.5 py-2'"
                    >
                      <ChatMessageThinkingBlock
                        v-if="isEmbeddedThinkingStage(stage)"
                        :compact="compact"
                        embedded
                        :index="0"
                        :msg="msg"
                      />

                      <div
                        v-else-if="hasThinkingBody(stage)"
                        class="turn-stage-inline-markdown min-w-0"
                      >
                        <MarkdownRender
                          :content="getThinkingBodyContent(stage) ?? ''"
                          :streaming="false"
                        />
                      </div>

                      <div
                        v-else-if="hasToolSelectionBody(stage)"
                        class="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-muted/[0.05] px-2.5 py-2 text-muted-foreground/70"
                        :class="compact ? 'text-[9.5px]' : 'text-[10px]'"
                      >
                        <IconifyIcon
                          icon="lucide:sparkles"
                          class="size-3 text-primary"
                        />
                        <span>{{
                          $t('common.globalAiChat.optimizingTools', {
                            total: displayOptimizingTools?.total ?? 0,
                            selected: displayOptimizingTools?.selected ?? 0,
                          })
                        }}</span>
                      </div>

                      <ChatMessageToolCalls
                        v-else-if="hasToolExecutionBody(stage)"
                        :compact="compact"
                        :countdown-now="countdownNow"
                        embedded
                        :index="0"
                        :msg="msg"
                        :pending-ops="pendingOps"
                        @copy="(content) => emit('copy', content)"
                      />

                      <div
                        v-else-if="hasRetrievalBody(stage)"
                        class="space-y-1.5"
                      >
                        <div
                          v-for="(source, sourceIndex) in displayRagSources"
                          :key="`${stage.id}-source-${source.doc_id}-${sourceIndex}`"
                          class="min-w-0 rounded-lg bg-muted/[0.04] px-2.5 py-2"
                        >
                          <div class="flex min-w-0 items-start gap-2">
                            <IconifyIcon
                              icon="lucide:book-open"
                              class="text-primary/68 mt-0.5 size-3 shrink-0"
                            />
                            <div class="min-w-0 flex-1">
                              <div
                                class="flex min-w-0 flex-wrap items-center gap-1.5"
                              >
                                <span
                                  class="text-foreground/74 truncate text-[10px] font-medium"
                                >
                                  {{ source.doc_name }}
                                </span>
                                <span
                                  v-if="source.knowledge_base_name"
                                  class="text-muted-foreground/58 text-[9px]"
                                >
                                  {{ source.knowledge_base_name }}
                                </span>
                              </div>
                              <p
                                v-if="source.snippet"
                                class="mt-0.5 line-clamp-2 text-[10px] leading-5 text-muted-foreground/60"
                              >
                                {{ source.snippet }}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.turn-process-toggle {
  border: 1px solid hsl(var(--border) / 0.16);
  background: hsl(var(--background) / 0.76);
  box-shadow: 0 10px 18px -26px hsl(var(--foreground) / 0.12);
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.turn-process-toggle:hover {
  border-color: hsl(var(--primary) / 0.14);
  background: hsl(var(--muted) / 0.1);
  box-shadow: 0 12px 20px -26px hsl(var(--foreground) / 0.14);
}

.turn-process-pill {
  color: hsl(var(--muted-foreground) / 0.58);
  border: 1px solid hsl(var(--border) / 0.24);
  background: hsl(var(--background) / 0.84);
}

.turn-process-count {
  color: hsl(var(--muted-foreground) / 0.6);
  border: 1px solid hsl(var(--border) / 0.18);
  background: hsl(var(--background) / 0.76);
}

.turn-process-track {
  border-color: hsl(var(--border) / 0.18);
}

.turn-process-chevron {
  color: hsl(var(--muted-foreground) / 0.5);
  border: 1px solid hsl(var(--border) / 0.18);
  background: hsl(var(--background) / 0.82);
}

.turn-process-toggle:hover .turn-process-chevron {
  color: hsl(var(--primary) / 0.76);
  border-color: hsl(var(--primary) / 0.16);
}

.turn-stage-detail-surface {
  border-color: hsl(var(--border) / 0.16);
  background: hsl(var(--background) / 0.84);
  box-shadow: 0 10px 18px -28px hsl(var(--foreground) / 0.12);
}

.turn-stage-inline-markdown {
  min-width: 0;
  color: hsl(var(--foreground) / 0.7);
  font-size: 0.72rem;
  line-height: 1.25rem;
}

.turn-stage-inline-markdown :deep(p:first-child) {
  margin-top: 0;
}

.turn-stage-inline-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.turn-stage-inline-markdown :deep(ul),
.turn-stage-inline-markdown :deep(ol) {
  margin: 0.5rem 0 0;
  padding-inline-start: 1.1rem;
}

.turn-stage-inline-markdown :deep(li + li) {
  margin-top: 0.25rem;
}
</style>

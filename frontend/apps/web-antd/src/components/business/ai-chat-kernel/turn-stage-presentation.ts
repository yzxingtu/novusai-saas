import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';

import { $t } from '#/locales';
import { normalizeOptionalString } from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';

interface StageErrorSurfaceLike {
  message?: null | string;
  summary?: null | string;
}

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

export function normalizeMeaningfulTranscriptCopy(
  value: unknown,
): string | undefined {
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

export function normalizeComparableStageCopy(value: string): string {
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

export function getMeaningfulStageTitle(stage: TurnFlowStageForDisplay) {
  const title = normalizeMeaningfulTranscriptCopy(stage.title);
  if (!title || isGenericBackendStageCopy(stage, title)) {
    return undefined;
  }
  return title;
}

export function getMeaningfulStageSummary(stage: TurnFlowStageForDisplay) {
  const summary = normalizeMeaningfulTranscriptCopy(stage.summary);
  if (!summary || isGenericBackendStageCopy(stage, summary)) {
    return undefined;
  }
  return summary === getMeaningfulStageTitle(stage) ? undefined : summary;
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

export function readMetricNumber(
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

export function getStageTypeLabel(stage: TurnFlowStageForDisplay) {
  const stageTitle = getMeaningfulStageTitle(stage);
  if (stageTitle) {
    return stageTitle;
  }
  return $t(`common.globalAiChat.turnStageType.${stage.type}`);
}

export function getStageStatusLabel(stage: TurnFlowStageForDisplay) {
  return $t(`common.globalAiChat.turnStageStatus.${stage.status}`);
}

export function getStageSummary(
  stage: TurnFlowStageForDisplay,
  options: {
    errorSurface?: null | StageErrorSurfaceLike;
  } = {},
) {
  const stageSummary = getMeaningfulStageSummary(stage);
  if (stageSummary) {
    return stageSummary;
  }

  if (stage.type === 'failed') {
    const errorSurface = options.errorSurface;
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

export function getProcessHeadlineForStage(
  stage: TurnFlowStageForDisplay,
  options: {
    errorSurface?: null | StageErrorSurfaceLike;
  } = {},
) {
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
    : getStageSummary(stage, options);
}

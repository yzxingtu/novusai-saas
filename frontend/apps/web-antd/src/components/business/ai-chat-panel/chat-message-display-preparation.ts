import type {
  ChatMessage,
  DisplayReferenceLink,
  PreparedMessageContent,
  TurnEvidenceItem,
} from './types';

import {
  getUrlDisplayLabel,
  getUrlHostLabel,
  isDefaultUrlDisplayLabel,
  isHttpUrl,
  normalizeHttpUrlForDedup,
} from '#/utils/url-display';

import { getTurnFlowForDisplay } from './chat-message-turn-flow';

type FenceState = null | {
  character: '`' | '~';
  length: number;
};

interface ParsedReferenceLine {
  href: string;
  label?: string;
}

interface MessageReferenceExtraction {
  bodyMarkdown: string;
  references: DisplayReferenceLink[];
}

const SOURCE_HEADER_LABELS = new Set([
  'links',
  'reference',
  'references',
  'source',
  'sources',
  '参考',
  '来源',
  '资料来源',
  '链接',
]);
const MODEL_FUNCTION_CALL_BLOCK_MARKERS = [
  ['<｜DSML｜function_calls>', '</｜DSML｜function_calls>'],
  ['<｜DSML｜tool_calls>', '</｜DSML｜tool_calls>'],
] as const;
const MODEL_FUNCTION_CALL_TAG_PREFIXES = ['<｜', '</｜'] as const;

function normalizeOptionalString(value: unknown) {
  if (typeof value !== 'string') {
    return '';
  }
  return value.trim();
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

function stripModelFunctionCallMarkup(content: string): string {
  if (!content.includes('｜')) {
    return content;
  }

  let cleaned = content;
  for (const [blockStart, blockEnd] of MODEL_FUNCTION_CALL_BLOCK_MARKERS) {
    while (true) {
      const start = cleaned.indexOf(blockStart);
      if (start === -1) {
        break;
      }

      const end = cleaned.indexOf(blockEnd, start + blockStart.length);
      if (end === -1) {
        cleaned = cleaned.slice(0, start);
        break;
      }

      cleaned = cleaned.slice(0, start) + cleaned.slice(end + blockEnd.length);
    }
  }

  const result: string[] = [];
  let index = 0;
  while (index < cleaned.length) {
    if (
      cleaned.startsWith(MODEL_FUNCTION_CALL_TAG_PREFIXES[0], index) ||
      cleaned.startsWith(MODEL_FUNCTION_CALL_TAG_PREFIXES[1], index)
    ) {
      const closeIndex = cleaned.indexOf('>', index);
      if (closeIndex === -1) {
        break;
      }
      index = closeIndex + 1;
      continue;
    }

    const currentChar = cleaned[index];
    if (currentChar !== undefined) {
      result.push(currentChar);
    }
    index += 1;
  }

  return result.join('');
}

function findUrlStart(text: string): number {
  const httpIndex = text.indexOf('http://');
  const httpsIndex = text.indexOf('https://');
  if (httpIndex === -1) {
    return httpsIndex;
  }
  if (httpsIndex === -1) {
    return httpIndex;
  }
  return Math.min(httpIndex, httpsIndex);
}

function parseFenceState(line: string): FenceState {
  let offset = 0;
  while (offset < line.length && offset < 3 && line[offset] === ' ') {
    offset += 1;
  }
  const markerChar = line[offset];
  if (markerChar !== '`' && markerChar !== '~') {
    return null;
  }
  let length = 0;
  while (line[offset + length] === markerChar) {
    length += 1;
  }
  if (length < 3) {
    return null;
  }
  return {
    character: markerChar,
    length,
  };
}

function isSourceHeaderLine(line: string) {
  const normalized = stripTrailingColon(stripListPrefix(line))
    .trim()
    .toLocaleLowerCase();
  return SOURCE_HEADER_LABELS.has(normalized);
}

function parseMarkdownLinkLine(line: string): null | ParsedReferenceLine {
  const content = stripListPrefix(line).trim();
  if (!content.startsWith('[') || !content.endsWith(')')) {
    return null;
  }
  const closingBracket = content.indexOf('](');
  if (closingBracket <= 1) {
    return null;
  }
  const label = normalizeOptionalString(content.slice(1, closingBracket));
  const href = normalizeOptionalString(content.slice(closingBracket + 2, -1));
  if (!label || !isHttpUrl(href)) {
    return null;
  }
  return { href, label };
}

function parseLabelAndUrlLine(line: string): null | ParsedReferenceLine {
  const content = stripListPrefix(line).trim();
  const urlStart = findUrlStart(content);
  if (urlStart <= 0) {
    return null;
  }
  const rawLabel = content.slice(0, urlStart).trimEnd();
  const rawUrl = content.slice(urlStart).trim();
  if (
    !(rawLabel.endsWith(':') || rawLabel.endsWith('：')) ||
    !isHttpUrl(rawUrl)
  ) {
    return null;
  }
  const label = stripTrailingColon(rawLabel).trim();
  if (!label) {
    return null;
  }
  return { href: rawUrl, label };
}

function parseStandaloneUrlLine(line: string): null | ParsedReferenceLine {
  const href = stripListPrefix(line).trim();
  if (!isHttpUrl(href)) {
    return null;
  }
  return { href };
}

function parseReferenceLine(line: string): null | ParsedReferenceLine {
  const markdownLink = parseMarkdownLinkLine(line);
  if (markdownLink) {
    return markdownLink;
  }

  const titleAndUrl = parseLabelAndUrlLine(line);
  if (titleAndUrl) {
    return titleAndUrl;
  }

  const standaloneUrl = parseStandaloneUrlLine(line);
  if (standaloneUrl) {
    return standaloneUrl;
  }

  return null;
}

function toDisplayReferenceLink(
  reference: ParsedReferenceLine,
  index: number,
): DisplayReferenceLink {
  const href = normalizeOptionalString(reference.href);
  const label = getUrlDisplayLabel(href, reference.label);
  const host = getUrlHostLabel(href);
  const hostLabel = host && label !== host ? host : '';
  return {
    id: `content-reference-${index + 1}-${normalizeHttpUrlForDedup(href)}`,
    href,
    hostLabel,
    kind: 'reference',
    label,
    source: 'content',
  };
}

function extractTailReferences(content: string): MessageReferenceExtraction {
  if (!content.trim()) {
    return {
      bodyMarkdown: '',
      references: [],
    };
  }

  const lines = content.split(/\r?\n/u);
  const insideFenceMap = Array.from({ length: lines.length }).fill(false);
  let activeFence: FenceState = null;
  lines.forEach((line, index) => {
    insideFenceMap[index] = Boolean(activeFence);
    const fence = parseFenceState(line);
    if (!fence) {
      return;
    }
    if (
      activeFence &&
      activeFence.character === fence.character &&
      fence.length >= activeFence.length
    ) {
      activeFence = null;
      insideFenceMap[index] = true;
      return;
    }
    if (!activeFence) {
      activeFence = fence;
    }
  });

  let tailEnd = lines.length - 1;
  while (tailEnd >= 0 && lines[tailEnd]?.trim() === '') {
    tailEnd -= 1;
  }
  if (tailEnd < 0) {
    return {
      bodyMarkdown: '',
      references: [],
    };
  }

  const extractedIndexes = new Set<number>();
  const references: DisplayReferenceLink[] = [];
  let foundReference = false;

  for (let index = tailEnd; index >= 0; index -= 1) {
    const line = lines[index] ?? '';
    if (insideFenceMap[index]) {
      break;
    }
    if (line.trim() === '') {
      if (foundReference) {
        extractedIndexes.add(index);
      }
      continue;
    }
    const parsedReference = parseReferenceLine(line);
    if (parsedReference) {
      foundReference = true;
      extractedIndexes.add(index);
      references.unshift(
        toDisplayReferenceLink(parsedReference, references.length),
      );
      continue;
    }
    if (foundReference && isSourceHeaderLine(line)) {
      extractedIndexes.add(index);
    }
    break;
  }

  if (!foundReference) {
    return {
      bodyMarkdown: content.trimEnd(),
      references: [],
    };
  }

  const bodyLines = lines.filter((_, index) => !extractedIndexes.has(index));
  return {
    bodyMarkdown: bodyLines.join('\n').replace(/\s+$/u, ''),
    references,
  };
}

function toEvidenceReference(item: TurnEvidenceItem): DisplayReferenceLink {
  const href = normalizeOptionalString(item.url);
  const explicitTitle = normalizeOptionalString(item.title);
  const label = href
    ? getUrlDisplayLabel(href, explicitTitle)
    : explicitTitle || getUrlDisplayLabel('', explicitTitle);
  const host = getUrlHostLabel(href);
  return {
    id: item.id,
    href,
    hostLabel: host && label !== host ? host : '',
    kind: item.kind,
    label,
    snippet: normalizeOptionalString(item.snippet) || undefined,
    source: 'turn_flow',
  };
}

function pickReferenceKey(reference: DisplayReferenceLink) {
  if (reference.href) {
    return `href:${normalizeHttpUrlForDedup(reference.href)}`;
  }
  return `id:${reference.id}`;
}

function choosePreferredReference(
  current: DisplayReferenceLink,
  incoming: DisplayReferenceLink,
): DisplayReferenceLink {
  let primary = current;
  if (incoming.source === 'turn_flow' && current.source !== 'turn_flow') {
    primary = incoming;
  }
  const secondary = primary === current ? incoming : current;
  const href = primary.href || secondary.href;
  const labelCandidates = [primary.label, secondary.label].filter(
    (label): label is string => label !== undefined,
  );
  const explicitLabel = labelCandidates.find(
    (label) => Boolean(href) && !isDefaultUrlDisplayLabel(label, href),
  );
  const label =
    explicitLabel ||
    primary.label ||
    secondary.label ||
    getUrlDisplayLabel(href, undefined);
  const snippet = [primary.snippet, secondary.snippet]
    .filter((value): value is string => value !== undefined)
    .toSorted((left, right) => right.length - left.length)[0];

  return {
    ...primary,
    href,
    hostLabel:
      primary.hostLabel ||
      secondary.hostLabel ||
      (() => {
        const host = getUrlHostLabel(href);
        return host && label !== host ? host : '';
      })(),
    kind: primary.kind === 'reference' ? secondary.kind : primary.kind,
    label,
    snippet,
  };
}

function mergeReferences(
  flowReferences: DisplayReferenceLink[],
  extractedReferences: DisplayReferenceLink[],
) {
  const merged = new Map<string, DisplayReferenceLink>();
  [...flowReferences, ...extractedReferences].forEach((reference) => {
    const key = pickReferenceKey(reference);
    const current = merged.get(key);
    if (!current) {
      merged.set(key, reference);
      return;
    }
    merged.set(key, choosePreferredReference(current, reference));
  });
  return [...merged.values()];
}

function resolvePreparedBodyMarkdown(msg: ChatMessage) {
  const messageRecord = msg as unknown as Record<string, unknown>;
  const preparedBody =
    normalizeOptionalString(
      messageRecord.prepared_content_body ?? messageRecord.preparedContentBody,
    ) || '';
  if (preparedBody) {
    return preparedBody;
  }
  return normalizeOptionalString(msg.content);
}

function shouldSuppressUntrustedFailureBody(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
): boolean {
  const errorType = normalizeOptionalString(flow.errorSurface?.errorType);
  const failureKind = normalizeOptionalString(flow.failureKind);
  return (
    errorType === 'untrusted_final_output_source' ||
    failureKind === 'untrusted_final_output_source'
  );
}

const GENERIC_ASSISTANT_FAILURE_BODIES = new Set([
  'the assistant could not finish this turn. please retry.',
  '这次处理没有成功生成最终答复,请再试一次。',
  '这次处理没有成功生成最终答复，请再试一次。',
]);

const PROCESS_ONLY_BODY_LINES = new Set([
  'completed',
  'process',
  'reference',
  'references',
  'source',
  'sources',
  'summary',
  '参考',
  '参考来源',
  '已完成',
  '本轮过程',
  '来源',
  '结果整理',
  '资料来源',
  '链接',
]);

interface ResidualBodyCleanup {
  bodyMarkdown: string;
  suppressed: boolean;
}

function hasReadableAnswerCard(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
): boolean {
  const card = flow.answerCard;
  if (!card) {
    return false;
  }
  if (normalizeOptionalString(card.summary)) {
    return true;
  }
  return (card.sections ?? []).some(
    (section) =>
      Boolean(normalizeOptionalString(section.title)) ||
      Boolean(normalizeOptionalString(section.body ?? section.content)),
  );
}

function readPositiveMetric(
  metrics: Record<string, unknown> | undefined,
  keys: string[],
): boolean {
  if (!metrics) {
    return false;
  }
  return keys.some((key) => {
    const value = metrics[key];
    if (typeof value === 'number') {
      return Number.isFinite(value) && value > 0;
    }
    if (typeof value === 'string' && value.trim()) {
      const numericValue = Number(value);
      return Number.isFinite(numericValue) && numericValue > 0;
    }
    return false;
  });
}

function hasTurnDisplayContext(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
): boolean {
  if (hasReadableAnswerCard(flow)) {
    return true;
  }
  if (flow.evidence.length > 0) {
    return true;
  }
  return flow.timeline.some((stage) => {
    if (stage.status === 'skipped') {
      return false;
    }
    if (stage.type === 'retrieval') {
      return true;
    }
    if (stage.type === 'tool_execution') {
      return readPositiveMetric(stage.metrics, [
        'completed',
        'running',
        'tool_call_count',
        'total',
      ]);
    }
    if (stage.type === 'tool_selection') {
      return readPositiveMetric(stage.metrics, ['selected']);
    }
    return false;
  });
}

function countVisibleContentCharacters(content: string): number {
  return [...content.replaceAll(/[\p{P}\p{S}\s]/gu, '')].length;
}

function looksLikeAbnormalShortResidualBody(content: string): boolean {
  return countVisibleContentCharacters(content) === 1;
}

function looksLikeBareNumericFragmentBody(content: string): boolean {
  const normalized = content.replaceAll(/\s+/gu, ' ').trim();
  if (!normalized) {
    return false;
  }
  const numericTokens = normalized.match(/[+-]?\d+(?:[.,]\d+)?%?/gu) ?? [];
  if (numericTokens.length < 4) {
    return false;
  }
  const remainder = normalized
    .replaceAll(/[+-]?\d+(?:[.,]\d+)?%?/gu, '')
    .replaceAll(/[,.，、;；:：|/()[\]{}<>%％+\-–—\s]/gu, '');
  return remainder.length === 0;
}

function normalizeProcessOnlyLine(line: string): string {
  return stripTrailingColon(stripListPrefix(line)).trim();
}

function isProcessOnlyLine(line: string): boolean {
  const normalized = normalizeProcessOnlyLine(line);
  if (!normalized) {
    return true;
  }
  const lower = normalized.toLocaleLowerCase();
  return (
    PROCESS_ONLY_BODY_LINES.has(normalized) ||
    PROCESS_ONLY_BODY_LINES.has(lower) ||
    /^找到\s*\d+\s*条(?:来源|证据|参考|结果)$/u.test(normalized) ||
    /^\d+\s*个阶段$/u.test(normalized) ||
    /^found\s+\d+\s+(?:sources?|references?|results?)$/iu.test(normalized) ||
    /^\d+\s+stages?$/iu.test(normalized)
  );
}

function looksLikeProcessOnlyBody(content: string): boolean {
  const lines = content
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length >= 2 && lines.every((line) => isProcessOnlyLine(line));
}

function isFailedTurnWithResidualRisk(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
): boolean {
  const failureSignals = [
    normalizeOptionalString(flow.errorSurface?.errorType),
    normalizeOptionalString(flow.failureKind),
    normalizeOptionalString(flow.completionReason),
    normalizeOptionalString(flow.turnOutcome),
  ].map((value) => value.toLocaleLowerCase());
  return (
    flow.finalStageStatus === 'error' ||
    failureSignals.some(
      (value) =>
        value === 'failed' ||
        value === 'partial' ||
        value === 'untrusted_final_output_source',
    )
  );
}

function normalizeResidualComparableText(value: string): string {
  return value
    .normalize('NFKC')
    .replaceAll(/\s+/gu, ' ')
    .trim()
    .toLocaleLowerCase();
}

function collectEvidenceResidualTexts(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
): string[] {
  return flow.evidence
    .flatMap((item) => [item.title, item.snippet, item.sourceRef])
    .map((value) => normalizeOptionalString(value))
    .filter((value): value is string => Boolean(value) && value.length >= 40)
    .map((value) => normalizeResidualComparableText(value));
}

function isLikelyEvidenceResidualLine(
  line: string,
  evidenceResidualTexts: string[],
): boolean {
  const normalized = normalizeResidualComparableText(line);
  if (normalized.length < 40) {
    return false;
  }
  return evidenceResidualTexts.some(
    (evidenceText) =>
      evidenceText.includes(normalized) || normalized.includes(evidenceText),
  );
}

function updateFenceState(activeFence: FenceState, line: string): FenceState {
  const fence = parseFenceState(line);
  if (!fence) {
    return activeFence;
  }
  if (
    activeFence &&
    activeFence.character === fence.character &&
    fence.length >= activeFence.length
  ) {
    return null;
  }
  return activeFence ?? fence;
}

function shouldRemoveResidualLine(
  line: string,
  evidenceResidualTexts: string[],
): boolean {
  const trimmed = line.trim();
  if (!trimmed) {
    return false;
  }
  return (
    isProcessOnlyLine(trimmed) ||
    looksLikeAbnormalShortResidualBody(trimmed) ||
    looksLikeBareNumericFragmentBody(trimmed) ||
    isLikelyEvidenceResidualLine(trimmed, evidenceResidualTexts)
  );
}

function cleanupResidualBodyWhitespace(lines: string[]): string {
  return lines
    .join('\n')
    .replaceAll(/[ \t]+\n/gu, '\n')
    .replaceAll(/\n{3,}/gu, '\n\n')
    .trim();
}

function sanitizeSuspiciousResidualBody(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
  content: string,
): ResidualBodyCleanup {
  const normalized = content.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
  if (!normalized.trim() || !hasTurnDisplayContext(flow)) {
    return { bodyMarkdown: content, suppressed: false };
  }
  if (
    looksLikeAbnormalShortResidualBody(normalized) ||
    looksLikeBareNumericFragmentBody(normalized) ||
    looksLikeProcessOnlyBody(normalized)
  ) {
    return { bodyMarkdown: '', suppressed: true };
  }

  const evidenceResidualTexts = collectEvidenceResidualTexts(flow);
  const keptLines: string[] = [];
  let activeFence: FenceState = null;
  for (const line of normalized.split('\n')) {
    const wasInsideFence = Boolean(activeFence);
    const nextFence = updateFenceState(activeFence, line);
    const isFenceBoundary = nextFence !== activeFence;
    if (
      !wasInsideFence &&
      !isFenceBoundary &&
      shouldRemoveResidualLine(line, evidenceResidualTexts)
    ) {
      activeFence = nextFence;
      continue;
    }
    keptLines.push(line);
    activeFence = nextFence;
  }

  const bodyMarkdown = cleanupResidualBodyWhitespace(keptLines);
  if (!bodyMarkdown && normalized.trim()) {
    return { bodyMarkdown: '', suppressed: true };
  }
  return { bodyMarkdown, suppressed: false };
}

function looksLikeGenericAssistantFailureBody(content: string): boolean {
  const normalized = content
    .normalize('NFKC')
    .replaceAll(/\s+/gu, ' ')
    .trim()
    .toLocaleLowerCase();
  return GENERIC_ASSISTANT_FAILURE_BODIES.has(normalized);
}

function shouldSuppressGenericFailureBody(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
  content: string,
): boolean {
  return (
    isFailedTurnWithResidualRisk(flow) &&
    looksLikeGenericAssistantFailureBody(content)
  );
}

function looksLikeRawHtmlFailureDocument(content: string): boolean {
  const normalized = content.trim().toLocaleLowerCase();
  if (!normalized) {
    return false;
  }
  if (
    !(normalized.startsWith('<!doctype html') || normalized.startsWith('<html'))
  ) {
    return false;
  }
  if (!normalized.includes('</html>')) {
    return false;
  }
  return (
    normalized.includes('<body') ||
    normalized.includes('bad gateway') ||
    normalized.includes('cloudflare ray id') ||
    normalized.includes('performance &amp; security by')
  );
}

function shouldSuppressProviderFailureBody(
  flow: ReturnType<typeof getTurnFlowForDisplay>,
  content: string,
): boolean {
  if (!looksLikeRawHtmlFailureDocument(content)) {
    return false;
  }
  const failureSignals = [
    normalizeOptionalString(flow.errorSurface?.errorType),
    normalizeOptionalString(flow.failureKind),
    normalizeOptionalString(flow.completionReason),
    normalizeOptionalString(flow.turnOutcome),
  ]
    .filter(Boolean)
    .map((value) => value.toLocaleLowerCase());
  return (
    flow.finalStageStatus === 'error' ||
    failureSignals.some(
      (value) =>
        value.startsWith('provider_') ||
        value === 'failed' ||
        value === 'partial',
    )
  );
}

export function prepareMessageContent(
  msg: ChatMessage,
): PreparedMessageContent {
  const flow = getTurnFlowForDisplay(msg);
  const preparedBody = stripModelFunctionCallMarkup(
    resolvePreparedBodyMarkdown(msg),
  );
  const residualCleanup = sanitizeSuspiciousResidualBody(
    flow,
    preparedBody,
  );
  if (
    shouldSuppressUntrustedFailureBody(flow) ||
    shouldSuppressGenericFailureBody(flow, preparedBody) ||
    shouldSuppressProviderFailureBody(flow, preparedBody) ||
    residualCleanup.suppressed
  ) {
    return {
      bodyMarkdown: '',
      references: [],
      suppressed: true,
    };
  }

  const extracted = extractTailReferences(residualCleanup.bodyMarkdown);
  const references = mergeReferences(
    flow.evidence.map((item) => toEvidenceReference(item)),
    extracted.references,
  );
  return {
    bodyMarkdown: extracted.bodyMarkdown,
    references,
    suppressed: false,
  };
}

export function selectAnswerCardReferences(
  references: DisplayReferenceLink[],
  sourceChipIds: string[] | undefined,
  limit = 6,
) {
  if (!sourceChipIds?.length) {
    return references.slice(0, limit);
  }

  const referenceMap = new Map(
    references.map((reference) => [reference.id, reference]),
  );
  const seenSourceIds = new Set<string>();
  const selected = sourceChipIds
    .filter((id) => {
      if (seenSourceIds.has(id)) {
        return false;
      }
      seenSourceIds.add(id);
      return true;
    })
    .map((id) => referenceMap.get(id))
    .filter((item): item is DisplayReferenceLink => item !== undefined);
  const remaining = references.filter(
    (reference) => !selected.some((item) => item.id === reference.id),
  );
  return [...selected, ...remaining].slice(0, limit);
}

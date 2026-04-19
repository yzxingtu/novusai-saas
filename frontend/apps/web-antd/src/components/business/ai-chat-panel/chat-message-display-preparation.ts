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

export function prepareMessageContent(
  msg: ChatMessage,
): PreparedMessageContent {
  const flow = getTurnFlowForDisplay(msg);
  if (shouldSuppressUntrustedFailureBody(flow)) {
    return {
      bodyMarkdown: '',
      references: [],
      suppressed: true,
    };
  }

  const extracted = extractTailReferences(resolvePreparedBodyMarkdown(msg));
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

import type { ToolDisplayItem } from './tool-call-utils';

import { getToolActionErrorHintKey } from './toolActionErrorHints';

export interface ToolCallDetailFieldLine {
  key: string;
  value: string;
}

export interface ToolCallDetailField {
  key: string;
  lines: string[];
  metaLines: ToolCallDetailFieldLine[];
  multiline: boolean;
  overflowCount: number;
  text?: string;
}

export interface ToolCallDetailPreview {
  lines: string[];
  multiline: boolean;
  overflowCount: number;
  text?: string;
}

export interface ToolCallDetailsViewModel {
  argumentFields: ToolCallDetailField[];
  errorHintKey?: string;
  hasStructuredOutputPreview: boolean;
  outputFields: ToolCallDetailField[];
  outputPreview: null | ToolCallDetailPreview;
  rawOutput?: string;
}

const DETAIL_FIELD_LIMIT = 4;
const DETAIL_ITEM_LIMIT = 4;
const INLINE_VALUE_LIMIT = 160;
const BLOCK_VALUE_LIMIT = 600;
const OBJECT_TITLE_KEYS = [
  'title',
  'name',
  'label',
  'id',
  'status',
  'message',
  'summary',
  'url',
  'href',
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value))
    return value.some((item) => hasMeaningfulValue(item));
  if (isRecord(value))
    return Object.values(value).some((item) => hasMeaningfulValue(item));
  return true;
}

function normalizeInlineWhitespace(text: string): string {
  return text.replaceAll(/\s+/g, ' ').trim();
}

function truncateText(text: string, limit: number): string {
  return text.length > limit ? `${text.slice(0, limit - 1)}...` : text;
}

function safeJsonStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? '';
  } catch {
    return String(value);
  }
}

function formatBlockValue(value: unknown): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return truncateText(trimmed, BLOCK_VALUE_LIMIT);
  }
  return truncateText(String(value), BLOCK_VALUE_LIMIT);
}

function formatInlineValue(value: unknown, depth = 0): string {
  if (value === null || value === undefined) return '';

  if (typeof value === 'string') {
    const trimmed = normalizeInlineWhitespace(value);
    return trimmed ? truncateText(trimmed, INLINE_VALUE_LIMIT) : '';
  }

  if (
    typeof value === 'boolean' ||
    typeof value === 'bigint' ||
    typeof value === 'number'
  ) {
    return String(value);
  }

  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    const visibleItems = items
      .slice(0, Math.max(2, DETAIL_ITEM_LIMIT - 1))
      .map((item) => formatInlineValue(item, depth + 1))
      .filter(Boolean);
    const joined = visibleItems.join(' | ');
    if (items.length > visibleItems.length) {
      return joined
        ? `${joined} +${items.length - visibleItems.length}`
        : `+${items.length - visibleItems.length}`;
    }
    return joined;
  }

  if (isRecord(value)) {
    if (depth >= 2) {
      return truncateText(safeJsonStringify(value), INLINE_VALUE_LIMIT);
    }

    const entries = Object.entries(value).filter(([, entryValue]) =>
      hasMeaningfulValue(entryValue),
    );
    const titleKey = OBJECT_TITLE_KEYS.find((candidate) =>
      hasMeaningfulValue(value[candidate]),
    );

    const parts: string[] = [];
    if (titleKey) {
      const title = formatInlineValue(value[titleKey], depth + 1);
      if (title) {
        parts.push(title);
      }
    }

    for (const [entryKey, entryValue] of entries) {
      if (titleKey && entryKey === titleKey) {
        continue;
      }
      const formatted = formatInlineValue(entryValue, depth + 1);
      if (!formatted) {
        continue;
      }
      parts.push(`${entryKey}: ${formatted}`);
      if (parts.length >= (titleKey ? 3 : 2)) {
        break;
      }
    }

    return truncateText(
      parts.join(' | ') || safeJsonStringify(value),
      INLINE_VALUE_LIMIT,
    );
  }

  return truncateText(String(value), INLINE_VALUE_LIMIT);
}

function buildDetailField(key: string, value: unknown): ToolCallDetailField {
  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    return {
      key,
      lines: items
        .slice(0, DETAIL_ITEM_LIMIT)
        .map((item) => formatInlineValue(item))
        .filter(Boolean),
      metaLines: [],
      multiline: false,
      overflowCount: Math.max(items.length - DETAIL_ITEM_LIMIT, 0),
    };
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, entryValue]) =>
      hasMeaningfulValue(entryValue),
    );
    return {
      key,
      lines: [],
      metaLines: entries
        .slice(0, DETAIL_FIELD_LIMIT)
        .map(([entryKey, entryValue]) => ({
          key: entryKey,
          value:
            formatInlineValue(entryValue) ||
            truncateText(safeJsonStringify(entryValue), INLINE_VALUE_LIMIT),
        })),
      multiline: false,
      overflowCount: Math.max(entries.length - DETAIL_FIELD_LIMIT, 0),
    };
  }

  return {
    key,
    lines: [],
    metaLines: [],
    multiline:
      typeof value === 'string' &&
      (value.includes('\n') || value.trim().length > 80),
    overflowCount: 0,
    text: formatBlockValue(value),
  };
}

function buildDetailFields(
  value?: Record<string, unknown>,
): ToolCallDetailField[] {
  if (!value) {
    return [];
  }
  return Object.entries(value)
    .filter(([, fieldValue]) => hasMeaningfulValue(fieldValue))
    .map(([key, fieldValue]) => buildDetailField(key, fieldValue));
}

function buildDetailPreview(value: unknown): null | ToolCallDetailPreview {
  if (!hasMeaningfulValue(value)) {
    return null;
  }
  if (Array.isArray(value)) {
    const items = value.filter((item) => hasMeaningfulValue(item));
    return {
      lines: items
        .slice(0, DETAIL_ITEM_LIMIT)
        .map((item) => formatInlineValue(item))
        .filter(Boolean),
      multiline: false,
      overflowCount: Math.max(items.length - DETAIL_ITEM_LIMIT, 0),
    };
  }

  return {
    lines: [],
    multiline:
      typeof value === 'string' &&
      (value.includes('\n') || value.trim().length > 80),
    overflowCount: 0,
    text: formatBlockValue(value),
  };
}

function parseStructuredOutput(raw?: string): unknown {
  if (!raw?.trim()) {
    return undefined;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export function buildToolCallDetailsViewModel(
  toolItem: ToolDisplayItem,
): ToolCallDetailsViewModel {
  const structuredOutput = toolItem.structuredOutput;
  const parsedRawOutput = parseStructuredOutput(structuredOutput.raw);
  const outputFields = isRecord(parsedRawOutput)
    ? buildDetailFields(parsedRawOutput)
    : [];
  const outputPreview = isRecord(parsedRawOutput)
    ? null
    : buildDetailPreview(parsedRawOutput);
  const argumentFields = buildDetailFields(toolItem.tc.arguments);

  return {
    argumentFields,
    errorHintKey: getToolActionErrorHintKey(toolItem.tc.errorType),
    hasStructuredOutputPreview:
      outputFields.length > 0 || outputPreview !== null,
    outputFields,
    outputPreview,
    rawOutput: structuredOutput.raw,
  };
}

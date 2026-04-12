import type { Ref } from 'vue';

export type ValueResolver<T> = (() => T) | Ref<T> | T;

export interface CrudPaginationState {
  current_page: number;
  page_size: number;
  total_pages: number;
  total_rows: number;
  has_next_page: boolean;
  has_previous_page: boolean;
}

function resolveValue<T>(value?: ValueResolver<T>): T | undefined {
  if (value === undefined) return undefined;
  if (typeof value === 'function') {
    return (value as () => T)();
  }
  if (typeof value === 'object' && value !== null && 'value' in value) {
    return (value as Ref<T>).value;
  }
  return value as T;
}

export function compactCrudContextValues(
  value: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => {
      if (entry === undefined || entry === null || entry === '') return false;
      if (Array.isArray(entry) && entry.length === 0) return false;
      return true;
    }),
  );
}

export function buildCrudPaginationState(opts: {
  currentPage?: ValueResolver<number>;
  pageSize?: ValueResolver<number>;
  total?: ValueResolver<number>;
}): CrudPaginationState {
  const currentPage = Math.max(1, Number(resolveValue(opts.currentPage) ?? 1));
  const pageSize = Math.max(1, Number(resolveValue(opts.pageSize) ?? 20));
  const totalRows = Math.max(0, Number(resolveValue(opts.total) ?? 0));
  const totalPages = Math.max(Math.ceil(totalRows / pageSize), 1);

  return {
    current_page: currentPage,
    page_size: pageSize,
    total_pages: totalPages,
    total_rows: totalRows,
    has_next_page: currentPage < totalPages,
    has_previous_page: currentPage > 1,
  };
}

function stringifySummaryValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'string') return value.slice(0, 80);
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (value instanceof Date) return value.toISOString();

  try {
    return JSON.stringify(value).slice(0, 80);
  } catch {
    return String(value).slice(0, 80);
  }
}

export function buildCrudListSummary(
  rows: unknown[],
  opts: {
    currentPage?: ValueResolver<number>;
    displayKeys?: string[];
    pageSize?: ValueResolver<number>;
    total?: ValueResolver<number>;
  },
): Record<string, unknown> | undefined {
  if (rows.length === 0) return undefined;

  const fallbackKeys = Object.keys(rows[0] as Record<string, unknown>)
    .filter((key) => !key.startsWith('_') && key !== 'id')
    .slice(0, 6);
  const displayKeys = (opts.displayKeys?.filter(Boolean) ?? fallbackKeys).slice(
    0,
    6,
  );

  const sampleRows = rows.slice(0, 5).map((row) => {
    const record = row as Record<string, unknown>;
    const summary: Record<string, unknown> = {};

    for (const key of displayKeys) {
      const text = stringifySummaryValue(record[key]);
      if (text !== undefined) {
        summary[key] = text;
      }
    }

    return summary;
  });

  const pagination = buildCrudPaginationState({
    currentPage: opts.currentPage,
    pageSize: opts.pageSize,
    total: opts.total,
  });

  return {
    ...pagination,
    sample_rows: sampleRows,
  };
}

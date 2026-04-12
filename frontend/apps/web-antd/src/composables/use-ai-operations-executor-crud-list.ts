import type { Ref } from 'vue';

import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import type { SearchParamEntry } from './use-ai-operations-schema';
import type {
  CrudPaginationState,
  ValueResolver,
} from './use-ai-operations-pagination';
import type { CrudOperationExecutorContext } from './use-ai-operations-executor-types';

import { $t } from '#/locales';

import { buildCrudPaginationState } from './use-ai-operations-pagination';

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

function buildRawSearchFormValues(
  params: Record<string, unknown>,
  searchParamsMap: Record<string, SearchParamEntry>,
): Record<string, unknown> {
  const rawFormValues: Record<string, unknown> = {};

  for (const entry of Object.values(searchParamsMap)) {
    rawFormValues[entry.formFieldName] = undefined;
  }

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    const entry = searchParamsMap[key];
    if (!entry) continue;

    if (entry.formFieldName.startsWith('_dateRange_')) {
      const current = Array.isArray(rawFormValues[entry.formFieldName])
        ? [...(rawFormValues[entry.formFieldName] as unknown[])]
        : [undefined, undefined];
      const slotIndex = entry.dateRangeRole === 'end' ? 1 : 0;
      current[slotIndex] = value;
      rawFormValues[entry.formFieldName] = current;
      continue;
    }

    rawFormValues[entry.formFieldName] = value;
  }

  return rawFormValues;
}

function getPaginationState(
  currentPage?: ValueResolver<number>,
  pageSize?: ValueResolver<number>,
  total?: number | Ref<number>,
): CrudPaginationState {
  return buildCrudPaginationState({
    currentPage,
    pageSize,
    total,
  });
}

function getRowKeyValue(
  row: Record<string, unknown>,
  rowKeyField: string,
): unknown {
  return row[rowKeyField] ?? row.id;
}

function getResolvedDisplayKeys(
  rows: Record<string, unknown>[],
  rowKeyField: string,
  displayKeys?: ValueResolver<string[]>,
): string[] {
  const configuredKeys = (resolveValue(displayKeys) ?? []).filter(Boolean);
  if (configuredKeys.length > 0) {
    return configuredKeys.slice(0, 8);
  }

  if (rows.length === 0) return [];
  return Object.keys(rows[0] ?? {})
    .filter((key) => !key.startsWith('_') && key !== rowKeyField && key !== 'id')
    .slice(0, 8);
}

function buildVisibleRowPayload(
  row: Record<string, unknown>,
  rowKeyField: string,
  displayFieldNames: string[],
): Record<string, unknown> {
  const preview: Record<string, unknown> = {
    [rowKeyField]: getRowKeyValue(row, rowKeyField),
  };

  for (const key of displayFieldNames) {
    const value = row[key];
    if (value === undefined) continue;
    preview[key] = value;
  }

  return preview;
}

export function buildCrudListOperations(
  context: CrudOperationExecutorContext,
): PageOperation[] {
  const {
    loadList,
    onSearch,
    list,
    total,
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    openExportModal,
    rowKeyField,
    displayKeys,
    searchParamsMap,
    searchOpParams,
  } = context;

  const operations: PageOperation[] = [];

  // ── 1. refresh_list — Reload list / 刷新列表 ──
  operations.push({
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: $t('shared.pageOperation.desc.refreshList'),
    readonly: true,
    handler: async () => {
      await loadList();
      return {
        success: true,
        message: $t('shared.pageOperation.msg.listRefreshed'),
      };
    },
  });

  // ── 2. export_data — Open export modal / 打开导出弹窗 ──
  if (openExportModal) {
    operations.push({
      name: 'export_data',
      label: $t('shared.pageOperation.exportData'),
      description: $t('shared.pageOperation.desc.exportData'),
      readonly: true,
      handler: async () => {
        openExportModal();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.uiOpened', {
            target: $t('shared.pageOperation.exportData'),
          }),
        };
      },
    });
  }

  // ── 3. search — Search (needs searchSchema) / 搜索，需 searchSchema ──
  if (Object.keys(searchParamsMap).length > 0) {
    operations.push({
      name: 'search',
      label: $t('shared.pageOperation.search'),
      description: $t('shared.pageOperation.desc.search'),
      readonly: true,
      params: searchOpParams,
      handler: async (params) => {
        const filterParams: Record<string, unknown> = {};
        const rawFormValues = buildRawSearchFormValues(
          params,
          searchParamsMap,
        );

        for (const [key, value] of Object.entries(params)) {
          if (value === undefined || value === null || value === '') continue;
          const entry = searchParamsMap[key];
          if (entry) {
            // Map AI param key back to JSON:API filter fieldName
            // 将 AI 参数 key 映射回 JSON:API filter 字段名
            filterParams[entry.filterFieldName] = value;
          }
        }

        await onSearch(filterParams, { rawFormValues });

        const applied = Object.keys(params).filter(
          (k) =>
            params[k] !== null && params[k] !== undefined && params[k] !== '',
        );
        return {
          success: true,
          message:
            applied.length > 0
              ? $t('shared.pageOperation.msg.searchApplied', {
                  fields: applied.join(', '),
                })
              : $t('shared.pageOperation.msg.searchCleared'),
        };
      },
    });
  }

  // ── 4. clear_search — Clear search (needs searchSchema) / 清空搜索，需 searchSchema ──
  if (Object.keys(searchParamsMap).length > 0) {
    operations.push({
      name: 'clear_search',
      label: $t('shared.pageOperation.clearSearch'),
      description: $t('shared.pageOperation.desc.clearSearch'),
      readonly: true,
      handler: async () => {
        await onSearch(
          {},
          {
            rawFormValues: buildRawSearchFormValues({}, searchParamsMap),
          },
        );
        return {
          success: true,
          message: $t('shared.pageOperation.msg.searchCleared'),
        };
      },
    });
  }

  // ── 3a. read_visible_rows — Read visible table rows / 读取当前可见表格行 ──
  operations.push({
    name: 'read_visible_rows',
    label: $t('shared.pageOperation.readVisibleRows'),
    description: $t('shared.pageOperation.desc.readVisibleRows'),
    readonly: true,
    handler: async () => {
      const rows = (list.value as Record<string, unknown>[]) ?? [];
      const visibleFieldNames = getResolvedDisplayKeys(
        rows,
        rowKeyField,
        displayKeys,
      );
      return {
        success: true,
        message: $t('shared.pageOperation.msg.visibleRowsRead', {
          count: rows.length,
        }),
        data: {
          pagination: getPaginationState(currentPage, pageSize, total),
          row_key_field: rowKeyField,
          rows: rows.map((row) =>
            buildVisibleRowPayload(row, rowKeyField, visibleFieldNames),
          ),
          visible_columns: visibleFieldNames,
        },
      };
    },
  });

  // ── 3b. pagination operations — Navigate list pages / 分页操作 ──
  if (
    currentPage !== undefined &&
    pageSize !== undefined &&
    total !== undefined &&
    setCurrentPage
  ) {
    operations.push({
      name: 'next_page',
      label: $t('shared.pageOperation.nextPage'),
      description: $t('shared.pageOperation.desc.nextPage'),
      readonly: true,
      handler: async () => {
        const pagination = getPaginationState(currentPage, pageSize, total);
        if (!pagination.has_next_page) {
          return {
            success: true,
            message: $t('shared.pageOperation.msg.alreadyLastPage', {
              page: pagination.current_page,
            }),
          };
        }

        const targetPage = pagination.current_page + 1;
        await setCurrentPage(targetPage);
        await loadList();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.pageChanged', {
            page: targetPage,
          }),
        };
      },
    });
  }

  // ── 3c. read_row_detail — Read a specific row detail / 读取指定行详情 ──
  operations.push({
    name: 'read_row_detail',
    label: $t('shared.pageOperation.readRowDetail'),
    description: $t('shared.pageOperation.desc.readRowDetail'),
    readonly: true,
    params: {
      id: {
        type: 'string',
        description: $t('shared.pageOperation.param.recordId'),
        required: true,
      },
    },
    handler: async (params) => {
      const id = params.id;
      if (id === null || id === undefined || id === '') {
        return {
          success: false,
          message: $t('shared.pageOperation.msg.missingIdParam'),
        };
      }

      const rows = (list.value as Record<string, unknown>[]) ?? [];
      const record = rows.find((row) => {
        const rowId = getRowKeyValue(row, rowKeyField);
        return rowId === id || String(rowId) === String(id);
      });

      if (!record) {
        return {
          success: false,
          message: $t('shared.pageOperation.msg.recordNotFoundInList', {
            id,
          }),
        };
      }

      return {
        success: true,
        message: $t('shared.pageOperation.msg.rowDetailRead', {
          id: String(id),
        }),
        data: {
          row: record,
          row_key_field: rowKeyField,
        },
      };
    },
  });

  if (
    currentPage !== undefined &&
    pageSize !== undefined &&
    total !== undefined &&
    setCurrentPage
  ) {
    operations.push({
      name: 'prev_page',
      label: $t('shared.pageOperation.prevPage'),
      description: $t('shared.pageOperation.desc.prevPage'),
      readonly: true,
      handler: async () => {
        const pagination = getPaginationState(currentPage, pageSize, total);
        if (!pagination.has_previous_page) {
          return {
            success: true,
            message: $t('shared.pageOperation.msg.alreadyFirstPage', {
              page: pagination.current_page,
            }),
          };
        }

        const targetPage = pagination.current_page - 1;
        await setCurrentPage(targetPage);
        await loadList();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.pageChanged', {
            page: targetPage,
          }),
        };
      },
    });
  }

  if (
    currentPage !== undefined &&
    pageSize !== undefined &&
    total !== undefined &&
    setCurrentPage
  ) {
    operations.push({
      name: 'go_to_page',
      label: $t('shared.pageOperation.goToPage'),
      description: $t('shared.pageOperation.desc.goToPage'),
      readonly: true,
      params: {
        page: {
          type: 'number',
          description: $t('shared.pageOperation.param.targetPageNumber'),
          required: true,
        },
      },
      handler: async (params) => {
        const targetPage = Number(params.page);
        const pagination = getPaginationState(currentPage, pageSize, total);
        if (
          !Number.isFinite(targetPage) ||
          targetPage < 1 ||
          targetPage > pagination.total_pages
        ) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.pageOutOfRange', {
              max: pagination.total_pages,
              min: 1,
              page: targetPage,
            }),
          };
        }

        await setCurrentPage(targetPage);
        await loadList();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.pageChanged', {
            page: targetPage,
          }),
        };
      },
    });
  }

  if (setPageSize) {
    operations.push({
      name: 'set_page_size',
      label: $t('shared.pageOperation.setPageSize'),
      description: $t('shared.pageOperation.desc.setPageSize'),
      readonly: true,
      params: {
        page_size: {
          type: 'number',
          description: $t('shared.pageOperation.param.rowsPerPage'),
          required: true,
        },
      },
      handler: async (params) => {
        const nextPageSize = Number(params.page_size);
        if (!Number.isFinite(nextPageSize) || nextPageSize < 1) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.invalidPageSize', {
              pageSize: nextPageSize,
            }),
          };
        }

        await setPageSize(nextPageSize);
        await loadList();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.pageSizeChanged', {
            pageSize: nextPageSize,
          }),
        };
      },
    });
  }

  return operations;
}

import type { Ref } from 'vue';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-types';
import type { VbenFormSchema } from '#/core/adapter/form/setup';

import type { EnhancedFormFieldDescriptor } from './ai-operation-types';
import type { SearchParamEntry } from './use-ai-operations-schema';
import type {
  CrudPaginationState,
  ValueResolver,
} from './use-ai-operations-pagination';

import { $t } from '#/locales';
import { router } from '#/router';
import { requestClient } from '#/utils/request';

import { resolveFormOptionsFieldName } from './form-option-param-utils';
import {
  requireOpenForm,
  requireOpenFormApi,
} from './use-ai-operations-confirmation';
import {
  ensureRemoteOptionsWithTimeout,
  resolveRemoteOptions,
} from './use-ai-operations-remote-options';
import {
  buildFieldParamSchema,
  extractFormParams,
} from './use-ai-operations-schema';
import { buildCrudPaginationState } from './use-ai-operations-pagination';
import {
  buildFillFormFeedback,
  collectRemainingEmptyFields,
  expandDotKeys,
  getFormState,
  isFormOpen,
  sanitizeRemoteSelectOverrides,
  waitForTrackedFormState,
} from './use-ai-operations-state';

interface CrudSearchStatePayload {
  rawFormValues?: Record<string, unknown>;
}

export interface CrudOperationExecutorContext {
  resource: string;
  loadList: () => Promise<void>;
  onSearch: (
    params?: Record<string, unknown>,
    state?: CrudSearchStatePayload,
  ) => Promise<void> | void;
  list: Ref<unknown[]>;
  total?: number | Ref<number>;
  currentPage?: ValueResolver<number>;
  pageSize?: ValueResolver<number>;
  setCurrentPage?: (page: number) => Promise<void> | void;
  setPageSize?: (size: number) => Promise<void> | void;
  formPopupApi?: {
    setData: (data: Record<string, unknown>) => { open: () => void };
  } | null;
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>;
  detailRoute?: string;
  hasFormSchema: boolean;
  hasRecycleBin?: boolean;
  openRecycleBin?: () => void;
  openExportModal?: () => void;
  pageKey?: string;
  rowKeyField: string;
  displayKeys?: ValueResolver<string[]>;
  searchParamsMap: Record<string, SearchParamEntry>;
  formParamsMap: Record<string, EnhancedFormFieldDescriptor>;
  rawFormSchema: VbenFormSchema[];
  searchOpParams: Record<string, unknown>;
  createOpParams: Record<string, unknown>;
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

export function buildStandardCrudOperations(
  context: CrudOperationExecutorContext,
): PageOperation[] {
  const {
    resource,
    loadList,
    onSearch,
    list,
    total,
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    formPopupApi,
    formDefaults,
    detailRoute,
    hasFormSchema,
    hasRecycleBin,
    openRecycleBin,
    openExportModal,
    pageKey: optsPageKey,
    rowKeyField,
    displayKeys,
    searchParamsMap,
    formParamsMap,
    rawFormSchema,
    searchOpParams,
    createOpParams,
  } = context;

  // Lazy-load remote options once and merge into formParamsMap
  // 惰性加载远程选项并合并到 formParamsMap
  let _remoteResolved = false;
  let _remoteResolvePromise: null | Promise<void> = null;
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    if (_remoteResolvePromise) {
      await _remoteResolvePromise;
      return;
    }
    _remoteResolvePromise = (async () => {
      const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
      for (const [field, options] of remoteOpts) {
        const existing = formParamsMap[field];
        if (existing && !existing.options) {
          existing.options = options;
        }
      }
      _remoteResolved = true;
    })();
    try {
      await _remoteResolvePromise;
    } finally {
      _remoteResolvePromise = null;
    }
  }
  // Fire-and-forget preload / 触发后台预加载
  if (
    rawFormSchema.some(
      (s) =>
        s.component === 'ApiSelect' ||
        s.component === 'ApiTreeSelect' ||
        s.component === 'IdentityRemoteSelect',
    )
  ) {
    ensureRemoteOptions();
  }

  // Get form defaults / 获取表单默认值
  function getFormDefaults(): Record<string, unknown> {
    return typeof formDefaults === 'function'
      ? formDefaults()
      : (formDefaults ?? {});
  }

  function buildRawSearchFormValues(
    params: Record<string, unknown>,
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

  function getPaginationState(): CrudPaginationState {
    return buildCrudPaginationState({
      currentPage,
      pageSize,
      total,
    });
  }

  function getRowKeyValue(row: Record<string, unknown>): unknown {
    return row[rowKeyField] ?? row.id;
  }

  function getResolvedDisplayKeys(rows: Record<string, unknown>[]): string[] {
    const configuredKeys = (resolveValue(displayKeys) ?? []).filter(Boolean);
    if (configuredKeys.length > 0) {
      return configuredKeys.slice(0, 8);
    }

    if (rows.length === 0) return [];
    return Object.keys(rows[0] ?? {})
      .filter(
        (key) => !key.startsWith('_') && key !== rowKeyField && key !== 'id',
      )
      .slice(0, 8);
  }

  function buildVisibleRowPayload(
    row: Record<string, unknown>,
    displayFieldNames: string[],
  ): Record<string, unknown> {
    const preview: Record<string, unknown> = {
      [rowKeyField]: getRowKeyValue(row),
    };

    for (const key of displayFieldNames) {
      const value = row[key];
      if (value === undefined) continue;
      preview[key] = value;
    }

    return preview;
  }

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
        return { success: true, message: 'Export dialog opened' };
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
        const rawFormValues = buildRawSearchFormValues(params);

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
            rawFormValues: buildRawSearchFormValues({}),
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
      const visibleFieldNames = getResolvedDisplayKeys(rows);
      return {
        success: true,
        message: $t('shared.pageOperation.msg.visibleRowsRead', {
          count: rows.length,
        }),
        data: {
          pagination: getPaginationState(),
          row_key_field: rowKeyField,
          rows: rows.map((row) => buildVisibleRowPayload(row, visibleFieldNames)),
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
        const pagination = getPaginationState();
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
        const rowId = getRowKeyValue(row);
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
        const pagination = getPaginationState();
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
        const pagination = getPaginationState();
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

  // ── 5. create_record — Create record (needs formSchema + formPopupApi) / 新建记录 ──
  if (formPopupApi && hasFormSchema) {
    operations.push({
      name: 'create_record',
      label: $t('shared.pageOperation.createRecord'),
      description: $t('shared.pageOperation.desc.createRecord'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        if (optsPageKey && isFormOpen(optsPageKey)) {
          const formState = await waitForTrackedFormState(optsPageKey);
          return {
            success: true,
            message: $t('shared.pageOperation.msg.formAlreadyOpen'),
            data: {
              already_open: true,
              current_values: formState.currentValues,
              form_is_open: formState.isOpen,
              remaining_empty_fields: collectRemainingEmptyFields(
                formParamsMap,
                formState.currentValues,
              ),
            },
          };
        }
        // Only accept fields defined in formSchema, ignore unknown fields
        // 只接受 formSchema 中定义的字段，忽略未知字段
        const rawOverrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) rawOverrides[key] = params[key];
        }
        const overrides = sanitizeRemoteSelectOverrides(
          formParamsMap,
          rawOverrides,
        );

        const defaults = getFormDefaults();
        formPopupApi
          .setData({
            mode: 'add',
            _resource: resource,
            _defaults: expandDotKeys({ ...defaults, ...overrides }),
            ...(optsPageKey ? { _pageKey: optsPageKey } : {}),
          })
          .open();

        // Wait for Drawer to open and render / 等待 Drawer 打开并渲染完成
        await new Promise<void>((resolve) => setTimeout(resolve, 200));

        const filled = Object.keys(overrides);
        const formState = optsPageKey
          ? await waitForTrackedFormState(optsPageKey)
          : null;
        return {
          success: true,
          message:
            filled.length > 0
              ? $t('shared.pageOperation.msg.createFormOpened', {
                  fields: filled.join(', '),
                })
              : $t('shared.pageOperation.msg.createFormOpenedEmpty'),
          data: {
            current_values: formState?.currentValues ?? {},
            form_is_open: Boolean(formState?.isOpen),
            prefilled_fields: filled,
            remaining_empty_fields: collectRemainingEmptyFields(
              formParamsMap,
              formState?.currentValues ?? {},
              filled,
            ),
            context_diff: {
              form_opened: Boolean(formState?.isOpen),
            },
          },
        };
      },
    });
  }

  // ── 6. edit_record — Edit record (needs formSchema + formPopupApi) / 编辑记录 ──
  if (formPopupApi && hasFormSchema) {
    const editOpParams: Record<string, unknown> = {
      id: {
        type: 'number',
        description: $t('shared.pageOperation.param.editRecordId'),
        required: true,
      },
      ...createOpParams,
    };

    operations.push({
      name: 'edit_record',
      label: $t('shared.pageOperation.editRecord'),
      description: $t('shared.pageOperation.desc.editRecord'),
      readonly: false,
      params: editOpParams,
      handler: async (params) => {
        if (optsPageKey && isFormOpen(optsPageKey)) {
          const formState = await waitForTrackedFormState(optsPageKey);
          return {
            success: true,
            message: $t('shared.pageOperation.msg.formAlreadyOpen'),
            data: {
              already_open: true,
              current_values: formState.currentValues,
              form_is_open: formState.isOpen,
              remaining_empty_fields: collectRemainingEmptyFields(
                formParamsMap,
                formState.currentValues,
              ),
            },
          };
        }
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.idRequired'),
          };
        }

        // Find record in current list (try exact match then Number coercion)
        // 在当前列表中查找记录（先精确匹配，再数字转换匹配）
        const rows = list.value as Record<string, unknown>[];
        const record =
          rows.find((r) => getRowKeyValue(r) === id) ??
          rows.find((r) => String(getRowKeyValue(r)) === String(id));

        if (!record) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.recordNotFoundInList', {
              id,
            }),
          };
        }

        // Apply overrides (only fields defined in formSchema)
        // 应用覆盖值（只接受 formSchema 中定义的字段）
        const rawOverrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) rawOverrides[key] = params[key];
        }
        const overrides = sanitizeRemoteSelectOverrides(
          formParamsMap,
          rawOverrides,
        );

        const expandedOverrides =
          Object.keys(overrides).length > 0
            ? expandDotKeys(overrides)
            : undefined;

        formPopupApi
          .setData({
            ...record,
            mode: 'edit',
            _resource: resource,
            ...(optsPageKey ? { _pageKey: optsPageKey } : {}),
            ...(expandedOverrides ? { _overrides: expandedOverrides } : {}),
          })
          .open();

        // Wait for Drawer to open and render / 等待 Drawer 打开并渲染完成
        await new Promise<void>((resolve) => setTimeout(resolve, 200));

        const changed = Object.keys(overrides);
        const formState = optsPageKey
          ? await waitForTrackedFormState(optsPageKey)
          : null;
        return {
          success: true,
          message:
            changed.length > 0
              ? $t('shared.pageOperation.msg.editFormOpened', {
                  id,
                  fields: changed.join(', '),
                })
              : $t('shared.pageOperation.msg.editFormOpenedEmpty', { id }),
          data: {
            current_values: formState?.currentValues ?? {},
            form_is_open: Boolean(formState?.isOpen),
            prefilled_fields: changed,
            remaining_empty_fields: collectRemainingEmptyFields(
              formParamsMap,
              formState?.currentValues ?? {},
              changed,
            ),
            context_diff: {
              form_opened: Boolean(formState?.isOpen),
            },
          },
        };
      },
    });
  }

  // ── 5b. delete_record — Delete by ID (same condition as edit_record) / 按 ID 删除记录 ──
  if (hasFormSchema && formPopupApi) {
    operations.push({
      name: 'delete_record',
      label: $t('shared.pageOperation.deleteRecord'),
      description: $t('shared.pageOperation.desc.deleteRecord'),
      readonly: false,
      params: {
        id: {
          type: 'number',
          description: $t('shared.pageOperation.param.deleteRecordId'),
          required: true,
        },
      },
      handler: async (params) => {
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.missingIdParam'),
          };
        }
        try {
          await requestClient.delete(`${resource}/${id}`, {
            showSuccessMessage: true,
            showCodeMessage: false,
          });
          await loadList();
          return {
            success: true,
            message: $t('shared.pageOperation.msg.recordDeleted', { id }),
          };
        } catch (error) {
          const msg = error instanceof Error ? error.message : String(error);
          return { success: false, message: msg };
        }
      },
    });
  }

  // ── 7. navigate_to_detail — Navigate to detail (needs detailRoute) / 跳转详情页 ──
  if (detailRoute) {
    operations.push({
      name: 'navigate_to_detail',
      label: $t('shared.pageOperation.navigateToDetail'),
      description: $t('shared.pageOperation.desc.navigateToDetail'),
      readonly: true,
      params: {
        id: {
          type: 'number',
          description: $t('shared.pageOperation.param.recordId'),
          required: true,
        },
      },
      handler: async (params) => {
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.navigateIdRequired'),
          };
        }
        const path = detailRoute.replace(':id', String(id));
        await router.push(path);
        return {
          success: true,
          message: $t('shared.pageOperation.msg.navigatedTo', { path }),
        };
      },
    });
  }

  // ── 8. view_recycle_bin — Open recycle bin (needs hasRecycleBin) / 打开回收站 ──
  if (hasRecycleBin && openRecycleBin) {
    operations.push({
      name: 'view_recycle_bin',
      label: $t('shared.pageOperation.viewRecycleBin'),
      description: $t('shared.pageOperation.desc.viewRecycleBin'),
      readonly: true,
      handler: async () => {
        openRecycleBin();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.recycleBinOpened'),
        };
      },
    });
  }

  // ── 8. get_form_state — Get form state (needs formSchema + pageKey) / 获取表单状态 ──
  if (hasFormSchema && optsPageKey) {
    operations.push({
      name: 'get_form_state',
      label: $t('shared.pageOperation.getFormState'),
      description: $t('shared.pageOperation.desc.getFormState'),
      readonly: true,
      handler: async () => {
        const state = await getFormState(optsPageKey);
        return {
          success: true,
          message: state.isOpen
            ? $t('shared.pageOperation.msg.formIsOpen', { mode: state.mode })
            : $t('shared.pageOperation.msg.formNotOpen'),
          data: {
            isOpen: state.isOpen,
            mode: state.mode,
            currentValues: state.currentValues,
            dirtyFields: state.dirtyFields,
            validationErrors: state.validationErrors,
            fieldDescriptors: state.fieldDescriptors,
          },
        };
      },
    });
  }

  // __BUILD_STANDARD_OPERATIONS_CONTINUE_6__
  return operations;
}

export function buildFormOperations(options: {
  pageKey: string;
  formSchema: (isEdit?: boolean) => VbenFormSchema[];
  resource: string;
}): PageOperation[] {
  const { pageKey, formSchema, resource } = options;

  const rawFormSchema = formSchema(false);
  const formParamsMap = extractFormParams(rawFormSchema);

  const createOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(formParamsMap)) {
    createOpParams[key] = buildFieldParamSchema(entry, {
      includeDefaultValue: false,
      includeRequired: false,
    });
  }

  let _remoteResolved = false;
  let _remoteResolvePromise: null | Promise<void> = null;
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    if (_remoteResolvePromise) {
      await _remoteResolvePromise;
      return;
    }
    _remoteResolvePromise = (async () => {
      const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
      for (const [field, options] of remoteOpts) {
        const existing = formParamsMap[field];
        if (existing && !existing.options) {
          existing.options = options;
        }
      }
      _remoteResolved = true;
    })();
    try {
      await _remoteResolvePromise;
    } finally {
      _remoteResolvePromise = null;
    }
  }
  if (
    rawFormSchema.some(
      (s) =>
        s.component === 'ApiSelect' ||
        s.component === 'ApiTreeSelect' ||
        s.component === 'IdentityRemoteSelect',
    )
  ) {
    ensureRemoteOptions();
  }

  const operations: PageOperation[] = [
    // get_form_state / 获取表单状态
    {
      name: 'get_form_state',
      label: $t('shared.pageOperation.getFormState'),
      description: $t('shared.pageOperation.desc.getFormState'),
      readonly: true,
      handler: async () => {
        const state = await getFormState(pageKey);
        return {
          success: true,
          message: state.isOpen
            ? $t('shared.pageOperation.msg.formIsOpen', { mode: state.mode })
            : $t('shared.pageOperation.msg.formNotOpen'),
          data: {
            isOpen: state.isOpen,
            mode: state.mode,
            currentValues: state.currentValues,
            dirtyFields: state.dirtyFields,
            validationErrors: state.validationErrors,
            fieldDescriptors: state.fieldDescriptors,
          },
        };
      },
    },

    // fill_form / 填充表单
    {
      name: 'fill_form',
      label: $t('shared.pageOperation.fillForm'),
      description: $t('shared.pageOperation.desc.fillForm'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }

        const validFields: Record<string, unknown> = {};
        const skippedFields: string[] = [];
        for (const [key, value] of Object.entries(params)) {
          if (formParamsMap[key]) {
            validFields[key] = value;
          } else {
            skippedFields.push(key);
          }
        }

        if (Object.keys(validFields).length === 0) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.noValidFields', {
              fields: Object.keys(formParamsMap).join(', '),
            }),
          };
        }

        try {
          access.formApi.setValues(expandDotKeys(validFields));
          await new Promise<void>((r) => setTimeout(r, 100));
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.setFormValuesFailed'),
          };
        }

        const filledKeys = Object.keys(validFields);
        const { feedback, mismatchCount } = await buildFillFormFeedback(
          access.formApi,
          validFields,
        );
        const skippedInfo =
          skippedFields.length > 0
            ? `. ${$t('shared.pageOperation.msg.skippedUnknown', { fields: skippedFields.join(', ') })}`
            : '';
        return {
          success: true,
          message:
            (mismatchCount > 0
              ? $t('shared.pageOperation.msg.fillFormPartial', {
                  count: filledKeys.length,
                  mismatch: mismatchCount,
                })
              : $t('shared.pageOperation.msg.fillFormResult', {
                  count: filledKeys.length,
                })) + skippedInfo,
          data: {
            filled: filledKeys,
            skipped: skippedFields,
            field_feedback: feedback,
          },
        };
      },
    },
    // validate_form / 校验表单
    {
      name: 'validate_form',
      label: $t('shared.pageOperation.validateForm'),
      description: $t('shared.pageOperation.desc.validateForm'),
      readonly: true,
      handler: async () => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }
        try {
          const { valid } = await access.formApi.validate();
          return {
            success: true,
            message: valid
              ? $t('shared.pageOperation.msg.allFieldsValid')
              : $t('shared.pageOperation.msg.formHasValidationErrors'),
            data: { valid },
          };
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.validationFailed'),
          };
        }
      },
    },
    // submit_form / 提交表单
    {
      name: 'submit_form',
      label: $t('shared.pageOperation.submitForm'),
      description: $t('shared.pageOperation.desc.submitForm'),
      readonly: false,
      handler: async () => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }
        const validResult = await access.formApi.validate();
        const valid =
          validResult && (validResult as { valid?: boolean }).valid !== false;
        const errors = (validResult as { errors?: Record<string, unknown> })
          ?.errors;
        if (!valid && errors && Object.keys(errors).length > 0) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.validationFailedMsg'),
            data: { errors },
          };
        }
        if (access.formApi.submitForm) {
          try {
            await access.formApi.submitForm();
            return {
              success: true,
              message: $t('shared.pageOperation.msg.formSubmittedSuccess'),
            };
          } catch (error) {
            const msg = error instanceof Error ? error.message : String(error);
            return { success: false, message: msg };
          }
        }
        return {
          success: false,
          message: $t('shared.pageOperation.msg.formApiNotAvailable'),
        };
      },
    },
  ];

  // get_form_options / 获取远程下拉选项
  const remoteFields = Object.entries(formParamsMap)
    .filter(([_, desc]) => desc.optionsSource === 'remote')
    .map(([key]) => key);

  if (remoteFields.length > 0) {
    operations.push({
      name: 'get_form_options',
      label: $t('shared.pageOperation.getFormOptions'),
      description: $t('shared.pageOperation.desc.getFormOptions', {
        fields: remoteFields.join(', '),
      }),
      readonly: true,
      params: {
        field_name: {
          type: 'string',
          description: $t('shared.pageOperation.param.exactFieldName', {
            fields: remoteFields.join(', '),
          }),
          required: true,
        },
      },
      handler: async (params) => {
        const openCheck = requireOpenForm(pageKey);
        if (!openCheck.ok) {
          return openCheck.result;
        }
        const fieldName = resolveFormOptionsFieldName(params);
        if (!fieldName || !formParamsMap[fieldName]) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.unknownField', {
              field: fieldName,
              available: remoteFields.join(', '),
            }),
          };
        }

        const status = await ensureRemoteOptionsWithTimeout(ensureRemoteOptions);
        if (status === 'timeout') {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.optionsLoadTimeout', {
              field: fieldName,
            }),
          };
        }
        const desc = formParamsMap[fieldName];
        if (desc?.options && desc.options.length > 0) {
          return {
            success: true,
            message: $t('shared.pageOperation.msg.foundOptions', {
              field: fieldName,
              count: desc.options.length,
            }),
            data: { field: fieldName, options: desc.options },
          };
        }

        return {
          success: true,
          message: $t('shared.pageOperation.msg.noOptionsLoaded', {
            field: fieldName,
          }),
          data: { field: fieldName, options: [] },
        };
      },
    });
  }

  return operations;
}

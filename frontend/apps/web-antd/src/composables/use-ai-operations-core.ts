/**
 * AI Page Operation Utilities
 * AI 页面操作工具函数
 *
 * Provides automatic schema extraction and standard CRUD operation generation
 * for CRUD pages using shared operation descriptors.
 * 为 CRUD 页面提供自动 schema 提取和标准操作生成能力，
 * 底层复用共享操作描述类型。
 *
 * Usage (in useCrudList/useCrudPage):
 * ```ts
 * const ops = createStandardOperations({
 *   resource: '/admin/ai/agents',
 *   loadList, onSearch, list, formPopupApi,
 *   searchSchema: useGridFormSchema,
 *   formSchema: useFormSchema,
 *   detailRoute: '/admin/ai/agents/:id',
 *   disabled: ['delete'],
 * });
 * // page-level registration has been removed from shared core
 * ```
 */

import type { Ref } from 'vue';

import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';
import type { VbenFormSchema } from '#/core/adapter/form/setup';
import type { PageAICapabilityKey } from '#/utils/ai-page-capabilities';

import { mergeDisabledOperations } from '#/utils/ai-page-capabilities';

import type { EnhancedFormFieldDescriptor } from './ai-operation-types';
import type { SearchParamEntry } from './use-ai-operations-schema';
import type { ValueResolver } from './use-ai-operations-pagination';

import {
  buildFormOperations,
  buildStandardCrudOperations,
} from './use-ai-operations-executor';
import {
  buildFieldParamSchema,
  extractFormParams,
  extractSearchParams,
} from './use-ai-operations-schema';

export {
  buildCrudListSummary,
  buildCrudPaginationState,
  compactCrudContextValues,
  type CrudPaginationState,
} from './use-ai-operations-pagination';
export {
  clearRemoteOptionsCache,
  resolveRemoteOptions,
} from './use-ai-operations-remote-options';
export { extractFormParams, extractSearchParams } from './use-ai-operations-schema';

// ============ Types / 类型定义 ============

/**
 * Form popup API interface (compatible with useVbenDrawer / useVbenModal result)
 * 表单弹窗 API 接口（兼容 useVbenDrawer / useVbenModal 返回值）
 */
export interface FormPopupApi {
  setData: (data: Record<string, unknown>) => { open: () => void };
}

interface CrudSearchStatePayload {
  rawFormValues?: Record<string, unknown>;
}

/**
 * Options for createStandardOperations
 * createStandardOperations 配置选项
 */
export interface CrudAiOperationsOptions {
  /** API resource base path / 资源基础路径 */
  resource: string;
  /** Reload list callback / 刷新列表回调 */
  loadList: () => Promise<void>;
  /** Apply search params callback / 应用搜索参数回调 */
  onSearch: (
    params?: Record<string, unknown>,
    state?: CrudSearchStatePayload,
  ) => Promise<void> | void;
  /** Current list data ref / 当前列表数据 ref */
  list: Ref<unknown[]>;
  /** Total row count / 总行数 */
  total?: number | Ref<number>;
  /** Current page number / 当前页码 */
  currentPage?: ValueResolver<number>;
  /** Current page size / 当前每页条数 */
  pageSize?: ValueResolver<number>;
  /** Set current page / 设置当前页 */
  setCurrentPage?: (page: number) => Promise<void> | void;
  /** Set page size / 设置每页条数 */
  setPageSize?: (size: number) => Promise<void> | void;
  /** Form popup API (from useVbenDrawer or useVbenModal) / 表单弹窗 API */
  formPopupApi?: FormPopupApi | null;
  /** Form default values / 表单默认值 */
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>;
  /** Search schema factory (returns searchFormSchema array) / 搜索 schema 工厂函数 */
  searchSchema?: () => VbenFormSchema[];
  /** Form schema factory (isEdit=false for create mode) / 表单 schema 工厂函数 */
  formSchema?: (isEdit?: boolean) => VbenFormSchema[];
  /** Detail page route template, e.g. '/admin/ai/agents/:id' / 详情页路由模板 */
  detailRoute?: string;
  /** Whether recycle bin is enabled / 是否启用回收站 */
  hasRecycleBin?: boolean;
  /** Open recycle bin callback / 打开回收站回调 */
  openRecycleBin?: () => void;
  /** Open export modal callback / 打开导出弹窗回调 */
  openExportModal?: () => void;
  /** Legacy disabled operation names / 旧版禁用操作名称列表 */
  disabled?: string[];
  /** Disabled capability groups / 禁用的能力分组 */
  disabledCapabilities?: PageAICapabilityKey[];
  /** Disabled operation names / 禁用的操作名称列表 */
  disabledOperations?: string[];
  /** Extra custom operations merged with standard ops (extra overrides same-named standard) / 额外自定义操作 */
  extra?: PageOperation[];
  /** Page key (for form state tracking via formStateTracker) / 页面标识（用于表单状态追踪） */
  pageKey?: string;
  /** Row key field name / 行主键字段名 */
  rowKeyField?: string;
  /** Preferred display keys for row previews / 行预览优先展示字段 */
  displayKeys?: ValueResolver<string[]>;
}

/**
 * Options for createFormOperations
 * createFormOperations 配置选项
 */
export interface FormAiOperationsOptions {
  /** Page key (for formStateTracker) / 页面标识 */
  pageKey: string;
  /** Form schema factory / 表单 schema 工厂函数 */
  formSchema: (isEdit?: boolean) => VbenFormSchema[];
  /** API resource path (for remote options cache) / API 资源路径（用于远程选项缓存） */
  resource: string;
}

function buildSearchParamSchema(
  searchParamsMap: Record<string, SearchParamEntry>,
): Record<string, unknown> {
  const searchOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(searchParamsMap)) {
    searchOpParams[key] = { type: entry.type, description: entry.description };
  }
  return searchOpParams;
}

function buildCreateParamSchema(
  formParamsMap: Record<string, EnhancedFormFieldDescriptor>,
): Record<string, unknown> {
  const createOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(formParamsMap)) {
    createOpParams[key] = buildFieldParamSchema(entry, {
      includeDefaultValue: false,
      includeRequired: false,
    });
  }
  return createOpParams;
}

/**
 * Create standard CRUD AI operations for a list page
 * 为列表页创建标准 CRUD AI 操作集
 */
export function createStandardOperations(
  opts: CrudAiOperationsOptions,
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
    searchSchema,
    formSchema,
    detailRoute,
    hasRecycleBin,
    openRecycleBin,
    openExportModal,
    disabled,
    disabledCapabilities,
    disabledOperations,
    extra = [],
    pageKey: optsPageKey,
    rowKeyField = 'id',
    displayKeys,
  } = opts;

  const disabledOperationNames = new Set(
    mergeDisabledOperations({
      disabledCapabilities,
      disabledOperations,
      legacyDisabledOperations: disabled,
    }),
  );

  const searchParamsMap: Record<string, SearchParamEntry> = searchSchema
    ? extractSearchParams(searchSchema())
    : {};
  const rawFormSchema = formSchema ? formSchema(false) : [];
  const formParamsMap: Record<string, EnhancedFormFieldDescriptor> = formSchema
    ? extractFormParams(rawFormSchema)
    : {};

  const operations = buildStandardCrudOperations({
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
    hasFormSchema: Boolean(formSchema),
    hasRecycleBin,
    openRecycleBin,
    openExportModal,
    pageKey: optsPageKey,
    rowKeyField,
    displayKeys,
    searchParamsMap,
    formParamsMap,
    rawFormSchema,
    searchOpParams: buildSearchParamSchema(searchParamsMap),
    createOpParams: buildCreateParamSchema(formParamsMap),
  });

  if (formSchema && optsPageKey) {
    for (const operation of buildFormOperations({
      pageKey: optsPageKey,
      formSchema,
      resource,
    })) {
      const existingIdx = operations.findIndex((item) => item.name === operation.name);
      if (existingIdx === -1) {
        operations.push(operation);
      } else {
        operations[existingIdx] = operation;
      }
    }
  }

  // Merge extra operations — extra overrides same-named standard operations
  // 合并额外操作 — extra 中的操作可覆盖同名标准操作
  for (const op of extra) {
    const existingIdx = operations.findIndex((o) => o.name === op.name);
    if (existingIdx === -1) {
      operations.push(op);
    } else {
      operations[existingIdx] = op;
    }
  }

  return operations.filter(
    (operation) => !disabledOperationNames.has(operation.name),
  );
}

/**
 * Create form-only AI operations (get_form_state, fill_form, validate_form, get_form_options)
 * 创建仅表单相关的 AI 操作
 *
 * For useCrudPage pages that manually register other operations but need form support.
 * 供 useCrudPage 页面使用：手动注册其他操作，但需要表单支持。
 */
export function createFormOperations(
  opts: FormAiOperationsOptions,
): PageOperation[] {
  return buildFormOperations(opts);
}

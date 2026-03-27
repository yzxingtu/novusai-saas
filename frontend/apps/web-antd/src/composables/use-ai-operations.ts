/**
 * AI Page Operation Utilities
 * AI 页面操作工具函数
 *
 * Provides automatic schema extraction and standard CRUD operation generation
 * for CRUD pages using the page-operation-registry mechanism.
 * 为 CRUD 页面提供自动 schema 提取和标准操作生成能力，
 * 底层复用 page-operation-registry 机制。
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
 * registerPageOperations(pageKey, ops);
 * ```
 */

import type { Ref } from 'vue';

import type { FormState } from './use-form-state-tracker';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';
import type { VbenFormSchema } from '#/core/adapter/form/setup';
import type { PageAICapabilityKey } from '#/utils/ai-page-capabilities';

import { useRouter } from 'vue-router';

import { $t } from '#/locales';
import { mergeDisabledOperations } from '#/utils/ai-page-capabilities';
import { requestClient } from '#/utils/request';

import { resolveFormOptionsFieldName } from './form-option-param-utils';
import { formStateTracker } from './use-form-state-tracker';

// ============ Types / 类型定义 ============

/**
 * Internal search param entry with JSON:API filter field mapping
 * 内部搜索参数条目，含 JSON:API filter 字段名映射
 */
interface SearchParamEntry {
  type: 'boolean' | 'number' | 'string';
  description: string;
  /** Original JSON:API filter fieldName (e.g. 'filter[name][ilike]') / 原始 JSON:API filter 字段名 */
  filterFieldName: string;
  /** Original search form field name / 原始搜索表单字段名 */
  formFieldName: string;
  /** Date-range slot role when the source field is _dateRange_* / 日期范围字段的槽位角色 */
  dateRangeRole?: 'end' | 'start';
}

/**
 * Option item for select/checkbox/radio fields
 * 选择器/多选框/单选框的选项条目
 */
export interface AiFieldOption {
  label: string;
  value: unknown;
}

/** Component type enum for AI field descriptors / AI 字段描述的组件类型枚举 */
export type AiFieldComponent =
  | 'custom'
  | 'date'
  | 'icon'
  | 'input'
  | 'number'
  | 'remote_select'
  | 'select'
  | 'switch'
  | 'textarea'
  | 'tree_select';

/**
 * Enhanced form field descriptor — provides complete metadata for AI
 * 增强的表单字段描述 — 为 AI 提供完整元数据
 */
export interface EnhancedFormFieldDescriptor {
  type: 'array' | 'boolean' | 'number' | 'string';
  description: string;
  required?: boolean;
  /** UI component kind / UI 组件种类 */
  component: AiFieldComponent;
  /** Field constraints / 字段约束 */
  constraints?: {
    max?: number;
    maxLength?: number;
    min?: number;
    precision?: number;
  };
  /** Static options (for select/checkbox/radio) / 静态可选项 */
  options?: AiFieldOption[];
  /** Options source type / 选项来源 */
  optionsSource?: 'remote' | 'static';
  /** Default value / 默认值 */
  defaultValue?: unknown;
  /** Placeholder hint / 占位提示 */
  placeholder?: string;
}

// FormParamEntry is now EnhancedFormFieldDescriptor (used throughout this module)
// FormParamEntry 现在是 EnhancedFormFieldDescriptor（在本模块中使用）

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

type ValueResolver<T> = (() => T) | Ref<T> | T;

export interface CrudPaginationState {
  current_page: number;
  page_size: number;
  total_pages: number;
  total_rows: number;
  has_next_page: boolean;
  has_previous_page: boolean;
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
  if (typeof value === 'number' || typeof value === 'boolean')
    return String(value);
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

// ============ Schema Extraction / schema 字段提取 ============

/**
 * Extract search params from searchFormSchema
 * 从搜索表单 schema 中提取搜索参数（含 JSON:API 字段名映射）
 *
 * Handles field name patterns:
 * - searchInput('code', '...')     → fieldName: 'filter[code][ilike]' → key: 'code'
 * - statusSelect()                 → fieldName: 'filter[is_active]'   → key: 'is_active'
 * - searchDateRange({ field: 'x'}) → fieldName: '_dateRange_x'        → keys: 'x_gte', 'x_lte'
 */
export function extractSearchParams(
  schema: VbenFormSchema[],
): Record<string, SearchParamEntry> {
  const params: Record<string, SearchParamEntry> = {};

  for (const item of schema) {
    const fieldName = item.fieldName as string | undefined;
    const label = item.label as string | undefined;
    if (!fieldName || !label) continue;

    // Date range: _dateRange_{field} → {field}_gte + {field}_lte
    // 日期范围：_dateRange_{field} → {field}_gte + {field}_lte
    if (fieldName.startsWith('_dateRange_')) {
      const field = fieldName.slice('_dateRange_'.length);
      params[`${field}_gte`] = {
        type: 'string',
        description: `${label} (start / 开始, YYYY-MM-DD)`,
        filterFieldName: `filter[${field}][gte]`,
        formFieldName: fieldName,
        dateRangeRole: 'start',
      };
      params[`${field}_lte`] = {
        type: 'string',
        description: `${label} (end / 结束, YYYY-MM-DD)`,
        filterFieldName: `filter[${field}][lte]`,
        formFieldName: fieldName,
        dateRangeRole: 'end',
      };
      continue;
    }

    const component = item.component as string;
    let type: 'boolean' | 'number' | 'string' = 'string';

    if (component === 'InputNumber') {
      type = 'number';
    }

    if (component === 'Select') {
      const opts = (item.componentProps as Record<string, unknown> | undefined)
        ?.options;
      if (
        Array.isArray(opts) &&
        opts.some(
          (o: unknown) => typeof (o as { value: unknown }).value === 'boolean',
        )
      ) {
        type = 'boolean';
      }
    }

    // Filter field: filter[field] or filter[field][op] / JSON:API 过滤字段
    const filterMatch = fieldName.match(/^filter\[([^\]]+)\](?:\[[^\]]+\])?$/);
    const filterField = filterMatch?.[1];
    if (filterField) {
      const field = filterField;
      params[field] = {
        type,
        description: label,
        filterFieldName: fieldName,
        formFieldName: fieldName,
      };
      continue;
    }

    params[fieldName] = {
      type,
      description: label,
      filterFieldName: fieldName,
      formFieldName: fieldName,
    };
  }

  return params;
}

/**
 * Map VbenFormSchema component name to AiFieldComponent
 * 将 VbenFormSchema 组件名映射为 AiFieldComponent
 */
function resolveAiComponent(component: string): AiFieldComponent {
  const map: Record<string, AiFieldComponent> = {
    Input: 'input',
    Textarea: 'textarea',
    InputNumber: 'number',
    Select: 'select',
    ApiSelect: 'remote_select',
    TreeSelect: 'tree_select',
    ApiTreeSelect: 'tree_select',
    Switch: 'switch',
    DatePicker: 'date',
    IconSelector: 'icon',
    Checkbox: 'select',
    CheckboxGroup: 'select',
    Radio: 'select',
    RadioGroup: 'select',
  };
  return map[component] ?? 'custom';
}

/**
 * Extract static options from componentProps
 * 从 componentProps 提取静态选项
 */
function extractStaticOptions(
  componentProps: Record<string, unknown> | undefined,
): AiFieldOption[] | undefined {
  if (!componentProps) return undefined;
  const opts = componentProps.options;
  if (!Array.isArray(opts) || opts.length === 0) return undefined;
  return opts.map((o: any) => ({
    label: String(o.label ?? o.title ?? o.value),
    value: o.value,
  }));
}

/**
 * Extract form field params from formSchema (for create/edit operations)
 * 从表单 schema 中提取完整字段元数据（用于 AI 感知表单结构）
 *
 * Enhanced: includes component type, options, constraints, defaultValue, placeholder
 * 增强版：包含组件类型、选项列表、约束、默认值、占位提示
 *
 * Excludes: Dividers, RangePickers, fields starting with '_', filter fields
 * 排除：分隔线、日期范围选择器、以 '_' 开头的字段、filter 字段
 */
export function extractFormParams(
  schema: VbenFormSchema[],
): Record<string, EnhancedFormFieldDescriptor> {
  const params: Record<string, EnhancedFormFieldDescriptor> = {};

  for (const item of schema) {
    const fieldName = item.fieldName as string | undefined;
    const label = item.label as string | undefined;
    const component = item.component as string;
    if (!fieldName || !label) continue;

    if (
      fieldName.startsWith('_') ||
      fieldName.startsWith('filter[') ||
      component === 'Divider' ||
      component === 'RangePicker'
    ) {
      continue;
    }

    const aiComponent = resolveAiComponent(component);
    const props = item.componentProps as Record<string, unknown> | undefined;

    // Infer value type from component / 根据组件推断值类型
    let type: 'array' | 'boolean' | 'number' | 'string' = 'string';
    if (component === 'InputNumber') type = 'number';
    if (component === 'Switch') type = 'boolean';
    if (component === 'DatePicker') type = 'string';
    if (
      component === 'ApiSelect' ||
      component === 'Select' ||
      component === 'TreeSelect' ||
      component === 'ApiTreeSelect'
    ) {
      const staticOpts = extractStaticOptions(props);
      const firstStaticOption = staticOpts?.[0];
      if (
        staticOpts &&
        staticOpts.length > 0 &&
        typeof firstStaticOption?.value === 'number'
      ) {
        type = 'number';
      }
      if (
        staticOpts &&
        staticOpts.length > 0 &&
        typeof firstStaticOption?.value === 'boolean'
      ) {
        type = 'boolean';
      }
      if (props?.mode === 'multiple' || props?.mode === 'tags') {
        type = 'array';
      }
    }

    const required =
      item.rules === 'required' || item.rules === 'selectRequired';

    // Build constraints / 构建约束
    const constraints: EnhancedFormFieldDescriptor['constraints'] = {};
    if (props?.maxLength !== undefined)
      constraints.maxLength = Number(props.maxLength);
    if (props?.min !== undefined) constraints.min = Number(props.min);
    if (props?.max !== undefined) constraints.max = Number(props.max);
    if (props?.precision !== undefined)
      constraints.precision = Number(props.precision);
    const hasConstraints = Object.keys(constraints).length > 0;

    // Resolve options / 解析选项
    const staticOptions = extractStaticOptions(props);
    const isRemote = component === 'ApiSelect' || component === 'ApiTreeSelect';
    let optionsSource: EnhancedFormFieldDescriptor['optionsSource'];
    if (isRemote) {
      optionsSource = 'remote';
    } else if (staticOptions) {
      optionsSource = 'static';
    }

    // Resolve placeholder / 解析占位提示
    const placeholder = props?.placeholder as string | undefined;

    const descriptor: EnhancedFormFieldDescriptor = {
      type,
      description: label,
      component: aiComponent,
      ...(required ? { required: true } : {}),
      ...(hasConstraints ? { constraints } : {}),
      ...(staticOptions ? { options: staticOptions } : {}),
      ...(optionsSource ? { optionsSource } : {}),
      ...(item.defaultValue === undefined
        ? {}
        : { defaultValue: item.defaultValue }),
      ...(placeholder ? { placeholder } : {}),
    };

    params[fieldName] = descriptor;
  }

  return params;
}

// ============ Remote Options Resolver / 远程选项解析 ============

/** Cache for resolved remote options / 远程选项缓存 */
const _remoteOptionsCache = new Map<string, AiFieldOption[]>();
const _remoteOptionsPending = new Map<string, Promise<AiFieldOption[]>>();

/**
 * Build a stable cache key from resource + field + api function
 * 从 resource + field + api 函数构建稳定的缓存 key
 */
function buildOptionsCacheKey(resource: string, fieldName: string): string {
  return `${resource}::${fieldName}`;
}

/**
 * Resolve remote options for all ApiSelect fields in a schema.
 * Returns a Map<fieldName, options[]>. Uses cache to avoid duplicate requests.
 * 解析 schema 中所有 ApiSelect 字段的远程选项。
 * 返回 Map<字段名, 选项列表>，使用缓存避免重复请求。
 */
export async function resolveRemoteOptions(
  schema: VbenFormSchema[],
  resource: string,
): Promise<Map<string, AiFieldOption[]>> {
  const result = new Map<string, AiFieldOption[]>();
  const tasks: Array<{
    fieldName: string;
    promise: Promise<AiFieldOption[]>;
  }> = [];

  for (const item of schema) {
    const fieldName = item.fieldName as string | undefined;
    const component = item.component as string;
    if (!fieldName) continue;
    if (component !== 'ApiSelect' && component !== 'ApiTreeSelect') continue;

    const props = item.componentProps as Record<string, unknown> | undefined;
    const apiFn = props?.api as ((...args: any[]) => Promise<any>) | undefined;
    if (!apiFn) continue;

    const cacheKey = buildOptionsCacheKey(resource, fieldName);

    // Return cached / 直接返回缓存
    const cachedOptions = _remoteOptionsCache.get(cacheKey);
    if (cachedOptions) {
      result.set(fieldName, cachedOptions);
      continue;
    }

    // Deduplicate in-flight requests / 去重进行中的请求 / 去重正在进行的请求
    const pendingOptionsPromise = _remoteOptionsPending.get(cacheKey);
    if (pendingOptionsPromise) {
      tasks.push({ fieldName, promise: pendingOptionsPromise });
      continue;
    }

    const apiParams = {
      ...(props?.params as Record<string, unknown>),
      'page[size]': 50,
    };
    const resultField = (props?.resultField as string) || 'items';

    const promise = apiFn(apiParams)
      .then((response: any) => {
        let items: any[] = [];
        if (Array.isArray(response)) {
          items = response;
        } else if (response && Array.isArray(response[resultField])) {
          items = response[resultField];
        } else if (response && Array.isArray(response.items)) {
          items = response.items;
        }
        const options: AiFieldOption[] = items.map((item: any) => ({
          label: String(item.label ?? item.name ?? item.title ?? item.id),
          value: item.value ?? item.id,
        }));
        _remoteOptionsCache.set(cacheKey, options);
        _remoteOptionsPending.delete(cacheKey);
        return options;
      })
      .catch(() => {
        _remoteOptionsPending.delete(cacheKey);
        return [] as AiFieldOption[];
      });

    _remoteOptionsPending.set(cacheKey, promise);
    tasks.push({ fieldName, promise });
  }

  // Wait for all in-flight / 等待所有进行中的请求
  const settled = await Promise.allSettled(tasks.map((t) => t.promise));
  for (const [i, task] of tasks.entries()) {
    const s = settled[i];
    if (!s) {
      continue;
    }
    if (s.status === 'fulfilled' && s.value.length > 0) {
      result.set(task.fieldName, s.value);
    }
  }

  return result;
}

/**
 * Clear remote options cache for a resource (or all)
 * 清除某资源（或全部）的远程选项缓存
 */
export function clearRemoteOptionsCache(resource?: string): void {
  if (!resource) {
    _remoteOptionsCache.clear();
    return;
  }
  for (const key of _remoteOptionsCache.keys()) {
    if (key.startsWith(`${resource}::`)) {
      _remoteOptionsCache.delete(key);
    }
  }
}

// ============ Dot-path helpers for nested form fields / 点号路径工具函数 ============

/**
 * Convert flat dot-notation keys to a nested object structure / 将扁平点号键转为嵌套对象
 * Non-dot keys are kept as-is.
 * e.g. { 'quota.max_users': 5, name: 'x' } => { quota: { max_users: 5 }, name: 'x' }
 */
function expandDotKeys(flat: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(flat)) {
    if (!key.includes('.')) {
      result[key] = value;
      continue;
    }
    const parts = key.split('.');
    let current = result as Record<string, any>;
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!part) {
        continue;
      }
      current[part] = current[part] ?? {};
      current = current[part];
    }
    const lastPart = parts.at(-1);
    if (lastPart) {
      current[lastPart] = value;
    }
  }
  return result;
}

/**
 * Read a value from a nested object using a dot-separated path / 按点号路径从嵌套对象取值
 * e.g. getByDotPath({ quota: { max_users: 5 } }, 'quota.max_users') => 5
 */
function getByDotPath(obj: Record<string, unknown>, path: string): unknown {
  if (!path.includes('.')) return obj[path];
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (
      current === null ||
      current === undefined ||
      typeof current !== 'object'
    )
      return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

// ============ Fill-form read-back verification / fill_form 读回验证 ============

interface FieldFeedback {
  requested: unknown;
  actual: unknown;
  match: boolean;
}

function isMeaningfullyFilled(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value as object).length > 0;
  return true;
}

/**
 * After setValues, read back actual form values and compare with the requested values / setValues 后读回表单实际值并与请求值对比
 * Returns per-field feedback so the LLM can detect
 * mismatches (e.g. passed a label instead of a value for Select fields).
 */
async function buildFillFormFeedback(
  trackedApi: {
    getValues: () => Promise<Record<string, unknown>> | Record<string, unknown>;
  },
  requestedValues: Record<string, unknown>,
): Promise<{
  feedback: Record<string, FieldFeedback>;
  mismatchCount: number;
}> {
  let actualValues: Record<string, unknown> = {};
  try {
    actualValues = await trackedApi.getValues();
  } catch {
    // Form may not be ready — return optimistic feedback / 表单可能未就绪，返回乐观反馈
    const feedback: Record<string, FieldFeedback> = {};
    for (const [k, v] of Object.entries(requestedValues)) {
      feedback[k] = { requested: v, actual: v, match: true };
    }
    return { feedback, mismatchCount: 0 };
  }

  const feedback: Record<string, FieldFeedback> = {};
  let mismatchCount = 0;
  for (const [key, requested] of Object.entries(requestedValues)) {
    const actual = getByDotPath(actualValues, key);
    const match =
      actual === requested ||
      ((actual === null || actual === undefined) &&
        (requested === null || requested === undefined)) ||
      JSON.stringify(actual) === JSON.stringify(requested);
    feedback[key] = { requested, actual, match };
    if (!match) mismatchCount++;
  }
  return { feedback, mismatchCount };
}

async function waitForTrackedFormState(
  pageKey: string,
  timeoutMs = 1500,
): Promise<FormState> {
  const intervalMs = 60;
  let elapsed = 0;
  let latest = await formStateTracker.getStateWithFallback(pageKey);

  while (!latest.isOpen && elapsed < timeoutMs) {
    await new Promise<void>((resolve) => {
      setTimeout(resolve, intervalMs);
    });
    elapsed += intervalMs;
    latest = await formStateTracker.getStateWithFallback(pageKey);
  }

  return latest;
}

function collectRemainingEmptyFields(
  fieldMap: Record<string, EnhancedFormFieldDescriptor>,
  currentValues: Record<string, unknown>,
  skipKeys: Iterable<string> = [],
): string[] {
  const skipped = new Set(skipKeys);
  return Object.keys(fieldMap).filter((key) => {
    if (skipped.has(key)) return false;
    return !isMeaningfullyFilled(getByDotPath(currentValues, key));
  });
}

// ============ Param Schema Builder / 参数 schema 构建 ============

/**
 * Build a JSON-Schema-like param descriptor from EnhancedFormFieldDescriptor
 * 从 EnhancedFormFieldDescriptor 构建 JSON Schema 风格的参数描述
 */
function buildFieldParamSchema(
  entry: EnhancedFormFieldDescriptor,
  options: {
    includeDefaultValue?: boolean;
    includeRequired?: boolean;
  } = {},
): Record<string, unknown> {
  const { includeDefaultValue = true, includeRequired = true } = options;
  const schema: Record<string, unknown> = {
    type: entry.type,
    description: entry.description,
  };
  if (includeRequired && entry.required) schema.required = true;
  if (entry.component) schema.component = entry.component;
  if (entry.constraints) schema.constraints = entry.constraints;
  if (entry.options && entry.options.length > 0) {
    schema.options = entry.options;
  }
  if (entry.optionsSource) schema.optionsSource = entry.optionsSource;
  if (includeDefaultValue && entry.defaultValue !== undefined)
    schema.defaultValue = entry.defaultValue;
  if (entry.placeholder) schema.placeholder = entry.placeholder;
  return schema;
}

// ============ Standard Operations / 标准操作生成 ============

/**
 * Create standard CRUD AI operations for a list page
 * 为列表页创建标准 CRUD AI 操作集
 *
 * Generates up to 8 standard operations based on provided options:
 * 根据配置生成最多 8 种标准操作：
 * 1. refresh_list       — always registered / 始终注册
 * 2. export_data        — registered if openExportModal provided / 有 openExportModal 时注册
 * 3. search             — registered if searchSchema provided / 有 searchSchema 时注册
 * 4. clear_search       — registered if searchSchema provided / 有 searchSchema 时注册
 * 5. create_record      — registered if formSchema + formPopupApi provided / 有表单时注册
 * 6. edit_record        — registered if formSchema + formPopupApi provided / 有表单时注册
 * 7. navigate_to_detail — registered if detailRoute provided / 有 detailRoute 时注册
 * 8. view_recycle_bin   — registered if hasRecycleBin=true / hasRecycleBin=true 时注册
 *
 * Extra operations can override same-named standard operations.
 * extra 中的操作可以覆盖同名的标准操作。
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
  const isDisabled = (name: string) => disabledOperationNames.has(name);

  // Extract internal param maps with filter field mappings
  // 提取含 filter 字段映射的内部参数 map
  const searchParamsMap: Record<string, SearchParamEntry> = searchSchema
    ? extractSearchParams(searchSchema())
    : {};
  const rawFormSchema = formSchema ? formSchema(false) : [];
  const formParamsMap: Record<string, EnhancedFormFieldDescriptor> = formSchema
    ? extractFormParams(rawFormSchema)
    : {};

  // Lazy-load remote options once and merge into formParamsMap
  // 惰性加载远程选项并合并到 formParamsMap
  let _remoteResolved = false;
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    _remoteResolved = true;
    const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
    for (const [field, options] of remoteOpts) {
      const existing = formParamsMap[field];
      if (existing && !existing.options) {
        existing.options = options;
      }
    }
  }
  // Fire-and-forget preload / 触发后台预加载
  if (
    rawFormSchema.some(
      (s) => s.component === 'ApiSelect' || s.component === 'ApiTreeSelect',
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

  // Convert internal maps to PageOperation params schema (JSON Schema subset)
  // 将内部 map 转换为 PageOperation.params schema（JSON Schema 子集）
  const searchOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(searchParamsMap)) {
    searchOpParams[key] = { type: entry.type, description: entry.description };
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

  const createOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(formParamsMap)) {
    createOpParams[key] = buildFieldParamSchema(entry, {
      includeDefaultValue: false,
      includeRequired: false,
    });
  }

  // Router for navigation operations / 导航操作用的 router
  const router = useRouter();

  const operations: PageOperation[] = [];

  // ── 1. refresh_list — Reload list / 刷新列表 ──
  if (!isDisabled('refresh_list')) {
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
  }

  // ── 2. export_data — Open export modal / 打开导出弹窗 ──
  if (!isDisabled('export_data') && openExportModal) {
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
  if (!isDisabled('search') && Object.keys(searchParamsMap).length > 0) {
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
  if (!isDisabled('clear_search') && Object.keys(searchParamsMap).length > 0) {
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
  if (!isDisabled('read_visible_rows')) {
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
            rows: rows.map((row) =>
              buildVisibleRowPayload(row, visibleFieldNames),
            ),
            visible_columns: visibleFieldNames,
          },
        };
      },
    });
  }

  // ── 3b. pagination operations — Navigate list pages / 分页操作 ──
  if (
    !isDisabled('next_page') &&
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
  if (!isDisabled('read_row_detail')) {
    operations.push({
      name: 'read_row_detail',
      label: $t('shared.pageOperation.readRowDetail'),
      description: $t('shared.pageOperation.desc.readRowDetail'),
      readonly: true,
      params: {
        id: {
          type: 'string',
          description: 'Record id / 记录主键',
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
  }

  if (
    !isDisabled('prev_page') &&
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
    !isDisabled('go_to_page') &&
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
          description: 'Target page number / 目标页码',
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

  if (!isDisabled('set_page_size') && setPageSize) {
    operations.push({
      name: 'set_page_size',
      label: $t('shared.pageOperation.setPageSize'),
      description: $t('shared.pageOperation.desc.setPageSize'),
      readonly: true,
      params: {
        page_size: {
          type: 'number',
          description: 'Rows per page / 每页行数',
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
  if (!isDisabled('create_record') && formPopupApi && formSchema) {
    operations.push({
      name: 'create_record',
      label: $t('shared.pageOperation.createRecord'),
      description: $t('shared.pageOperation.desc.createRecord'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        if (optsPageKey && formStateTracker.isOpenWithFallback(optsPageKey)) {
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
        const overrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) overrides[key] = params[key];
        }

        const defaults = getFormDefaults();
        formPopupApi
          .setData({
            mode: 'add',
            _resource: resource,
            _defaults: expandDotKeys({ ...defaults, ...overrides }),
            ...(optsPageKey ? { _aiPageKey: optsPageKey } : {}),
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
  if (!isDisabled('edit_record') && formPopupApi && formSchema) {
    const editOpParams: Record<string, unknown> = {
      id: {
        type: 'number',
        description: 'Record ID to edit / 要编辑的记录 ID',
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
        if (optsPageKey && formStateTracker.isOpenWithFallback(optsPageKey)) {
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
        const overrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) overrides[key] = params[key];
        }

        const expandedOverrides =
          Object.keys(overrides).length > 0
            ? expandDotKeys(overrides)
            : undefined;

        formPopupApi
          .setData({
            ...record,
            mode: 'edit',
            _resource: resource,
            ...(optsPageKey ? { _aiPageKey: optsPageKey } : {}),
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
  if (!isDisabled('delete_record') && formSchema && formPopupApi) {
    operations.push({
      name: 'delete_record',
      label: $t('shared.pageOperation.deleteRecord'),
      description: $t('shared.pageOperation.desc.deleteRecord'),
      readonly: false,
      params: {
        id: {
          type: 'number',
          description: 'Record ID to delete / 要删除的记录 ID',
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
  if (!isDisabled('navigate_to_detail') && detailRoute) {
    operations.push({
      name: 'navigate_to_detail',
      label: $t('shared.pageOperation.navigateToDetail'),
      description: $t('shared.pageOperation.desc.navigateToDetail'),
      readonly: true,
      params: {
        id: {
          type: 'number',
          description: 'Record ID / 记录 ID',
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
        router.push(path);
        return {
          success: true,
          message: $t('shared.pageOperation.msg.navigatedTo', { path }),
        };
      },
    });
  }

  // ── 8. view_recycle_bin — Open recycle bin (needs hasRecycleBin) / 打开回收站 ──
  if (!isDisabled('view_recycle_bin') && hasRecycleBin && openRecycleBin) {
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
  if (!isDisabled('get_form_state') && formSchema && optsPageKey) {
    operations.push({
      name: 'get_form_state',
      label: $t('shared.pageOperation.getFormState'),
      description: $t('shared.pageOperation.desc.getFormState'),
      readonly: true,
      handler: async () => {
        const state = await formStateTracker.getStateWithFallback(optsPageKey);
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

  // ── 9. fill_form — Fill form (needs formSchema + pageKey) / 填充表单 ──
  if (!isDisabled('fill_form') && formSchema && optsPageKey) {
    operations.push({
      name: 'fill_form',
      label: $t('shared.pageOperation.fillForm'),
      description: $t('shared.pageOperation.desc.fillForm'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        if (!formStateTracker.isOpenWithFallback(optsPageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }

        const trackedApi = formStateTracker.getFormApi(optsPageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
        }

        // Filter to known fields / 过滤为已知字段
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
          trackedApi.setValues(expandDotKeys(validFields));
          await new Promise<void>((r) => setTimeout(r, 100));
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.setFormValuesFailed'),
          };
        }

        const filledKeys = Object.keys(validFields);
        const { feedback, mismatchCount } = await buildFillFormFeedback(
          trackedApi,
          validFields,
        );
        const actualValues = await trackedApi.getValues().catch(() => ({}));
        const remainingEmptyFields = collectRemainingEmptyFields(
          formParamsMap,
          actualValues,
          Object.keys(validFields),
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
            remaining_empty_fields: remainingEmptyFields,
          },
        };
      },
    });
  }

  // ── 10. validate_form — Trigger validation / 校验表单 ──
  if (!isDisabled('validate_form') && formSchema && optsPageKey) {
    operations.push({
      name: 'validate_form',
      label: $t('shared.pageOperation.validateForm'),
      description: $t('shared.pageOperation.desc.validateForm'),
      readonly: true,
      handler: async () => {
        if (!formStateTracker.isOpenWithFallback(optsPageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }
        const trackedApi = formStateTracker.getFormApi(optsPageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
        }
        try {
          const { valid } = await trackedApi.validate();
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
    });
  }

  // ── 10b. submit_form — Submit form (same condition as fill_form) / 提交表单 ──
  if (!isDisabled('submit_form') && formSchema && optsPageKey) {
    operations.push({
      name: 'submit_form',
      label: $t('shared.pageOperation.submitForm'),
      description: $t('shared.pageOperation.desc.submitForm'),
      readonly: false,
      handler: async () => {
        if (!formStateTracker.isOpenWithFallback(optsPageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }
        const trackedApi = formStateTracker.getFormApi(optsPageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
        }
        const validResult = await trackedApi.validate();
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
        if (trackedApi.submitForm) {
          try {
            await trackedApi.submitForm();
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
    });
  }

  // ── 11. get_form_options — Remote select options / 远程下拉选项 ──
  if (!isDisabled('get_form_options') && formSchema && optsPageKey) {
    const remoteFields = Object.entries(formParamsMap)
      .filter(([_, desc]) => desc.optionsSource === 'remote')
      .map(([key]) => key);

    if (remoteFields.length > 0) {
      operations.push({
        name: 'get_form_options',
        label: $t('shared.pageOperation.getFormOptions'),
        description: `Get available options for remote select fields. Required params shape: {"field_name":"<field>"}; available remote fields: ${remoteFields.join(', ')} / 获取远程下拉字段的可选项。必传参数格式：{"field_name":"<字段名>"}；可用字段：${remoteFields.join(', ')}`,
        readonly: true,
        params: {
          field_name: {
            type: 'string',
            description: `Exact field key to get options for. One of: ${remoteFields.join(', ')} / 要获取选项的精确字段名`,
            required: true,
          },
        },
        handler: async (params) => {
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

          await ensureRemoteOptions();
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

  return operations.filter((operation) => !isDisabled(operation.name));
}

// ============ Form-only Operations / 仅表单操作 ============

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
  const { pageKey, formSchema, resource } = opts;

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
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    _remoteResolved = true;
    const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
    for (const [field, options] of remoteOpts) {
      const existing = formParamsMap[field];
      if (existing && !existing.options) {
        existing.options = options;
      }
    }
  }
  if (
    rawFormSchema.some(
      (s) => s.component === 'ApiSelect' || s.component === 'ApiTreeSelect',
    )
  ) {
    ensureRemoteOptions();
  }

  const operations: PageOperation[] = [
    // get_form_state / 获取表单状态
    {
      name: 'get_form_state',
      label: $t('shared.pageOperation.getFormState'),
      description:
        'Get the current form state: open/closed, field values, dirty fields, validation errors. Call after opening a form. / 获取当前表单状态：打开/关闭、字段值、脏字段、验证错误。在打开表单后调用。',
      readonly: true,
      handler: async () => {
        const state = await formStateTracker.getStateWithFallback(pageKey);
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
      description:
        'Fill form fields with provided values. Form must be open first (use create_record or edit_record). Supports all field types: input, select, switch, date, remote_select. / 用提供的值填充表单字段。需先打开表单。支持所有字段类型。',
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        if (!formStateTracker.isOpenWithFallback(pageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }

        const trackedApi = formStateTracker.getFormApi(pageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
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
          trackedApi.setValues(expandDotKeys(validFields));
          await new Promise<void>((r) => setTimeout(r, 100));
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.setFormValuesFailed'),
          };
        }

        const filledKeys = Object.keys(validFields);
        const { feedback, mismatchCount } = await buildFillFormFeedback(
          trackedApi,
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
      description:
        'Trigger form validation and return errors. / 触发表单校验并返回错误信息。',
      readonly: true,
      handler: async () => {
        if (!formStateTracker.isOpenWithFallback(pageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }
        const trackedApi = formStateTracker.getFormApi(pageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
        }
        try {
          const { valid } = await trackedApi.validate();
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
      description:
        'Validate and submit the currently open form. The form must be filled first. / 校验并提交当前打开的表单。需先填充表单。',
      readonly: false,
      handler: async () => {
        if (!formStateTracker.isOpenWithFallback(pageKey)) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formNotOpen'),
          };
        }
        const trackedApi = formStateTracker.getFormApi(pageKey);
        if (!trackedApi) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.formApiNotAvailable'),
          };
        }
        const validResult = await trackedApi.validate();
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
        if (trackedApi.submitForm) {
          try {
            await trackedApi.submitForm();
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
      description: `Get available options for remote select fields. Required params shape: {"field_name":"<field>"}; available remote fields: ${remoteFields.join(', ')} / 获取远程下拉字段的可选项。必传参数格式：{"field_name":"<字段名>"}；可用字段：${remoteFields.join(', ')}`,
      readonly: true,
      params: {
        field_name: {
          type: 'string',
          description: `Exact field key to get options for. One of: ${remoteFields.join(', ')} / 要获取选项的精确字段名`,
          required: true,
        },
      },
      handler: async (params) => {
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

        await ensureRemoteOptions();
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

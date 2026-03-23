/**
 * Schema Helper Functions
 * Schema 辅助函数
 *
 * Provides simplified configuration for common form fields, reducing boilerplate code.
 * 提供常用表单字段的简化配置，减少重复代码。
 *
 * @example
 * ```ts
 * import { searchInput, statusSelect } from '#/adapter/form';
 * // Business-specific helpers (e.g. planSelect) should be defined in business code
 * // 业务特定的 helper (如 planSelect) 应在业务代码中定义
 * import { planSelect } from './data';
 *
 * // Search form / 搜索表单
 * export function useGridFormSchema() {
 *   return [
 *     searchInput('code', '企业编码'),
 *     searchInput('name', '企业名称'),
 *     statusSelect(),
 *     planSelect({ fieldName: 'filter[plan_id]' }),
 *   ];
 * }
 *
 * // Edit form / 编辑表单
 * export function useFormSchema() {
 *   return [
 *     planSelect({ fieldName: 'plan_id', label: '所属套餐' }),
 *   ];
 * }
 * ```
 */

import type { Dayjs } from 'dayjs';

import type { VbenFormSchema } from './setup';

import dayjs from 'dayjs';

import { $t } from '#/locales';

// ============ Type Definitions / 类型定义 ============

/** ApiSelect simplified config / ApiSelect 简化配置 */
export interface ApiSelectOptions {
  /** API function / API 函数 */
  api: (...args: any[]) => Promise<any>;
  /** Field name / 字段名 */
  fieldName: string;
  /** Label / 标签 */
  label?: string;
  /** Placeholder / 占位符 */
  placeholder?: string;
  /** Fixed params / 固定参数 */
  params?: Record<string, any>;
  /** Option right-side display field, supports dot notation e.g. 'extra.code' / 选项右侧显示字段，支持点表语法如 'extra.code' */
  extraField?: string;
  /** Page size, default 10 / 每页数量，默认 10 */
  pageSize?: number;
  /** Enable click pagination, default true / 是否启用点击分页，默认 true */
  clickPagination?: boolean;
  /** Required / 是否必填 */
  required?: boolean;
}

/** Search input config / 搜索输入框配置 */
export interface SearchInputOptions {
  /** Field name (snake_case, without filter prefix) / 字段名（snake_case，不含 filter 前缀） */
  field: string;
  /** Label / 标签 */
  label: string;
  /** Placeholder / 占位符 */
  placeholder?: string;
  /** Operator, default 'ilike' / 操作符，默认 'ilike' */
  op?: 'eq' | 'ilike' | 'like';
}

/** Status selector config / 状态选择器配置 */
export interface StatusSelectOptions {
  /** Field name (without filter prefix), default 'is_active' / 字段名（不含 filter 前缀），默认 'is_active' */
  field?: string;
  /** Label, default 'Status' / 标签，默认 '状态' */
  label?: string;
  /** Enabled option text / 启用选项文本 */
  enabledLabel?: string;
  /** Disabled option text / 禁用选项文本 */
  disabledLabel?: string;
  /** All option text / 全部选项文本 */
  allLabel?: string;
}

/**
 * General selector config, supports auto-switching between remote API and static options
 * 通用选择器配置，支持远程 API 和静态 Options 自动切换
 */
export interface SelectOptions extends Omit<
  ApiSelectOptions,
  'api' | 'fieldName'
> {
  /** Remote API / 远程 API */
  api?: (...args: any[]) => Promise<any>;
  /** Static options / 静态选项 */
  options?:
    | number[]
    | string[]
    | { [key: string]: any; label: string; value: any }[];
  /** Field name (optional, if passed as parameter) / 字段名（可选，如果作为参数传入） */
  fieldName?: string;
}

/**
 * Unified selector (Modern)
 * 统一选择器 (Modern)
 *
 * Smart detection of remote vs static selector, hiding component differences.
 * 智能判断使用远程还是静态选择器，屏蔽组件差异。
 *
 * @example
 * ```ts
 * // 1. Remote dropdown / 远程下拉
 * select('plan_id', '套餐', { api: getPlanApi })
 *
 * // 2. Static dropdown (object array) / 静态下拉 (对象数组)
 * select('gender', '性别', {
 *   options: [
 *     { label: '男', value: 1 },
 *     { label: '女', value: 2 }
 *   ]
 * })
 *
 * // 3. Static dropdown (simple array -> auto-convert to label=value) / 静态下拉 (简单数组 -> 自动转 label=value)
 * select('tags', '标签', { options: ['Vue', 'React'] })
 * ```
 */
export function select(
  field: string,
  label: string,
  options: SelectOptions = {},
): VbenFormSchema {
  const { api, options: staticOptions, ...rest } = options;

  // 1. If API provided, use ApiSelect / 如果有 API，使用 ApiSelect
  if (api) {
    return apiSelect({
      api,
      fieldName: field,
      label,
      ...rest,
    });
  }

  // 2. If static options, use Select / 如果是静态 Options，使用 Select
  let normalizedOptions: { label: string; value: any }[] = [];
  if (staticOptions) {
    normalizedOptions =
      staticOptions.length > 0 && typeof staticOptions[0] === 'object'
        ? (staticOptions as { label: string; value: any }[])
        : (staticOptions as (number | string)[]).map((val) => ({
            label: String(val),
            value: val,
          }));
  }

  const { required, placeholder, ...componentProps } = rest;

  return {
    component: 'Select',
    componentProps: {
      allowClear: true,
      class: 'w-full',
      placeholder: placeholder || `请选择${label}`,
      options: normalizedOptions,
      showSearch: true,
      optionFilterProp: 'label', // Allow searching by label / 允许按 label 搜索
      ...componentProps,
    },
    fieldName: field,
    label,
    ...(required ? { rules: 'selectRequired' } : {}),
  };
}

/**
 * Tree select config / 树形选择器配置
 */
export interface TreeSelectOptions extends Omit<
  ApiSelectOptions,
  'api' | 'fieldName'
> {
  /** Remote API / 远程 API */
  api?: (...args: any[]) => Promise<any>;
  /** Static tree data / 静态树数据 */
  options?: any[];
  /** Field name / 字段名 */
  fieldName?: string;
}

/**
 * General tree select, auto-detects ApiTreeSelect or TreeSelect
 * 通用树形选择器，自动判断使用 ApiTreeSelect 或 TreeSelect
 */
export function treeSelect(
  field: string,
  label: string,
  options: TreeSelectOptions = {},
): VbenFormSchema {
  const { api, options: staticOptions, ...rest } = options;

  if (api) {
    return apiTreeSelect({
      api,
      fieldName: field,
      label,
      ...rest,
    });
  }

  const { required, placeholder, ...componentProps } = rest;

  return {
    component: 'TreeSelect',
    componentProps: {
      allowClear: true,
      class: 'w-full',
      placeholder: placeholder || `请选择${label}`,
      showSearch: true,
      treeData: staticOptions,
      treeNodeFilterProp: 'label',
      ...componentProps,
    },
    fieldName: field,
    label,
    ...(required ? { rules: 'selectRequired' } : {}),
  };
}

/**
 * Create ApiTreeSelect schema / 创建 ApiTreeSelect schema
 */
export function apiTreeSelect(options: ApiSelectOptions): VbenFormSchema {
  const {
    api,
    fieldName,
    label = '',
    placeholder,
    params = {},
    required = false,
    ...rest
  } = options;

  return {
    component: 'ApiTreeSelect',
    componentProps: {
      api,
      class: 'w-full',
      params,
      placeholder: placeholder || `请选择${label}`,
      resultField: 'items',
      ...rest,
    },
    fieldName,
    label,
    ...(required ? { rules: 'selectRequired' } : {}),
  };
}

// ============ Core Helper Functions / 核心辅助函数 ============

/**
 * Create ApiSelect schema (general)
 * 创建 ApiSelect schema（通用）
 *
 * @example
 * ```ts
 * apiSelect({
 *   api: getTenantPlanSelectApi,
 *   fieldName: 'plan_id',
 *   label: '套餐',
 *   extraField: 'code',
 * })
 * ```
 */
export function apiSelect(options: ApiSelectOptions): VbenFormSchema {
  const {
    api,
    fieldName,
    label = '',
    placeholder,
    params = {},
    extraField,
    pageSize = 10,
    clickPagination = true,
    required = false,
  } = options;

  return {
    component: 'ApiSelect',
    componentProps: {
      allowClear: true,
      api,
      class: 'w-full',
      filterOption: false,
      params,
      placeholder,
      resultField: 'items',
      showSearch: true,
      pagination: true,
      clickPagination,
      pageSize,
      ...(extraField
        ? {
            optionRightField: extraField.includes('.')
              ? extraField
              : `extra.${extraField}`,
          }
        : {}),
    },
    fieldName,
    label,
    ...(required ? { rules: 'selectRequired' } : {}),
  };
}

/**
 * Create search input schema
 * 创建搜索输入框 schema
 *
 * Automatically adds JSON:API format field name
 * 自动添加 JSON:API 格式的字段名
 *
 * @example
 * ```ts
 * searchInput('code', '企业编码')
 * // => fieldName: 'filter[code][ilike]'
 *
 * searchInput('name', '名称', { op: 'eq' })
 * // => fieldName: 'filter[name]'
 * ```
 */
export function searchInput(
  field: string,
  label: string,
  options: Partial<SearchInputOptions> = {},
): VbenFormSchema {
  const { placeholder, op = 'ilike' } = options;

  // Build JSON:API format field name / 构造 JSON:API 格式的字段名
  const fieldName =
    op === 'eq' ? `filter[${field}]` : `filter[${field}][${op}]`;

  return {
    component: 'Input',
    componentProps: {
      allowClear: true,
      placeholder: placeholder || `搜索${label}`,
    },
    fieldName,
    label,
  };
}

/**
 * Create status selector schema
 * 创建状态选择器 schema
 *
 * @example
 * ```ts
 * statusSelect()
 * // => 默认 is_active 字段
 *
 * statusSelect({ field: 'is_visible', label: '可见状态' })
 * ```
 */
export function statusSelect(
  options: StatusSelectOptions = {},
): VbenFormSchema {
  const {
    field = 'is_active',
    label = $t('shared.common.status'),
    enabledLabel = $t('shared.common.enabled'),
    disabledLabel = $t('shared.common.disabled'),
    allLabel = $t('shared.common.all'),
  } = options;

  return {
    component: 'Select',
    componentProps: {
      allowClear: true,
      class: 'w-full',
      options: [
        { label: enabledLabel, value: true },
        { label: disabledLabel, value: false },
      ],
      placeholder: allLabel,
    },
    fieldName: `filter[${field}]`,
    label,
  };
}

/**
 * Create date-time picker schema
 * 创建日期时间选择器 schema
 *
 * @example
 *  ```ts
 * dateField('expires_at', '到期时间')
 * dateField('created_at', '创建时间', { showTime: true })
 * dateField('birthday', '生日', { showTime: false })  // 仅日期
 * ```
 */
export function dateField(
  fieldName: string,
  label: string,
  options: {
    placeholder?: string;
    required?: boolean;
    showTime?: boolean;
  } = {},
): VbenFormSchema {
  const { placeholder, required = false, showTime = true } = options;

  const componentProps: Record<string, any> = {
    class: 'w-full',
    placeholder: placeholder || `选择${label}`,
    // showTime config (if time picker needs to be shown) / showTime 配置(如果需要显示时间选择器)
    ...(showTime
      ? {
          showTime: {
            defaultValue: dayjs('00:00:00', 'HH:mm:ss'),
            format: 'HH:mm:ss',
          },
        }
      : {}),
  };

  return {
    component: 'DatePicker',
    componentProps,
    fieldName,
    label,
    ...(required ? { rules: 'selectRequired' } : {}),
  };
}

/** Date range search config / 日期范围搜索配置 */
export interface SearchDateRangeOptions {
  /** Start date field name, default 'created_at' / 开始日期字段名，默认 'created_at' */
  field?: string;
  /** Label / 标签 */
  label?: string;
  /** Placeholder [start, end] / 占位符 [start, end] */
  placeholder?: [string, string];
  /** Whether to show time, default true / 是否显示时间，默认 true */
  showTime?: boolean;
  /** Whether to show preset shortcuts, default true / 是否显示快捷选项，默认 true */
  showPresets?: boolean;
}

/**
 * Get date range preset shortcuts (using dayjs objects)
 * 获取日期范围快捷选项（使用 dayjs 对象）
 * @param withTime Whether to include time (start 00:00:00, end 23:59:59) / 是否包含时间（开始 00:00:00，结束 23:59:59）
 */
function getDateRangePresets(
  withTime = false,
): Array<{ label: string; value: [Dayjs, Dayjs] }> {
  const today = dayjs().startOf('day');

  // Set start and end time based on whether to show time / 根据是否显示时间，设置开始和结束时间
  const toStart = (d: Dayjs): Dayjs =>
    withTime ? d.startOf('day') : d.startOf('day');
  const toEnd = (d: Dayjs): Dayjs =>
    withTime ? d.endOf('day') : d.startOf('day');

  return [
    {
      label: $t('shared.common.dateRange.today'),
      value: [toStart(today), toEnd(today)],
    },
    {
      label: $t('shared.common.dateRange.yesterday'),
      value: [
        toStart(today.subtract(1, 'day')),
        toEnd(today.subtract(1, 'day')),
      ],
    },
    {
      label: $t('shared.common.dateRange.last3Days'),
      value: [toStart(today.subtract(2, 'day')), toEnd(today)],
    },
    {
      label: $t('shared.common.dateRange.last7Days'),
      value: [toStart(today.subtract(6, 'day')), toEnd(today)],
    },
    {
      label: $t('shared.common.dateRange.lastMonth'),
      value: [toStart(today.subtract(1, 'month')), toEnd(today)],
    },
    {
      label: $t('shared.common.dateRange.last2Months'),
      value: [toStart(today.subtract(2, 'month')), toEnd(today)],
    },
    {
      label: $t('shared.common.dateRange.last3Months'),
      value: [toStart(today.subtract(3, 'month')), toEnd(today)],
    },
  ];
}

/**
 * Create date range search schema
 * 创建日期范围搜索 schema
 *
 * Auto-converts to JSON:API format filter params.
 * 自动转换为 JSON:API 格式的 filter 参数
 * Default shows time picker, start 00:00:00, end 23:59:59
 * 默认显示时间选择器，开始时间 00:00:00，结束时间 23:59:59
 *
 * @example
 * ```ts
 * searchDateRange()
 * // => 默认 created_at 字段，显示时分秒
 *
 * searchDateRange({ field: 'updated_at', label: '更新时间', showTime: false })
 * // => 仅日期选择
 * ```
 */
export function searchDateRange(
  options: SearchDateRangeOptions = {},
): VbenFormSchema {
  const {
    field = 'created_at',
    label = '时间范围',
    placeholder = ['开始时间', '结束时间'],
    showTime = true,
    showPresets = true,
  } = options;

  return {
    component: 'RangePicker',
    componentProps: {
      allowClear: true,
      class: 'w-full',
      format: showTime ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD',
      placeholder,
      valueFormat: showTime ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD',
      showTime: showTime
        ? {
            defaultValue: [
              dayjs('00:00:00', 'HH:mm:ss'),
              dayjs('23:59:59', 'HH:mm:ss'),
            ],
            format: 'HH:mm:ss',
          }
        : false,
      ...(showPresets ? { presets: getDateRangePresets(showTime) } : {}),
    },
    fieldName: `_dateRange_${field}`,
    label,
  };
}

/**
 * Create text input schema
 * 创建文本输入框 schema
 *
 * @example
 * ```ts
 * inputField('name', '名称', { required: true, maxLength: 100 })
 * ```
 */
export function inputField(
  fieldName: string,
  label: string,
  options: {
    disabled?: boolean;
    maxLength?: number;
    placeholder?: string;
    required?: boolean;
  } = {},
): VbenFormSchema {
  const {
    placeholder,
    required = false,
    maxLength,
    disabled = false,
  } = options;

  return {
    component: 'Input',
    componentProps: {
      placeholder: placeholder || `请输入${label}`,
      ...(maxLength ? { maxLength } : {}),
      ...(disabled ? { disabled } : {}),
    },
    fieldName,
    label,
    ...(required ? { rules: 'required' } : {}),
  };
}

/**
 * Create textarea schema
 * 创建多行文本框 schema
 */
export function textareaField(
  fieldName: string,
  label: string,
  options: {
    maxLength?: number;
    placeholder?: string;
    required?: boolean;
    rows?: number;
  } = {},
): VbenFormSchema {
  const { placeholder, required = false, rows = 3, maxLength } = options;

  return {
    component: 'Textarea',
    componentProps: {
      placeholder: placeholder || `请输入${label}`,
      rows,
      ...(maxLength ? { maxLength } : {}),
    },
    fieldName,
    label,
    ...(required ? { rules: 'required' } : {}),
  };
}

/**
 * Create number input schema
 * 创建数字输入框 schema
 *
 * @example
 * ```ts
 * numberField('price', '价格', { min: 0, precision: 2 })
 * numberField('sort_order', '排序', { min: 0, defaultValue: 0 })
 * ```
 */
export function numberField(
  fieldName: string,
  label: string,
  options: {
    defaultValue?: number;
    max?: number;
    min?: number;
    placeholder?: string;
    precision?: number;
    required?: boolean;
  } = {},
): VbenFormSchema {
  const {
    placeholder,
    required = false,
    min,
    max,
    precision,
    defaultValue,
  } = options;

  return {
    component: 'InputNumber',
    componentProps: {
      style: { width: '100%' },
      placeholder: placeholder || `请输入${label}`,
      ...(min === undefined ? {} : { min }),
      ...(max === undefined ? {} : { max }),
      ...(precision === undefined ? {} : { precision }),
    },
    fieldName,
    label,
    ...(defaultValue === undefined ? {} : { defaultValue }),
    ...(required ? { rules: 'required' } : {}),
  };
}

/**
 * Create switch schema
 * 创建开关 schema
 *
 * @example
 * ```ts
 * switchField('is_active', '启用状态', { defaultValue: true })
 * ```
 */
export function switchField(
  fieldName: string,
  label: string,
  options: { defaultValue?: boolean; help?: string } = {},
): VbenFormSchema {
  const { defaultValue = false, help } = options;

  return {
    component: 'Switch',
    defaultValue,
    fieldName,
    ...(help ? { help } : {}),
    label,
  };
}

/**
 * Create divider schema (for form grouping)
 * 创建分隔线 schema (用于表单分组)
 *
 * @example
 * ```ts
 * dividerField('_quota_divider', '配额设置')
 * ```
 */
export function dividerField(fieldName: string, label: string): VbenFormSchema {
  return {
    component: 'Divider',
    componentProps: {
      orientation: 'left',
    },
    fieldName,
    hideLabel: true,
    renderComponentContent: () => ({
      default: () => label,
    }),
  };
}

/**
 * Create icon selector schema
 * 创建图标选择器 schema
 *
 * Uses custom component, supports IconPicker modal selection
 * 使用自定义组件，支持 IconPicker 弹窗选择
 *
 * @example
 * ```ts
 * iconField('icon', '图标', { placeholder: 'lucide:cpu' })
 * ```
 */
export function iconField(
  fieldName: string,
  label: string,
  options: { placeholder?: string; required?: boolean } = {},
): VbenFormSchema {
  const { placeholder = 'lucide:cpu', required = false } = options;

  return {
    component: 'IconSelector',
    componentProps: {
      placeholder,
    },
    fieldName,
    label,
    ...(required ? { rules: 'required' } : {}),
  };
}

// ============ Business Presets / 业务预设 ============
// Note: Business-specific helpers (e.g. planSelect) should be defined in business code, to avoid Adapter layer depending on specific business APIs / 注意：业务特定 helper 应在业务代码中定义，避免 Adapter 层依赖具体业务 API

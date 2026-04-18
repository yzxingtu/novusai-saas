import type {
  AiFieldComponent,
  AiFieldOption,
  AiFieldScalarType,
  EnhancedFormFieldDescriptor,
} from './ai-operation-types';

import type { VbenFormSchema } from '#/core/adapter/form/setup';

/**
 * Internal search param entry with JSON:API filter field mapping
 * 内部搜索参数条目，含 JSON:API filter 字段名映射
 */
export interface SearchParamEntry {
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
    IdentityRemoteSelect: 'remote_select',
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

function inferScalarTypeFromOptions(
  options: AiFieldOption[] | undefined,
): AiFieldScalarType {
  const firstOption = options?.[0];
  if (typeof firstOption?.value === 'number') return 'number';
  if (typeof firstOption?.value === 'boolean') return 'boolean';
  return 'string';
}

function inferFieldScalarType(
  fieldName: string,
  options: AiFieldOption[] | undefined,
): AiFieldScalarType {
  const optionType = inferScalarTypeFromOptions(options);
  if (optionType !== 'string') return optionType;
  if (fieldName.endsWith('_id')) return 'number';
  return 'string';
}

function inferArrayItemType(
  fieldName: string,
  options: AiFieldOption[] | undefined,
): AiFieldScalarType {
  const optionType = inferFieldScalarType(fieldName, options);
  if (optionType !== 'string') return optionType;
  if (fieldName.endsWith('_ids')) return 'number';
  return 'string';
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
    let items: EnhancedFormFieldDescriptor['items'];
    if (component === 'InputNumber') type = 'number';
    if (component === 'Switch') type = 'boolean';
    if (component === 'DatePicker') type = 'string';
    if (component === 'CheckboxGroup') {
      type = 'array';
    }
    if (
      component === 'ApiSelect' ||
      component === 'IdentityRemoteSelect' ||
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
      if (type === 'string') {
        type = inferFieldScalarType(fieldName, staticOpts);
      }
      if (
        props?.mode === 'multiple' ||
        props?.mode === 'tags' ||
        props?.multiple === true
      ) {
        type = 'array';
        items = {
          type: inferArrayItemType(fieldName, staticOpts),
        };
      }
    }
    if (component === 'CheckboxGroup') {
      items = {
        type: inferArrayItemType(fieldName, extractStaticOptions(props)),
      };
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
    const isRemote =
      component === 'ApiSelect' ||
      component === 'ApiTreeSelect' ||
      component === 'IdentityRemoteSelect';
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
      label,
      component: aiComponent,
      ...(items ? { items } : {}),
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

/**
 * Build a JSON-Schema-like param descriptor from EnhancedFormFieldDescriptor
 * 从 EnhancedFormFieldDescriptor 构建 JSON Schema 风格的参数描述
 */
export function buildFieldParamSchema(
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
  if (entry.items) schema.items = entry.items;
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

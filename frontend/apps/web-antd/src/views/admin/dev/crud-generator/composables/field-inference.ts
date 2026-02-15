/**
 * CRUD Generator — 字段名智能推断
 *
 * 根据字段名模式自动推断 type、required、searchable、
 * list_render、form_component、sortable 等属性。
 */

import type { FieldConfig, FieldType, FormComponent, ListRenderPreset } from '../types';

import { $t } from '#/locales';

interface InferenceResult {
  type: FieldType;
  required?: boolean;
  searchable?: boolean;
  sortable?: boolean;
  in_list?: boolean;
  in_form?: boolean;
  filterable?: boolean;
  max_length?: number;
  list_render?: ListRenderPreset;
  form_component?: FormComponent;
  list_width?: number;
  list_align?: string;
}

interface InferenceRule {
  pattern: RegExp;
  result: InferenceResult;
}

/**
 * 15+ 条字段名推断规则
 * 按优先级排列，首次匹配生效
 */
const FIELD_NAME_INFERENCE_RULES: InferenceRule[] = [
  // 1. 名称/标题
  {
    pattern: /^(name|title|subject)$/i,
    result: {
      type: 'string',
      required: true,
      searchable: true,
      max_length: 200,
      form_component: 'Input',
    },
  },
  // 2. 描述/备注
  {
    pattern: /^(description|remark|note|memo|summary|comment)$/i,
    result: {
      type: 'text',
      in_list: false,
      form_component: 'Textarea',
    },
  },
  // 3. 内容/正文
  {
    pattern: /^(content|body|detail|text)$/i,
    result: {
      type: 'text',
      in_list: false,
      form_component: 'RichText',
    },
  },
  // 4. 状态 (枚举)
  {
    pattern: /^(status|state)$/i,
    result: {
      type: 'enum',
      required: true,
      searchable: true,
      filterable: true,
      list_render: 'tag',
      form_component: 'Select',
      list_width: 100,
      list_align: 'center',
    },
  },
  // 5. 类型/分类
  {
    pattern: /^(type|category|kind|level|priority)$/i,
    result: {
      type: 'string',
      searchable: true,
      filterable: true,
      max_length: 50,
      list_render: 'tag',
      form_component: 'Select',
      list_width: 100,
    },
  },
  // 6. 邮箱
  {
    pattern: /^(email|mail)$/i,
    result: {
      type: 'string',
      max_length: 255,
      searchable: true,
      form_component: 'Input',
    },
  },
  // 7. 手机/电话
  {
    pattern: /^(phone|mobile|tel|telephone)$/i,
    result: {
      type: 'string',
      max_length: 20,
      form_component: 'Input',
    },
  },
  // 8. URL/链接
  {
    pattern: /^(url|link|website|homepage)$/i,
    result: {
      type: 'string',
      max_length: 500,
      list_render: 'link',
      form_component: 'Input',
    },
  },
  // 9. 图片/头像
  {
    pattern: /^(avatar|image|photo|picture|cover|icon|logo|thumbnail)$/i,
    result: {
      type: 'file',
      in_list: true,
      list_render: 'avatar',
      list_width: 64,
      list_align: 'center',
      form_component: 'Upload',
    },
  },
  // 10. 布尔开关 (is_xxx / has_xxx / enable_xxx)
  {
    pattern: /^(is_|has_|enable_|allow_|can_)/i,
    result: {
      type: 'boolean',
      list_render: 'switch',
      list_width: 80,
      list_align: 'center',
      form_component: 'Switch',
    },
  },
  // 11. 金额/价格
  {
    pattern: /^(price|amount|cost|fee|total|balance|salary|budget)$/i,
    result: {
      type: 'decimal',
      sortable: true,
      list_render: 'money',
      list_width: 120,
      list_align: 'right',
      form_component: 'InputNumber',
    },
  },
  // 12. 数量/计数
  {
    pattern: /^(count|quantity|qty|num|number|total_|stock|weight|height|width|age)$/i,
    result: {
      type: 'integer',
      sortable: true,
      list_width: 90,
      list_align: 'center',
      form_component: 'InputNumber',
    },
  },
  // 13. 百分比/比率
  {
    pattern: /^(rate|ratio|percent|percentage|progress|score)$/i,
    result: {
      type: 'float',
      list_render: 'progress',
      list_width: 120,
      form_component: 'Slider',
    },
  },
  // 14. 日期时间 (xxx_at / xxx_date / xxx_time)
  {
    pattern: /(_(at|date|time))$|^(start|end|begin|expire|deadline|birth)/i,
    result: {
      type: 'datetime',
      sortable: true,
      list_render: 'relative_time',
      list_width: 160,
      form_component: 'DatePicker',
    },
  },
  // 15. 外键 (xxx_id)
  {
    pattern: /_id$/i,
    result: {
      type: 'integer',
      filterable: true,
      in_list: false,
      form_component: 'ApiSelect',
    },
  },
  // 16. JSON / 配置
  {
    pattern: /^(config|settings|options|metadata|extra|data|payload|params|attributes)$/i,
    result: {
      type: 'json',
      in_list: false,
      form_component: 'JsonEditor',
    },
  },
  // 17. 排序字段
  {
    pattern: /^(sort_order|sort|order|position|rank|seq|sequence)$/i,
    result: {
      type: 'integer',
      sortable: true,
      in_list: false,
      in_form: false,
      form_component: 'InputNumber',
    },
  },
  // 18. 颜色
  {
    pattern: /^(color|colour|bg_color|text_color)$/i,
    result: {
      type: 'string',
      max_length: 20,
      list_render: 'color',
      list_width: 80,
      form_component: 'ColorPicker',
    },
  },
];

/**
 * 根据字段名推断字段属性
 *
 * @param name 字段名 (snake_case)
 * @returns 推断结果（部分字段属性），未匹配返回 null
 */
export function inferFieldByName(name: string): InferenceResult | null {
  for (const rule of FIELD_NAME_INFERENCE_RULES) {
    if (rule.pattern.test(name)) {
      return { ...rule.result };
    }
  }
  return null;
}

/**
 * 创建一个新的默认 FieldConfig
 */
export function createDefaultField(name = ''): FieldConfig {
  const base: FieldConfig = {
    name,
    type: 'string',
    label_zh: '',
    label_en: '',
    required: false,
    nullable: true,
    unique: false,
    max_length: null,
    default: null,
    index: false,
    enum_ref: null,
    enum_values: null,
    relation_ref: null,
    filterable: true,
    sortable: false,
    searchable: false,
    search_op: 'ilike',
    in_list: true,
    list_width: null,
    list_align: 'left',
    list_render: null,
    list_slot: null,
    list_fixed: null,
    list_sortable: false,
    in_form: true,
    form_component: 'Input',
    form_group: null,
    form_placeholder: null,
    form_rules: null,
    form_depends_on: null,
    form_col_span: null,
    form_help: null,
    upload: null,
  };

  if (name) {
    const inferred = inferFieldByName(name);
    if (inferred) {
      return { ...base, ...inferred } as FieldConfig;
    }
  }

  return base;
}

/**
 * 根据字段类型返回推荐的默认属性
 */
export function getDefaultsByType(type: FieldType): Partial<FieldConfig> {
  switch (type) {
    case 'string': {
      return { max_length: 255, form_component: 'Input', search_op: 'ilike' };
    }
    case 'text': {
      return { max_length: null, form_component: 'Textarea', search_op: 'ilike', list_render: 'ellipsis' };
    }
    case 'integer': {
      return { form_component: 'InputNumber', search_op: 'eq' };
    }
    case 'float':
    case 'decimal': {
      return { form_component: 'InputNumber', search_op: 'eq', list_render: 'money' };
    }
    case 'boolean': {
      return { form_component: 'Switch', list_render: 'switch', search_op: 'eq', nullable: false };
    }
    case 'datetime': {
      return { form_component: 'DatePicker', list_render: 'datetime', search_op: 'between', sortable: true };
    }
    case 'date': {
      return { form_component: 'DatePicker', list_render: 'date', search_op: 'between', sortable: true };
    }
    case 'json': {
      return { form_component: 'JsonEditor', search_op: 'ilike', in_list: false };
    }
    case 'enum': {
      return { form_component: 'Select', list_render: 'tag', search_op: 'eq' };
    }
    case 'file': {
      return { form_component: 'Upload', search_op: 'ilike', in_list: false };
    }
    default: {
      return {};
    }
  }
}

const _FT = 'admin.dev.crudGenerator.field.fieldType';

/** 字段类型选项（函数形式，保证 $t 响应性） */
export function getFieldTypeOptions(): { label: string; value: FieldType }[] {
  return [
    { label: $t(`${_FT}.string`), value: 'string' },
    { label: $t(`${_FT}.text`), value: 'text' },
    { label: $t(`${_FT}.integer`), value: 'integer' },
    { label: $t(`${_FT}.float`), value: 'float' },
    { label: $t(`${_FT}.decimal`), value: 'decimal' },
    { label: $t(`${_FT}.boolean`), value: 'boolean' },
    { label: $t(`${_FT}.datetime`), value: 'datetime' },
    { label: $t(`${_FT}.date`), value: 'date' },
    { label: $t(`${_FT}.json`), value: 'json' },
    { label: $t(`${_FT}.enum`), value: 'enum' },
    { label: $t(`${_FT}.file`), value: 'file' },
  ];
}

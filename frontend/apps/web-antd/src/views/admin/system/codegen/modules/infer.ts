/**
 * 字段名后缀自动推断引擎 / Field name suffix auto-inference engine
 *
 * 参考 BuildAdmin / RuoYi Plus 的命名约定
 * References BuildAdmin / RuoYi Plus naming conventions.
 */

export interface InferredConfig {
  type: string;
  component: string;
  multiple?: boolean;
  queryType?: string;
  listVisible?: boolean;
  filterable?: boolean;
  insertable?: boolean;
  editable?: boolean;
  sortable?: boolean;
  precision?: number;
}

/** 系统字段权限映射（DB 导入时自动应用）/ System field permission mapping */
export const SYSTEM_FIELDS: Record<string, Partial<InferredConfig>> = {
  id: {
    insertable: false,
    editable: false,
    listVisible: true,
    filterable: false,
  },
  created_at: {
    insertable: false,
    editable: false,
    listVisible: true,
    filterable: true,
    queryType: 'between',
  },
  updated_at: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  created_by: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  updated_by: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  deleted_at: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  is_deleted: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  tenant_id: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  dept_id: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
  version: {
    insertable: false,
    editable: false,
    listVisible: false,
    filterable: false,
  },
};

interface InferRule {
  pattern: RegExp;
  config: Partial<InferredConfig>;
}

const RULES: InferRule[] = [
  // -- 系统字段（DB导入可能残留）/ System fields (may remain from DB import) --
  {
    pattern: /^(created_by|dept_id)$/i,
    config: {
      type: 'Integer',
      component: 'number',
      insertable: false,
      editable: false,
      listVisible: false,
      filterable: false,
    },
  },

  // -- 关联（必须在 image/file 之前，_id 优先级最高） --
  {
    pattern: /_ids$/i,
    config: {
      type: 'ForeignKey',
      component: 'ApiSelect',
      multiple: true,
      queryType: 'in',
      listVisible: false,
      filterable: true,
    },
  },
  {
    pattern: /_id$/i,
    config: {
      type: 'ForeignKey',
      component: 'ApiSelect',
      queryType: 'eq',
      listVisible: true,
      filterable: true,
    },
  },

  // -- 多图（复数后缀）/ Multiple images (plural suffix) --
  {
    pattern:
      /(images|avatars|covers|logos|photos|thumbnails|banners|posters|pictures|galleries)$/i,
    config: {
      type: 'Images',
      component: 'ImageUpload',
      multiple: true,
      listVisible: false,
    },
  },
  // -- 单图 / Single image --
  {
    pattern:
      /(image|avatar|cover|logo|photo|thumbnail|banner|poster|picture)$/i,
    config: {
      type: 'ImageUpload',
      component: 'ImageUpload',
      listVisible: true,
    },
  },

  // -- 多文件（复数后缀）/ Multiple files (plural suffix) --
  {
    pattern: /(files|attachments|documents|docs)$/i,
    config: {
      type: 'Files',
      component: 'FilePicker',
      multiple: true,
      listVisible: false,
    },
  },
  // -- 单文件 / Single file --
  {
    pattern: /(file|attachment|document|doc)$/i,
    config: {
      type: 'File',
      component: 'FilePicker',
      listVisible: false,
    },
  },

  // -- 富文本（不含 description/detail，避免误判）/ RichText (exclude description/detail) --
  {
    pattern: /(content|body|summary|intro|bio|about)$/i,
    config: { type: 'RichText', component: 'RichText', listVisible: false },
  },

  // -- uuid / code / slug / sn（可搜索）/ Searchable identifiers --
  {
    pattern: /^(uuid|code|slug|sn)$/i,
    config: {
      type: 'String',
      component: 'input',
      filterable: true,
      queryType: 'ilike',
      listVisible: true,
    },
  },

  // -- 密码 / Password --
  {
    pattern: /(password|passwd|secret|pin)$/i,
    config: {
      type: 'String',
      component: 'password',
      insertable: true,
      editable: false,
      listVisible: false,
      filterable: false,
    },
  },

  // -- Boolean（开关类字段）/ Boolean switch fields --
  {
    pattern:
      /^is_|^has_|^can_|_(enabled|active|visible|locked|published|verified|approved)$/i,
    config: {
      type: 'Boolean',
      component: 'switch',
      queryType: 'eq',
      listVisible: true,
      filterable: true,
    },
  },
  {
    pattern: /(switch|toggle|enabled|disabled|active)$/i,
    config: {
      type: 'Boolean',
      component: 'switch',
      queryType: 'eq',
      listVisible: true,
      filterable: true,
    },
  },

  // -- Enum / 状态 / Status & enum --
  {
    pattern: /^(status|state|type|level|priority|category|gender|role)$/i,
    config: {
      type: 'Enum',
      component: 'select',
      queryType: 'eq',
      listVisible: true,
      filterable: true,
    },
  },

  // -- 日期时间 / Date & datetime --
  {
    pattern: /(_at|_time|datetime|timestamp)$/i,
    config: {
      type: 'DateTime',
      component: 'date',
      queryType: 'between',
      listVisible: true,
    },
  },
  {
    pattern: /^(date|birthday|birth_date|start_date|end_date|expire_date)$/i,
    config: {
      type: 'Date',
      component: 'date',
      queryType: 'between',
      listVisible: true,
    },
  },

  // -- 图标 / 颜色 / Icon & color --
  {
    pattern: /icon$/i,
    config: { type: 'IconPicker', component: 'IconPicker' },
  },
  {
    pattern: /(color|colour)$/i,
    config: { type: 'String', component: 'ColorPicker', listVisible: true },
  },

  // -- 金额（含 precision:2）/ Amount (with precision:2) --
  {
    pattern: /(amount|price|cost|fee|total|balance|salary|wage|money)$/i,
    config: {
      type: 'Decimal',
      component: 'number',
      listVisible: true,
      precision: 2,
    },
  },

  // -- 整数 / Integer --
  {
    pattern:
      /(count|quantity|num|number|age|weight|height|score|rating|rank|version)$/i,
    config: {
      type: 'Integer',
      component: 'number',
      listVisible: true,
    },
  },

  // -- 排序（含 sortable）/ Sort order (with sortable) --
  {
    pattern:
      /^(sort|sort_order|weigh|weight|position|seq|sequence|display_order|sort_num|order_num)$/i,
    config: {
      type: 'Integer',
      component: 'number',
      listVisible: false,
      sortable: true,
    },
  },

  // -- JSON / Code（配置类字段）/ Config-like fields --
  {
    pattern: /(config|settings|options|metadata|extra|payload)$/i,
    config: {
      type: 'JSON',
      component: 'CodeEditor',
      listVisible: false,
    },
  },

  // -- 长文本（含 description）/ Long text (incl. description, moved from RichText) --
  {
    pattern:
      /(text|memo|remark|comment|feedback|review|message|note|description)$/i,
    config: {
      type: 'Text',
      component: 'textarea',
      listVisible: false,
    },
  },

  // -- URL / Email / Phone（IR-3/4/5）/ 链接、邮箱、电话字段 --
  {
    pattern: /(url|link|href|website|homepage)$/i,
    config: { type: 'String', component: 'input', listVisible: true },
  },
  {
    pattern: /(email|mail)$/i,
    config: {
      type: 'String',
      component: 'input',
      queryType: 'ilike',
      listVisible: true,
      filterable: true,
    },
  },
  {
    pattern: /(phone|mobile|tel|cellphone)$/i,
    config: {
      type: 'String',
      component: 'input',
      listVisible: true,
      filterable: true,
    },
  },

  // -- 下拉单选/多选（_list/_select/_multi/_tags）/ Select single/multi --
  {
    pattern: /(_list|_select|_data)$/i,
    config: {
      type: 'String',
      component: 'select',
      queryType: 'eq',
      listVisible: true,
      filterable: true,
    },
  },
  {
    pattern: /(_lists|_selects|_multi|_tags)$/i,
    config: {
      type: 'JSON',
      component: 'select',
      multiple: true,
      queryType: 'in',
      listVisible: false,
      filterable: true,
    },
  },

  // -- 数组 / Array --
  {
    pattern: /(array|_arr)$/i,
    config: { type: 'JSON', component: 'input', listVisible: false },
  },

  // -- 评分（在 percent 之前，避免 rating 被误判为 percent）--
  {
    pattern: /^rating$/i,
    config: { type: 'Integer', component: 'Rate', listVisible: true },
  },
  // -- 百分比 / Percent --
  {
    pattern: /^(percent|ratio)$/i,
    config: {
      type: 'Decimal',
      component: 'number',
      listVisible: true,
      precision: 2,
    },
  },

  // -- 常见可搜索字段 / Common searchable fields --
  {
    pattern: /^(name|title|label|subject)$/i,
    config: {
      type: 'String',
      component: 'input',
      queryType: 'ilike',
      listVisible: true,
      filterable: true,
    },
  },
];

const DEFAULTS: InferredConfig = {
  type: 'String',
  component: 'input',
  listVisible: true,
  insertable: true,
  editable: true,
};

export function inferFieldConfig(fieldName: string): InferredConfig {
  if (!fieldName) return { ...DEFAULTS };
  const name = String(fieldName).trim();
  const sys = SYSTEM_FIELDS[name];
  if (sys) {
    return { ...DEFAULTS, ...sys };
  }
  for (const rule of RULES) {
    if (rule.pattern.test(name)) {
      return { ...DEFAULTS, ...rule.config };
    }
  }
  return { ...DEFAULTS };
}

/** 常见字段名对应的 display_name/comment 映射（中文优先）/ Field display_name/comment mapping (Chinese first) */
export const FIELD_DISPLAY_NAMES: Record<
  string,
  { comment?: string; display_name: string; display_name_en: string }
> = {
  title: { display_name: '标题', display_name_en: 'Title', comment: '标题' },
  name: { display_name: '名称', display_name_en: 'Name', comment: '名称' },
  content: {
    display_name: '内容',
    display_name_en: 'Content',
    comment: '内容',
  },
  status: { display_name: '状态', display_name_en: 'Status', comment: '状态' },
  sort_order: {
    display_name: '排序',
    display_name_en: 'Sort Order',
    comment: '排序号',
  },
  price: { display_name: '单价', display_name_en: 'Price', comment: '单价' },
  amount: { display_name: '金额', display_name_en: 'Amount', comment: '金额' },
  quantity: {
    display_name: '数量',
    display_name_en: 'Quantity',
    comment: '数量',
  },
  created_at: {
    display_name: '创建时间',
    display_name_en: 'Created At',
    comment: '创建时间',
  },
  updated_at: {
    display_name: '更新时间',
    display_name_en: 'Updated At',
    comment: '更新时间',
  },
  created_by: {
    display_name: '创建人',
    display_name_en: 'Creator',
    comment: '创建人',
  },
  updated_by: {
    display_name: '更新人',
    display_name_en: 'Updater',
    comment: '更新人',
  },
  description: {
    display_name: '描述',
    display_name_en: 'Description',
    comment: '描述',
  },
  remark: { display_name: '备注', display_name_en: 'Remark', comment: '备注' },
};

/** snake_case 转可读文本（英文）/ snake_case to human-readable text (English) */
export function humanizeSnakeCase(name: string): string {
  if (!name) return '';
  return name
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * 从字段名推断 display_name / comment（仅当缺失时填充）/ Infer display_name/comment from field name (only when missing)
 */
export function inferFieldDisplayNames(fieldName: string): {
  comment?: string;
  display_name?: string;
  display_name_en?: string;
} {
  if (!fieldName) return {};
  const name = String(fieldName).trim();
  const known = FIELD_DISPLAY_NAMES[name];
  if (known) return known;
  const humanized = humanizeSnakeCase(name);
  return {
    display_name: humanized,
    display_name_en: humanized,
    comment: humanized,
  };
}

/**
 * 推断结果转为可直接 merge 到字段配置的格式（snake_case）
 * Convert inferred config to field-friendly format (snake_case) for Object.assign.
 */
export function inferFieldConfigForMerge(
  fieldName: string,
): Record<string, unknown> {
  const c = inferFieldConfig(fieldName);
  const form: Record<string, unknown> = {};
  if (c.component) form.component = c.component;
  if (c.queryType) form.queryType = c.queryType;
  if (c.precision !== null && c.precision !== undefined) {
    form.precision = c.precision;
  }
  const displayNames = inferFieldDisplayNames(fieldName);
  const out: Record<string, unknown> = {
    type: c.type,
    multiple: c.multiple,
    list_visible: c.listVisible,
    filterable: c.filterable,
    insertable: c.insertable,
    editable: c.editable,
    sortable: c.sortable,
    ...(Object.keys(form).length > 0 ? { form } : {}),
    ...displayNames,
    _auto_detected: true,
  };
  return out;
}

export function pluralize(word: string): string {
  if (!word) return word;
  if (word.endsWith('y') && !/[aeiou]y$/i.test(word))
    return `${word.slice(0, -1)}ies`;
  if (/(?:s|x|ch|sh)$/i.test(word)) return `${word}es`;
  const irregulars: Record<string, string> = {
    category: 'categories',
    person: 'people',
    child: 'children',
  };
  const lower = word.toLowerCase();
  if (irregulars[lower]) return irregulars[lower];
  return `${word}s`;
}

/** 单数化（与后端 generator _singularize 一致）/ Singularize (aligned with backend) */
export function singularize(word: string): string {
  if (!word) return word;
  const w = word.trim();
  const irregularsRev: Record<string, string> = {
    categories: 'category',
    people: 'person',
    children: 'child',
    addresses: 'address',
  };
  const lower = w.toLowerCase();
  if (irregularsRev[lower]) return irregularsRev[lower];
  if (w.endsWith('ies') && !/[aeiou]ies$/i.test(w)) return `${w.slice(0, -3)}y`;
  if (/(?:s|ch|sh|x)es$/i.test(w)) return w.slice(0, -2);
  if (w.endsWith('s') && !/(?:us|as|is|os|ss)$/i.test(w)) return w.slice(0, -1);
  return w;
}

/** 解析数据库列注释为枚举值（借鉴 BuildAdmin），与 EnumValuesEditor 格式统一用 label_zh */
export interface ParsedEnumItem {
  value: number | string;
  label_zh: string;
}

/**
 * 解析 `状态:0=禁用,1=启用` 或 `类型(0=普通,1=VIP)` 格式 / Parse `status:0=disabled,1=enabled` format
 * @returns 解析成功返回枚举项数组，否则返回 null / Returns ParsedEnumItem[] or null
 */
export function parseCommentEnum(
  comment: null | string | undefined,
): null | ParsedEnumItem[] {
  if (!comment || typeof comment !== 'string') return null;
  const s = comment.trim();
  if (!s) return null;
  const colonIdx = s.indexOf(':');
  const parenStart = s.indexOf('(');
  let body = s;
  if (colonIdx !== -1) body = s.slice(colonIdx + 1).trim();
  else if (parenStart !== -1) {
    const parenEnd = s.indexOf(')', parenStart);
    if (parenEnd !== -1) body = s.slice(parenStart + 1, parenEnd).trim();
  }
  const items: ParsedEnumItem[] = [];
  for (const part of body.split(/[,，]/)) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const m = trimmed.match(/^(\d+)=(.+)$/);
    if (m) {
      const numText = m[1];
      const label = m[2];
      if (!numText || !label) continue;
      const num = Number.parseInt(numText, 10);
      items.push({ value: num, label_zh: label.trim() });
    } else {
      const m2 = trimmed.match(/^(["'])(.+)\1=(.+)$/);
      if (m2) {
        const value = m2[2];
        const label = m2[3];
        if (!value || !label) continue;
        items.push({ value, label_zh: label.trim() });
      } else {
        const m3 = trimmed.match(/^([^=]+)=(.+)$/);
        if (m3) {
          const value = m3[1];
          const label = m3[2];
          if (!value || !label) continue;
          items.push({ value: value.trim(), label_zh: label.trim() });
        }
      }
    }
  }
  return items.length > 0 ? items : null;
}

/**
 * 从字段名推断关联表名（复数）
 * Infer relation table name (plural) from field name.
 * e.g. category_id -> categories, tag_ids -> tags
 */
export function inferRelationTable(fieldName: string): string | undefined {
  const m = fieldName.match(/^(.+?)_ids?$/);
  if (!m) return undefined;
  const stem = m[1];
  return stem ? pluralize(stem) : undefined;
}

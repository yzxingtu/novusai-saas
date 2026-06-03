/**
 * 字段操作与预览工具函数 / Field utils for editor and WYSIWYG preview
 *
 * 供 FieldCardList、WysiwygCenter 共用
 */
import { preferences } from '@vben/preferences';

import { inferFieldConfigForMerge, inferRelationTable } from './infer';

type FieldRecord = Record<string, unknown>;

/** 根据当前语言获取字段显示名 / Get field display label for current locale */
export function getFieldLabel(f: FieldRecord): string {
  const locale = String(preferences.app.locale ?? '').toLowerCase();
  if (
    locale.startsWith('en') &&
    f.display_name_en !== null &&
    f.display_name_en !== undefined &&
    String(f.display_name_en).trim() !== ''
  ) {
    return String(f.display_name_en).trim();
  }
  return String(f.display_name || f.name || '').trim();
}

/** 永不在列表显示的组件类型 / Component types never shown in list */
const NEVER_LIST_VISIBLE = new Set([
  'CodeEditor',
  'CronPicker',
  'password',
  'RangePicker',
  'RichText',
]);
const NEVER_LIST_TYPES = new Set(['Files', 'Images', 'JSON', 'RichText']);

export interface PaletteItem {
  type: string;
  component: string;
  icon: string;
  label: string;
  defaultName: string;
  multiple?: boolean;
}

export function genKey(): string {
  return `f_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/** 确保每项都有非空 __key / Ensure each has non-empty __key */
export function ensureFieldKeys(fields: FieldRecord[]): FieldRecord[] {
  return fields.map((f) => {
    const k = f.__key;
    if (!k || (typeof k === 'string' && !k.trim()))
      return { ...f, __key: genKey() };
    return f;
  });
}

/** 确保字段名唯一，必要时自动后缀 / Ensure unique field name, auto suffix if needed */
export function ensureUniqueName(
  name: string,
  fields: FieldRecord[],
  excludeKey?: string,
): string {
  const existingNames = new Set(
    fields
      .filter((f) => (f.__key as string) !== excludeKey)
      .map((f) => (f.name as string) || '')
      .filter(Boolean),
  );
  if (!name || !existingNames.has(name)) return name;
  let suffix = 1;
  let candidate = `${name}_${suffix}`;
  while (existingNames.has(candidate)) {
    suffix += 1;
    candidate = `${name}_${suffix}`;
  }
  return candidate;
}

/** 从 Palette 创建字段配置 / Create field config from palette item */
export function createFieldFromPalette(
  item: PaletteItem,
  fields: FieldRecord[],
): FieldRecord {
  const base: FieldRecord = {
    __key: genKey(),
    name: item.defaultName,
    type: item.type,
  };
  if (item.type === '__divider__') {
    return { ...base, divider: true, divider_title: '' };
  }
  const inferred = inferFieldConfigForMerge(item.defaultName);
  if (item.multiple) inferred.multiple = true;
  if (item.type === 'ForeignKey' && item.multiple) {
    inferred.relation_table = inferRelationTable(item.defaultName);
  }
  const preserveTypes = ['TreeSelect', 'Cascader', 'UserSelect', 'DeptSelect'];
  const merged: FieldRecord = preserveTypes.includes(item.type)
    ? { ...inferred, ...base, type: item.type }
    : { ...base, ...inferred };
  merged.form_component = item.component;
  const form = (merged.form as Record<string, unknown>) || {};
  merged.form = { ...form, component: item.component };
  merged.name = ensureUniqueName(merged.name as string, fields);
  // 新建字段默认在列表中显示（除密码、富文本、JSON、多图/多文件等永不在列表显示的类型）
  const comp = String(item.component || '');
  const fieldType = String(merged.type || '');
  const isMulti = !!(merged.multiple || item.multiple);
  const shouldForce =
    !NEVER_LIST_VISIBLE.has(comp) &&
    !NEVER_LIST_TYPES.has(fieldType) &&
    !(isMulti && ['ApiSelect', 'FilePicker', 'ImageUpload'].includes(comp));
  if (
    merged.list_visible === false &&
    merged.insertable !== false &&
    shouldForce
  ) {
    merged.list_visible = true;
  }
  return merged;
}

/** 文本型基础组件（可被 enum_render 覆盖为 select/radio/checkbox） */
const TEXT_LIKE_COMPONENTS = new Set([
  'input',
  'Input',
  'password',
  'Password',
  'textarea',
  'TextArea',
]);

/** 获取表单组件名 / Get form component name */
export function getComponent(f: FieldRecord): string {
  const form = (f.form as Record<string, unknown>) || {};
  const comp =
    (typeof form.component === 'string' ? form.component : '') ||
    (typeof f.form_component === 'string' ? f.form_component : '');
  const ev = (f.enum_values as Array<unknown>) || [];
  const enumRender =
    (form.enumRender as string) || (f.enum_render as string) || 'select';

  let base: string;
  if (comp) {
    base = comp;
  } else {
    const t = String(f.type || '').trim();
    const normalized = t.toLowerCase();

    if (t === 'RichText') base = 'RichText';
    else if (['Image', 'Images', 'ImageUpload'].includes(t))
      base = 'ImageUpload';
    else if (['File', 'Files'].includes(t)) base = 'FilePicker';
    else if (t === 'JSON') base = 'CodeEditor';
    else if (t === 'TreeSelect') base = 'ApiTreeSelect';
    else if (['DeptSelect', 'UserSelect'].includes(t))
      base = t === 'UserSelect' ? 'ApiSelect' : 'ApiTreeSelect';
    else
      switch (t) {
        case 'Cascader': {
          base = 'Cascader';
          break;
        }
        case 'CronPicker': {
          base = 'CronPicker';
          break;
        }
        case 'Enum': {
          base = 'select';
          break;
        }
        case 'ForeignKey': {
          base = 'ApiSelect';
          break;
        }
        default: {
          if (
            t === 'Boolean' ||
            normalized === 'bool' ||
            normalized.includes('boolean')
          )
            base = 'switch';
          else if (t === 'Text') base = 'textarea';
          else if (
            ['Decimal', 'Float', 'Integer', 'Number'].includes(t) ||
            normalized.includes('int') ||
            normalized.includes('float') ||
            normalized.includes('decimal')
          ) {
            base = 'number';
          } else if (
            t === 'Date' ||
            t === 'DateTime' ||
            normalized.includes('date') ||
            normalized.includes('timestamp')
          ) {
            base = 'date';
          } else {
            base = 'input';
          }
        }
      }
  }

  // 当基础组件为 Input 等文本型，且配置了枚举 + 枚举渲染方式时，优先按枚举渲染（下拉框/单选/多选）
  if (
    TEXT_LIKE_COMPONENTS.has(base) &&
    ev.length > 0 &&
    ['checkbox', 'radio', 'select'].includes(enumRender)
  ) {
    return enumRender;
  }
  return base;
}

/** 判断字段是否应隐藏在列表中 / Whether field should be hidden in list */
export function shouldHideInList(f: FieldRecord): boolean {
  const comp = getComponent(f);
  if (NEVER_LIST_VISIBLE.has(comp)) return true;
  const t = String(f.type || '');
  if (NEVER_LIST_TYPES.has(t)) return true;
  if (f.multiple && ['ApiSelect', 'FilePicker', 'ImageUpload'].includes(comp))
    return true;
  return false;
}

/** 获取表格单元格渲染类型 / Get cell render type for table preview */
export function getTableCellRenderType(f: FieldRecord): string {
  const comp = getComponent(f);
  if (comp === 'password') return 'Password';
  if (['Rate', 'Slider', 'Switch'].includes(comp)) return comp;
  const t = String(f.type || '').toLowerCase();
  if (t.includes('boolean')) return 'Switch';
  if (t.includes('image')) return 'Image';
  if (t.includes('file')) return 'File';
  if (t.includes('richtext')) return 'RichText';
  return 'text';
}

export function isMultiple(f: FieldRecord): boolean {
  return !!(
    f.multiple || ['Files', 'Images'].includes(String(f.type || '').trim())
  );
}

export function isDatetimeType(f: FieldRecord): boolean {
  const t = String(f.type || '').toLowerCase();
  return t.includes('datetime') || t.includes('timestamp');
}

/** 获取表格列对齐方式 (D31) / Get column align class for table */
export function getColumnAlign(f: FieldRecord): string {
  const comp = getComponent(f);
  const t = String(f.type || '').toLowerCase();
  if (['Rate', 'Slider', 'Switch', 'switch'].includes(comp))
    return 'text-center';
  if (t.includes('boolean')) return 'text-center';
  if (t.includes('int') || t.includes('float') || t.includes('decimal'))
    return 'text-center';
  if (t.includes('date')) return 'text-center';
  return 'text-left';
}

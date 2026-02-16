/**
 * 字段批量导入解析器
 *
 * 支持四种导入来源：
 * 1. DDL (CREATE TABLE) → FieldConfig[]
 * 2. JSON (字段数组) → FieldConfig[]
 * 3. CSV (表格输入) → FieldConfig[]
 * 4. Migration (Alembic op.create_table) → FieldConfig[]
 *
 * 每个解析器返回统一结构 ParseResult。
 */

import type { FieldConfig, FieldType } from '../types';

import { getDefaultsByType } from './field-inference';

// ============================================================
// 解析结果
// ============================================================

export interface ParsedField {
  name: string;
  type: FieldType;
  label_zh: string;
  label_en: string;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  max_length: number | null;
  default_value: unknown;
  index: boolean;
  primary_key: boolean;
}

export interface ParseError {
  line: number;
  field: string;
  reason: string;
}

export interface ParseResult {
  fields: ParsedField[];
  errors: ParseError[];
  source: 'ddl' | 'json' | 'csv' | 'migration';
}

// ============================================================
// SQL 类型 → FieldType 映射
// ============================================================

const SQL_TYPE_MAP: Record<string, FieldType> = {
  // 字符串
  varchar: 'string',
  char: 'string',
  character: 'string',
  nvarchar: 'string',
  nchar: 'string',
  // 文本
  text: 'text',
  longtext: 'text',
  mediumtext: 'text',
  tinytext: 'text',
  clob: 'text',
  // 整数
  int: 'integer',
  integer: 'integer',
  bigint: 'integer',
  smallint: 'integer',
  tinyint: 'integer',
  serial: 'integer',
  bigserial: 'integer',
  // 浮点
  float: 'float',
  double: 'float',
  real: 'float',
  // 精确数值
  decimal: 'decimal',
  numeric: 'decimal',
  money: 'decimal',
  // 布尔
  boolean: 'boolean',
  bool: 'boolean',
  bit: 'boolean',
  // 日期时间
  timestamp: 'datetime',
  datetime: 'datetime',
  timestamptz: 'datetime',
  date: 'date',
  // JSON
  json: 'json',
  jsonb: 'json',
  // 枚举
  enum: 'enum',
};

function mapSqlType(raw: string): FieldType {
  const base = raw
    .toLowerCase()
    .replace(/\(.*\)/, '')
    .replace(/\s+(varying|precision|without\s+time\s+zone|with\s+time\s+zone)/gi, '')
    .trim();

  return SQL_TYPE_MAP[base] ?? 'string';
}

function extractMaxLength(typeStr: string): number | null {
  const m = /\((\d+)\)/.exec(typeStr);
  return m && m[1] ? Number.parseInt(m[1], 10) : null;
}

function snakeToLabel(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================
// 系统列过滤
// ============================================================

const SYSTEM_COLUMNS = new Set([
  'id',
  'created_at',
  'updated_at',
  'deleted_at',
  'is_deleted',
  'delete_level',
  'tenant_id',
  'created_by',
  'updated_by',
  'sort_order',
]);

function isSystemColumn(name: string): boolean {
  return SYSTEM_COLUMNS.has(name.toLowerCase());
}

/** Valid FieldType values for direct type matching (avoids O(n) Object.values each call) */
const VALID_FIELD_TYPES: ReadonlySet<string> = new Set(Object.values(SQL_TYPE_MAP));

function isValidFieldType(t: string): t is FieldType {
  return VALID_FIELD_TYPES.has(t);
}

/** Parse boolean-like string values */
function toBool(val: string | undefined): boolean {
  return val !== undefined && ['true', '1', 'yes', 'y'].includes(val.toLowerCase());
}

// ============================================================
// 1. DDL 解析器
// ============================================================

const DDL_COLUMN_RE =
  /^\s*"?(\w+)"?\s+([\w\s()]+?)(?:\s+(NOT\s+NULL|NULL))?(?:\s+DEFAULT\s+('(?:[^'\\]|\\.)*'|[^\s,]+))?(?:\s+(PRIMARY\s+KEY|UNIQUE))?(?:\s*,?\s*)$/i;

export function parseDDL(input: string): ParseResult {
  const fields: ParsedField[] = [];
  const errors: ParseError[] = [];
  const lines = input.split('\n');

  let inCreateTable = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    if (rawLine === undefined) continue;
    const line = rawLine.trim();
    const lineNum = i + 1;

    // Detect CREATE TABLE start
    if (/CREATE\s+TABLE/i.test(line)) {
      inCreateTable = true;
      continue;
    }

    // Skip closing paren or empty lines
    if (!inCreateTable || !line || line.startsWith(')') || line.startsWith('--')) {
      if (line.startsWith(')')) inCreateTable = false;
      continue;
    }

    // Skip constraint lines
    if (/^\s*(PRIMARY\s+KEY|UNIQUE|CHECK|CONSTRAINT|FOREIGN\s+KEY|INDEX)/i.test(line)) {
      continue;
    }

    const match = DDL_COLUMN_RE.exec(line);
    if (!match) {
      // Try simpler pattern: name type
      const simpleMatch = /^\s*"?(\w+)"?\s+([\w()]+)/i.exec(line);
      if (simpleMatch) {
        const name = simpleMatch[1] ?? '';
        const typeStr = simpleMatch[2] ?? 'string';
        if (isSystemColumn(name)) continue;

        fields.push({
          name,
          type: mapSqlType(typeStr),
          label_zh: name,
          label_en: snakeToLabel(name),
          required: false,
          nullable: true,
          unique: false,
          max_length: extractMaxLength(typeStr),
          default_value: null,
          index: false,
          primary_key: false,
        });
      } else {
        errors.push({ line: lineNum, field: '', reason: 'cannotParseColumn' });
      }
      continue;
    }

    const colName = match[1] ?? '';
    const typeStr = match[2] ?? 'string';
    const nullability = match[3] ?? '';
    const defaultVal = match[4] ?? '';
    const constraint = match[5] ?? '';
    if (isSystemColumn(colName)) continue;

    const notNull = nullability ? /NOT\s+NULL/i.test(nullability) : false;
    const isPK = constraint ? /PRIMARY\s+KEY/i.test(constraint) : false;
    const isUnique = constraint ? /UNIQUE/i.test(constraint) : false;

    fields.push({
      name: colName,
      type: mapSqlType(typeStr),
      label_zh: colName,
      label_en: snakeToLabel(colName),
      required: notNull,
      nullable: !notNull,
      unique: isUnique || isPK,
      max_length: extractMaxLength(typeStr),
      default_value: defaultVal
        ? (defaultVal.toUpperCase() === 'NULL'
          ? null
          : defaultVal.replace(/'/g, '').trim() || null)
        : null,
      index: isPK,
      primary_key: isPK,
    });
  }

  return { fields, errors, source: 'ddl' };
}

// ============================================================
// 2. JSON 解析器
// ============================================================

interface RawJsonField {
  name?: string;
  type?: string;
  label_zh?: string;
  label_en?: string;
  required?: boolean;
  nullable?: boolean;
  unique?: boolean;
  max_length?: number | null;
  default?: unknown;
  index?: boolean;
}

export function parseJSON(input: string): ParseResult {
  const fields: ParsedField[] = [];
  const errors: ParseError[] = [];

  let parsed: unknown;
  try {
    parsed = JSON.parse(input);
  } catch {
    errors.push({ line: 1, field: '', reason: 'invalidJson' });
    return { fields, errors, source: 'json' };
  }

  const arr = Array.isArray(parsed) ? parsed : [parsed];

  for (let i = 0; i < arr.length; i++) {
    const item = arr[i] as RawJsonField;
    if (!item || typeof item !== 'object') {
      errors.push({ line: i + 1, field: '', reason: 'itemNotObject' });
      continue;
    }

    if (!item.name || typeof item.name !== 'string') {
      errors.push({ line: i + 1, field: '', reason: 'missingName' });
      continue;
    }

    if (isSystemColumn(item.name)) continue;

    const typeStr = typeof item.type === 'string' ? item.type.toLowerCase() : 'string';
    const mappedType: FieldType = isValidFieldType(typeStr)
      ? typeStr
      : mapSqlType(typeStr);

    fields.push({
      name: item.name,
      type: mappedType,
      label_zh: item.label_zh ?? item.name,
      label_en: item.label_en ?? snakeToLabel(item.name),
      required: item.required ?? false,
      nullable: item.nullable ?? true,
      unique: item.unique ?? false,
      max_length: item.max_length ?? null,
      default_value: item.default ?? null,
      index: item.index ?? false,
      primary_key: false,
    });
  }

  return { fields, errors, source: 'json' };
}

// ============================================================
// 3. CSV 解析器
// ============================================================

export function parseCSV(input: string): ParseResult {
  const fields: ParsedField[] = [];
  const errors: ParseError[] = [];
  const lines = input.trim().split('\n');

  if (lines.length === 0) {
    return { fields, errors, source: 'csv' };
  }

  // Parse header
  const headerLine = lines[0] ?? '';
  const headers = headerLine.split(',').map((h) => h.trim().toLowerCase());
  const nameIdx = headers.indexOf('name');

  if (nameIdx === -1) {
    errors.push({ line: 1, field: '', reason: 'csvMissingNameColumn' });
    return { fields, errors, source: 'csv' };
  }

  const typeIdx = headers.indexOf('type');
  const labelZhIdx = headers.indexOf('label_zh');
  const labelEnIdx = headers.indexOf('label_en');
  const requiredIdx = headers.indexOf('required');
  const nullableIdx = headers.indexOf('nullable');
  const uniqueIdx = headers.indexOf('unique');
  const maxLenIdx = headers.indexOf('max_length');
  const indexIdx = headers.indexOf('index');

  for (let i = 1; i < lines.length; i++) {
    const rawCsvLine = lines[i];
    if (!rawCsvLine) continue;
    const line = rawCsvLine.trim();
    if (!line) continue;

    const cols = line.split(',').map((c) => c.trim());
    const name = cols[nameIdx] ?? '';
    if (!name) {
      errors.push({ line: i + 1, field: '', reason: 'emptyName' });
      continue;
    }

    if (isSystemColumn(name)) continue;

    const typeStr = typeIdx >= 0 ? (cols[typeIdx] ?? 'string') : 'string';
    const mappedType: FieldType = isValidFieldType(typeStr)
      ? typeStr
      : mapSqlType(typeStr);

    fields.push({
      name,
      type: mappedType,
      label_zh: labelZhIdx >= 0 ? (cols[labelZhIdx] ?? name) : name,
      label_en: labelEnIdx >= 0 ? (cols[labelEnIdx] ?? snakeToLabel(name)) : snakeToLabel(name),
      required: requiredIdx >= 0 ? toBool(cols[requiredIdx]) : false,
      nullable: nullableIdx >= 0 ? toBool(cols[nullableIdx]) : true,
      unique: uniqueIdx >= 0 ? toBool(cols[uniqueIdx]) : false,
      max_length: maxLenIdx >= 0 && cols[maxLenIdx] ? Number.parseInt(cols[maxLenIdx], 10) || null : null,
      default_value: null,
      index: indexIdx >= 0 ? toBool(cols[indexIdx]) : false,
      primary_key: false,
    });
  }

  return { fields, errors, source: 'csv' };
}

// ============================================================
// 4. Migration 解析器 (Alembic op.create_table)
// ============================================================

/**
 * Regex to match sa.Column('name', sa.Type(...), ...) lines
 * Captures: column name, SA type call, rest of args
 */
const SA_COLUMN_RE =
  /sa\.Column\(\s*'(\w+)'\s*,\s*sa\.(\w+)\(([^)]*)\)\s*(?:,\s*(.+?))?\s*\)/;

/** Map SQLAlchemy type names to FieldType */
const SA_TYPE_MAP: Record<string, FieldType> = {
  String: 'string',
  Text: 'text',
  Integer: 'integer',
  BigInteger: 'integer',
  SmallInteger: 'integer',
  Float: 'float',
  Numeric: 'decimal',
  Boolean: 'boolean',
  DateTime: 'datetime',
  Date: 'date',
  JSON: 'json',
};

function parseSaMaxLength(typeArgs: string): number | null {
  const m = /length\s*=\s*(\d+)/.exec(typeArgs);
  return m && m[1] ? Number.parseInt(m[1], 10) : null;
}

function parseSaComment(rest: string): string {
  const m = /comment\s*=\s*'([^']*)'/.exec(rest);
  return m && m[1] ? m[1] : '';
}

export function parseMigration(input: string): ParseResult {
  const fields: ParsedField[] = [];
  const errors: ParseError[] = [];
  const lines = input.split('\n');

  let inCreateTable = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    if (rawLine === undefined) continue;
    const line = rawLine.trim();
    const lineNum = i + 1;

    // Detect op.create_table( start
    if (/op\.create_table\s*\(/.test(line)) {
      inCreateTable = true;
      continue;
    }

    // Detect closing paren of create_table
    if (inCreateTable && /^\)/.test(line)) {
      inCreateTable = false;
      continue;
    }

    if (!inCreateTable) continue;

    // Skip constraint lines
    if (/sa\.(PrimaryKeyConstraint|ForeignKeyConstraint|UniqueConstraint)/.test(line)) {
      continue;
    }

    const match = SA_COLUMN_RE.exec(line);
    if (!match) {
      // Skip comment-only or empty lines
      if (line.startsWith('#') || line.startsWith('//') || !line) continue;
      // Non-matching sa.Column line
      if (/sa\.Column/.test(line)) {
        errors.push({ line: lineNum, field: '', reason: 'cannotParseColumn' });
      }
      continue;
    }

    const colName = match[1] ?? '';
    const saType = match[2] ?? 'String';
    const typeArgs = match[3] ?? '';
    const rest = match[4] ?? '';

    if (isSystemColumn(colName)) continue;

    const fieldType = SA_TYPE_MAP[saType] ?? 'string';
    const notNull = /nullable\s*=\s*False/i.test(rest);
    const isUnique = /unique\s*=\s*True/i.test(rest);
    const comment = parseSaComment(rest);
    const maxLen = fieldType === 'string' ? parseSaMaxLength(typeArgs) : null;

    // Extract server_default
    let defaultVal: string | null = null;
    const defMatch = /server_default\s*=\s*'([^']*)'/.exec(rest);
    if (defMatch && defMatch[1]) {
      defaultVal = defMatch[1];
    }

    fields.push({
      name: colName,
      type: fieldType,
      label_zh: comment || colName,
      label_en: comment || snakeToLabel(colName),
      required: notNull,
      nullable: !notNull,
      unique: isUnique,
      max_length: maxLen,
      default_value: defaultVal,
      index: false,
      primary_key: false,
    });
  }

  return { fields, errors, source: 'migration' };
}

// ============================================================
// 转换为 FieldConfig
// ============================================================

export function parsedFieldToConfig(pf: ParsedField): FieldConfig {
  const typeDefaults = getDefaultsByType(pf.type);

  return {
    name: pf.name,
    type: pf.type,
    label_zh: pf.label_zh,
    label_en: pf.label_en,
    required: pf.required,
    nullable: pf.nullable,
    unique: pf.unique,
    max_length: pf.max_length,
    default: pf.default_value,
    index: pf.index,
    enum_ref: null,
    enum_values: null,
    relation_ref: null,
    filterable: true,
    sortable: typeDefaults.sortable ?? false,
    searchable: false,
    search_op: typeDefaults.search_op ?? 'ilike',
    search_component: typeDefaults.search_component ?? 'Input',
    in_list: typeDefaults.in_list ?? true,
    list_width: null,
    list_align: 'left',
    list_render: typeDefaults.list_render ?? null,
    list_slot: null,
    list_fixed: null,
    list_sortable: false,
    in_form: true,
    form_component: typeDefaults.form_component ?? 'Input',
    form_group: null,
    form_placeholder: null,
    form_rules: null,
    form_depends_on: null,
    form_col_span: null,
    form_help: null,
    upload: null,
  };
}

// ============================================================
// 合并策略
// ============================================================

export type MergeMode = 'add_only' | 'overwrite_same' | 'replace_all';

export function mergeFields(
  existing: FieldConfig[],
  incoming: FieldConfig[],
  mode: MergeMode,
): { merged: FieldConfig[]; added: string[]; overwritten: string[]; skipped: string[] } {
  const added: string[] = [];
  const overwritten: string[] = [];
  const skipped: string[] = [];

  if (mode === 'replace_all') {
    return {
      merged: [...incoming],
      added: incoming.map((f) => f.name),
      overwritten: [],
      skipped: [],
    };
  }

  const existingIndexMap = new Map(existing.map((f, idx) => [f.name, idx]));
  const result = [...existing];

  for (const field of incoming) {
    const existIdx = existingIndexMap.get(field.name);

    if (existIdx === undefined) {
      result.push(field);
      added.push(field.name);
    } else if (mode === 'overwrite_same') {
      result[existIdx] = field;
      overwritten.push(field.name);
    } else {
      skipped.push(field.name);
    }
  }

  return { merged: result, added, overwritten, skipped };
}

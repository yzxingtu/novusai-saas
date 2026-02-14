/**
 * CRUD Generator — CrudConfig 合并工具
 *
 * 按文档《CrudConfig 合并策略》(#296) 实现：
 * - touchedPaths：用户修改过的路径不会被 AI 输出覆盖
 * - 幂等合并：同一 AI 输出重复应用不会产生重复条目
 * - 合并摘要：返回 added/updated/skipped 供 UI 展示
 */

import { ref } from 'vue';

import type {
  CrudConfig,
  CustomSlotConfig,
  EnumDefinition,
  EnumOption,
  FieldConfig,
  RelationConfig,
  SearchFieldConfig,
} from '../types';

// ============================================================
// Merge Summary
// ============================================================

export interface MergeSummaryItem {
  type: 'added' | 'skipped' | 'updated';
  category: 'enum' | 'field' | 'meta' | 'relation' | 'search' | 'slot';
  name: string;
  details?: string;
}

export interface MergeSummary {
  items: MergeSummaryItem[];
  added: number;
  updated: number;
  skipped: number;
}

function createSummary(): MergeSummary {
  return { items: [], added: 0, updated: 0, skipped: 0 };
}

function addItem(
  summary: MergeSummary,
  type: MergeSummaryItem['type'],
  category: MergeSummaryItem['category'],
  name: string,
  details?: string,
) {
  summary.items.push({ type, category, name, details });
  summary[type]++;
}

// ============================================================
// TouchedPaths — tracks user-edited paths
// ============================================================

/**
 * Reactive Set of dot-delimited paths that the user has explicitly edited.
 * Paths in this set are never overwritten by AI merge.
 *
 * Examples:
 * - `"module"` — top-level field
 * - `"fields.title.label_zh"` — field attribute
 * - `"enums.OrderStatus.values.draft.label_zh"` — enum option attribute
 * - `"relations.category.target_model"` — relation attribute
 */
export function useTouchedPaths() {
  const touched = ref<Set<string>>(new Set());

  /** Mark a path as user-edited */
  function touch(path: string) {
    touched.value.add(path);
  }

  /** Mark multiple paths */
  function touchMany(paths: string[]) {
    for (const p of paths) {
      touched.value.add(p);
    }
  }

  /** Check if a path is user-edited */
  function isTouched(path: string): boolean {
    return touched.value.has(path);
  }

  /** Check if any path with the given prefix is touched */
  function hasAnyTouched(prefix: string): boolean {
    for (const p of touched.value) {
      if (p.startsWith(prefix)) return true;
    }
    return false;
  }

  /** Clear all touched paths (e.g. on reset) */
  function clearAll() {
    touched.value.clear();
  }

  return {
    touched,
    touch,
    touchMany,
    isTouched,
    hasAnyTouched,
    clearAll,
  };
}

export type TouchedPaths = ReturnType<typeof useTouchedPaths>;

// ============================================================
// Merge Logic
// ============================================================

/**
 * Merge an AI-produced partial CrudConfig patch into the current config.
 *
 * Rules:
 * - Top-level scalar: fill only if current is empty/default, skip if touched
 * - fields/enums/relations/search/slots: merge by unique key, deduplicate
 * - touched paths never overwritten
 * - Idempotent: applying same patch twice produces same result
 */
export function mergeConfig(
  current: CrudConfig,
  patch: Partial<CrudConfig>,
  touchedPaths: TouchedPaths,
): { config: CrudConfig; summary: MergeSummary } {
  const summary = createSummary();
  const result = structuredClone(current);

  // 1. Top-level meta fields (empty-fill only)
  mergeMetaField(result, patch, touchedPaths, summary, 'module');
  mergeMetaField(result, patch, touchedPaths, summary, 'table_name');
  mergeMetaField(result, patch, touchedPaths, summary, 'display_name');
  mergeMetaField(result, patch, touchedPaths, summary, 'display_name_en');
  mergeMetaField(result, patch, touchedPaths, summary, 'parent_menu');
  mergeMetaField(result, patch, touchedPaths, summary, 'description');

  // 2. Fields
  if (patch.fields && Array.isArray(patch.fields)) {
    mergeFields(result, patch.fields, touchedPaths, summary);
  }

  // 3. Enums
  if (patch.enums && Array.isArray(patch.enums)) {
    mergeEnums(result, patch.enums, touchedPaths, summary);
  }

  // 4. Relations
  if (patch.relations && Array.isArray(patch.relations)) {
    mergeRelations(result, patch.relations, touchedPaths, summary);
  }

  // 5. Search config
  if (patch.search_config?.fields) {
    mergeSearchFields(result, patch.search_config.fields, touchedPaths, summary);
  }

  // 6. Custom slots
  if (patch.custom_slots && Array.isArray(patch.custom_slots)) {
    mergeSlots(result, patch.custom_slots, touchedPaths, summary);
  }

  return { config: result, summary };
}

// ============================================================
// Top-level meta merge (empty-fill)
// ============================================================

type MetaKey = 'description' | 'display_name' | 'display_name_en' | 'module' | 'parent_menu' | 'table_name';

function mergeMetaField(
  result: CrudConfig,
  patch: Partial<CrudConfig>,
  tp: TouchedPaths,
  summary: MergeSummary,
  key: MetaKey,
) {
  const patchValue = patch[key];
  if (patchValue === undefined || patchValue === null || patchValue === '') return;

  if (tp.isTouched(key)) {
    addItem(summary, 'skipped', 'meta', key, 'user edited');
    return;
  }

  const currentValue = result[key];
  if (!currentValue || currentValue === '') {
    (result as unknown as Record<string, unknown>)[key] = patchValue;
    addItem(summary, 'added', 'meta', key);
  } else {
    addItem(summary, 'skipped', 'meta', key, 'already set');
  }
}

// ============================================================
// Fields merge (by name)
// ============================================================

function mergeFields(
  result: CrudConfig,
  patchFields: FieldConfig[],
  tp: TouchedPaths,
  summary: MergeSummary,
) {
  const existingMap = new Map(result.fields.map((f) => [f.name, f]));

  for (const pf of patchFields) {
    if (!pf.name) continue;

    const existing = existingMap.get(pf.name);
    if (!existing) {
      // New field — append
      result.fields.push(pf);
      addItem(summary, 'added', 'field', pf.name);
    } else {
      // Existing field — fill missing attributes only
      const prefix = `fields.${pf.name}`;
      let updated = false;

      for (const [attr, val] of Object.entries(pf)) {
        if (attr === 'name') continue;
        const path = `${prefix}.${attr}`;

        if (tp.isTouched(path)) continue;

        const currentVal = (existing as unknown as Record<string, unknown>)[attr];
        if (isEmptyValue(currentVal) && !isEmptyValue(val)) {
          (existing as unknown as Record<string, unknown>)[attr] = val;
          updated = true;
        }
      }

      addItem(
        summary,
        updated ? 'updated' : 'skipped',
        'field',
        pf.name,
        updated ? 'filled missing attrs' : 'no changes needed',
      );
    }
  }
}

// ============================================================
// Enums merge (by name, values by value)
// ============================================================

function mergeEnums(
  result: CrudConfig,
  patchEnums: EnumDefinition[],
  tp: TouchedPaths,
  summary: MergeSummary,
) {
  const existingMap = new Map(result.enums.map((e) => [e.name, e]));

  for (const pe of patchEnums) {
    if (!pe.name) continue;

    const existing = existingMap.get(pe.name);
    if (!existing) {
      // New enum — append
      result.enums.push(pe);
      addItem(summary, 'added', 'enum', pe.name);
    } else {
      // Existing enum — merge values by `value` key
      const prefix = `enums.${pe.name}`;
      let updated = false;

      // Fill description if missing
      if (!existing.description && pe.description && !tp.isTouched(`${prefix}.description`)) {
        existing.description = pe.description;
        updated = true;
      }

      // Merge values
      if (pe.values && Array.isArray(pe.values)) {
        const existingValues = new Map(existing.values.map((v) => [v.value, v]));

        for (const pv of pe.values) {
          const ev = existingValues.get(pv.value);
          if (!ev) {
            // New value — append
            existing.values.push(pv);
            updated = true;
          } else {
            // Existing value — fill missing labels
            const vPrefix = `${prefix}.values.${pv.value}`;
            updated = fillEnumOptionAttrs(ev, pv, tp, vPrefix) || updated;
          }
        }
      }

      addItem(
        summary,
        updated ? 'updated' : 'skipped',
        'enum',
        pe.name,
        updated ? 'merged values' : 'no changes',
      );
    }
  }
}

function fillEnumOptionAttrs(
  existing: EnumOption,
  patch: EnumOption,
  tp: TouchedPaths,
  prefix: string,
): boolean {
  let changed = false;
  const attrs: (keyof EnumOption)[] = ['label_zh', 'label_en', 'color', 'icon'];

  for (const attr of attrs) {
    const path = `${prefix}.${attr}`;
    if (tp.isTouched(path)) continue;

    const cur = existing[attr];
    const val = patch[attr];
    if (isEmptyValue(cur) && !isEmptyValue(val)) {
      (existing as unknown as Record<string, unknown>)[attr] = val;
      changed = true;
    }
  }
  return changed;
}

// ============================================================
// Relations merge (by name)
// ============================================================

function mergeRelations(
  result: CrudConfig,
  patchRelations: RelationConfig[],
  tp: TouchedPaths,
  summary: MergeSummary,
) {
  const existingMap = new Map(result.relations.map((r) => [r.name, r]));

  for (const pr of patchRelations) {
    if (!pr.name) continue;

    // v1: only merge complete relations (must have name + type + target_model)
    if (!pr.type || !pr.target_model) {
      addItem(summary, 'skipped', 'relation', pr.name, 'incomplete relation');
      continue;
    }

    const existing = existingMap.get(pr.name);
    if (!existing) {
      result.relations.push(pr);
      addItem(summary, 'added', 'relation', pr.name);
    } else {
      const prefix = `relations.${pr.name}`;
      let updated = false;

      for (const [attr, val] of Object.entries(pr)) {
        if (attr === 'name') continue;
        const path = `${prefix}.${attr}`;

        if (tp.isTouched(path)) continue;

        const currentVal = (existing as unknown as Record<string, unknown>)[attr];
        if (isEmptyValue(currentVal) && !isEmptyValue(val)) {
          (existing as unknown as Record<string, unknown>)[attr] = val;
          updated = true;
        }
      }

      addItem(
        summary,
        updated ? 'updated' : 'skipped',
        'relation',
        pr.name,
        updated ? 'filled missing attrs' : 'no changes',
      );
    }
  }
}

// ============================================================
// Search fields merge (by field name)
// ============================================================

function mergeSearchFields(
  result: CrudConfig,
  patchFields: SearchFieldConfig[],
  tp: TouchedPaths,
  summary: MergeSummary,
) {
  if (!result.search_config) {
    // Adopt entire search config from AI
    result.search_config = { fields: patchFields, collapsed: false, max_visible: 3 };
    for (const sf of patchFields) {
      addItem(summary, 'added', 'search', sf.field);
    }
    return;
  }

  const existingMap = new Map(result.search_config.fields.map((f) => [f.field, f]));

  for (const pf of patchFields) {
    if (!pf.field) continue;

    if (existingMap.has(pf.field)) {
      const prefix = `search_config.${pf.field}`;
      if (tp.hasAnyTouched(prefix)) {
        addItem(summary, 'skipped', 'search', pf.field, 'user edited');
      } else {
        addItem(summary, 'skipped', 'search', pf.field, 'already exists');
      }
    } else {
      result.search_config.fields.push(pf);
      addItem(summary, 'added', 'search', pf.field);
    }
  }
}

// ============================================================
// Custom slots merge (by field + slot_type)
// ============================================================

function mergeSlots(
  result: CrudConfig,
  patchSlots: CustomSlotConfig[],
  tp: TouchedPaths,
  summary: MergeSummary,
) {
  const slotKey = (s: CustomSlotConfig) => `${s.field}:${s.slot_type}`;
  const existingMap = new Map(result.custom_slots.map((s) => [slotKey(s), s]));

  for (const ps of patchSlots) {
    const key = slotKey(ps);
    const existing = existingMap.get(key);

    if (!existing) {
      result.custom_slots.push(ps);
      addItem(summary, 'added', 'slot', key);
    } else {
      const path = `custom_slots.${key}`;
      if (tp.isTouched(path)) {
        addItem(summary, 'skipped', 'slot', key, 'user edited');
      } else {
        addItem(summary, 'skipped', 'slot', key, 'already exists');
      }
    }
  }
}

// ============================================================
// Helpers
// ============================================================

function isEmptyValue(val: unknown): boolean {
  if (val === undefined || val === null) return true;
  if (typeof val === 'string' && val === '') return true;
  return false;
}

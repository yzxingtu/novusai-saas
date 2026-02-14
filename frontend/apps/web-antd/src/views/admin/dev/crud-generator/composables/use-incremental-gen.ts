/**
 * Incremental Generation — 增量生成 + 反向解析
 *
 * 职责:
 * 1. 对比新旧 CrudConfig，计算差异 (diff)
 * 2. 仅生成变更部分的代码
 * 3. 反向解析: 从已有代码还原 CrudConfig (前端侧辅助)
 * 4. 差异合并模式标记
 */

import { computed, ref } from 'vue';

import type { CrudConfig, FieldConfig } from '../types';

export interface ConfigDiff {
  addedFields: string[];
  removedFields: string[];
  modifiedFields: string[];
  addedEnums: string[];
  removedEnums: string[];
  listConfigChanged: boolean;
  formConfigChanged: boolean;
  searchConfigChanged: boolean;
  relationsChanged: boolean;
  metaChanged: boolean;
}

/**
 * 计算两个 CrudConfig 之间的差异
 */
export function diffConfigs(
  oldConfig: CrudConfig,
  newConfig: CrudConfig,
): ConfigDiff {
  const oldFieldNames = new Set(oldConfig.fields.map((f) => f.name));
  const newFieldNames = new Set(newConfig.fields.map((f) => f.name));

  const addedFields = [...newFieldNames].filter((n) => !oldFieldNames.has(n));
  const removedFields = [...oldFieldNames].filter((n) => !newFieldNames.has(n));

  const modifiedFields: string[] = [];
  for (const name of newFieldNames) {
    if (!oldFieldNames.has(name)) continue;
    const oldField = oldConfig.fields.find((f) => f.name === name);
    const newField = newConfig.fields.find((f) => f.name === name);
    if (oldField && newField && JSON.stringify(oldField) !== JSON.stringify(newField)) {
      modifiedFields.push(name);
    }
  }

  const oldEnumNames = new Set(oldConfig.enums.map((e) => e.name));
  const newEnumNames = new Set(newConfig.enums.map((e) => e.name));
  const addedEnums = [...newEnumNames].filter((n) => !oldEnumNames.has(n));
  const removedEnums = [...oldEnumNames].filter((n) => !newEnumNames.has(n));

  const listConfigChanged =
    JSON.stringify(oldConfig.list_config) !== JSON.stringify(newConfig.list_config);
  const formConfigChanged =
    JSON.stringify(oldConfig.form_config) !== JSON.stringify(newConfig.form_config);
  const searchConfigChanged =
    JSON.stringify(oldConfig.search_config) !== JSON.stringify(newConfig.search_config);
  const relationsChanged =
    JSON.stringify(oldConfig.relations) !== JSON.stringify(newConfig.relations);

  const metaChanged =
    oldConfig.module !== newConfig.module ||
    oldConfig.table_name !== newConfig.table_name ||
    oldConfig.display_name !== newConfig.display_name ||
    oldConfig.scope !== newConfig.scope ||
    oldConfig.soft_delete !== newConfig.soft_delete ||
    oldConfig.drag_sort !== newConfig.drag_sort;

  return {
    addedFields,
    removedFields,
    modifiedFields,
    addedEnums,
    removedEnums,
    listConfigChanged,
    formConfigChanged,
    searchConfigChanged,
    relationsChanged,
    metaChanged,
  };
}

/**
 * 判断 diff 是否有变更
 */
export function hasDiffChanges(diff: ConfigDiff): boolean {
  return (
    diff.addedFields.length > 0 ||
    diff.removedFields.length > 0 ||
    diff.modifiedFields.length > 0 ||
    diff.addedEnums.length > 0 ||
    diff.removedEnums.length > 0 ||
    diff.listConfigChanged ||
    diff.formConfigChanged ||
    diff.searchConfigChanged ||
    diff.relationsChanged ||
    diff.metaChanged
  );
}

/**
 * 生成 diff 变更摘要 (用于显示给用户)
 */
export function diffSummary(diff: ConfigDiff): string[] {
  const lines: string[] = [];

  if (diff.metaChanged) lines.push('Meta fields changed');
  if (diff.addedFields.length > 0) lines.push(`Added fields: ${diff.addedFields.join(', ')}`);
  if (diff.removedFields.length > 0) lines.push(`Removed fields: ${diff.removedFields.join(', ')}`);
  if (diff.modifiedFields.length > 0) lines.push(`Modified fields: ${diff.modifiedFields.join(', ')}`);
  if (diff.addedEnums.length > 0) lines.push(`Added enums: ${diff.addedEnums.join(', ')}`);
  if (diff.removedEnums.length > 0) lines.push(`Removed enums: ${diff.removedEnums.join(', ')}`);
  if (diff.listConfigChanged) lines.push('List config changed');
  if (diff.formConfigChanged) lines.push('Form config changed');
  if (diff.searchConfigChanged) lines.push('Search config changed');
  if (diff.relationsChanged) lines.push('Relations changed');

  return lines;
}

/**
 * useIncrementalGen — 增量生成 composable
 */
export function useIncrementalGen() {
  const baseConfig = ref<CrudConfig | null>(null);
  const isIncremental = computed(() => baseConfig.value !== null);

  /**
   * 设置基准配置 (从已有模块加载)
   */
  function setBaseConfig(config: CrudConfig) {
    baseConfig.value = structuredClone(config);
  }

  /**
   * 清除基准配置 (切换为全量生成模式)
   */
  function clearBaseConfig() {
    baseConfig.value = null;
  }

  /**
   * 计算当前配置与基准的差异
   */
  function getDiff(currentConfig: CrudConfig): ConfigDiff | null {
    if (!baseConfig.value) return null;
    return diffConfigs(baseConfig.value, currentConfig);
  }

  /**
   * 获取差异摘要
   */
  function getDiffSummary(currentConfig: CrudConfig): string[] {
    const diff = getDiff(currentConfig);
    if (!diff) return [];
    return diffSummary(diff);
  }

  /**
   * 从字段列表中提取字段名和类型映射
   * (辅助反向解析 — 从已有代码还原时使用)
   */
  function extractFieldMap(fields: FieldConfig[]): Record<string, string> {
    const map: Record<string, string> = {};
    for (const field of fields) {
      map[field.name] = field.type;
    }
    return map;
  }

  return {
    baseConfig,
    isIncremental,
    setBaseConfig,
    clearBaseConfig,
    getDiff,
    getDiffSummary,
    extractFieldMap,
  };
}

// ============================================================
// v1 Boundary Definitions
// ============================================================

/**
 * Generator block markers — only code between these markers is managed
 * by the generator. User edits outside markers are preserved.
 */
export const GEN_BLOCK_START = '// --- CRUD-GEN:START ---';
export const GEN_BLOCK_END = '// --- CRUD-GEN:END ---';

/**
 * v1 反向解析范围 (Reverse Parse Scope)
 *
 * 仅解析以下文件中的标记区块:
 * - Model: 字段定义 (__filterable__, __sortable__, columns)
 * - Controller: 路由、权限装饰器
 * - data.ts: column definitions, search form schema, edit form schema
 * - i18n JSON: key-value pairs
 *
 * 非标记区块不做解析，用户手改内容不受影响。
 */
export const V1_PARSEABLE_FILES = [
  'models/{module}.py',
  'controllers/{module}.py',
  'services/{module}_service.py',
  'repositories/{module}_repository.py',
  'views/{scope}/{module}/data.ts',
  'views/{scope}/{module}/index.vue',
  'locales/langs/zh-CN/{scope}/{module}.json',
  'locales/langs/en-US/{scope}/{module}.json',
] as const;

/**
 * v1 增量更新策略
 *
 * - MARKER_ONLY: 仅更新标记区块内容 (默认, 安全)
 * - FULL_REPLACE: 完整替换文件 (需二次确认)
 * - MERGE: 智能合并 (v2 规划)
 */
export type UpdateStrategy = 'full_replace' | 'marker_only' | 'merge';

export interface IncrementalUpdatePlan {
  file: string;
  strategy: UpdateStrategy;
  hasUserEdits: boolean;
  diffLines: number;
  previewAvailable: boolean;
}

/**
 * 检测文件内容是否包含生成器标记区块
 */
export function hasGeneratorMarkers(content: string): boolean {
  return content.includes(GEN_BLOCK_START) && content.includes(GEN_BLOCK_END);
}

/**
 * 提取生成器标记区块之间的内容
 */
export function extractMarkerBlock(content: string): string | null {
  const startIdx = content.indexOf(GEN_BLOCK_START);
  const endIdx = content.indexOf(GEN_BLOCK_END);
  if (startIdx < 0 || endIdx < 0 || endIdx <= startIdx) return null;
  return content.slice(startIdx + GEN_BLOCK_START.length, endIdx).trim();
}

/**
 * 替换生成器标记区块之间的内容，保留区块外的用户代码
 */
export function replaceMarkerBlock(
  content: string,
  newBlock: string,
): string {
  const startIdx = content.indexOf(GEN_BLOCK_START);
  const endIdx = content.indexOf(GEN_BLOCK_END);
  if (startIdx < 0 || endIdx < 0 || endIdx <= startIdx) {
    return content;
  }

  const before = content.slice(0, startIdx + GEN_BLOCK_START.length);
  const after = content.slice(endIdx);

  return `${before}\n${newBlock}\n${after}`;
}

/**
 * 生成增量更新计划
 */
export function buildUpdatePlan(
  diff: ConfigDiff,
  module: string,
  scope: string,
): IncrementalUpdatePlan[] {
  const plans: IncrementalUpdatePlan[] = [];

  const hasFieldChanges =
    diff.addedFields.length > 0 ||
    diff.removedFields.length > 0 ||
    diff.modifiedFields.length > 0;

  if (hasFieldChanges || diff.metaChanged) {
    plans.push({
      file: `models/${module}.py`,
      strategy: 'marker_only',
      hasUserEdits: false,
      diffLines: diff.addedFields.length + diff.removedFields.length + diff.modifiedFields.length,
      previewAvailable: true,
    });
  }

  if (diff.listConfigChanged || hasFieldChanges) {
    plans.push({
      file: `views/${scope}/${module}/data.ts`,
      strategy: 'marker_only',
      hasUserEdits: false,
      diffLines: 0,
      previewAvailable: true,
    });
  }

  if (diff.addedEnums.length > 0 || diff.removedEnums.length > 0) {
    plans.push({
      file: `locales/langs/zh-CN/${scope}/${module}.json`,
      strategy: 'marker_only',
      hasUserEdits: false,
      diffLines: diff.addedEnums.length,
      previewAvailable: true,
    });
    plans.push({
      file: `locales/langs/en-US/${scope}/${module}.json`,
      strategy: 'marker_only',
      hasUserEdits: false,
      diffLines: diff.addedEnums.length,
      previewAvailable: true,
    });
  }

  return plans;
}

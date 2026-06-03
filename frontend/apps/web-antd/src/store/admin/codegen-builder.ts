/**
 * Codegen 可视化构建器状态 Store / Codegen builder state store
 *
 * 管理配置 JSON、预览缓存、Undo/Redo 历史、抽屉状态、Tab 验证状态等
 * Manages config JSON, preview cache, undo/redo history, drawer state, tab validation, etc.
 */

import type { PreviewFile } from '#/api/admin/codegen';

import { computed, ref } from 'vue';

import { defineStore } from 'pinia';

import { genKey } from '#/views/admin/system/codegen/modules/field-utils';
import {
  FIELD_DISPLAY_NAMES,
  humanizeSnakeCase,
} from '#/views/admin/system/codegen/modules/infer';

const MAX_HISTORY = 50;

type PreviewCacheSnapshot = {
  conflicts?: Array<Record<string, string>>;
  error?: string;
  files: PreviewFile[];
  step?: string;
  summary?: {
    backend_files: number;
    create_count: number;
    frontend_files: number;
    modify_count: number;
    total_lines: number;
  };
  timestamp?: number;
  warnings?: string[];
};

/** configJson 持久化最大体积（约 400KB），超过则不持久化 configJson 防占满 localStorage / Max size for configJson persist (~400KB) */
const CONFIG_JSON_PERSIST_MAX_BYTES = 400 * 1024;

function getByteLength(str: string): number {
  return new TextEncoder().encode(str).length;
}

function createCodegenStorage() {
  return {
    getItem: (key: string) => localStorage.getItem(key),
    setItem: (key: string, value: string) => {
      try {
        const parsed = JSON.parse(value) as Record<string, unknown>;
        const configStr = JSON.stringify(parsed.configJson ?? {});
        if (getByteLength(configStr) > CONFIG_JSON_PERSIST_MAX_BYTES) {
          if (typeof console !== 'undefined' && console.warn) {
            console.warn(
              '[codegen] configJson exceeds persist limit, skipping persist to avoid quota',
            );
          }
          parsed.configJson = {};
        }
        localStorage.setItem(key, JSON.stringify(parsed));
      } catch {
        localStorage.setItem(key, value);
      }
    },
    removeItem: (key: string) => localStorage.removeItem(key),
  };
}

function ensureFieldsDisplayNames(
  fields: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  return fields.map((f) => {
    const name = (f.name as string) || '';
    if (!name || f.type === '__divider__' || f.divider) return f;
    const known = FIELD_DISPLAY_NAMES[name];
    const fallbackZh = known?.display_name ?? humanizeSnakeCase(name);
    const fallbackEn = known?.display_name_en ?? humanizeSnakeCase(name);
    const fallbackComment = known?.comment ?? fallbackZh;
    const patch: Record<string, unknown> = {};
    if (!f.display_name) patch.display_name = fallbackZh;
    if (!f.display_name_en) patch.display_name_en = fallbackEn;
    if (!f.comment) patch.comment = fallbackComment;
    if (Object.keys(patch).length === 0) return f;
    return { ...f, ...patch };
  });
}

/** 按 name 去重，同名字段保留第一个原名，后续加 _2、_3 后缀 / Dedupe by name, suffix _2/_3 for duplicates */
function dedupeFieldsByName(
  fields: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const seen = new Map<string, number>();
  return fields.map((f) => {
    if (f.type === '__divider__' || f.divider) return f;
    const name = ((f.name as string) || '').trim();
    if (!name) return f;
    const key = name.toLowerCase();
    const count = seen.get(key) ?? 0;
    seen.set(key, count + 1);
    if (count === 0) return f;
    return { ...f, name: `${name}_${count + 1}` };
  });
}

/** 确保 fields 中每项有 __key、display_name、comment，缺失时自动补全；并去重 / Ensure __key, display_name, comment; dedupe */
function ensureFieldsHaveKey(
  json: Record<string, unknown>,
): Record<string, unknown> {
  const rawFields = json.fields;
  if (!Array.isArray(rawFields)) return json;
  let fields: Array<Record<string, unknown>> = rawFields as Array<
    Record<string, unknown>
  >;
  if (fields.length === 0) return json;
  fields = dedupeFieldsByName(fields);
  fields = ensureFieldsDisplayNames(fields);
  const normalized = fields.map((f) => {
    if (f.__key && typeof f.__key === 'string') return f;
    return { ...f, __key: genKey() };
  });
  return { ...json, fields: normalized };
}

export const useCodegenBuilderStore = defineStore(
  'codegen-builder',
  () => {
    // ── State / 状态 ──

    /** 配置 ID（编辑模式）/ Config ID (edit mode) */
    const configId = ref<null | number>(null);

    /** 配置 JSON / Config JSON */
    const configJson = ref<Record<string, unknown>>({});

    /** 撤销历史栈（最多 50 步）/ Undo history stack (max 50) */
    const historyStack = ref<Record<string, unknown>[]>([]);

    /** 重做栈 / Redo stack */
    const redoStack = ref<Record<string, unknown>[]>([]);

    /** 预览缓存 / Preview cache */
    const previewCache = ref<null | PreviewCacheSnapshot>(null);

    /** 校验警告 / Validation warnings */
    const validationWarnings = ref<string[]>([]);

    /** 是否已修改未保存 / Is dirty (unsaved changes) */
    const isDirty = ref(false);

    /** 当前选中字段的 __key / Currently selected field's __key */
    const selectedFieldKey = ref<null | string>(null);

    /** 当前激活的 endpoint 索引 / Active endpoint index */
    const activeEndpointIdx = ref(0);

    /** WYSIWYG 主视图模式 / WYSIWYG view mode */
    const wysiwygViewMode = ref<'detail' | 'form' | 'list'>('list');

    /** 是否显示字段管理面板（覆盖 WYSIWYG）/ Show field manager overlay */
    const showFieldManager = ref(false);

    // ── Actions / 操作 ──

    function safeClone<T>(value: T): T {
      try {
        return structuredClone(value);
      } catch {
        return value;
      }
    }

    function pushHistory(snapshot: Record<string, unknown>) {
      historyStack.value.push(safeClone(snapshot));
      if (historyStack.value.length > MAX_HISTORY) {
        historyStack.value.shift();
      }
    }

    /** 撤销 / Undo */
    function undo() {
      if (historyStack.value.length === 0) return false;
      redoStack.value.push(safeClone(configJson.value));
      if (redoStack.value.length > MAX_HISTORY) redoStack.value.shift();
      const prev = historyStack.value.pop();
      if (prev) {
        configJson.value = prev;
        isDirty.value = true;
        return true;
      }
      return false;
    }

    /** 重做 / Redo */
    function redo() {
      if (redoStack.value.length === 0) return false;
      historyStack.value.push(safeClone(configJson.value));
      const next = redoStack.value.pop();
      if (next) {
        configJson.value = next;
        isDirty.value = true;
        return true;
      }
      return false;
    }

    /** 深合并嵌套对象 / Deep merge nested objects */
    function deepMerge(
      target: Record<string, unknown>,
      patch: Record<string, unknown>,
    ): Record<string, unknown> {
      const result = { ...target };
      for (const [key, val] of Object.entries(patch)) {
        if (
          val !== null &&
          val !== undefined &&
          typeof val === 'object' &&
          !Array.isArray(val)
        ) {
          const cur = result[key];
          result[key] = deepMerge(
            (typeof cur === 'object' &&
            cur !== null &&
            cur !== undefined &&
            !Array.isArray(cur)
              ? cur
              : {}) as Record<string, unknown>,
            val as Record<string, unknown>,
          );
        } else {
          result[key] = val;
        }
      }
      return result;
    }

    /** 更新配置 JSON（深合并嵌套对象）/ Update config JSON (deep merge) */
    function updateConfig(patch: Record<string, unknown>) {
      if (!patch || Object.keys(patch).length === 0) return;
      const next = deepMerge({ ...configJson.value }, patch) as Record<
        string,
        unknown
      >;
      if (JSON.stringify(configJson.value) === JSON.stringify(next)) return;
      pushHistory(configJson.value);
      redoStack.value = [];
      previewCache.value = null;
      configJson.value = next;
      isDirty.value = true;
    }

    /** 覆盖配置 JSON / Replace config JSON */
    function setConfigJson(json: Record<string, unknown>) {
      pushHistory(configJson.value);
      redoStack.value = [];
      previewCache.value = null;
      configJson.value = ensureFieldsHaveKey(json ?? {});
      isDirty.value = true;
    }

    /** 清空预览缓存 / Clear preview cache */
    function clearCache() {
      previewCache.value = null;
    }

    /** 设置预览缓存 / Set preview cache */
    function setPreviewCache(cache: null | PreviewCacheSnapshot) {
      previewCache.value = cache;
    }

    /** 重置构建器（新建模式）/ Reset builder (new mode) */
    function resetWizard() {
      configId.value = null;
      configJson.value = {};
      historyStack.value = [];
      redoStack.value = [];
      previewCache.value = null;
      validationWarnings.value = [];
      isDirty.value = false;
      selectedFieldKey.value = null;
      activeEndpointIdx.value = 0;
    }

    /** 加载配置（编辑模式或导入）/ Load config (edit mode or import) */
    function loadConfig(id: null | number, json: Record<string, unknown>) {
      configId.value = id;
      const raw = json ?? {};
      configJson.value = ensureFieldsHaveKey(raw);
      historyStack.value = [];
      redoStack.value = [];
      previewCache.value = null;
      isDirty.value = false;
      selectedFieldKey.value = null;
      activeEndpointIdx.value = 0;
      showFieldManager.value = false;
    }

    /** 保存配置到 Store（从 API 响应）/ Save config to store (from API response) */
    function saveConfig(id: number, json: Record<string, unknown>) {
      configId.value = id;
      configJson.value = ensureFieldsHaveKey(json ?? {});
      isDirty.value = false;
    }

    /** 设置校验警告 / Set validation warnings */
    function setValidationWarnings(warnings: string[] | unknown) {
      validationWarnings.value = Array.isArray(warnings) ? warnings : [];
    }

    // ── Computed / 计算属性 ──

    const canUndo = computed(() => historyStack.value.length > 0);
    const canRedo = computed(() => redoStack.value.length > 0);

    /** 字段数量（不含 divider）/ Field count (excluding divider) */
    const fieldCount = computed(() => {
      const fields =
        (configJson.value.fields as Array<Record<string, unknown>>) || [];
      return fields.filter((f) => f.type !== '__divider__' && !f.divider)
        .length;
    });

    /** 专家模式已配置项计数 / Expert mode item count */
    const expertItemCount = computed(() => {
      const cfg = configJson.value as Record<string, unknown>;
      const model = (cfg.model as Record<string, unknown>) || {};
      const tree = (model.tree as Record<string, unknown>) || {};
      const unique = (model.unique_together as unknown[]) || [];
      const deps = (model.__delete_deps__ as unknown[]) || [];
      const wf = (cfg.workflow as Record<string, unknown>) || {};
      const actions = (cfg.actions as unknown[]) || [];
      const detail = (cfg.detail as Record<string, unknown>) || {};
      const groups = (detail.groups as unknown[]) || [];
      const clone = (cfg.clone as Record<string, unknown>) || {};
      const relations = (cfg.relations as unknown[]) || [];
      const endpoints = (cfg.endpoints as Array<Record<string, unknown>>) || [];
      const ep0 = endpoints[0] || {};
      const fe = (ep0.frontend as Record<string, unknown>) || {};
      const batch = (ep0.batch as Record<string, unknown>) || {};
      const menu =
        ((ep0.permission as Record<string, unknown>)?.menu as Record<
          string,
          unknown
        >) || {};
      let count = 0;
      if (tree.enabled) count++;
      if (unique.length > 0) count++;
      if (deps.length > 0) count++;
      if (wf.status_field) count++;
      if ((wf.transitions as unknown[])?.length) count++;
      if (model.soft_delete) count++;
      if (model.data_permission) count++;
      if ((batch as { import?: boolean }).import) count++;
      if (actions.length > 0) count++;
      if (groups.length > 0) count++;
      if (fe.mode === 'card') count++;
      if (clone.enabled) count++;
      if (fe.default_sort) count++;
      if (relations.length > 0) count++;
      if (fe.recycle_bin) count++;
      if (fe.export) count++;
      if (batch.delete) count++;
      if (fe.drag_sort) count++;
      if (
        (fe.form_columns as number) !== undefined &&
        (fe.form_columns as number) !== 1
      )
        count++;
      if (ep0.route_prefix) count++;
      if (ep0.data_mode) count++;
      if (menu.icon || menu.title) count++;
      return count;
    });

    return {
      configId,
      configJson,
      historyStack,
      redoStack,
      canUndo,
      canRedo,
      fieldCount,
      previewCache,
      validationWarnings,
      isDirty,
      selectedFieldKey,
      activeEndpointIdx,
      wysiwygViewMode,
      showFieldManager,
      expertItemCount,
      updateConfig,
      setConfigJson,
      undo,
      redo,
      clearCache,
      setPreviewCache,
      resetWizard,
      loadConfig,
      saveConfig,
      setValidationWarnings,
    };
  },
  {
    persist: {
      key: 'codegen-builder',
      storage: createCodegenStorage(),
      pick: ['configId', 'configJson', 'activeEndpointIdx', 'wysiwygViewMode'],
    },
  },
);

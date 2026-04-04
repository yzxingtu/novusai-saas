/**
 * Page Operation Registry
 * 页面操作注册表
 *
 * Pages declare available operations (with handler callbacks) via registerPageOperations();
 * the AI layer discovers operations via listPageOperations() and executes them via executePageOperation().
 * 页面通过 registerPageOperations() 声明当前页面可用的操作列表（含 handler 回调），
 * AI 层通过 listPageOperations() 发现操作，通过 executePageOperation() 执行操作。
 *
 * Usage:
 * ```ts
 * import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';
 *
 * const cleanup = registerPageOperations('tenant.order.detail', [
 *   {
 *     name: 'refresh_order',
 *     label: 'Refresh Order',
 *     description: 'Reload the current order details',
 *     readonly: true,
 *     handler: async () => {
 *       await loadOrderDetail();
 *       return { success: true, message: 'Order refreshed' };
 *     },
 *   },
 *   {
 *     name: 'update_status',
 *     label: 'Update Status',
 *     description: 'Change the order status',
 *     readonly: false,
 *     params: { status: { type: 'string', enum: ['pending', 'shipped', 'delivered'] } },
 *     handler: async (params) => {
 *       await updateOrderStatus(params.status);
 *       return { success: true, message: `Status updated to ${params.status}` };
 *     },
 *   },
 * ]);
 *
 * onUnmounted(cleanup);
 * ```
 */

import { ref } from 'vue';

import { formStateTracker } from '#/composables/use-form-state-tracker';
import { $t } from '#/locales';

import { normalizePageKey } from './page-key-utils';
import { getDefaultPageOperations } from './page-operation-defaults';
import type {
  PageOperation,
  PageOperationHandler,
  PageOperationResult,
} from './page-operation-types';

// --- Internal: param schemas, guards, sanitization / 内部：参数 schema、守卫与清洗 ---

interface PageOperationParamSchema {
  default?: unknown;
  defaultValue?: unknown;
  description?: string;
  enum?: unknown[];
  required?: boolean;
  type?: 'array' | 'boolean' | 'number' | 'object' | 'string';
}

interface PageOperationContextSnapshot {
  formOpen: boolean;
  drawerCount: number;
  modalCount: number;
}

type PageOperationContextDiff = Record<string, boolean>;

// --- Post-handler UI context diff (modal / drawer / form) / 执行后 UI 差分（弹窗/抽屉/表单）---

const CONTEXT_DIFF_POLL_INTERVAL_MS = 60;
const CONTEXT_DIFF_WAIT_TIMEOUT_MS = 1500;

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isValidPageOperation(value: unknown): value is PageOperation {
  if (!isPlainRecord(value)) return false;
  return (
    isNonEmptyString(value.name) &&
    isNonEmptyString(value.label) &&
    typeof value.readonly === 'boolean'
  );
}

function sanitizePageOperations(
  operations: readonly unknown[],
  sourceLabel: string,
): PageOperation[] {
  const sanitized: PageOperation[] = [];
  for (const operation of operations) {
    if (isValidPageOperation(operation)) {
      sanitized.push(operation);
      continue;
    }
    console.warn(
      `[PageOperation] Ignored invalid operation from ${sourceLabel}`,
      operation,
    );
  }
  return sanitized;
}

function isPageOperationResult(value: unknown): value is PageOperationResult {
  return (
    isPlainRecord(value) &&
    typeof value.success === 'boolean' &&
    typeof value.message === 'string'
  );
}

function buildMissingParamResult(paramName: string): PageOperationResult {
  return {
    success: false,
    message: $t('shared.pageOperation.msg.paramRequired', {
      param: paramName,
    }),
    error_type: 'invalid_input',
  };
}

function buildInvalidParamTypeResult(
  paramName: string,
  expectedType: string,
): PageOperationResult {
  return {
    success: false,
    message: $t('shared.pageOperation.msg.paramInvalidType', {
      expected: expectedType,
      param: paramName,
    }),
    error_type: 'invalid_input',
  };
}

function buildInvalidParamEnumResult(
  paramName: string,
  allowedValues: unknown[],
): PageOperationResult {
  return {
    success: false,
    message: $t('shared.pageOperation.msg.paramInvalidEnum', {
      allowed: allowedValues.map(String).join(', '),
      param: paramName,
    }),
    error_type: 'invalid_input',
  };
}

// --- Coerce & validate params against JSON-like schema / 按类 JSON schema 强制并校验参数 ---

function parseStructuredParamValue(
  value: string,
  expectedType: 'array' | 'object',
): unknown {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const looksStructured =
    (expectedType === 'array' && trimmed.startsWith('[')) ||
    (expectedType === 'object' && trimmed.startsWith('{'));
  if (!looksStructured) return undefined;

  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

function coerceOperationParamValue(
  paramName: string,
  rawValue: unknown,
  schema: PageOperationParamSchema,
): PageOperationResult | unknown {
  const expectedType = schema.type;
  if (!expectedType) {
    return rawValue;
  }

  switch (expectedType) {
    case 'array': {
      if (Array.isArray(rawValue)) return rawValue;
      if (typeof rawValue === 'string') {
        const parsed = parseStructuredParamValue(rawValue, 'array');
        if (Array.isArray(parsed)) return parsed;
      }
      return buildInvalidParamTypeResult(paramName, expectedType);
    }
    case 'boolean': {
      if (typeof rawValue === 'boolean') return rawValue;
      if (typeof rawValue === 'string') {
        const normalized = rawValue.trim().toLowerCase();
        if (['1', 'true', 'yes'].includes(normalized)) return true;
        if (['0', 'false', 'no'].includes(normalized)) return false;
      }
      if (rawValue === 1) return true;
      if (rawValue === 0) return false;
      return buildInvalidParamTypeResult(paramName, expectedType);
    }
    case 'number': {
      if (typeof rawValue === 'number' && Number.isFinite(rawValue)) {
        return rawValue;
      }
      if (typeof rawValue === 'string' && rawValue.trim()) {
        const parsed = Number(rawValue);
        if (Number.isFinite(parsed)) {
          return parsed;
        }
      }
      return buildInvalidParamTypeResult(paramName, expectedType);
    }
    case 'object': {
      if (isPlainRecord(rawValue)) return rawValue;
      if (typeof rawValue === 'string') {
        const parsed = parseStructuredParamValue(rawValue, 'object');
        if (isPlainRecord(parsed)) return parsed;
      }
      return buildInvalidParamTypeResult(paramName, expectedType);
    }
    case 'string': {
      if (typeof rawValue === 'string') return rawValue;
      if (Array.isArray(rawValue) || isPlainRecord(rawValue)) {
        return buildInvalidParamTypeResult(paramName, expectedType);
      }
      return String(rawValue);
    }
    default: {
      return rawValue;
    }
  }
}

function validateAndNormalizeOperationParams(
  operation: PageOperation,
  rawParams: Record<string, unknown>,
): PageOperationResult | Record<string, unknown> {
  if (!isPlainRecord(operation.params)) {
    return rawParams;
  }

  const normalizedParams: Record<string, unknown> = { ...rawParams };
  for (const [paramName, rawSchema] of Object.entries(operation.params)) {
    if (!isPlainRecord(rawSchema)) continue;

    const schema = rawSchema as PageOperationParamSchema;
    const rawValue = rawParams[paramName];
    const hasValue = !(
      rawValue === undefined ||
      rawValue === null ||
      (typeof rawValue === 'string' && rawValue.trim() === '')
    );

    if (!hasValue) {
      if (schema.defaultValue !== undefined) {
        normalizedParams[paramName] = schema.defaultValue;
        continue;
      }
      if (schema.default !== undefined) {
        normalizedParams[paramName] = schema.default;
        continue;
      }
      if (schema.required) {
        return buildMissingParamResult(paramName);
      }
      continue;
    }

    const coerced = coerceOperationParamValue(paramName, rawValue, schema);
    if (isPageOperationResult(coerced)) {
      return coerced;
    }

    if (
      Array.isArray(schema.enum) &&
      schema.enum.length > 0 &&
      !schema.enum.includes(coerced)
    ) {
      return buildInvalidParamEnumResult(paramName, schema.enum);
    }

    normalizedParams[paramName] = coerced;
  }

  return normalizedParams;
}

// --- Snapshot & diff helpers (after handler runs) / 快照与差分（handler 执行后）---

function getContextSnapshot(pageKey: string): PageOperationContextSnapshot {
  return {
    formOpen: formStateTracker.isOpenWithFallback(pageKey),
    modalCount: document.querySelectorAll(
      '.ant-modal-wrap:not(.ant-modal-wrap-hidden)',
    ).length,
    drawerCount: document.querySelectorAll('.ant-drawer-open').length,
  };
}

function buildContextDiff(
  before: PageOperationContextSnapshot,
  after: PageOperationContextSnapshot,
): PageOperationContextDiff {
  return {
    form_opened: !before.formOpen && after.formOpen,
    form_closed: before.formOpen && !after.formOpen,
    modal_opened: after.modalCount > before.modalCount,
    modal_closed: after.modalCount < before.modalCount,
    drawer_opened: after.drawerCount > before.drawerCount,
    drawer_closed: after.drawerCount < before.drawerCount,
  };
}

function hasContextDiffChange(diff: PageOperationContextDiff): boolean {
  return Object.values(diff).some(Boolean);
}

function mergeContextDiffs(
  ...diffs: Array<Record<string, unknown> | undefined>
): PageOperationContextDiff {
  const merged: PageOperationContextDiff = {};
  for (const diff of diffs) {
    if (!isPlainRecord(diff)) continue;
    for (const [key, value] of Object.entries(diff)) {
      if (typeof value === 'boolean') {
        merged[key] = Boolean(merged[key]) || value;
      }
    }
  }
  return merged;
}

// Poll until modal/drawer/form state changes after handler / 在 handler 后轮询直至弹窗/抽屉/表单状态变化

async function waitForContextSnapshotChange(
  pageKey: string,
  before: PageOperationContextSnapshot,
): Promise<PageOperationContextSnapshot> {
  let elapsed = 0;
  let latest = getContextSnapshot(pageKey);

  while (elapsed < CONTEXT_DIFF_WAIT_TIMEOUT_MS) {
    const diff = buildContextDiff(before, latest);
    if (hasContextDiffChange(diff)) {
      return latest;
    }

    await new Promise<void>((resolve) => {
      setTimeout(resolve, CONTEXT_DIFF_POLL_INTERVAL_MS);
    });
    elapsed += CONTEXT_DIFF_POLL_INTERVAL_MS;
    latest = getContextSnapshot(pageKey);
  }

  return latest;
}

// --- Registry maps, defaults merge, extras / 注册表、默认操作合并、extras ---

/**
 * Registry: normalized page key (dot-notation) → operations[]
 * Keys are automatically normalized via normalizePageKey().
 * 注册表：规范化的页面标识（点号格式） → operations[]
 * key 通过 normalizePageKey() 自动规范化。
 */
const registry = new Map<string, PageOperation[]>();

/**
 * Extra operation groups: merged on top of primary registrations.
 * Used by platform auto-enhancement, plugins, editors, etc.
 * 追加操作组：合并到主注册之上。
 * 供平台自动增强、插件、编辑器等场景使用。
 */
const extrasRegistry = new Map<string, PageOperation[][]>();

/**
 * Reactive version number — incremented on each register/unregister,
 * allowing external computed properties to track changes in real time.
 * 响应式版本号 — 每次注册/注销时自增，
 * 供外部 computed 建立依赖以实现实时感知。
 */
export const pageOperationVersion = ref(0);

/**
 * Register page operation list
 * 注册页面操作列表
 *
 * @param key - Page identifier (any format, auto-normalized to dot-notation) / 页面标识（任意格式，自动规范化为点号格式）
 * @param operations - Available operations for this page / 该页面可用的操作列表
 * @returns Cleanup function / cleanup 函数
 */
export function registerPageOperations(
  key: string,
  operations: PageOperation[],
): () => void {
  const nk = normalizePageKey(key);
  const sanitizedOperations = sanitizePageOperations(
    operations as unknown[],
    `registerPageOperations(${nk})`,
  );
  registry.set(nk, sanitizedOperations);
  pageOperationVersion.value++;
  return () => {
    if (registry.get(nk) === sanitizedOperations) {
      registry.delete(nk);
      pageOperationVersion.value++;
    }
  };
}

function mergeOperationGroups(groups: PageOperation[][] = []): PageOperation[] {
  const merged: PageOperation[] = [];

  // Later groups override earlier groups with the same name.
  // 后面的分组会覆盖前面分组中的同名操作。
  for (const group of groups) {
    for (const op of group) {
      if (!isValidPageOperation(op)) {
        console.warn(
          '[PageOperation] Ignored invalid operation during merge',
          op,
        );
        continue;
      }
      const existingIndex = merged.findIndex((item) => item.name === op.name);
      if (existingIndex !== -1) {
        merged.splice(existingIndex, 1);
      }
      merged.push(op);
    }
  }

  return merged;
}

function getMergedOperations(key: string): PageOperation[] {
  const defaults = getDefaultPageOperations(key);
  const primary = registry.get(key) ?? [];
  const extraGroups = extrasRegistry.get(key) ?? [];
  return mergeOperationGroups([defaults, primary, ...extraGroups]);
}

/**
 * Append page operations to the current list for a key (without replacing).
 * Use when a consumer (e.g. plugin) needs to add ops on top of platform-registered ops.
 * 向指定 key 的当前操作列表追加操作（不替换）。用于插件等在平台已注册操作之上追加。
 *
 * Contract: For a given key, the platform should register (registerPageOperations) first, once;
 * then plugins may append. If the platform calls registerPageOperations again later (e.g. editor
 * recreated), it replaces the entire list and any previously appended ops are lost.
 * 约定：同一 key 下平台应先 register 一次，再由插件 append；若平台再次 register 会整体替换，已追加的 ops 会丢失。
 *
 * @param key - Page identifier / 页面标识
 * @param operations - Operations to append / 要追加的操作列表
 * @returns Cleanup function; removes only the appended ops / cleanup 仅移除本次追加的操作
 */
export function appendPageOperations(
  key: string,
  operations: PageOperation[],
): () => void {
  const nk = normalizePageKey(key);
  const sanitizedOperations = sanitizePageOperations(
    operations as unknown[],
    `appendPageOperations(${nk})`,
  );
  if (sanitizedOperations.length === 0) {
    return () => {};
  }
  const current = extrasRegistry.get(nk) ?? [];
  current.push(sanitizedOperations);
  extrasRegistry.set(nk, current);
  pageOperationVersion.value++;
  return () => {
    const cur = extrasRegistry.get(nk);
    if (cur) {
      const next = cur.filter((group) => group !== sanitizedOperations);
      if (next.length > 0) {
        extrasRegistry.set(nk, next);
      } else {
        extrasRegistry.delete(nk);
      }
      pageOperationVersion.value++;
    }
  };
}

// --- Public API: discover & execute / 对外 API：发现与执行 ---

/**
 * Get operation list for a specific page (read-only discovery)
 * 获取指定页面的操作列表（只读发现）
 *
 * @param key - Page identifier / 页面标识
 * @returns Operation list, empty array if not registered / 操作列表，未注册时返回空数组
 */
export function listPageOperations(key: string): readonly PageOperation[] {
  return getMergedOperations(normalizePageKey(key));
}

/**
 * Execute a page operation
 * 执行页面操作
 *
 * @param key - Page identifier (any format, auto-normalized) / 页面标识（任意格式，自动规范化）
 * @param operationName - Operation name / 操作名称
 * @param params - Operation parameters / 操作参数
 * @returns Execution result / 执行结果
 */
export async function executePageOperation(
  key: string,
  operationName: string,
  params: Record<string, unknown> = {},
): Promise<PageOperationResult> {
  const nk = normalizePageKey(key);
  const operations = getMergedOperations(nk);
  if (operations.length === 0) {
    return {
      success: false,
      message: $t('shared.pageOperation.msg.pageNoOperations', { page: nk }),
    };
  }

  const operation = operations.find((op) => op.name === operationName);
  if (!operation) {
    const available = operations.map((op) => op.name).join(', ') || 'none';
    return {
      success: false,
      message: $t('shared.pageOperation.msg.opNotFound', {
        op: operationName,
        page: nk,
        available,
      }),
    };
  }

  if (!operation.handler) {
    return {
      success: false,
      message: $t('shared.pageOperation.msg.opNoHandler', {
        op: operationName,
      }),
    };
  }

  const normalizedParams = validateAndNormalizeOperationParams(
    operation,
    params,
  );
  if (isPageOperationResult(normalizedParams)) {
    return normalizedParams;
  }

  const beforeSnapshot = getContextSnapshot(nk);

  try {
    const result = await operation.handler(normalizedParams);
    const afterSnapshot = await waitForContextSnapshotChange(
      nk,
      beforeSnapshot,
    );
    const observedContextDiff = buildContextDiff(beforeSnapshot, afterSnapshot);
    const resultData = isPlainRecord(result.data) ? result.data : {};
    const mergedContextDiff = mergeContextDiffs(
      observedContextDiff,
      isPlainRecord(resultData.context_diff)
        ? (resultData.context_diff as Record<string, unknown>)
        : undefined,
    );

    result.data = {
      ...resultData,
      context_diff: mergedContextDiff,
    };

    return result;
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.warn(
      `[PageOperation] Failed to execute "${operationName}" on "${nk}":`,
      error,
    );
    return {
      success: false,
      message: $t('shared.pageOperation.msg.opFailed', {
        op: operationName,
        error: errorMessage,
      }),
    };
  }
}

/**
 * Find a specific operation (for safety confirmation scenarios)
 * 查找指定操作（用于安全确认等场景）
 *
 * @param key - Page identifier / 页面标识
 * @param operationName - Operation name / 操作名称
 * @returns Operation definition, undefined if not found / 操作定义，未找到时返回 undefined
 */
export function findPageOperation(
  key: string,
  operationName: string,
): PageOperation | undefined {
  const operations = getMergedOperations(normalizePageKey(key));
  return operations?.find((op) => op.name === operationName);
}

// --- Debug & test helpers / 调试与测试辅助 ---

/**
 * Get all currently registered page operation keys (for debugging)
 * 获取当前所有已注册的页面操作 key（调试用）
 */
export function getRegisteredOperationKeys(): string[] {
  return [...new Set([...extrasRegistry.keys(), ...registry.keys()])];
}

/**
 * Clear all registrations (for testing/reset)
 * 清空所有注册（测试/重置用）
 */
export function clearPageOperationRegistry(): void {
  registry.clear();
  extrasRegistry.clear();
  pageOperationVersion.value++;
}

export type { PageOperation, PageOperationHandler, PageOperationResult };

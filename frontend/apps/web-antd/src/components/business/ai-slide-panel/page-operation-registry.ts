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

/** Operation execution result / 操作执行结果 */
export interface PageOperationResult {
  /** Whether execution succeeded / 是否执行成功 */
  success: boolean;
  /** Result message (returned to LLM) / 结果消息（返回给 LLM） */
  message: string;
  /** Additional data (optional, structured result for LLM analysis) / 附加数据（可选，结构化结果供 LLM 分析） */
  data?: Record<string, unknown>;
}

/** Operation handler function type / 操作处理函数类型 */
export type PageOperationHandler = (
  params: Record<string, unknown>,
) => PageOperationResult | Promise<PageOperationResult>;

/**
 * Page operation declaration
 * 页面操作声明
 *
 * readonly=true:  Read-only operation (e.g. refresh, export), executed without confirmation
 * readonly=false: Mutation operation (e.g. update, delete), requires user confirmation before execution
 * readonly=true:  只读操作（如刷新、导出），直接执行无需确认
 * readonly=false: 变更操作（如更新、删除），执行前需用户确认
 */
export interface PageOperation {
  /** Operation unique identifier / 操作唯一标识 */
  name: string;
  /** Human-readable label / 人类可读标签 */
  label: string;
  /** Operation description (for LLM intent understanding) / 操作描述（供 LLM 理解意图） */
  description?: string;
  /** Whether it is a read-only operation / 是否为只读操作 */
  readonly: boolean;
  /** Parameter schema (JSON Schema subset, for LLM to build parameters) / 参数 schema（JSON Schema 子集，供 LLM 构建参数） */
  params?: Record<string, unknown>;
  /** Operation handler function (if not provided, operation is discoverable but not executable) / 操作处理函数（未提供时操作不可执行，仅可发现） */
  handler?: PageOperationHandler;
}

/**
 * Registry: pageContextKey → operations[]
 * Key should match the registerPageContext key.
 * 注册表：pageContextKey → operations[]
 * key 建议与 registerPageContext 的 key 保持一致。
 */
const registry = new Map<string, PageOperation[]>();

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
 * @param key - Page identifier (recommended: same as pageContextKey) / 页面标识
 * @param operations - Available operations for this page / 该页面可用的操作列表
 * @returns Cleanup function / cleanup 函数
 */
export function registerPageOperations(
  key: string,
  operations: PageOperation[],
): () => void {
  registry.set(key, operations);
  pageOperationVersion.value++;
  return () => {
    if (registry.get(key) === operations) {
      registry.delete(key);
      pageOperationVersion.value++;
    }
  };
}

/**
 * Get operation list for a specific page (read-only discovery)
 * 获取指定页面的操作列表（只读发现）
 *
 * @param key - Page identifier / 页面标识
 * @returns Operation list, empty array if not registered / 操作列表，未注册时返回空数组
 */
export function listPageOperations(key: string): readonly PageOperation[] {
  return registry.get(key) ?? [];
}

/**
 * Execute a page operation
 * 执行页面操作
 *
 * @param key - Page identifier (pageContextKey) / 页面标识
 * @param operationName - Operation name / 操作名称
 * @param params - Operation parameters / 操作参数
 * @returns Execution result / 执行结果
 */
export async function executePageOperation(
  key: string,
  operationName: string,
  params: Record<string, unknown> = {},
): Promise<PageOperationResult> {
  const operations = registry.get(key);
  if (!operations) {
    return {
      success: false,
      message: `Page "${key}" has no registered operations`,
    };
  }

  const operation = operations.find((op) => op.name === operationName);
  if (!operation) {
    const available = operations.map((op) => op.name).join(', ');
    return {
      success: false,
      message: `Operation "${operationName}" not found on page "${key}". Available: ${available || 'none'}`,
    };
  }

  if (!operation.handler) {
    return {
      success: false,
      message: `Operation "${operationName}" has no handler (discovery only)`,
    };
  }

  try {
    return await operation.handler(params);
  } catch (error: unknown) {
    const errorMessage =
      error instanceof Error ? error.message : String(error);
    console.error(
      `[PageOperation] Failed to execute "${operationName}" on "${key}":`,
      error,
    );
    return {
      success: false,
      message: `Operation "${operationName}" failed: ${errorMessage}`,
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
  const operations = registry.get(key);
  return operations?.find((op) => op.name === operationName);
}

/**
 * Get all currently registered page operation keys (for debugging)
 * 获取当前所有已注册的页面操作 key（调试用）
 */
export function getRegisteredOperationKeys(): string[] {
  return [...registry.keys()];
}

/**
 * Clear all registrations (for testing/reset)
 * 清空所有注册（测试/重置用）
 */
export function clearPageOperationRegistry(): void {
  registry.clear();
  pageOperationVersion.value++;
}

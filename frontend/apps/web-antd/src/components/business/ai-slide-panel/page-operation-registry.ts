/**
 * 页面操作注册表
 *
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

/** 操作执行结果 */
export interface PageOperationResult {
  /** 是否执行成功 */
  success: boolean;
  /** 结果消息（返回给 LLM） */
  message: string;
  /** 附加数据（可选，结构化结果供 LLM 分析） */
  data?: Record<string, unknown>;
}

/** 操作处理函数类型 */
export type PageOperationHandler = (
  params: Record<string, unknown>,
) => PageOperationResult | Promise<PageOperationResult>;

/**
 * 页面操作声明
 *
 * readonly=true:  只读操作（如刷新、导出），直接执行无需确认
 * readonly=false: 变更操作（如更新、删除），执行前需用户确认
 */
export interface PageOperation {
  /** 操作唯一标识 */
  name: string;
  /** 人类可读标签 */
  label: string;
  /** 操作描述（供 LLM 理解意图） */
  description?: string;
  /** 是否为只读操作 */
  readonly: boolean;
  /** 参数 schema（JSON Schema 子集，供 LLM 构建参数） */
  params?: Record<string, unknown>;
  /** 操作处理函数（未提供时操作不可执行，仅可发现） */
  handler?: PageOperationHandler;
}

/**
 * 注册表：pageContextKey → operations[]
 *
 * key 建议与 registerPageContext 的 key 保持一致。
 */
const registry = new Map<string, PageOperation[]>();

/**
 * 注册页面操作列表
 *
 * @param key 页面标识（建议与 pageContextKey 一致）
 * @param operations 该页面可用的操作列表
 * @returns cleanup 函数
 */
export function registerPageOperations(
  key: string,
  operations: PageOperation[],
): () => void {
  registry.set(key, operations);
  return () => {
    if (registry.get(key) === operations) {
      registry.delete(key);
    }
  };
}

/**
 * 获取指定页面的操作列表（只读发现）
 *
 * @param key 页面标识
 * @returns 操作列表，未注册时返回空数组
 */
export function listPageOperations(key: string): readonly PageOperation[] {
  return registry.get(key) ?? [];
}

/**
 * 执行页面操作
 *
 * @param key 页面标识（pageContextKey）
 * @param operationName 操作名称
 * @param params 操作参数
 * @returns 执行结果
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
 * 查找指定操作（用于安全确认等场景）
 *
 * @param key 页面标识
 * @param operationName 操作名称
 * @returns 操作定义，未找到时返回 undefined
 */
export function findPageOperation(
  key: string,
  operationName: string,
): PageOperation | undefined {
  const operations = registry.get(key);
  return operations?.find((op) => op.name === operationName);
}

/**
 * 获取当前所有已注册的页面操作 key（调试用）
 */
export function getRegisteredOperationKeys(): string[] {
  return [...registry.keys()];
}

/**
 * 清空所有注册（测试/重置用）
 */
export function clearPageOperationRegistry(): void {
  registry.clear();
}

/**
 * 页面上下文注册表
 *
 * 各页面通过 registerPageContext() 注册上下文解析函数，
 * AI 交互层通过 resolvePageContext() 获取当前页面上下文。
 *
 * Usage:
 * ```ts
 * // 在页面 setup 中注册
 * import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
 *
 * const cleanup = registerPageContext('tenant/orders/detail', () => ({
 *   page_key: 'tenant.order.detail',
 *   page_title: `Order #${orderId.value}`,
 *   page_data: { order_id: orderId.value, status: order.value?.status },
 * }));
 *
 * onUnmounted(cleanup);
 * ```
 */

import type { PageContext } from '#/api/shared/ai-chat';

/** 页面上下文结构（对应后端 PageContext schema） */
export type PageContextData = PageContext;

/** 上下文解析函数 */
export type PageContextResolver = () => PageContextData | null;

/**
 * 注册表：route path → resolver
 *
 * 使用 Map 保证注册顺序，后注册覆盖先注册。
 * key 建议使用路由 path 或自定义唯一标识。
 */
const registry = new Map<string, PageContextResolver>();

/**
 * 注册页面上下文解析函数
 *
 * @param key 唯一标识（建议使用路由 path，如 'tenant/orders/detail'）
 * @param resolver 上下文解析函数
 * @returns cleanup 函数，用于取消注册（建议在 onUnmounted 中调用）
 */
export function registerPageContext(
  key: string,
  resolver: PageContextResolver,
): () => void {
  registry.set(key, resolver);
  return () => {
    // 仅删除自己注册的（避免新注册被意外清除）
    if (registry.get(key) === resolver) {
      registry.delete(key);
    }
  };
}

/**
 * 获取当前页面上下文
 *
 * 优先使用指定 key 的 resolver，未指定时遍历所有 resolver，
 * 返回最后注册的非空结果。
 *
 * @param key 可选，指定要使用的 resolver key
 * @returns 页面上下文数据或 null
 */
export function resolvePageContext(
  key?: string,
): PageContextData | null {
  if (key) {
    const resolver = registry.get(key);
    if (resolver) {
      try {
        return resolver();
      } catch (error) {
        console.error(
          `[PageContextRegistry] Resolver '${key}' error:`,
          error,
        );
        return null;
      }
    }
    return null;
  }

  // 遍历所有 resolver，返回最后一个非空结果
  let result: PageContextData | null = null;
  for (const [registeredKey, resolver] of registry) {
    try {
      const ctx = resolver();
      if (ctx) {
        result = ctx;
      }
    } catch (error) {
      console.error(
        `[PageContextRegistry] Resolver '${registeredKey}' error:`,
        error,
      );
    }
  }
  return result;
}

/**
 * 获取当前活跃的注册 key 列表（调试用）
 */
export function getRegisteredKeys(): string[] {
  return [...registry.keys()];
}

/**
 * 清空所有注册（测试/重置用）
 */
export function clearPageContextRegistry(): void {
  registry.clear();
}

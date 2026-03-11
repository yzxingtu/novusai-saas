/**
 * Page Context Registry
 * 页面上下文注册表
 *
 * Pages register context resolvers via registerPageContext();
 * the AI interaction layer retrieves current page context via resolvePageContext().
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

import { ref } from 'vue';

import type { PageContext } from '#/api/shared/ai-chat';

/** Page context structure (maps to backend PageContext schema) / 页面上下文结构（对应后端 PageContext schema） */
export type PageContextData = PageContext;

/** Context resolver function / 上下文解析函数 */
export type PageContextResolver = () => PageContextData | null;

/**
 * Registry: route path → resolver
 * Uses Map to guarantee registration order; later registrations override earlier ones.
 * Key should be route path or a custom unique identifier.
 * 注册表：route path → resolver
 * 使用 Map 保证注册顺序，后注册覆盖先注册。
 * key 建议使用路由 path 或自定义唯一标识。
 */
const registry = new Map<string, PageContextResolver>();

/**
 * Reactive version number — incremented on each register/unregister,
 * allowing external computed properties to track changes in real time.
 * 响应式版本号 — 每次注册/注销时自增，
 * 供外部 computed 建立依赖以实现实时感知。
 */
export const pageContextVersion = ref(0);

/**
 * Register a page context resolver function
 * 注册页面上下文解析函数
 *
 * @param key - Unique identifier (recommended: route path, e.g. 'tenant/orders/detail') / 唯一标识
 * @param resolver - Context resolver function / 上下文解析函数
 * @returns Cleanup function to unregister (call in onUnmounted) / cleanup 函数
 */
export function registerPageContext(
  key: string,
  resolver: PageContextResolver,
): () => void {
  registry.set(key, resolver);
  pageContextVersion.value++;
  return () => {
    // Only remove if this is our own resolver (avoid clearing new registrations) / 仅删除自己注册的（避免新注册被意外清除）
    if (registry.get(key) === resolver) {
      registry.delete(key);
      pageContextVersion.value++;
    }
  };
}

/**
 * Get current page context
 * Prioritizes the specified key's resolver; if not specified, iterates all resolvers
 * and returns the last registered non-null result.
 * 获取当前页面上下文
 * 优先使用指定 key 的 resolver，未指定时遍历所有 resolver，
 * 返回最后注册的非空结果。
 *
 * @param key - Optional, specifies the resolver key to use / 可选，指定要使用的 resolver key
 * @returns Page context data or null / 页面上下文数据或 null
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

  // Iterate all resolvers, return the last non-null result / 遍历所有 resolver，返回最后一个非空结果
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
 * Get list of currently active registered keys (for debugging)
 * 获取当前活跃的注册 key 列表（调试用）
 */
export function getRegisteredKeys(): string[] {
  return [...registry.keys()];
}

/**
 * Clear all registrations (for testing/reset)
 * 清空所有注册（测试/重置用）
 */
export function clearPageContextRegistry(): void {
  registry.clear();
  pageContextVersion.value++;
}

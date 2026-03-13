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

import { scanDomSemantics } from './dom-semantic-scanner';
import { normalizePageKey } from './page-key-utils';

/** Page context structure (maps to backend PageContext schema) / 页面上下文结构（对应后端 PageContext schema） */
export type PageContextData = PageContext;

/** Context resolver function / 上下文解析函数 */
export type PageContextResolver = () => PageContextData | null;

/**
 * Registry: normalized page key (dot-notation) → resolver
 * Uses Map to guarantee registration order; later registrations override earlier ones.
 * Keys are automatically normalized via normalizePageKey().
 * 注册表：规范化的页面标识（点号格式） → resolver
 * 使用 Map 保证注册顺序，后注册覆盖先注册。
 * key 通过 normalizePageKey() 自动规范化。
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
 * @param key - Unique identifier (any format, auto-normalized to dot-notation) / 唯一标识（任意格式，自动规范化为点号格式）
 * @param resolver - Context resolver function / 上下文解析函数
 * @returns Cleanup function to unregister (call in onUnmounted) / cleanup 函数
 */
export function registerPageContext(
  key: string,
  resolver: PageContextResolver,
): () => void {
  const nk = normalizePageKey(key);
  registry.set(nk, resolver);
  pageContextVersion.value++;
  return () => {
    // Only remove if this is our own resolver (avoid clearing new registrations) / 仅删除自己注册的（避免新注册被意外清除）
    if (registry.get(nk) === resolver) {
      registry.delete(nk);
      pageContextVersion.value++;
    }
  };
}

/**
 * Get current page context
 * 获取当前页面上下文
 *
 * Resolution order (when key is not provided):
 * 1. Route-based: infer key from current URL, try exact registry match
 * 2. Iterate all resolvers, return last non-null result
 * 3. DOM semantic snapshot fallback
 *
 * 解析优先级（未提供 key 时）：
 * 1. 路由匹配：从当前 URL 推断 key，精确匹配 registry
 * 2. 遍历所有 resolver，返回最后非空结果
 * 3. DOM 语义快照降级
 *
 * @param key - Optional, specifies the resolver key (any format, auto-normalized) / 可选，指定 resolver key（任意格式，自动规范化）
 * @returns Page context data or null / 页面上下文数据或 null
 */
export function resolvePageContext(
  key?: string,
): PageContextData | null {
  if (key) {
    const resolver = registry.get(normalizePageKey(key));
    if (resolver) {
      try {
        return resolver();
      } catch (error) {
        console.error(
          `[PageContextRegistry] Resolver '${key}' error:`,
          error,
        );
      }
    }
    // Fallback: use DOM semantic snapshot for unregistered pages / 降级：对未注册页面使用 DOM 语义快照
    return buildDomFallbackContext(normalizePageKey(key));
  }

  // Attempt route-based matching first to avoid multi-resolver conflicts / 优先路由匹配，避免多 resolver 冲突
  const inferredKey = normalizePageKey(window.location.pathname);
  const routeResolver = registry.get(inferredKey);
  if (routeResolver) {
    try {
      const ctx = routeResolver();
      if (ctx) return ctx;
    } catch (error) {
      console.error(
        `[PageContextRegistry] Route-inferred resolver '${inferredKey}' error:`,
        error,
      );
    }
  }

  // Fallback: iterate all resolvers, return the last non-null result / 降级：遍历所有 resolver，返回最后非空结果
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
  if (!result) {
    return buildDomFallbackContext();
  }
  return result;
}

/**
 * Build a minimal page context from DOM semantic scanning.
 * Used as fallback when no resolver is registered or none returns a result.
 * 从 DOM 语义扫描构建最小页面上下文。
 * 当无 resolver 注册或全部返回 null 时作为降级方案。
 */
function buildDomFallbackContext(pageKey?: string): PageContextData | null {
  const snapshot = scanDomSemantics();
  if (!snapshot) return null;

  const inferredKey = pageKey || window.location.pathname.replace(/^\//, '').replaceAll('/', '.');
  return {
    page_key: inferredKey,
    page_title: snapshot.page_title || inferredKey,
    page_data: {
      source: 'dom_snapshot',
      ...snapshot,
    },
  };
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

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
 * Extras resolvers: merge into primary context instead of replacing.
 * Used by DocumentEditor etc. to add fields without overwriting platform editor context.
 * 附加 resolver：合并到主 context，不替换。供 DocumentEditor 等添加字段且保留平台编辑器原有说明。
 */
const extrasRegistry = new Map<string, PageContextResolver[]>();

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
 * Register extras to be merged into the primary context for a key.
 * Does NOT replace the primary context; merges page_data (preserves base entity_description).
 * 注册附加字段，合并到主 context。不替换主 context；合并 page_data（保留 base 的 entity_description）。
 *
 * Use when a consumer (e.g. DocumentEditor) needs to add fields on top of platform context.
 * 当消费方（如 DocumentEditor）需在平台 context 之上追加字段时使用。
 *
 * @param key - Page identifier (same as primary) / 页面标识（与主注册相同）
 * @param resolver - Returns partial context to merge (page_data only) / 返回要合并的局部 context（仅 page_data）
 * @returns Cleanup function / cleanup 函数
 */
export function registerPageContextExtras(
  key: string,
  resolver: PageContextResolver,
): () => void {
  const nk = normalizePageKey(key);
  const list = extrasRegistry.get(nk) ?? [];
  list.push(resolver);
  extrasRegistry.set(nk, list);
  pageContextVersion.value++;
  return () => {
    const cur = extrasRegistry.get(nk);
    if (cur) {
      const idx = cur.indexOf(resolver);
      if (idx >= 0) {
        cur.splice(idx, 1);
        if (cur.length === 0) extrasRegistry.delete(nk);
        pageContextVersion.value++;
      }
    }
  };
}

function mergeExtrasIntoContext(
  base: PageContextData,
  extrasList: PageContextResolver[],
): PageContextData {
  let result = { ...base, page_data: { ...(base.page_data || {}) } };
  for (const res of extrasList) {
    try {
      const ext = res();
      if (!ext?.page_data || typeof ext.page_data !== 'object') continue;
      const extAppend = (ext.page_data as Record<string, unknown>).entity_description_append as string | undefined;
      const merged = { ...(result.page_data as object), ...(ext.page_data as object) } as Record<string, unknown>;
      const currentDesc =
        typeof merged.entity_description === 'string'
          ? merged.entity_description
          : undefined;
      if (extAppend) {
        merged.entity_description = currentDesc
          ? currentDesc + '\n\n' + extAppend
          : extAppend;
      }
      delete merged.entity_description_append;
      result = { ...result, page_data: merged };
    } catch (e) {
      console.warn('[PageContextRegistry] Extras merge error:', e);
    }
  }
  return result;
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
    const nk = normalizePageKey(key);
    const resolver = registry.get(nk);
    const extras = extrasRegistry.get(nk);
    if (resolver) {
      try {
        const base = resolver();
        if (base && extras?.length) {
          return mergeExtrasIntoContext(base, extras);
        }
        return base;
      } catch (error) {
        console.warn(
          `[PageContextRegistry] Resolver '${key}' error:`,
          error,
        );
      }
    }
    // Fallback: use DOM semantic snapshot for unregistered pages / 降级：对未注册页面使用 DOM 语义快照
    const fallback = buildDomFallbackContext(nk, {
      allowMinimal: !!extras?.length,
    });
    return fallback && extras?.length
      ? mergeExtrasIntoContext(fallback, extras)
      : fallback;
  }

  // Attempt route-based matching first to avoid multi-resolver conflicts / 优先路由匹配，避免多 resolver 冲突
  const inferredKey = normalizePageKey(window.location.pathname);
  const routeResolver = registry.get(inferredKey);
  const routeExtras = extrasRegistry.get(inferredKey);
  if (routeResolver) {
    try {
      const base = routeResolver();
      if (base && routeExtras?.length) {
        return mergeExtrasIntoContext(base, routeExtras);
      }
      if (base) return base;
    } catch (error) {
      console.warn(
        `[PageContextRegistry] Route-inferred resolver '${inferredKey}' error:`,
        error,
      );
    }
  }

  if (routeExtras?.length) {
    const fallback = buildDomFallbackContext(inferredKey, {
      allowMinimal: true,
    });
    if (fallback) {
      return mergeExtrasIntoContext(fallback, routeExtras);
    }
  }

  // Fallback: iterate all resolvers, return the last non-null result (with extras merged) / 遍历解析器取最后非空
  let result: PageContextData | null = null;
  let resultKey: string | null = null;
  for (const [registeredKey, resolver] of registry) {
    try {
      const ctx = resolver();
      if (ctx) {
        result = ctx;
        resultKey = registeredKey;
      }
    } catch (error) {
      console.warn(
        `[PageContextRegistry] Resolver '${registeredKey}' error:`,
        error,
      );
    }
  }
  if (result && resultKey) {
    const extras = extrasRegistry.get(resultKey);
    if (extras?.length) {
      result = mergeExtrasIntoContext(result, extras);
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
function buildMinimalFallbackContext(pageKey: string): PageContextData {
  const title =
    typeof document !== 'undefined'
      ? document.title.trim()
      : '';

  return {
    page_key: pageKey,
    page_title: title || pageKey,
    page_data: {
      source: 'minimal_fallback',
    },
  };
}

function buildDomFallbackContext(
  pageKey?: string,
  options: { allowMinimal?: boolean } = {},
): PageContextData | null {
  const inferredKey =
    pageKey || window.location.pathname.replace(/^\//, '').replaceAll('/', '.');
  const snapshot = scanDomSemantics();
  if (!snapshot) {
    return options.allowMinimal && pageKey
      ? buildMinimalFallbackContext(inferredKey)
      : null;
  }

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
  extrasRegistry.clear();
  pageContextVersion.value++;
}

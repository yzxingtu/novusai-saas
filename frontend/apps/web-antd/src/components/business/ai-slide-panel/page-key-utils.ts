/**
 * Page Key Utilities
 * 页面标识工具函数
 *
 * Provides a single canonical format for page keys across the entire AI page
 * awareness system (context registry, operation registry, WebSocket channel).
 * 为整个 AI 页面感知系统提供统一的 page key 规范格式。
 *
 * Canonical format: dot-notation, e.g. 'admin.ai.agents'
 * 规范格式：点号分隔，如 'admin.ai.agents'
 *
 * Accepts any of:
 *   '/admin/ai/agents'  → 'admin.ai.agents'  (route.path)
 *   'admin/ai/agents'   → 'admin.ai.agents'  (registerPageContext key)
 *   'admin.ai.agents'   → 'admin.ai.agents'  (already canonical)
 */

/**
 * Normalize a page key to the canonical dot-notation format.
 * 将页面标识规范化为点号格式。
 *
 * This is the **single source of truth** for key normalization.
 * All registries and lookups MUST go through this function.
 * 这是 key 规范化的唯一权威来源，所有注册表和查找都必须经过此函数。
 *
 * @param raw - Raw page key in any format / 任意格式的原始 page key
 * @returns Normalized dot-notation key / 规范化后的点号格式 key
 *
 * @example
 * normalizePageKey('/admin/ai/agents')  // 'admin.ai.agents'
 * normalizePageKey('admin/ai/agents')   // 'admin.ai.agents'
 * normalizePageKey('admin.ai.agents')   // 'admin.ai.agents'
 */
export function normalizePageKey(raw: string): string {
  return raw.replace(/^\//, '').replaceAll('/', '.');
}

export interface PageKeyRouteLike {
  meta?: null | Record<string, unknown>;
  path?: string;
}

/** Read ``meta.ai.pageContextKey`` when present / 读取路由 meta 中显式配置的 page key */
function extractMetaPageContextKey(route?: null | PageKeyRouteLike): string {
  const meta = route?.meta;
  if (!meta || typeof meta !== 'object') {
    return '';
  }
  const aiMeta =
    'ai' in meta && meta.ai && typeof meta.ai === 'object'
      ? (meta.ai as { pageContextKey?: unknown })
      : undefined;
  return typeof aiMeta?.pageContextKey === 'string'
    ? aiMeta.pageContextKey.trim()
    : '';
}

export function resolveRoutePageKey(
  route?: null | PageKeyRouteLike,
  fallbackPath = '',
): string {
  const pageContextKey = extractMetaPageContextKey(route);
  if (pageContextKey) {
    return normalizePageKey(pageContextKey);
  }
  const rawPath = route?.path || fallbackPath;
  return normalizePageKey(rawPath);
}

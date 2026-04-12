/**
 * Page session ID management
 * 页面会话 ID 管理
 *
 * Call once in layout component, auto-listens to route changes and generates unique page_session_id (UUID v4).
 * Auto-updates ID on each route switch, used for precise AI operation targeting.
 * 在 layout 组件中调用一次，自动监听路由变化并生成唯一 page_session_id。
 *
 * @example
 * ```ts
 * // Call once in layout / layout 中调用一次
 * usePageSession();
 *
 * // Get active ID from anywhere / 任意位置获取当前活跃 ID
 * import { getActivePageSessionId } from '#/composables/use-page-session';
 * const id = getActivePageSessionId(); // "a1b2c3d4-..."
 * ```
 */

import type { Ref } from 'vue';

import { ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { resolveRoutePageKey } from '#/components/business/ai-runtime/page-key-utils';

/** Global active page_session_id (only one active page in SPA) / 全局当前活跃的 page_session_id */
const activePageSessionId = ref<string>('');
let lastResolvedPageKey = '';

/**
 * Generate UUID v4
 * 生成 UUID v4
 *
 * Prefers crypto.randomUUID(), falls back to manual implementation
 * 优先使用 crypto.randomUUID()，降级到手动实现
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback: RFC 4122 v4 UUID / 降级为伪随机 UUID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replaceAll(/[xy]/g, (c) => {
    const r = Math.trunc(Math.random() * 16);
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface UsePageSessionReturn {
  /** Current page session ID (reactive) / 当前页面的 session ID（响应式） */
  pageSessionId: Ref<string>;
}

/**
 * Page session ID management (call once in layout component setup)
 * 页面会话 ID 管理（在 layout 组件 setup 中调用一次）
 *
 * Watches route path changes, auto-generates new UUID on each navigation.
 * Immediately generates an ID on initialization.
 * 监听路由 path 变化，每次导航自动生成新 UUID。初始化时立即生成。
 */
export function usePageSession(): UsePageSessionReturn {
  const route = useRoute();
  const resolveCurrentPageKey = () =>
    resolveRoutePageKey(
      route,
      typeof window === 'undefined' ? '' : window.location.pathname,
    );

  // Reuse current session id when remounted on the same route / 同一路由重挂载时复用当前 session id
  if (
    !activePageSessionId.value ||
    lastResolvedPageKey !== resolveCurrentPageKey()
  ) {
    activePageSessionId.value = generateUUID();
    lastResolvedPageKey = resolveCurrentPageKey();
  }

  // Regenerate on effective AI page key change / 页面 AI key 变化时重新生成
  watch(
    resolveCurrentPageKey,
    (nextPageKey) => {
      if (nextPageKey === lastResolvedPageKey && activePageSessionId.value) {
        return;
      }
      activePageSessionId.value = generateUUID();
      lastResolvedPageKey = nextPageKey;
    },
    { immediate: true },
  );

  return { pageSessionId: activePageSessionId };
}

/**
 * Get current active page_session_id (for use outside component context)
 * 获取当前活跃的 page_session_id（非组件上下文中使用）
 *
 * For getting current page session ID in composables or stores without props.
 * 用于在 composable 或 store 中获取当前页面的 session ID，无需通过 props 传递。
 */
export function getActivePageSessionId(): string {
  return activePageSessionId.value;
}

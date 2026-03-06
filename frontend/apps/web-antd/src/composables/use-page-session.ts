/**
 * 页面会话 ID 管理
 *
 * 在 layout 组件中调用一次，自动监听路由变化并生成唯一 page_session_id（UUID v4）。
 * 每次路由切换时自动更新 ID，用于精确定位 AI 操作的目标页面实例。
 *
 * @example
 * ```ts
 * // layout 中调用一次
 * usePageSession();
 *
 * // 任意位置获取当前活跃 ID
 * import { getActivePageSessionId } from '#/composables/use-page-session';
 * const id = getActivePageSessionId(); // "a1b2c3d4-..."
 * ```
 */

import { type Ref, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

/** 全局当前活跃的 page_session_id（SPA 中只有一个活跃页面） */
const activePageSessionId = ref<string>('');

/**
 * 生成 UUID v4
 *
 * 优先使用 crypto.randomUUID()，降级到手动实现
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback: RFC 4122 v4 UUID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface UsePageSessionReturn {
  /** 当前页面的 session ID（响应式） */
  pageSessionId: Ref<string>;
}

/**
 * 页面会话 ID 管理（在 layout 组件 setup 中调用一次）
 *
 * 监听路由 path 变化，每次导航自动生成新 UUID。
 * 初始化时立即生成一个 ID。
 */
export function usePageSession(): UsePageSessionReturn {
  const route = useRoute();

  // 立即生成初始 ID
  activePageSessionId.value = generateUUID();

  // 路由变化时重新生成
  watch(
    () => route.path,
    () => {
      activePageSessionId.value = generateUUID();
    },
  );

  return { pageSessionId: activePageSessionId };
}

/**
 * 获取当前活跃的 page_session_id（非组件上下文中使用）
 *
 * 用于在 composable 或 store 中获取当前页面的 session ID，
 * 无需通过 props 传递。
 */
export function getActivePageSessionId(): string {
  return activePageSessionId.value;
}

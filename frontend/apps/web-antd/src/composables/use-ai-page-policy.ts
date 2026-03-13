/**
 * Page-level AI policy composable
 * 页面级 AI 策略 Composable
 *
 * Combines route meta.ai config with RBAC permissions to compute effective AI mode.
 * 结合路由 meta.ai 配置与 RBAC 权限，计算当前页面的有效 AI 模式。
 *
 * Priority (high to low) / 优先级（从高到低）:
 * 1. RBAC permission check (disabled if no permission) / RBAC 权限检查
 * 2. Route meta.ai.mode (page-level config) / 路由 meta.ai.mode
 * 3. Default mode DEFAULT_AI_MODE / 默认模式
 *
 * @example
 * ```ts
 * const { isAIEnabled, effectiveAIMode, pageContextKey } = useCurrentPageAIPolicy();
 * ```
 */
import type { AIPageMode } from '@vben-core/typings';

import { computed } from 'vue';

import { useRoute } from 'vue-router';

import { normalizePageKey } from '#/components/business/ai-slide-panel/page-key-utils';
import { useAIPermission } from './use-ai-permission';

/** Default AI mode: global assistant (sidebar panel, page-unaware) / 默认 AI 模式：全局助手（侧边栏浮窗，不感知页面） */
const DEFAULT_AI_MODE: AIPageMode = 'context_only';

export function useCurrentPageAIPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();

  /** Effective AI mode: route config > default / 生效的 AI 模式：路由配置 > 默认值 */
  const pageMode = computed<AIPageMode>(
    () => route.meta?.ai?.mode ?? DEFAULT_AI_MODE,
  );

  /**
   * Current page context key in canonical dot-notation (e.g. 'admin.ai.agents')
   * 当前页面上下文标识（规范点号格式，如 'admin.ai.agents'）
   *
   * Priority: route.meta.ai.pageContextKey > normalizePageKey(route.path)
   * Used for precise matching with registered page contexts / 用于精确匹配注册表
   */
  const pageContextKey = computed<string | undefined>(
    () =>
      (route.meta?.ai?.pageContextKey
        ? normalizePageKey(route.meta.ai.pageContextKey as string)
        : undefined) ??
      (route.path ? normalizePageKey(route.path) : undefined),
  );

  /** Page AI disabled flag / 页面 AI 禁用标志 */
  const pageDisabled = computed(() => pageMode.value === 'disabled');

  /**
   * Final AI availability (permission + config) / 最终 AI 可用性（权限 + 配置）
   * Only true when RBAC allows and page is not disabled / 仅当 RBAC 允许且页面未禁用时为 true
   */
  const aiEnabled = computed(() => canChat.value && !pageDisabled.value);

  /**
   * Effective AI mode for current page / 当前页面生效的 AI 模式
   * No AI permission: disabled / 无 AI 权限：禁用
   * Has AI permission: page config mode / 有 AI 权限：页面配置模式
   */
  const effectiveMode = computed<AIPageMode>(() => {
    if (!canChat.value) return 'disabled';
    return pageMode.value;
  });

  return {
    /** AI total switch (permission + config) / AI 总开关（权限 + 配置） */
    aiEnabled,
    /** Whether has AI chat permission (pure RBAC) / 是否有 AI 聊天权限（纯 RBAC） */
    canChat,
    /** Whether can view conversation history (pure RBAC) / 是否可查看对话历史（纯 RBAC） */
    canViewHistory,
    /** Whether can execute route (pure RBAC) / 是否可执行路由（纯 RBAC） */
    canRoute,
    /** Effective AI mode for current page / 当前页面生效的 AI 模式 */
    effectiveMode,
    /** Page AI disabled flag / 页面 AI 禁用标志 */
    pageDisabled,
    /** Current page context key / 页面上下文标识 */
    pageContextKey,
    /** Page AI mode / 页面 AI 模式 */
    pageMode,
    /** Current resource name / 当前资源名 */
    resource,
  };
}

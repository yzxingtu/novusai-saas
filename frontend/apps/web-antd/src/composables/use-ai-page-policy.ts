/**
 * 页面级 AI 策略 Composable
 *
 * 合并 route.meta.ai（页面策略）与 RBAC 权限，输出宿主层可直接消费的策略结果。
 *
 * 优先级：RBAC 权限 > 页面策略
 *   - 无 AI 权限 → 一律禁用（忽略页面策略）
 *   - 有 AI 权限 + 页面 mode=disabled → 禁用
 *   - 有 AI 权限 + 页面 mode=context_only/operate → 启用
 *   - 有 AI 权限 + 未声明 meta.ai → 按默认策略（context_only）启用
 */
import type { AIPageMode } from '@vben-core/typings';

import { computed } from 'vue';

import { useRoute } from 'vue-router';

import { useAIPermission } from './use-ai-permission';

/** 未声明 meta.ai 时的默认模式 */
const DEFAULT_AI_MODE: AIPageMode = 'context_only';

export function useCurrentPageAIPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();

  /** 当前页面声明的 AI 模式（未声明时为默认值） */
  const pageMode = computed<AIPageMode>(
    () => route.meta?.ai?.mode ?? DEFAULT_AI_MODE,
  );

  /**
   * 当前页面的 pageContextKey（用于精确匹配注册表）
   *
   * 优先使用 meta.ai.pageContextKey 显式声明；
   * 未声明时自动从路由 path 推导（去掉前导 /），
   * 与 registerPageContext 的 key 约定一致。
   */
  const pageContextKey = computed<string | undefined>(
    () =>
      route.meta?.ai?.pageContextKey ??
      (route.path ? route.path.replace(/^\//, '') : undefined),
  );

  /** 页面策略是否禁用 AI */
  const pageDisabled = computed(() => pageMode.value === 'disabled');

  /**
   * 最终 AI 可用性（权限 + 页面策略双重控制）
   *
   * 仅当 RBAC 允许且页面未禁用时为 true
   */
  const aiEnabled = computed(() => canChat.value && !pageDisabled.value);

  /**
   * 最终有效模式
   *
   * 无 AI 权限时强制为 disabled；否则使用页面声明的模式
   */
  const effectiveMode = computed<AIPageMode>(() => {
    if (!canChat.value) return 'disabled';
    return pageMode.value;
  });

  return {
    /** AI 总开关（权限 + 页面策略） */
    aiEnabled,
    /** 是否有 AI 聊天权限（纯 RBAC） */
    canChat,
    /** 是否可查看对话历史（纯 RBAC） */
    canViewHistory,
    /** 是否可执行路由（纯 RBAC） */
    canRoute,
    /** 最终有效 AI 模式 */
    effectiveMode,
    /** 页面策略是否禁用 */
    pageDisabled,
    /** 页面声明的 pageContextKey */
    pageContextKey,
    /** 页面声明的 AI 模式 */
    pageMode,
    /** 当前端权限资源名 */
    resource,
  };
}

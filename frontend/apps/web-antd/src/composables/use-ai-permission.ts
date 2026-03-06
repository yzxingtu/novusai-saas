/**
 * AI 权限检查 Composable
 *
 * 根据当前路由前缀动态切换权限资源（admin_agent_chat / agent_chat），
 * 提供 canChat / canViewHistory 等响应式权限判断。
 */
import { computed } from 'vue';

import { useRoute } from 'vue-router';

import { ADMIN_ROUTE_PREFIX } from '#/constants/endpoints';
import { useAccess } from '#/utils/access';

/**
 * AI 交互权限
 *
 * - `canChat`: 是否可发送消息（基于 stream 权限）
 * - `canViewHistory`: 是否可查看对话历史
 * - `resource`: 当前端对应的权限资源名
 */
export function useAIPermission() {
  const { hasAccessByCodes } = useAccess();
  const route = useRoute();

  /** 当前端权限资源名 */
  const resource = computed(() =>
    route.path.startsWith(ADMIN_ROUTE_PREFIX)
      ? 'admin_agent_chat'
      : 'agent_chat',
  );

  /** 是否可发送 AI 消息 */
  const canChat = computed(() =>
    hasAccessByCodes([`${resource.value}:stream`]),
  );

  /** 是否可查看对话历史 */
  const canViewHistory = computed(() =>
    hasAccessByCodes([`${resource.value}:conversations`]),
  );

  /** 是否可执行路由 */
  const canRoute = computed(() =>
    hasAccessByCodes([`${resource.value}:route`]),
  );

  return {
    canChat,
    canRoute,
    canViewHistory,
    resource,
  };
}

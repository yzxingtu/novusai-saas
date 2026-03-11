/**
 * AI permission check composable
 * AI 权限检查 Composable
 *
 * Dynamically switches permission resource (admin_agent_chat / agent_chat) based on route prefix.
 * Provides reactive permission checks: canChat / canViewHistory.
 * 根据当前路由前缀动态切换权限资源，提供响应式权限判断。
 */
import { computed } from 'vue';

import { useRoute } from 'vue-router';

import { ADMIN_ROUTE_PREFIX } from '#/constants/endpoints';
import { useAccess } from '#/utils/access';

/**
 * AI interaction permissions
 * AI 交互权限
 *
 * - `canChat`: whether messages can be sent (based on stream permission) / 是否可发送消息
 * - `canViewHistory`: whether conversation history can be viewed / 是否可查看对话历史
 * - `resource`: permission resource name for current endpoint / 当前端权限资源名
 */
export function useAIPermission() {
  const { hasAccessByCodes } = useAccess();
  const route = useRoute();

  /** Permission resource name for current endpoint / 当前端权限资源名 */
  const resource = computed(() =>
    route.path.startsWith(ADMIN_ROUTE_PREFIX)
      ? 'admin_agent_chat'
      : 'agent_chat',
  );

  /** Whether AI messages can be sent / 是否可发送 AI 消息 */
  const canChat = computed(() =>
    hasAccessByCodes([`${resource.value}:stream`]),
  );

  /** Whether conversation history can be viewed / 是否可查看对话历史 */
  const canViewHistory = computed(() =>
    hasAccessByCodes([`${resource.value}:conversations`]),
  );

  /** Whether routing can be executed / 是否可执行路由 */
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

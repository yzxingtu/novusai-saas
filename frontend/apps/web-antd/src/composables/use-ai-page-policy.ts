/**
 * Page-level AI entry policy.
 *
 * Page awareness and page operations are retired. This composable only decides
 * whether the global AI chat entry is visible on the current route.
 */
import type { AIPageMode } from '@vben/types';

import { computed } from 'vue';
import { useRoute } from 'vue-router';

import { useAIPermission } from './use-ai-permission';

type RouteAIMeta = {
  mode?: AIPageMode | string;
};

function normalizeAIMode(mode: unknown): AIPageMode {
  return String(mode ?? '')
    .trim()
    .toLowerCase() === 'disabled'
    ? 'disabled'
    : 'enabled';
}

export function useCurrentPageAIPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();
  const rawAIMeta = computed<RouteAIMeta>(
    () => (route.meta?.ai as RouteAIMeta | undefined) ?? {},
  );

  const pageMode = computed<AIPageMode>(() =>
    normalizeAIMode(rawAIMeta.value.mode),
  );
  const pageDisabled = computed(() => pageMode.value === 'disabled');
  const aiEnabled = computed(() => canChat.value && !pageDisabled.value);
  const effectiveMode = computed<AIPageMode>(() =>
    aiEnabled.value ? 'enabled' : 'disabled',
  );

  return {
    aiEnabled,
    canChat,
    canViewHistory,
    canRoute,
    effectiveMode,
    pageDisabled,
    pageMode,
    resource,
  };
}

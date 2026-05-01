/**
 * Route AI entry policy.
 *
 * This composable only decides whether the global AI chat entry is visible on
 * the current route.
 */
import type { AIEntryMode } from '@vben/types';

import { computed } from 'vue';
import { useRoute } from 'vue-router';

import { useAIPermission } from './use-ai-permission';

type RouteAIMeta = {
  mode?: AIEntryMode | string;
};

function normalizeAIMode(mode: unknown): AIEntryMode {
  return String(mode ?? '')
    .trim()
    .toLowerCase() === 'disabled'
    ? 'disabled'
    : 'enabled';
}

export function useAIEntryPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();
  const rawAIMeta = computed<RouteAIMeta>(
    () => (route.meta?.ai as RouteAIMeta | undefined) ?? {},
  );

  const entryMode = computed<AIEntryMode>(() =>
    normalizeAIMode(rawAIMeta.value.mode),
  );
  const entryDisabled = computed(() => entryMode.value === 'disabled');
  const aiEnabled = computed(() => canChat.value && !entryDisabled.value);
  const effectiveMode = computed<AIEntryMode>(() =>
    aiEnabled.value ? 'enabled' : 'disabled',
  );

  return {
    aiEnabled,
    canChat,
    canViewHistory,
    canRoute,
    effectiveMode,
    entryDisabled,
    entryMode,
    resource,
  };
}

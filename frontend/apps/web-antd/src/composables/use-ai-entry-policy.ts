/**
 * Route AI entry policy.
 *
 * This composable only decides whether the global AI chat entry is visible on
 * the current route.
 */
import type { AIEntryMode } from '@vben/types';

import type { BaseUserInfo } from '#/api';

import { computed } from 'vue';
import { useRoute } from 'vue-router';

import { useUserStore } from '@vben/stores';

import { getActivePinia } from 'pinia';

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

function normalizeBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function normalizeReason(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) {
    return undefined;
  }
  const reason = value.trim();
  if (reason === 'account_ai_disabled') {
    return 'account_disabled';
  }
  if (
    reason === 'tenant_ai_disabled' ||
    reason === 'tenant_plan_ai_disabled' ||
    reason === 'tenant_plan_unassigned'
  ) {
    return 'tenant_plan_disabled';
  }
  if (reason === 'permission_denied') {
    return 'permission_missing';
  }
  return reason;
}

export function useAIEntryPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();
  const userStore = getActivePinia() ? useUserStore() : null;
  const rawAIMeta = computed<RouteAIMeta>(
    () => (route.meta?.ai as RouteAIMeta | undefined) ?? {},
  );
  const routePath = computed(() => String(route.path ?? ''));
  const userInfo = computed(
    () => userStore?.userInfo as null | Partial<BaseUserInfo> | undefined,
  );

  const entryMode = computed<AIEntryMode>(() =>
    normalizeAIMode(rawAIMeta.value.mode),
  );
  const entryDisabled = computed(() => entryMode.value === 'disabled');
  const commandBarEnabled = computed(() => true);
  const accountAIEnabled = computed(() =>
    normalizeBoolean(userInfo.value?.accountAIEnabled, true),
  );
  const tenantPlanAIEnabled = computed(() => {
    if (!routePath.value.startsWith('/tenant')) {
      return true;
    }
    return normalizeBoolean(userInfo.value?.tenantPlanAIEnabled, true);
  });
  const serverAIChatEnabled = computed(() =>
    normalizeBoolean(
      userInfo.value?.aiChatEnabled ?? userInfo.value?.aiEnabled,
      accountAIEnabled.value && tenantPlanAIEnabled.value,
    ),
  );
  const aiChatEnabled = computed(
    () =>
      canChat.value &&
      !entryDisabled.value &&
      accountAIEnabled.value &&
      tenantPlanAIEnabled.value &&
      serverAIChatEnabled.value,
  );
  const aiEnabled = aiChatEnabled;
  const aiUnavailableReason = computed(() => {
    const backendReason = normalizeReason(userInfo.value?.aiUnavailableReason);
    if (!accountAIEnabled.value) {
      return backendReason ?? 'account_disabled';
    }
    if (!tenantPlanAIEnabled.value) {
      return backendReason ?? 'tenant_plan_disabled';
    }
    if (!serverAIChatEnabled.value) {
      return backendReason ?? 'ai_disabled';
    }
    if (entryDisabled.value) {
      return backendReason ?? 'route_disabled';
    }
    if (!canChat.value) {
      return backendReason ?? 'permission_missing';
    }
    return undefined;
  });
  const effectiveMode = computed<AIEntryMode>(() =>
    aiChatEnabled.value ? 'enabled' : 'disabled',
  );

  return {
    accountAIEnabled,
    aiEnabled,
    aiChatEnabled,
    aiUnavailableReason,
    canChat,
    canViewHistory,
    canRoute,
    commandBarEnabled,
    effectiveMode,
    entryDisabled,
    entryMode,
    resource,
    tenantPlanAIEnabled,
  };
}

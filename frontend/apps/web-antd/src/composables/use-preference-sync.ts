/**
 * Preference sync composable / 偏好同步组合式函数
 *
 * Watches Vben preferences changes and syncs to backend with debounce.
 * Listens for WebSocket global preference updates and applies them.
 * 监听 Vben 偏好变更并防抖同步到后端，监听 WS 全局偏好更新并应用。
 */
import type { PreferencesData } from '#/api/shared/types';

import { onUnmounted, watch } from 'vue';

import { preferences as vbenPreferences, updatePreferences } from '@vben/preferences';

import { useDebounceFn } from '@vueuse/core';

import {
  getVbenSnapshot,
  mapFromVbenPreferences,
  mapToVbenPreferences,
  useUserPreferenceStore,
} from '#/store/shared/user-preference';
import { useSocketIOStore } from '#/store';

interface GlobalUpdatedPayload {
  preferences: Record<string, boolean | number | string>;
}

const GLOBAL_ONLY_KEYS = new Set(['watermark_enable', 'watermark_content']);

/**
 * 提取差异 key / Extract diff keys between two preference objects
 */
function getDiff(
  current: PreferencesData,
  snapshot: PreferencesData,
): PreferencesData | null {
  const diff: PreferencesData = {};
  let hasDiff = false;

  for (const [key, value] of Object.entries(current)) {
    if (GLOBAL_ONLY_KEYS.has(key)) continue;
    if (snapshot[key] !== value) {
      diff[key] = value;
      hasDiff = true;
    }
  }

  return hasDiff ? diff : null;
}

const WS_SKIP_WINDOW_MS = 500;

export function usePreferenceSync() {
  const preferenceStore = useUserPreferenceStore();
  const sioStore = useSocketIOStore();

  let lastWsTimestamp = 0;
  let serverSnapshot: PreferencesData = {};

  /**
   * 初始化：从后端加载偏好后设置快照
   * Initialize: set snapshot after loading preferences from backend
   */
  function initSnapshot() {
    serverSnapshot = getVbenSnapshot();
  }

  /**
   * 将 Vben 当前偏好同步到后端 / Sync current Vben preferences to backend
   */
  async function syncToBackend() {
    if (Date.now() - lastWsTimestamp < WS_SKIP_WINDOW_MS) {
      return;
    }

    if (!preferenceStore.loaded || !preferenceStore.side) return;
    if (preferenceStore.globalPreviewActive) return;

    const current = mapFromVbenPreferences(
      vbenPreferences as Parameters<typeof mapFromVbenPreferences>[0],
    );
    const diff = getDiff(current, serverSnapshot);

    if (!diff) return;

    const result = await preferenceStore.updateMyPreferences(diff);
    if (result) {
      serverSnapshot = { ...serverSnapshot, ...diff };
    }
  }

  const debouncedSync = useDebounceFn(syncToBackend, 2000);

  const stopWatcher = watch(
    () =>
      mapFromVbenPreferences(
        vbenPreferences as Parameters<typeof mapFromVbenPreferences>[0],
      ),
    () => {
      debouncedSync();
    },
    { deep: true },
  );

  /**
   * WebSocket 全局偏好更新处理 / WebSocket global preference update handler
   */
  const onGlobalUpdated = (data: GlobalUpdatedPayload) => {
    lastWsTimestamp = Date.now();

    if (preferenceStore.preferences) {
      preferenceStore.preferences = {
        ...preferenceStore.preferences,
        ...data.preferences,
      };
    }

    const mapped = mapToVbenPreferences(data.preferences);
    if (Object.keys(mapped).length > 0) {
      updatePreferences(mapped as Parameters<typeof updatePreferences>[0]);
    }

    serverSnapshot = getVbenSnapshot();
  };

  const onGlobalUpdatedRaw = (data: unknown) => {
    onGlobalUpdated(data as GlobalUpdatedPayload);
  };

  sioStore.registerHandler('preference:global_updated', onGlobalUpdatedRaw);

  /**
   * 设置跳过标志，用于登录后初始加载
   * Set skip flag, used after initial load on login
   */
  function skipSync() {
    lastWsTimestamp = Date.now();
  }

  function cleanup() {
    stopWatcher();
    sioStore.unregisterHandler('preference:global_updated', onGlobalUpdatedRaw);
  }

  onUnmounted(() => {
    cleanup();
  });

  return {
    initSnapshot,
    skipSync,
    cleanup,
  };
}

import { onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue';

import { useSocketIOStore } from '#/store/shared/socketio';

interface DashboardRealtimeRefreshOptions {
  delayMs?: number;
  events?: string[];
  refreshOnConnect?: boolean;
}

export function useDashboardRealtimeRefresh(
  load: () => Promise<void>,
  options: DashboardRealtimeRefreshOptions = {},
) {
  const {
    delayMs = 1200,
    events = ['dashboard:refresh', 'notification'],
    refreshOnConnect = true,
  } = options;
  const socketStore = useSocketIOStore();
  let attached = false;
  let timer: null | ReturnType<typeof setTimeout> = null;
  let stopStatusWatch: (() => void) | null = null;

  const scheduleRefresh = () => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      void load();
    }, delayMs);
  };

  const attach = () => {
    if (attached) {
      return;
    }
    attached = true;
    for (const event of events) {
      socketStore.unregisterHandler(event, scheduleRefresh);
      socketStore.registerHandler(event, scheduleRefresh);
    }
    stopStatusWatch = watch(
      () => socketStore.status,
      (status, previousStatus) => {
        if (
          refreshOnConnect &&
          status === 'connected' &&
          previousStatus !== 'connected'
        ) {
          scheduleRefresh();
        }
      },
      { immediate: false },
    );
  };

  const detach = () => {
    if (!attached) {
      return;
    }
    attached = false;
    for (const event of events) {
      socketStore.unregisterHandler(event, scheduleRefresh);
    }
    stopStatusWatch?.();
    stopStatusWatch = null;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  onMounted(attach);
  onActivated(attach);
  onDeactivated(detach);
  onUnmounted(detach);
}

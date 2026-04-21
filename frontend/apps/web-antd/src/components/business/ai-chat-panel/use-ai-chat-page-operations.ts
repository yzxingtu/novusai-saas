import type { PageContext } from '#/api/shared/ai-chat';

import { waitForPageSessionJoin } from '#/composables/use-ui-action-channel';

interface PageOperationSocketStore {
  connect?: (endpoint: 'admin' | 'tenant' | 'user') => void;
  emit: (event: string, payload: Record<string, unknown>) => void;
  isConnected: boolean;
}

interface UseAIChatPageOperationsOptions {
  pageSessionIdGetter?: () => null | string | undefined;
  socketIOStore: PageOperationSocketStore;
  socketReadyPollMs?: number;
  socketReadyTimeoutMs?: number;
  socketSettleMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function hasInteractivePageContext(
  pageContext?: null | PageContext,
): boolean {
  if (!pageContext?.page_key) {
    return false;
  }

  const pageContextRecord = pageContext as unknown as Record<string, unknown>;

  if (
    typeof pageContextRecord.ui_epoch === 'number' ||
    Array.isArray(pageContextRecord.surface_stack as unknown[]) ||
    typeof pageContextRecord.active_surface_id === 'string' ||
    typeof pageContextRecord.active_form_session_id === 'string'
  ) {
    return true;
  }
  return false;
}

function resolveSocketEndpoint(apiPrefix: string): 'admin' | 'tenant' | 'user' {
  if (apiPrefix.startsWith('/admin')) {
    return 'admin';
  }
  if (apiPrefix.startsWith('/api/user')) {
    return 'user';
  }
  return 'tenant';
}

export function createAIChatPageOperations(
  options: UseAIChatPageOperationsOptions,
) {
  const {
    pageSessionIdGetter,
    socketIOStore,
    socketReadyPollMs = 100,
    socketReadyTimeoutMs = 3000,
    socketSettleMs = 250,
  } = options;

  function refreshPageSessionRoom(): void {
    const pageSessionId = pageSessionIdGetter?.();
    if (!pageSessionId || !socketIOStore.isConnected) {
      return;
    }
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
    });
  }

  async function ensureSocketReady(apiPrefix: string): Promise<boolean> {
    if (!socketIOStore.isConnected) {
      socketIOStore.connect?.(resolveSocketEndpoint(apiPrefix));

      const startedAt = Date.now();
      while (
        !socketIOStore.isConnected &&
        Date.now() - startedAt < socketReadyTimeoutMs
      ) {
        await sleep(socketReadyPollMs);
      }
    }

    return socketIOStore.isConnected;
  }

  async function ensurePageOperationChannelReady(
    apiPrefix: string,
    pageContext?: null | PageContext,
  ): Promise<boolean> {
    if (!hasInteractivePageContext(pageContext) || !pageSessionIdGetter) {
      return true;
    }

    if (!(await ensureSocketReady(apiPrefix))) {
      return false;
    }

    refreshPageSessionRoom();
    const pageSessionId = pageSessionIdGetter?.() || '';
    if (!pageSessionId) {
      return false;
    }

    const joined = await waitForPageSessionJoin(
      pageSessionId,
      socketReadyTimeoutMs,
      socketReadyPollMs,
    );
    if (!joined) {
      return false;
    }

    await sleep(socketSettleMs);
    return true;
  }

  return {
    ensurePageOperationChannelReady,
    hasPageOperations: hasInteractivePageContext,
  };
}

import type { PageContext } from '#/api/shared/ai-chat';

import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-runtime/page-key-utils';
import { waitForPageSessionJoin } from '#/composables/use-ui-action-channel';

interface PageOperationSocketStore {
  connect?: (endpoint: 'admin' | 'tenant' | 'user') => void;
  emit: (event: string, payload: Record<string, unknown>) => void;
  isConnected: boolean;
}

interface UseAIChatPageOperationsOptions {
  pageSessionIdGetter?: () => null | string | undefined;
  routePathnameGetter?: () => string;
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

function getDefaultRoutePathname(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.location.pathname;
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

  const suggestedTools = pageContextRecord.suggested_tools;
  return !!(
    suggestedTools &&
    typeof suggestedTools === 'object' &&
    Array.isArray((suggestedTools as Record<string, unknown>).primary) &&
    ((suggestedTools as Record<string, unknown>).primary as unknown[]).length >
      0
  );
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

function resolvePageOperationPageKey(
  pageContext: null | PageContext | undefined,
  routePathnameGetter: () => string,
): string {
  return (
    normalizePageKey(pageContext?.page_key ?? '') ||
    resolveRoutePageKey(undefined, routePathnameGetter())
  );
}

export function createAIChatPageOperations(
  options: UseAIChatPageOperationsOptions,
) {
  const {
    pageSessionIdGetter,
    routePathnameGetter = getDefaultRoutePathname,
    socketIOStore,
    socketReadyPollMs = 100,
    socketReadyTimeoutMs = 3000,
    socketSettleMs = 250,
  } = options;

  function refreshPageSessionRoom(pageContext?: null | PageContext): void {
    const pageSessionId = pageSessionIdGetter?.();
    if (!pageSessionId || !socketIOStore.isConnected) {
      return;
    }
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
      page_key: resolvePageOperationPageKey(pageContext, routePathnameGetter),
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

    refreshPageSessionRoom(pageContext);
    const pageSessionId = pageSessionIdGetter?.() || '';
    const pageKey = resolvePageOperationPageKey(
      pageContext,
      routePathnameGetter,
    );
    if (!pageSessionId || !pageKey) {
      return false;
    }

    const joined = await waitForPageSessionJoin(
      pageSessionId,
      pageKey,
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

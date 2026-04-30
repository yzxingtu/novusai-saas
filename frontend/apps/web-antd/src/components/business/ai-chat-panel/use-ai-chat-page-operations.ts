import type { PageContext } from '#/api/shared/ai-chat';

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

export function hasInteractivePageContext(
  pageContext?: null | PageContext,
): boolean {
  void pageContext;
  return false;
}

export function createAIChatPageOperations(
  options: UseAIChatPageOperationsOptions,
) {
  void options;

  async function ensurePageOperationChannelReady(): Promise<boolean> {
    return true;
  }

  return {
    ensurePageOperationChannelReady,
    hasPageOperations: hasInteractivePageContext,
  };
}

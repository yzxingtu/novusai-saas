import type { IdentityDetail, IdentityDetailRequest } from './identity-detail';

import { reactive, readonly } from 'vue';

import { loadIdentityDetail } from './identity-detail';

interface IdentityDetailDialogState {
  detail: IdentityDetail | null;
  error: null | string;
  loading: boolean;
  open: boolean;
  request: IdentityDetailRequest | null;
}

const state = reactive<IdentityDetailDialogState>({
  detail: null,
  error: null,
  loading: false,
  open: false,
  request: null,
});

let activeRequestId = 0;

function normalizeError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return '';
}

export async function openIdentityDetailDialog(
  request: IdentityDetailRequest,
): Promise<void> {
  const requestId = ++activeRequestId;
  state.open = true;
  state.loading = true;
  state.error = null;
  state.request = request;
  state.detail = request.fallback
    ? await loadIdentityDetail({ ...request, disableFetch: true })
    : null;

  try {
    const detail = await loadIdentityDetail(request);
    if (requestId !== activeRequestId) {
      return;
    }
    state.detail = detail;
  } catch (error) {
    if (requestId !== activeRequestId) {
      return;
    }
    state.error = normalizeError(error);
  } finally {
    if (requestId === activeRequestId) {
      state.loading = false;
    }
  }
}

export function closeIdentityDetailDialog(): void {
  state.open = false;
}

export function useIdentityDetailDialog() {
  return {
    closeIdentityDetailDialog,
    identityDetailDialogState: readonly(state),
    openIdentityDetailDialog,
  };
}

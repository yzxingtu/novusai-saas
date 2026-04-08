import { onScopeDispose, watch } from 'vue';

import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-slide-panel';
import {
  fillRuntimeForm,
  getRuntimeFormState,
  getRuntimeSnapshot,
  listRuntimeInteractables,
  readRuntimeRegion,
  readRuntimeTable,
  setRuntimeFormField,
  submitRuntimeForm,
} from '#/components/business/ai-runtime/runtime-bridge';
import {
  UIActionExecutor,
  type UIActionDiff,
} from '#/components/business/ai-runtime/ui-action-executor';
import { tAiRuntime } from '#/components/business/ai-runtime/i18n';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { getSocketTraceId } from '#/composables/use-socketio';
import { router } from '#/router';
import { useSocketIOStore } from '#/store';

const REJOIN_RETRY_DELAYS_MS = [0, 400, 1200] as const;
const RECENT_RESULT_TTL_MS = 90_000;

type UIActionType =
  | 'ui_click'
  | 'ui_open_surface'
  | 'ui_get_form_state'
  | 'ui_set_field'
  | 'ui_fill_form'
  | 'ui_submit_form';

let currentJoinedRoom = '';
let uiEpochValue = 0;
let lastJoinedSessionAck: null | {
  pageKey: string;
  pageSessionId: string;
  receivedAt: number;
} = null;

const inFlightRequests = new Map<string, Promise<void>>();
const recentRequestResults = new Map<string, { eventName: string; payload: Record<string, unknown> }>();
const recentRequestTimers = new Map<string, ReturnType<typeof setTimeout>>();

export interface UIActionInvokeEvent {
  action_type: UIActionType;
  confirm?: boolean;
  fields?: Record<string, unknown>;
  form_session_id?: string;
  invoke_id: string;
  surface?: {
    kind?: 'drawer' | 'dropdown' | 'modal' | 'page' | 'popover';
    locator?: string;
    title?: string;
  };
  target_locator?: string;
  trace_id?: string;
  value?: unknown;
  wait_timeout_ms?: number;
  field_name?: string;
}

export interface UIActionResultEvent {
  data?: Record<string, unknown>;
  diff?: UIActionDiff;
  error?: string;
  error_type?: string;
  invoke_id: string;
  message: string;
  success: boolean;
  trace_id?: string;
}

export interface UIActionPageSessionJoinedEvent {
  page_key: string;
  page_session_id: string;
  trace_id?: string;
}

interface UISnapshotRequestEvent {
  mode?: 'compact' | 'full';
  request_id: string;
  surface_id?: string;
  trace_id?: string;
}

interface UISnapshotResultEvent {
  error?: string;
  error_type?: string;
  request_id: string;
  snapshot?: Record<string, unknown>;
  success: boolean;
  trace_id?: string;
}

interface UIReadRegionRequestEvent {
  region_locator?: string;
  request_id: string;
  trace_id?: string;
}

interface UIReadTableRequestEvent {
  page?: number;
  page_size?: number;
  request_id: string;
  table_locator?: string;
  trace_id?: string;
}

interface UIListInteractablesRequestEvent {
  request_id: string;
  surface_id?: string;
  trace_id?: string;
}

type GenericSocketResult = Record<string, unknown>;

function requestCacheKey(eventName: string, requestId: string): string {
  return `${eventName}:${requestId}`;
}

function clearRecentResultTimer(cacheKey: string): void {
  const timerId = recentRequestTimers.get(cacheKey);
  if (timerId !== undefined) {
    clearTimeout(timerId);
    recentRequestTimers.delete(cacheKey);
  }
}

function clearTrackedInvocations(): void {
  inFlightRequests.clear();
  for (const timer of recentRequestTimers.values()) {
    clearTimeout(timer);
  }
  recentRequestTimers.clear();
  recentRequestResults.clear();
}

function rememberResult(
  eventName: string,
  requestId: string,
  payload: Record<string, unknown>,
): void {
  const cacheKey = requestCacheKey(eventName, requestId);
  clearRecentResultTimer(cacheKey);
  recentRequestResults.set(cacheKey, { eventName, payload });
  const timerId = setTimeout(() => {
    recentRequestResults.delete(cacheKey);
    recentRequestTimers.delete(cacheKey);
  }, RECENT_RESULT_TTL_MS);
  recentRequestTimers.set(cacheKey, timerId);
}

function replayResult(
  socketIOStore: ReturnType<typeof useSocketIOStore>,
  eventName: string,
  requestId: string,
): boolean {
  const cached = recentRequestResults.get(requestCacheKey(eventName, requestId));
  if (!cached) {
    return false;
  }
  socketIOStore.emit(cached.eventName, cached.payload);
  return true;
}

function rememberPageSessionAck(pageSessionId: string, pageKey: string): void {
  lastJoinedSessionAck = {
    pageKey,
    pageSessionId,
    receivedAt: Date.now(),
  };
}

function emitCachedResult(
  socketIOStore: ReturnType<typeof useSocketIOStore>,
  eventName: string,
  requestId: string,
  payload: Record<string, unknown>,
): void {
  rememberResult(eventName, requestId, payload);
  socketIOStore.emit(eventName, payload);
}

function buildTraceId(traceId?: string): string {
  return traceId || getSocketTraceId();
}

export function hasJoinedPageSession(
  pageSessionId: string,
  pageKey: string,
): boolean {
  return (
    lastJoinedSessionAck?.pageSessionId === pageSessionId &&
    lastJoinedSessionAck?.pageKey === pageKey
  );
}

export async function waitForPageSessionJoin(
  pageSessionId: string,
  pageKey: string,
  timeoutMs = 1500,
  pollMs = 50,
): Promise<boolean> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (hasJoinedPageSession(pageSessionId, pageKey)) {
      return true;
    }
    await new Promise<void>((resolve) => {
      setTimeout(resolve, pollMs);
    });
  }
  return hasJoinedPageSession(pageSessionId, pageKey);
}

export function useUIActionChannel(): void {
  const socketIOStore = useSocketIOStore();
  const resolveCurrentPageKey = () =>
    resolveRoutePageKey(router.currentRoute.value, window.location.pathname);
  const actionExecutor = new UIActionExecutor({
    getPageKey: resolveCurrentPageKey,
    getUiEpoch: () => uiEpochValue,
    setUiEpoch: (nextEpoch) => {
      uiEpochValue = nextEpoch;
    },
  });

  async function runDeduped(
    cacheEventName: string,
    requestId: string,
    run: () => Promise<Record<string, unknown>>,
  ): Promise<void> {
    if (replayResult(socketIOStore, cacheEventName, requestId)) {
      return;
    }

    const cacheKey = requestCacheKey(cacheEventName, requestId);
    const inFlight = inFlightRequests.get(cacheKey);
    if (inFlight) {
      await inFlight;
      replayResult(socketIOStore, cacheEventName, requestId);
      return;
    }

    const promise = (async () => {
      const payload = await run();
      emitCachedResult(socketIOStore, cacheEventName, requestId, payload);
    })();
    inFlightRequests.set(cacheKey, promise);
    try {
      await promise;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  }

  async function handleInvoke(rawData: unknown): Promise<void> {
    const event = rawData as Partial<UIActionInvokeEvent>;
    const invokeId = String(event?.invoke_id || '').trim();
    const actionType = String(event?.action_type || '').trim() as UIActionType;
    if (!invokeId || !actionType) {
      return;
    }

    const normalizedEvent: UIActionInvokeEvent = {
      action_type: actionType,
      confirm: Boolean(event.confirm),
      invoke_id: invokeId,
      ...(event.fields && typeof event.fields === 'object'
        ? { fields: event.fields as Record<string, unknown> }
        : {}),
      ...(event.form_session_id
        ? { form_session_id: String(event.form_session_id) }
        : {}),
      ...(event.surface ? { surface: event.surface } : {}),
      ...(event.target_locator
        ? { target_locator: String(event.target_locator) }
        : {}),
      ...(event.trace_id ? { trace_id: String(event.trace_id) } : {}),
      ...(typeof event.value !== 'undefined' ? { value: event.value } : {}),
      ...(typeof event.wait_timeout_ms === 'number'
        ? { wait_timeout_ms: event.wait_timeout_ms }
        : {}),
      ...(event.field_name ? { field_name: String(event.field_name) } : {}),
    };

    await runDeduped('ui_action_result', invokeId, async () => {
      try {
        if (actionType === 'ui_click' || actionType === 'ui_open_surface') {
          const result = await actionExecutor.execute({
            ...normalizedEvent,
            action_type: actionType,
          });
          return {
            ...(result.data ? { data: result.data } : {}),
            ...(result.diff ? { diff: result.diff } : {}),
            ...(result.error ? { error: result.error } : {}),
            ...(result.error_type ? { error_type: result.error_type } : {}),
            invoke_id: invokeId,
            message: result.message,
            success: result.success,
            trace_id: buildTraceId(normalizedEvent.trace_id),
          } satisfies UIActionResultEvent;
        }

        if (actionType === 'ui_get_form_state') {
          const result = await getRuntimeFormState(normalizedEvent.form_session_id);
          return {
            ...(result.data ? { data: result.data } : {}),
            ...(result.error ? { error: result.error } : {}),
            ...(result.error_type ? { error_type: result.error_type } : {}),
            invoke_id: invokeId,
            message: result.message,
            success: result.success,
            trace_id: buildTraceId(normalizedEvent.trace_id),
          } satisfies UIActionResultEvent;
        }

        if (actionType === 'ui_set_field') {
          const result = await setRuntimeFormField({
            fieldName: String(normalizedEvent.field_name || '').trim(),
            formSessionId: normalizedEvent.form_session_id,
            value: normalizedEvent.value,
          });
          return {
            ...(result.data ? { data: result.data } : {}),
            ...(result.error ? { error: result.error } : {}),
            ...(result.error_type ? { error_type: result.error_type } : {}),
            invoke_id: invokeId,
            message: result.message,
            success: result.success,
            trace_id: buildTraceId(normalizedEvent.trace_id),
          } satisfies UIActionResultEvent;
        }

        if (actionType === 'ui_fill_form') {
          const result = await fillRuntimeForm({
            fields: normalizedEvent.fields ?? {},
            formSessionId: normalizedEvent.form_session_id,
          });
          return {
            ...(result.data ? { data: result.data } : {}),
            ...(result.error ? { error: result.error } : {}),
            ...(result.error_type ? { error_type: result.error_type } : {}),
            invoke_id: invokeId,
            message: result.message,
            success: result.success,
            trace_id: buildTraceId(normalizedEvent.trace_id),
          } satisfies UIActionResultEvent;
        }

        if (actionType === 'ui_submit_form') {
          const result = await submitRuntimeForm({
            confirm: normalizedEvent.confirm,
            formSessionId: normalizedEvent.form_session_id,
          });
          return {
            ...(result.data ? { data: result.data } : {}),
            ...(result.error ? { error: result.error } : {}),
            ...(result.error_type ? { error_type: result.error_type } : {}),
            invoke_id: invokeId,
            message: result.message,
            success: result.success,
            trace_id: buildTraceId(normalizedEvent.trace_id),
          } satisfies UIActionResultEvent;
        }

        return {
          error: tAiRuntime('unsupportedUiAction', { actionType }),
          error_type: 'invalid_action_type',
          invoke_id: invokeId,
          message: tAiRuntime('actionExecutionFailed'),
          success: false,
          trace_id: buildTraceId(normalizedEvent.trace_id),
        } satisfies UIActionResultEvent;
      } catch (error) {
        return {
          error: error instanceof Error ? error.message : String(error),
          error_type: 'internal_error',
          invoke_id: invokeId,
          message: tAiRuntime('actionExecutionFailed'),
          success: false,
          trace_id: buildTraceId(normalizedEvent.trace_id),
        } satisfies UIActionResultEvent;
      }
    });
  }

  async function handleSnapshotRequest(rawData: unknown): Promise<void> {
    const event = rawData as Partial<UISnapshotRequestEvent>;
    const requestId = String(event?.request_id || '').trim();
    if (!requestId) {
      return;
    }
    await runDeduped('ui_snapshot_result', requestId, async () => {
      try {
        return {
          request_id: requestId,
          snapshot: getRuntimeSnapshot(event.mode === 'full' ? 'full' : 'compact') as unknown as Record<string, unknown>,
          success: true,
          trace_id: buildTraceId(event.trace_id),
        } satisfies UISnapshotResultEvent;
      } catch (error) {
        return {
          error: tAiRuntime('snapshotFailed'),
          error_type: 'snapshot_failed',
          request_id: requestId,
          success: false,
          trace_id: buildTraceId(event.trace_id),
        } satisfies UISnapshotResultEvent;
      }
    });
  }

  async function handleReadRegionRequest(rawData: unknown): Promise<void> {
    const event = rawData as Partial<UIReadRegionRequestEvent>;
    const requestId = String(event?.request_id || '').trim();
    const locator = String(event?.region_locator || '').trim();
    if (!requestId || !locator) {
      return;
    }
    await runDeduped('ui_read_region_result', requestId, async () => {
      try {
        return {
          data: readRuntimeRegion(locator),
          request_id: requestId,
          success: true,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      } catch (error) {
        return {
          error: tAiRuntime('readRegionFailed'),
          error_type: 'read_region_failed',
          request_id: requestId,
          success: false,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      }
    });
  }

  async function handleReadTableRequest(rawData: unknown): Promise<void> {
    const event = rawData as Partial<UIReadTableRequestEvent>;
    const requestId = String(event?.request_id || '').trim();
    const locator = String(event?.table_locator || '').trim();
    if (!requestId || !locator) {
      return;
    }
    await runDeduped('ui_read_table_result', requestId, async () => {
      try {
        return {
          data: readRuntimeTable({
            locator,
            page: event.page,
            pageSize: event.page_size,
          }),
          request_id: requestId,
          success: true,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      } catch (error) {
        return {
          error: tAiRuntime('readTableFailed'),
          error_type: 'read_table_failed',
          request_id: requestId,
          success: false,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      }
    });
  }

  async function handleListInteractablesRequest(rawData: unknown): Promise<void> {
    const event = rawData as Partial<UIListInteractablesRequestEvent>;
    const requestId = String(event?.request_id || '').trim();
    if (!requestId) {
      return;
    }
    await runDeduped('ui_list_interactables_result', requestId, async () => {
      try {
        return {
          data: listRuntimeInteractables(
            event.surface_id ? String(event.surface_id) : undefined,
          ),
          request_id: requestId,
          success: true,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      } catch (error) {
        return {
          error: tAiRuntime('listInteractablesFailed'),
          error_type: 'list_interactables_failed',
          request_id: requestId,
          success: false,
          trace_id: buildTraceId(event.trace_id),
        } satisfies GenericSocketResult;
      }
    });
  }

  function handlePageSessionJoined(rawData: unknown): void {
    const event = rawData as Partial<UIActionPageSessionJoinedEvent>;
    const pageSessionId = String(event.page_session_id || '').trim();
    const pageKey = normalizePageKey(String(event.page_key || '').trim());
    if (!pageSessionId || !pageKey) {
      return;
    }
    rememberPageSessionAck(pageSessionId, pageKey);
  }

  function leavePageSessionRoom() {
    if (!currentJoinedRoom) {
      return;
    }
    socketIOStore.emit('page_session_leave', {
      page_session_id: currentJoinedRoom,
      trace_id: getSocketTraceId(),
    });
    currentJoinedRoom = '';
  }

  function joinPageSessionRoom(force = false): void {
    const pageSessionId = getActivePageSessionId();
    if (!pageSessionId || !socketIOStore.isConnected) {
      return;
    }
    if (!force && currentJoinedRoom === pageSessionId) {
      return;
    }
    if (currentJoinedRoom && currentJoinedRoom !== pageSessionId) {
      leavePageSessionRoom();
    }

    socketIOStore.emit('page_session_join', {
      page_key: resolveCurrentPageKey(),
      page_session_id: pageSessionId,
      trace_id: getSocketTraceId(),
    });
    currentJoinedRoom = pageSessionId;
  }

  let rejoinRetryTimers: Array<ReturnType<typeof setTimeout>> = [];

  function clearRejoinRetryTimers() {
    for (const timerId of rejoinRetryTimers) {
      window.clearTimeout(timerId);
    }
    rejoinRetryTimers = [];
  }

  function scheduleJoinRetries() {
    clearRejoinRetryTimers();
    if (!socketIOStore.isConnected || !getActivePageSessionId()) {
      return;
    }
    rejoinRetryTimers = REJOIN_RETRY_DELAYS_MS.map((delay) =>
      setTimeout(() => {
        joinPageSessionRoom(true);
      }, delay),
    );
  }

  function handleWindowFocus(): void {
    joinPageSessionRoom(true);
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      joinPageSessionRoom(true);
    }
  }

  socketIOStore.registerHandler(
    'ui_action_invoke',
    handleInvoke as (data: unknown) => void,
  );
  socketIOStore.registerHandler(
    'ui_snapshot_request',
    handleSnapshotRequest as (data: unknown) => void,
  );
  socketIOStore.registerHandler(
    'ui_read_region_request',
    handleReadRegionRequest as (data: unknown) => void,
  );
  socketIOStore.registerHandler(
    'ui_read_table_request',
    handleReadTableRequest as (data: unknown) => void,
  );
  socketIOStore.registerHandler(
    'ui_list_interactables_request',
    handleListInteractablesRequest as (data: unknown) => void,
  );
  socketIOStore.registerHandler(
    'page_session_joined',
    handlePageSessionJoined as (data: unknown) => void,
  );

  window.addEventListener('focus', handleWindowFocus);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  onScopeDispose(() => {
    clearRejoinRetryTimers();
    window.removeEventListener('focus', handleWindowFocus);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    leavePageSessionRoom();
    clearTrackedInvocations();
    lastJoinedSessionAck = null;
    socketIOStore.unregisterHandler(
      'ui_action_invoke',
      handleInvoke as (data: unknown) => void,
    );
    socketIOStore.unregisterHandler(
      'ui_snapshot_request',
      handleSnapshotRequest as (data: unknown) => void,
    );
    socketIOStore.unregisterHandler(
      'ui_read_region_request',
      handleReadRegionRequest as (data: unknown) => void,
    );
    socketIOStore.unregisterHandler(
      'ui_read_table_request',
      handleReadTableRequest as (data: unknown) => void,
    );
    socketIOStore.unregisterHandler(
      'ui_list_interactables_request',
      handleListInteractablesRequest as (data: unknown) => void,
    );
    socketIOStore.unregisterHandler(
      'page_session_joined',
      handlePageSessionJoined as (data: unknown) => void,
    );
  });

  watch(
    () => socketIOStore.isConnected,
    (connected) => {
      if (!connected) {
        clearRejoinRetryTimers();
        clearTrackedInvocations();
        currentJoinedRoom = '';
        lastJoinedSessionAck = null;
        return;
      }
      currentJoinedRoom = '';
      scheduleJoinRetries();
    },
    { immediate: true },
  );

  watch(
    () => getActivePageSessionId(),
    (newId, oldId) => {
      clearRejoinRetryTimers();
      if (oldId && newId !== oldId && currentJoinedRoom === oldId) {
        leavePageSessionRoom();
      }
      if (newId) {
        scheduleJoinRetries();
      }
    },
  );
}

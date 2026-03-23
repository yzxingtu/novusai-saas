/**
 * Page operation WebSocket channel
 * 页面操作 WebSocket 通道
 *
 * Establishes a bidirectional Socket.IO channel for page_operation events:
 * 建立 page_operation 事件类型的 Socket.IO 双向通道：
 * - Sends page_session_join to join page_session_id room after connection / 连接后加入房间
 * - Listens for page_operation_invoke and executes operations / 监听并执行操作
 * - Sends back results via page_operation_result / 回传执行结果
 * - Mutation operations (readonly=false) show confirmation dialog / 变更操作弹出确认框
 * - Auto-updates room on route change / 路由变化时自动更新房间
 *
 * Call once in layout component. Watchers and handler are recreated on remount
 * so room join/switch logic works correctly after layout unmount/remount.
 * 在 layout 组件中调用一次。重新挂载时会重建 watchers 和 handler，确保房间加入/切换逻辑正确。
 */

import { onScopeDispose, watch } from 'vue';

import { $t } from '@vben/locales';

import { normalizePageKey } from '#/components/business/ai-slide-panel';
import {
  executePageOperation,
  findPageOperation,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';
import { currentPageAIExecutionPolicy } from '#/composables/use-ai-page-policy';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { useSocketIOStore } from '#/store';
import { useAIPanelStore } from '#/store/shared/ai-panel';
import { filterPageOperationsByPolicy } from '#/utils/ai-page-capabilities';
import { getSocketTraceId } from '#/composables/use-socketio';

/** Operation invoke event from backend / 后端下发的操作调用事件 */
export interface PageOperationInvokeEvent {
  /** Unique operation invoke ID (for result matching) / 操作调用唯一 ID */
  invoke_id: string;
  /** Page identifier (pageContextKey) / 页面标识 */
  page_key: string;
  /** Operation name / 操作名称 */
  operation_name: string;
  /** Operation parameters / 操作参数 */
  params: Record<string, unknown>;
  /** Whether user confirmation is needed (for readonly=false operations) / 是否需要用户确认 */
  requires_confirmation: boolean;
  /** Tool call ID for associating confirmation card with chat message / 工具调用 ID，用于将确认卡片关联到聊天消息 */
  tool_call_id?: string;
  /** Trace ID supplied by backend invoke (propagated back on result) / 后端传来的 trace_id，回传时优先使用 */
  trace_id?: string;
}

/** Operation result sent back to backend / 回传给后端的操作结果 */
export interface PageOperationResultEvent {
  /** Unique operation invoke ID / 操作调用唯一 ID */
  invoke_id: string;
  /** Whether successful / 是否成功 */
  success: boolean;
  /** Result message / 结果消息 */
  message: string;
  /** Additional data / 附加数据 */
  data?: Record<string, unknown>;
  /** Failure reason type / 失败原因类型 */
  error_type?: string;
  /** Trace ID for correlation / 用于链路关联的 trace_id */
  trace_id?: string;
}

/** Currently joined page_session room (per composable instance) / 当前已加入的 page_session room */
let currentJoinedRoom = '';
/** Retry rejoin after reconnect/hot-reload races / 连接恢复后补发重入，覆盖热更新竞态 */
const REJOIN_RETRY_DELAYS_MS = [0, 400, 1200] as const;
const RECENT_INVOKE_RESULT_TTL_MS = 90_000;
const recentInvokeResults = new Map<string, PageOperationResultEvent>();
const recentInvokeResultTimers = new Map<
  string,
  ReturnType<typeof setTimeout>
>();
const inFlightInvocations = new Map<string, Promise<void>>();

/**
 * Agent Loop: track recently confirmed mutation operations per page key / 按页面 key 跟踪最近确认的变更操作
 * When user confirms create_record/edit_record, subsequent fill_form
 * operations on the same page within CHAIN_CONFIRM_TTL_MS are auto-approved.
 */
const CHAIN_CONFIRM_TTL_MS = 60_000;
const _chainConfirmed = new Map<string, number>();

function markChainConfirmed(pageKey: string): void {
  _chainConfirmed.set(pageKey, Date.now());
}

function isChainConfirmed(pageKey: string): boolean {
  const ts = _chainConfirmed.get(pageKey);
  if (!ts) return false;
  if (Date.now() - ts > CHAIN_CONFIRM_TTL_MS) {
    _chainConfirmed.delete(pageKey);
    return false;
  }
  return true;
}

const CHAIN_TRIGGER_OPS = new Set(['create_record', 'edit_record']);
const CHAIN_AUTO_OPS = new Set(['fill_form']);

function clearChainConfirmed(): void {
  _chainConfirmed.clear();
}

function clearRecentInvokeResultTimer(invokeId: string): void {
  const timerId = recentInvokeResultTimers.get(invokeId);
  if (timerId !== undefined) {
    clearTimeout(timerId);
    recentInvokeResultTimers.delete(invokeId);
  }
}

function rememberInvokeResult(payload: PageOperationResultEvent): void {
  clearRecentInvokeResultTimer(payload.invoke_id);
  recentInvokeResults.set(payload.invoke_id, payload);
  const timerId = setTimeout(() => {
    recentInvokeResults.delete(payload.invoke_id);
    recentInvokeResultTimers.delete(payload.invoke_id);
  }, RECENT_INVOKE_RESULT_TTL_MS);
  recentInvokeResultTimers.set(payload.invoke_id, timerId);
}

function replayInvokeResult(
  socketIOStore: ReturnType<typeof useSocketIOStore>,
  invokeId: string,
): boolean {
  const payload = recentInvokeResults.get(invokeId);
  if (!payload) return false;
  socketIOStore.emit('page_operation_result', payload);
  return true;
}

function clearTrackedInvocations(): void {
  for (const timerId of recentInvokeResultTimers.values()) {
    clearTimeout(timerId);
  }
  recentInvokeResultTimers.clear();
  recentInvokeResults.clear();
  inFlightInvocations.clear();
}

/**
 * Execute operation and send result back via WebSocket
 * 执行操作并通过 WebSocket 回传结果
 */
function emitResult(
  socketIOStore: ReturnType<typeof useSocketIOStore>,
  invokeId: string,
  result: { success: boolean; message: string; data?: Record<string, unknown> },
  errorType?: string,
  traceId?: string,
): void {
  const resolvedTraceId = traceId || getSocketTraceId();
  const payload = {
    invoke_id: invokeId,
    success: result.success,
    message: result.message,
    data: result.data,
    ...(errorType ? { error_type: errorType } : {}),
    ...(resolvedTraceId ? { trace_id: resolvedTraceId } : {}),
  } satisfies PageOperationResultEvent;
  rememberInvokeResult(payload);
  socketIOStore.emit('page_operation_result', payload);
}

/**
 * Initialize page operation WebSocket channel (call once in layout setup)
 * 初始化页面操作 WebSocket 通道（在 layout setup 中调用一次）
 *
 * Features / 功能:
 * 1. Auto-join page_session_id room after connection / 连接后自动加入房间
 * 2. Auto-switch room on route change / 路由变化时自动切换房间
 * 3. Listen for page_operation_invoke and execute / 监听并执行操作
 * 4. Show confirmation dialog for mutation operations / 变更操作弹出确认框
 * 5. Send back page_operation_result / 回传结果
 */
export function usePageOperationChannel(): void {
  const socketIOStore = useSocketIOStore();

  /**
   * Execute operation and send back result directly
   * 直接执行操作并回传结果
   */
  async function executeAndEmit(
    event: PageOperationInvokeEvent,
  ): Promise<void> {
    const result = await executePageOperation(
      event.page_key,
      event.operation_name,
      event.params || {},
    );
    const errorType = result.success
      ? undefined
      : (result.error_type ?? 'execution_failed');
    emitResult(socketIOStore, event.invoke_id, result, errorType, event.trace_id);
  }

  const aiPanelStore = useAIPanelStore();

  const CONFIRM_TIMEOUT_MS = 60_000;

  /**
   * Request confirmation in AI chat panel, execute after user allows.
   * Forces the panel open and races against a timeout so the promise
   * never hangs indefinitely if the panel fails to render.
   * 在 AI 聊天面板中请求确认，用户允许后执行操作。
   * 强制打开面板并与超时竞争，避免面板无法渲染时 Promise 永久挂起。
   */
  async function confirmAndExecute(
    event: PageOperationInvokeEvent,
    operationLabel: string,
    operationDescription: string,
  ): Promise<void> {
    aiPanelStore.open();

    const confirmPromise = aiPanelStore.requestPageOpConfirmation({
      invokeId: event.invoke_id,
      pageKey: event.page_key,
      operationName: event.operation_name,
      operationLabel,
      operationDescription,
      params: event.params || {},
      toolCallId: event.tool_call_id,
    });

    // null sentinel distinguishes timeout from user-cancel (false) / null 哨兵区分超时与用户取消(false)
    let timerId: ReturnType<typeof setTimeout> | undefined;
    const timeoutPromise = new Promise<null>((resolve) => {
      timerId = setTimeout(() => resolve(null), CONFIRM_TIMEOUT_MS);
    });

    let result: boolean | null;
    try {
      result = await Promise.race([confirmPromise, timeoutPromise]);
    } finally {
      if (timerId !== undefined) clearTimeout(timerId);
    }

    if (result === null) {
      // Timeout: dismiss the lingering confirmation card in the panel / 超时：清理面板中残留的确认卡片
      aiPanelStore.resolvePageOp(event.invoke_id, false);
      emitResult(
        socketIOStore,
        event.invoke_id,
        {
          success: false,
          message: $t('shared.pageOperation.msg.confirmationTimedOut'),
        },
        'timeout',
        event.trace_id,
      );
    } else if (result) {
      if (CHAIN_TRIGGER_OPS.has(event.operation_name)) {
        markChainConfirmed(event.page_key);
      }
      await executeAndEmit(event);
    } else {
      emitResult(
        socketIOStore,
        event.invoke_id,
        {
          success: false,
          message: $t('shared.pageOperation.msg.userCancelled'),
        },
        'user_cancelled',
        event.trace_id,
      );
    }
  }

  // Operation invoke handler / 操作调用处理器
  async function handleInvoke(data: unknown): Promise<void> {
    const event = data as PageOperationInvokeEvent;
    if (!event?.invoke_id || !event?.page_key || !event?.operation_name) {
      return;
    }

    if (replayInvokeResult(socketIOStore, event.invoke_id)) {
      return;
    }

    const inFlight = inFlightInvocations.get(event.invoke_id);
    if (inFlight) {
      await inFlight;
      replayInvokeResult(socketIOStore, event.invoke_id);
      return;
    }

    const run = (async () => {
      try {
        // Find operation registration / 查找操作注册
        const operation = findPageOperation(
          event.page_key,
          event.operation_name,
        );

        const currentPolicy = currentPageAIExecutionPolicy.value;
        const normalizedEventPageKey = normalizePageKey(event.page_key);
        const currentPolicyPageKey = currentPolicy.pageContextKey
          ? normalizePageKey(currentPolicy.pageContextKey)
          : '';
        const activePageKey =
          currentPolicyPageKey || normalizePageKey(window.location.pathname);

        if (activePageKey && normalizedEventPageKey !== activePageKey) {
          emitResult(
            socketIOStore,
            event.invoke_id,
            {
              success: false,
              message: $t('shared.pageOperation.msg.pageKeyMismatch', {
                active: activePageKey,
                requested: normalizedEventPageKey,
              }),
            },
            'page_key_mismatch',
            event.trace_id,
          );
          return;
        }

        if (
          operation &&
          currentPolicyPageKey &&
          currentPolicyPageKey === normalizedEventPageKey
        ) {
          const allowedOperations = filterPageOperationsByPolicy(
            listPageOperations(normalizedEventPageKey),
            currentPolicy,
          );
          const isAllowed = allowedOperations.some(
            (item) => item.name === event.operation_name,
          );
          if (!isAllowed) {
            emitResult(
              socketIOStore,
              event.invoke_id,
              {
                success: false,
                message: $t('shared.pageOperation.msg.operationDisabled', {
                  op: event.operation_name,
                  page: normalizedEventPageKey,
                }),
              },
              'disabled_by_policy',
              event.trace_id,
            );
            return;
          }
        }

        // Unregistered operation → reject / 未注册操作 → 拒绝执行
        if (!operation) {
          emitResult(
            socketIOStore,
            event.invoke_id,
            {
              success: false,
              message: $t('shared.pageOperation.msg.operationNotRegistered', {
                op: event.operation_name,
                page: event.page_key,
              }),
            },
            'not_registered',
            event.trace_id,
          );
          return;
        }

        // Backend explicit requires_confirmation → always show confirmation (overrides readonly/chain) / 后端强制确认语义优先
        if (event.requires_confirmation) {
          let desc = operation.description || '';
          if (event.operation_name === 'replace_content') {
            const contentLen = String(event.params?.content ?? '').length;
            desc = $t('shared.pageOperation.replaceContentConfirm', {
              count: contentLen,
            });
          }
          await confirmAndExecute(event, operation.label, desc);
          return;
        }

        // readonly=true → execute directly (no confirmation needed) / 直接执行（无需确认）
        if (operation.readonly) {
          await executeAndEmit(event);
          return;
        }

        // Agent Loop: auto-approve chain-follow operations (e.g. fill_form after create_record) / 链式自动确认仅作附加优化
        if (
          CHAIN_AUTO_OPS.has(event.operation_name) &&
          isChainConfirmed(event.page_key)
        ) {
          await executeAndEmit(event);
          return;
        }

        // readonly=false → show confirmation dialog / 弹出确认对话框
        let desc = operation.description || '';
        if (event.operation_name === 'replace_content') {
          const contentLen = String(event.params?.content ?? '').length;
          desc = $t('shared.pageOperation.replaceContentConfirm', {
            count: contentLen,
          });
        }
        await confirmAndExecute(event, operation.label, desc);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        emitResult(
          socketIOStore,
          event.invoke_id,
          {
            success: false,
            message: msg,
          },
          'internal_error',
          event.trace_id,
        );
      }
    })();

    inFlightInvocations.set(event.invoke_id, run);
    try {
      await run;
    } finally {
      inFlightInvocations.delete(event.invoke_id);
    }
  }

  // Register invoke event handler / 注册 invoke 事件处理器
  socketIOStore.registerHandler(
    'page_operation_invoke',
    handleInvoke as (data: unknown) => void,
  );

  function leavePageSessionRoom() {
    if (!currentJoinedRoom) return;
    socketIOStore.emit('page_session_leave', {
      page_session_id: currentJoinedRoom,
      trace_id: getSocketTraceId(),
    });
    clearChainConfirmed();
    currentJoinedRoom = '';
  }

  // Join page_session room / 加入 page_session 房间
  function joinPageSessionRoom(force = false) {
    const pageSessionId = getActivePageSessionId();
    if (!pageSessionId || !socketIOStore.isConnected) return;
    if (!force && currentJoinedRoom === pageSessionId) return;

    if (currentJoinedRoom && currentJoinedRoom !== pageSessionId) {
      leavePageSessionRoom();
    }

    // Join new room / 加入新 room
    const pageKey = normalizePageKey(window.location.pathname);
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
      page_key: pageKey,
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
    if (!socketIOStore.isConnected || !getActivePageSessionId()) return;
    rejoinRetryTimers = REJOIN_RETRY_DELAYS_MS.map((delay) =>
      setTimeout(() => {
        joinPageSessionRoom(true);
      }, delay),
    );
  }

  function handleWindowFocus() {
    joinPageSessionRoom(true);
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'visible') {
      joinPageSessionRoom(true);
    }
  }

  window.addEventListener('focus', handleWindowFocus);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  onScopeDispose(() => {
    clearRejoinRetryTimers();
    window.removeEventListener('focus', handleWindowFocus);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    leavePageSessionRoom();
    clearTrackedInvocations();
    socketIOStore.unregisterHandler(
      'page_operation_invoke',
      handleInvoke as (data: unknown) => void,
    );
  });

  // Join room when connection status changes / 连接状态变化时加入房间
  watch(
    () => socketIOStore.isConnected,
    (connected) => {
      if (connected) {
        currentJoinedRoom = '';
        scheduleJoinRetries();
      } else {
        clearRejoinRetryTimers();
        clearChainConfirmed();
        clearTrackedInvocations();
        currentJoinedRoom = '';
      }
    },
    { immediate: true },
  );

  // Switch room when page_session_id changes (more reliable than watch route.path + setTimeout) / page_session_id 变化时切换房间
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

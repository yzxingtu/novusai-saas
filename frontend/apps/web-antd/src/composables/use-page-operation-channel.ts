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
 * Call once in layout component / 在 layout 组件中调用一次即可。
 */

import { watch } from 'vue';

import {
  executePageOperation,
  findPageOperation,
} from '#/components/business/ai-slide-panel/page-operation-registry';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { useSocketIOStore } from '#/store';
import { useAIPanelStore } from '#/store/shared/ai-panel';

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
}

/** Currently joined page_session room / 当前已加入的 page_session room */
let currentJoinedRoom = '';

/** Prevent duplicate handler registration on layout remount / 防止 layout 重新挂载时重复注册 */
let _initialized = false;

/**
 * Agent Loop: track recently confirmed mutation operations per page key.
 * When user confirms create_record/edit_record, subsequent fill_form
 * operations on the same page within CHAIN_CONFIRM_TTL_MS are auto-approved.
 */
const CHAIN_CONFIRM_TTL_MS = 30_000;
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

/**
 * Execute operation and send result back via WebSocket
 * 执行操作并通过 WebSocket 回传结果
 */
function emitResult(
  socketIOStore: ReturnType<typeof useSocketIOStore>,
  invokeId: string,
  result: { success: boolean; message: string; data?: Record<string, unknown> },
  errorType?: string,
): void {
  socketIOStore.emit('page_operation_result', {
    invoke_id: invokeId,
    success: result.success,
    message: result.message,
    data: result.data,
    ...(errorType ? { error_type: errorType } : {}),
  } satisfies PageOperationResultEvent);
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
  if (_initialized) return;
  _initialized = true;

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
    emitResult(
      socketIOStore,
      event.invoke_id,
      result,
      result.success ? undefined : 'execution_failed',
    );
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
    });

    // null sentinel distinguishes timeout from user-cancel (false) / null 哨兵区分超时与用户取消(false)
    const timeoutPromise = new Promise<null>((resolve) => {
      setTimeout(() => resolve(null), CONFIRM_TIMEOUT_MS);
    });

    const result = await Promise.race([confirmPromise, timeoutPromise]);

    if (result === null) {
      // Timeout: dismiss the lingering confirmation card in the panel / 超时：清理面板中残留的确认卡片
      aiPanelStore.resolvePageOp(event.invoke_id, false);
      emitResult(socketIOStore, event.invoke_id, {
        success: false,
        message: 'Confirmation timed out',
      }, 'timeout');
    } else if (result) {
      if (CHAIN_TRIGGER_OPS.has(event.operation_name)) {
        markChainConfirmed(event.page_key);
      }
      await executeAndEmit(event);
    } else {
      emitResult(socketIOStore, event.invoke_id, {
        success: false,
        message: 'User cancelled the operation',
      }, 'user_cancelled');
    }
  }

  // Operation invoke handler / 操作调用处理器
  async function handleInvoke(data: unknown): Promise<void> {
    const event = data as PageOperationInvokeEvent;
    if (!event?.invoke_id || !event?.page_key || !event?.operation_name) {
      return;
    }

    // Find operation registration / 查找操作注册
    const operation = findPageOperation(
      event.page_key,
      event.operation_name,
    );

    // Unregistered operation → reject / 未注册操作 → 拒绝执行
    if (!operation) {
      emitResult(socketIOStore, event.invoke_id, {
        success: false,
        message: `Operation '${event.operation_name}' is not registered on page '${event.page_key}'`,
      }, 'not_registered');
      return;
    }

    // readonly=true → execute directly (no confirmation needed) / 直接执行（无需确认）
    if (operation.readonly) {
      await executeAndEmit(event);
      return;
    }

    // Agent Loop: auto-approve chain-follow operations (e.g. fill_form after create_record)
    if (
      CHAIN_AUTO_OPS.has(event.operation_name) &&
      isChainConfirmed(event.page_key)
    ) {
      await executeAndEmit(event);
      return;
    }

    // readonly=false → show confirmation dialog / 弹出确认对话框
    confirmAndExecute(
      event,
      operation.label,
      operation.description || '',
    );
  }

  // Register invoke event handler / 注册 invoke 事件处理器
  socketIOStore.registerHandler(
    'page_operation_invoke',
    handleInvoke as (data: unknown) => void,
  );

  // Join page_session room / 加入 page_session 房间
  function joinPageSessionRoom() {
    const pageSessionId = getActivePageSessionId();
    if (!pageSessionId || !socketIOStore.isConnected) return;
    if (currentJoinedRoom === pageSessionId) return;

    // Leave old room / 离开旧 room
    if (currentJoinedRoom) {
      socketIOStore.emit('page_session_leave', {
        page_session_id: currentJoinedRoom,
      });
    }

    // Join new room / 加入新 room
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
    });
    currentJoinedRoom = pageSessionId;
  }

  // Join room when connection status changes / 连接状态变化时加入房间
  watch(
    () => socketIOStore.isConnected,
    (connected) => {
      if (connected) {
        currentJoinedRoom = '';
        joinPageSessionRoom();
      } else {
        currentJoinedRoom = '';
      }
    },
    { immediate: true },
  );

  // Switch room when page_session_id changes (more reliable than watch route.path + setTimeout) / page_session_id 变化时切换房间
  watch(
    () => getActivePageSessionId(),
    (newId) => {
      if (newId) {
        joinPageSessionRoom();
      }
    },
  );
}

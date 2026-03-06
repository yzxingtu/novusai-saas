/**
 * 页面操作 WebSocket 通道
 *
 * 建立 page_operation 事件类型的 Socket.IO 双向通道：
 * - 连接后发送 page_session_join 加入 page_session_id 房间
 * - 监听 page_operation_invoke 事件，执行对应操作
 * - 通过 page_operation_result 回传执行结果
 * - 变更操作（readonly=false）弹出确认对话框，用户确认后才执行
 * - 路由变化时自动更新房间
 *
 * 在 layout 组件中调用一次即可。
 */

import { watch } from 'vue';

import { Modal } from 'ant-design-vue';

import {
  executePageOperation,
  findPageOperation,
} from '#/components/business/ai-slide-panel/page-operation-registry';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { useSocketIOStore } from '#/store';

/** 后端下发的操作调用事件 */
export interface PageOperationInvokeEvent {
  /** 操作调用唯一 ID（用于回传结果匹配） */
  invoke_id: string;
  /** 页面标识（pageContextKey） */
  page_key: string;
  /** 操作名称 */
  operation_name: string;
  /** 操作参数 */
  params: Record<string, unknown>;
  /** 是否需要用户确认（readonly=false 的操作） */
  requires_confirmation: boolean;
}

/** 回传给后端的操作结果 */
export interface PageOperationResultEvent {
  /** 操作调用唯一 ID */
  invoke_id: string;
  /** 是否成功 */
  success: boolean;
  /** 结果消息 */
  message: string;
  /** 附加数据 */
  data?: Record<string, unknown>;
  /** 失败原因类型 */
  error_type?: string;
}

/** 当前已加入的 page_session room */
let currentJoinedRoom = '';

/** 防止 layout 重新挂载时重复注册 handler */
let _initialized = false;

/**
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
 * 初始化页面操作 WebSocket 通道（在 layout setup 中调用一次）
 *
 * 功能：
 * 1. 连接后自动 join page_session_id 房间
 * 2. 路由变化时自动切换房间
 * 3. 监听 page_operation_invoke 并执行操作
 * 4. 变更操作弹出确认对话框
 * 5. 回传 page_operation_result
 */
export function usePageOperationChannel(): void {
  if (_initialized) return;
  _initialized = true;

  const socketIOStore = useSocketIOStore();

  /**
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

  /**
   * 弹出确认对话框，用户确认后执行操作
   */
  function confirmAndExecute(
    event: PageOperationInvokeEvent,
    operationLabel: string,
    operationDescription: string,
  ): void {
    Modal.confirm({
      title: $t('shared.pageOperation.confirmTitle'),
      content: operationDescription
        ? $t('shared.pageOperation.confirmContentWithDesc', {
            operation: operationLabel,
            description: operationDescription,
          })
        : $t('shared.pageOperation.confirmContent', {
            operation: operationLabel,
          }),
      okText: $t('shared.pageOperation.confirmOk'),
      cancelText: $t('shared.pageOperation.confirmCancel'),
      onOk: async () => {
        await executeAndEmit(event);
      },
      onCancel: () => {
        emitResult(socketIOStore, event.invoke_id, {
          success: false,
          message: 'User cancelled the operation',
        }, 'user_cancelled');
      },
    });
  }

  // 操作调用处理器
  async function handleInvoke(data: unknown): Promise<void> {
    const event = data as PageOperationInvokeEvent;
    if (!event?.invoke_id || !event?.page_key || !event?.operation_name) {
      return;
    }

    // 查找操作注册
    const operation = findPageOperation(
      event.page_key,
      event.operation_name,
    );

    // 未注册操作 → 拒绝执行
    if (!operation) {
      emitResult(socketIOStore, event.invoke_id, {
        success: false,
        message: `Operation '${event.operation_name}' is not registered on page '${event.page_key}'`,
      }, 'not_registered');
      return;
    }

    // readonly=true → 直接执行（无需确认）
    if (operation.readonly) {
      await executeAndEmit(event);
      return;
    }

    // readonly=false → 弹出确认对话框
    confirmAndExecute(
      event,
      operation.label,
      operation.description || '',
    );
  }

  // 注册 invoke 事件处理器
  socketIOStore.registerHandler(
    'page_operation_invoke',
    handleInvoke as (data: unknown) => void,
  );

  // 加入 page_session 房间
  function joinPageSessionRoom() {
    const pageSessionId = getActivePageSessionId();
    if (!pageSessionId || !socketIOStore.isConnected) return;
    if (currentJoinedRoom === pageSessionId) return;

    // 离开旧 room
    if (currentJoinedRoom) {
      socketIOStore.emit('page_session_leave', {
        page_session_id: currentJoinedRoom,
      });
    }

    // 加入新 room
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
    });
    currentJoinedRoom = pageSessionId;
  }

  // 连接状态变化时加入房间
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

  // page_session_id 变化时切换房间（比 watch route.path + setTimeout 更可靠）
  watch(
    () => getActivePageSessionId(),
    (newId) => {
      if (newId) {
        joinPageSessionRoom();
      }
    },
  );
}

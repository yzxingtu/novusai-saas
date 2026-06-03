/**
 * Plugin install/uninstall progress store
 * 插件安装/卸载进度 Store
 *
 * Listens to plugin:install:progress events via Socket.IO
 * to manage real-time install/uninstall progress state.
 * 通过 Socket.IO 监听进度事件，管理安装/卸载的实时进度状态。
 */

import { computed, ref } from 'vue';

import { defineStore } from 'pinia';

import { useSocketIOStore } from '#/store';

/** Progress event name (aligned with backend progress.py) / 进度事件名 */
const EVENT_PLUGIN_PROGRESS = 'plugin:install:progress';

/** Single step status / 单个步骤状态 */
export interface ProgressStep {
  step: string;
  status: 'error' | 'pending' | 'running' | 'success';
  message: string;
  timestamp: string;
}

/** Socket.IO progress event payload / Socket.IO 推送的进度事件 payload */
interface ProgressPayload {
  plugin_name: string;
  action: string;
  step: string;
  status: string;
  message: string;
  progress: number;
  timestamp: string;
}

export const usePluginInstallProgressStore = defineStore(
  'plugin-install-progress',
  () => {
    // ── State / 状态 ──

    /** Current operation type / 当前操作类型 */
    const currentAction = ref<
      'disable' | 'enable' | 'install' | 'uninstall' | null
    >(null);

    /** Current plugin name / 当前插件名 */
    const pluginName = ref('');

    /** Steps list (chronological order) / 步骤列表（按时间顺序） */
    const steps = ref<ProgressStep[]>([]);

    /** Real-time log lines (pip/pnpm/alembic output) / 实时日志行 */
    const logs = ref<string[]>([]);

    /** Current step name / 当前步骤名 */
    const currentStep = ref('');

    /** Overall progress 0-100 / 整体进度 */
    const progress = ref(0);

    /** Whether operation is running / 是否正在执行 */
    const isRunning = ref(false);

    /** Whether operation is complete / 是否已完成 */
    const isComplete = ref(false);

    /** Whether operation has failed / 是否失败 */
    const isFailed = ref(false);

    /** Error message / 错误信息 */
    const errorMessage = ref('');

    /** Whether page reload is needed (after npm dependency install) / 是否需要刷新页面 */
    const needsReload = ref(false);

    /** Whether progress panel is visible / 是否显示进度面板 */
    const visible = ref(false);

    // ── Computed / 计算属性 ──

    const isActive = computed(
      () => isRunning.value || isComplete.value || isFailed.value,
    );

    // ── Internal state / 内部状态 ──

    let _handlerRegistered = false;

    // ── Methods / 方法 ──

    function _handleProgress(data: unknown) {
      const payload = data as ProgressPayload;
      if (!payload?.plugin_name) return;

      // Initialize on first event / 首次收到事件时初始化
      if (!isRunning.value && !isComplete.value) {
        isRunning.value = true;
        pluginName.value = payload.plugin_name;
        currentAction.value = payload.action as
          | 'disable'
          | 'enable'
          | 'install'
          | 'uninstall';
        visible.value = true;
      }

      // Update progress / 更新进度
      progress.value = payload.progress ?? 0;
      currentStep.value = payload.step;

      if (payload.status === 'log') {
        // Sub-process output log line / 子进程输出日志行
        if (payload.message) {
          logs.value.push(payload.message);
          // Limit log lines to prevent memory overflow / 限制日志行数防止内存溢出
          if (logs.value.length > 500) {
            logs.value = logs.value.slice(-300);
          }
        }
        return;
      }

      // Update or add step / 更新或添加步骤
      const existingIdx = steps.value.findIndex((s) => s.step === payload.step);
      const stepData: ProgressStep = {
        step: payload.step,
        status: payload.status as ProgressStep['status'],
        message: payload.message,
        timestamp: payload.timestamp,
      };

      if (existingIdx === -1) {
        steps.value.push(stepData);
      } else {
        steps.value[existingIdx] = stepData;
      }

      // Complete/failed / 完成/失败
      if (payload.step === 'done' && payload.status === 'success') {
        isRunning.value = false;
        isComplete.value = true;
        progress.value = 100;

        // Mark reload needed if npm deps were actually installed (pnpm ran)
        // 如果实际安装了 npm 依赖，标记需要刷新
        if (
          (currentAction.value === 'install' ||
            currentAction.value === 'enable') &&
          steps.value.some(
            (s) =>
              s.step === 'npm' &&
              s.status === 'success' &&
              s.message.startsWith('Installed'),
          )
        ) {
          needsReload.value = true;
        }
      }

      if (payload.step === 'error' || payload.status === 'error') {
        isRunning.value = false;
        isFailed.value = true;
        errorMessage.value = payload.message;
      }
    }

    /** Start listening to Socket.IO progress events / 开始监听 Socket.IO 进度事件 */
    function startListening() {
      if (_handlerRegistered) return;

      const sioStore = useSocketIOStore();
      sioStore.registerHandler(EVENT_PLUGIN_PROGRESS, _handleProgress);
      _handlerRegistered = true;
    }

    /** Stop listening / 停止监听 */
    function stopListening() {
      if (!_handlerRegistered) return;

      const sioStore = useSocketIOStore();
      sioStore.unregisterHandler(EVENT_PLUGIN_PROGRESS, _handleProgress);
      _handlerRegistered = false;
    }

    /** Reset state / 重置状态 */
    function reset() {
      currentAction.value = null;
      pluginName.value = '';
      steps.value = [];
      logs.value = [];
      currentStep.value = '';
      progress.value = 0;
      isRunning.value = false;
      isComplete.value = false;
      isFailed.value = false;
      errorMessage.value = '';
      needsReload.value = false;
      visible.value = false;
    }

    /** Show panel / 显示面板 */
    function show() {
      visible.value = true;
    }

    /**
     * Fallback complete: called when HTTP returns success but Socket.IO event not received
     * 后备完成：HTTP 返回成功但 Socket.IO 事件未到达时调用
     * Normally driven by Socket.IO done event; this is a defensive fallback.
     */
    function markComplete() {
      if (!isComplete.value && !isFailed.value) {
        isRunning.value = false;
        isComplete.value = true;
        progress.value = 100;
      }
    }

    /**
     * Fallback error: called when HTTP returns error but Socket.IO didn't push error event
     * 后备失败：HTTP 返回错误但 Socket.IO 未推送错误事件时调用
     */
    function markError(message: string) {
      if (!isFailed.value) {
        isRunning.value = false;
        isFailed.value = true;
        errorMessage.value = message;
      }
    }

    /**
     * Immediately mark operation as started (provide user feedback before first Socket.IO event)
     * 立即标记操作开始（在 Socket.IO 首条事件到来前给用户反馈）
     * Called after modal close, before HTTP request.
     */
    function startOperation(
      name: string,
      action: 'disable' | 'enable' | 'install' | 'uninstall',
    ) {
      pluginName.value = name;
      currentAction.value = action;
      isRunning.value = true;
      visible.value = true;
    }

    /** Hide panel and reset / 隐藏面板并重置 */
    function hide() {
      visible.value = false;
      if (!isRunning.value) {
        reset();
      }
    }

    return {
      // State / 状态
      currentAction,
      pluginName,
      steps,
      logs,
      currentStep,
      progress,
      isRunning,
      isComplete,
      isFailed,
      errorMessage,
      needsReload,
      visible,
      isActive,

      // Methods / 方法
      startListening,
      stopListening,
      reset,
      show,
      hide,
      startOperation,
      markComplete,
      markError,
    };
  },
);

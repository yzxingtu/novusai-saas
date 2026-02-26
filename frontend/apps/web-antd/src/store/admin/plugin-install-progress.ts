/**
 * 插件安装/卸载进度 Store
 *
 * 通过 Socket.IO 监听 plugin:install:progress 事件，
 * 管理安装/卸载的实时进度状态。
 */

import { computed, ref } from 'vue';

import { defineStore } from 'pinia';

import { useSocketIOStore } from '#/store';

/** 进度事件名（与后端 progress.py 对齐） */
const EVENT_PLUGIN_PROGRESS = 'plugin:install:progress';

/** 单个步骤状态 */
export interface ProgressStep {
  step: string;
  status: 'running' | 'success' | 'error' | 'pending';
  message: string;
  timestamp: string;
}

/** Socket.IO 推送的进度事件 payload */
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
    // ── 状态 ──

    /** 当前操作类型 */
    const currentAction = ref<'install' | 'uninstall' | null>(null);

    /** 当前插件名 */
    const pluginName = ref('');

    /** 步骤列表（按时间顺序） */
    const steps = ref<ProgressStep[]>([]);

    /** 实时日志行（pip/pnpm/alembic 输出） */
    const logs = ref<string[]>([]);

    /** 当前步骤名 */
    const currentStep = ref('');

    /** 整体进度 0-100 */
    const progress = ref(0);

    /** 是否正在执行 */
    const isRunning = ref(false);

    /** 是否已完成 */
    const isComplete = ref(false);

    /** 是否失败 */
    const isFailed = ref(false);

    /** 错误信息 */
    const errorMessage = ref('');

    /** 是否需要刷新页面（npm 依赖安装后） */
    const needsReload = ref(false);

    /** 是否显示进度面板 */
    const visible = ref(false);

    // ── 计算属性 ──

    const isActive = computed(() => isRunning.value || isComplete.value || isFailed.value);

    // ── 内部状态 ──

    let _handlerRegistered = false;

    // ── 方法 ──

    function _handleProgress(data: unknown) {
      const payload = data as ProgressPayload;
      if (!payload?.plugin_name) return;

      // 首次收到事件时初始化
      if (!isRunning.value && !isComplete.value) {
        isRunning.value = true;
        pluginName.value = payload.plugin_name;
        currentAction.value = payload.action as 'install' | 'uninstall';
        visible.value = true;
      }

      // 更新进度
      progress.value = payload.progress ?? 0;
      currentStep.value = payload.step;

      if (payload.status === 'log') {
        // 子进程输出日志行
        if (payload.message) {
          logs.value.push(payload.message);
          // 限制日志行数防止内存溢出
          if (logs.value.length > 500) {
            logs.value = logs.value.slice(-300);
          }
        }
        return;
      }

      // 更新或添加步骤
      const existingIdx = steps.value.findIndex((s) => s.step === payload.step);
      const stepData: ProgressStep = {
        step: payload.step,
        status: payload.status as ProgressStep['status'],
        message: payload.message,
        timestamp: payload.timestamp,
      };

      if (existingIdx >= 0) {
        steps.value[existingIdx] = stepData;
      } else {
        steps.value.push(stepData);
      }

      // 完成/失败
      if (payload.step === 'done' && payload.status === 'success') {
        isRunning.value = false;
        isComplete.value = true;
        progress.value = 100;

        // 如果安装了 npm 依赖，标记需要刷新
        if (
          currentAction.value === 'install' &&
          steps.value.some((s) => s.step === 'npm' && s.status === 'success')
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

    /** 开始监听 Socket.IO 进度事件 */
    function startListening() {
      if (_handlerRegistered) return;

      const sioStore = useSocketIOStore();
      sioStore.registerHandler(EVENT_PLUGIN_PROGRESS, _handleProgress);
      _handlerRegistered = true;
    }

    /** 停止监听 */
    function stopListening() {
      if (!_handlerRegistered) return;

      const sioStore = useSocketIOStore();
      sioStore.unregisterHandler(EVENT_PLUGIN_PROGRESS, _handleProgress);
      _handlerRegistered = false;
    }

    /** 重置状态 */
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

    /** 显示面板 */
    function show() {
      visible.value = true;
    }

    /** 隐藏面板并重置 */
    function hide() {
      visible.value = false;
      if (!isRunning.value) {
        reset();
      }
    }

    return {
      // 状态
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

      // 方法
      startListening,
      stopListening,
      reset,
      show,
      hide,
    };
  },
);

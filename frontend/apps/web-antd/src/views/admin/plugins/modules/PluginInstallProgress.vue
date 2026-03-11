<script lang="ts" setup>
/**
 * Plugin install/uninstall progress drawer
 * 插件安装/卸载进度抽屉
 *
 * Displays install steps, log output, and progress bar via Socket.IO in real-time.
 * 通过 Socket.IO 实时展示安装步骤、日志输出、进度条。
 */
import { nextTick, onUnmounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Drawer, Progress, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { usePluginInstallProgressStore } from '#/store';

const progressStore = usePluginInstallProgressStore();

const logContainer = ref<HTMLElement | null>(null);

/** Step name → display label / 步骤名 → 显示标签 */
function stepLabel(step: string): string {
  const map: Record<string, string> = {
    copy: $t('admin.plugin.progress.step.copy'),
    pip: $t('admin.plugin.progress.step.pip'),
    npm: $t('admin.plugin.progress.step.npm'),
    alembic: $t('admin.plugin.progress.step.alembic'),
    ai_features: $t('admin.plugin.progress.step.ai_features'),
    on_install: $t('admin.plugin.progress.step.on_install'),
    db: $t('admin.plugin.progress.step.db'),
    done: $t('admin.plugin.progress.step.done'),
    error: $t('admin.plugin.progress.step.error'),
    disable: $t('admin.plugin.progress.step.disable'),
    on_uninstall: $t('admin.plugin.progress.step.on_uninstall'),
    cleanup_extensions: $t('admin.plugin.progress.step.cleanup_extensions'),
    cleanup_skills: $t('admin.plugin.progress.step.cleanup_skills'),
    cleanup_ai_features: $t('admin.plugin.progress.step.cleanup_ai'),
    cleanup_db: $t('admin.plugin.progress.step.cleanup_db'),
    cleanup_pip: $t('admin.plugin.progress.step.cleanup_pip'),
    cleanup_npm: $t('admin.plugin.progress.step.cleanup_npm'),
    cleanup_records: $t('admin.plugin.progress.step.cleanup_records'),
    cleanup_files: $t('admin.plugin.progress.step.cleanup_files'),
    extensions: $t('admin.plugin.progress.step.extensions'),
    on_enable: $t('admin.plugin.progress.step.on_enable'),
  };
  return map[step] || step;
}

/** Step status icon / 步骤状态图标 */
function stepIcon(status: string): string {
  switch (status) {
    case 'error': {
      return 'lucide:x-circle';
    }
    case 'running': {
      return 'lucide:loader-2';
    }
    case 'success': {
      return 'lucide:check-circle-2';
    }
    default: {
      return 'lucide:circle';
    }
  }
}

function stepIconClass(status: string): string {
  switch (status) {
    case 'error': {
      return 'text-destructive';
    }
    case 'running': {
      return 'text-primary animate-spin';
    }
    case 'success': {
      return 'text-success';
    }
    default: {
      return 'text-muted-foreground';
    }
  }
}

function progressStatus(): 'active' | 'exception' | 'success' | undefined {
  if (progressStore.isFailed) return 'exception';
  if (progressStore.isComplete) return 'success';
  if (progressStore.isRunning) return 'active';
  return undefined;
}

function handleClose() {
  progressStore.hide();
}

function handleReload() {
  window.location.reload();
}

// Auto-close after 3 seconds on completion (when no page reload needed) / 完成后 3 秒自动关闭（不需要页面刷新时）
let autoCloseTimer: null | ReturnType<typeof setTimeout> = null;
watch(
  () => progressStore.isComplete,
  (complete) => {
    if (complete && !progressStore.needsReload) {
      autoCloseTimer = setTimeout(() => {
        progressStore.hide();
        autoCloseTimer = null;
      }, 3000);
    }
  },
);
onUnmounted(() => {
  if (autoCloseTimer !== null) {
    clearTimeout(autoCloseTimer);
  }
});

// Auto-scroll logs to bottom / 日志自动滚到底部
watch(
  () => progressStore.logs.length,
  () => {
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    });
  },
);
</script>

<template>
  <Drawer
    :open="progressStore.visible"
    :title="
      progressStore.currentAction === 'uninstall'
        ? $t('admin.plugin.progress.uninstallTitle')
        : progressStore.currentAction === 'enable'
          ? $t('admin.plugin.progress.enableTitle')
          : $t('admin.plugin.progress.installTitle')
    "
    :width="480"
    :closable="!progressStore.isRunning"
    :mask-closable="!progressStore.isRunning"
    @close="handleClose"
  >
    <!-- 插件名 -->
    <div class="mb-4 flex items-center gap-2">
      <IconifyIcon icon="lucide:puzzle" class="size-5 text-primary" />
      <span class="text-base font-semibold">{{
        progressStore.pluginName
      }}</span>
      <Tag v-if="progressStore.isComplete" color="success">
        {{ $t('admin.plugin.progress.completed') }}
      </Tag>
      <Tag v-else-if="progressStore.isFailed" color="error">
        {{ $t('admin.plugin.progress.failed') }}
      </Tag>
      <Tag v-else-if="progressStore.isRunning" color="processing">
        {{ $t('admin.plugin.progress.running') }}
      </Tag>
    </div>

    <!-- 进度条 -->
    <Progress
      :percent="progressStore.progress"
      :status="progressStatus()"
      :stroke-color="progressStore.isFailed ? undefined : undefined"
      class="mb-4"
    />

    <!-- 步骤列表 -->
    <div class="mb-4 space-y-2">
      <div
        v-for="step in progressStore.steps"
        :key="step.step"
        class="flex items-start gap-2 text-sm"
      >
        <IconifyIcon
          :icon="stepIcon(step.status)"
          class="mt-0.5 size-4 shrink-0"
          :class="[stepIconClass(step.status)]"
        />
        <div class="min-w-0 flex-1">
          <span class="font-medium">{{ stepLabel(step.step) }}</span>
          <span v-if="step.message" class="ml-2 text-muted-foreground">{{
            step.message
          }}</span>
        </div>
      </div>
    </div>

    <!-- 实时日志 -->
    <div v-if="progressStore.logs.length > 0" class="mb-4">
      <div class="mb-1 text-xs font-medium text-muted-foreground">
        {{ $t('admin.plugin.progress.logs') }}
      </div>
      <div
        ref="logContainer"
        class="max-h-[240px] overflow-y-auto rounded-md bg-accent/50 p-3 font-mono text-xs leading-relaxed text-foreground"
      >
        <div
          v-for="(line, idx) in progressStore.logs"
          :key="idx"
          class="whitespace-pre-wrap break-all"
        >
          {{ line }}
        </div>
      </div>
    </div>

    <!-- 错误信息 -->
    <div
      v-if="progressStore.isFailed && progressStore.errorMessage"
      class="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
    >
      <div class="flex items-start gap-2">
        <IconifyIcon
          icon="lucide:alert-circle"
          class="mt-0.5 size-4 shrink-0"
        />
        <span>{{ progressStore.errorMessage }}</span>
      </div>
    </div>

    <!-- 底部操作 -->
    <div class="flex items-center justify-end gap-3">
      <Button
        v-if="progressStore.needsReload && progressStore.isComplete"
        type="primary"
        @click="handleReload"
      >
        <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
        {{ $t('admin.plugin.progress.reload') }}
      </Button>
      <Button v-if="!progressStore.isRunning" @click="handleClose">
        {{ $t('common.close') }}
      </Button>
    </div>
  </Drawer>
</template>

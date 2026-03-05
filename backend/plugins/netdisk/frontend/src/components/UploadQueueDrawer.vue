<script lang="ts" setup>
/**
 * N15c: UploadQueueDrawer — 右下角上传队列抽屉
 * - 展开/收起动画（transform + opacity，禁止 width/height 动画）
 * - 进度条 + 速度显示
 * - 暂停/继续/取消按钮
 * - 全部完成 5s 后自动收起
 */
import { ref, computed, watch } from 'vue';
import type { UploadTask } from '../composables/useNetDiskStore';

interface Props {
  queue: UploadTask[];
}
interface Emits {
  (e: 'pause',  id: string): void;
  (e: 'resume', id: string): void;
  (e: 'cancel', id: string): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const expanded  = ref(true);
const autoHide  = ref<ReturnType<typeof setTimeout> | null>(null);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

const allDone = computed(() => props.queue.length > 0 && props.queue.every(t => t.status === 'done' || t.status === 'error'));
const activeCount = computed(() => props.queue.filter(t => t.status === 'uploading').length);
const totalCount  = computed(() => props.queue.length);

function fmtSpeed(bps: number): string {
  if (bps < 1024)        return `${bps} B/s`;
  if (bps < 1024 ** 2)   return `${(bps / 1024).toFixed(1)} KB/s`;
  return `${(bps / 1024 ** 2).toFixed(2)} MB/s`;
}

function statusColor(status: UploadTask['status']): string {
  switch (status) {
    case 'done':      return '#22c55e';
    case 'error':     return '#ef4444';
    case 'paused':    return '#f59e0b';
    case 'uploading': return '#6366f1';
    default:          return '#94a3b8';
  }
}

function progressStatus(status: UploadTask['status']): 'success' | 'exception' | 'active' | 'normal' {
  if (status === 'done')    return 'success';
  if (status === 'error')   return 'exception';
  if (status === 'uploading') return 'active';
  return 'normal';
}

// 全部完成时 5s 后自动收起
watch(allDone, (done) => {
  if (done) {
    autoHide.value = setTimeout(() => { expanded.value = false; }, 5000);
  } else if (autoHide.value) {
    clearTimeout(autoHide.value);
  }
});
</script>

<template>
  <div
    v-if="queue.length > 0"
    class="fixed right-5 bottom-5 z-[8000] w-[340px] rounded-[10px] shadow-2xl bg-background border border-border overflow-hidden"
  >
    <!-- 抽屉头部 -->
    <div
      class="flex items-center justify-between px-3.5 py-2.5 bg-accent border-b border-border cursor-pointer select-none"
      @click="expanded = !expanded"
    >
      <div class="flex items-center gap-2 text-[13px] font-semibold">
        <svg v-if="!allDone" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        <span v-if="allDone" class="text-green-500">{{ $t('plugin.netdisk.upload.done') }}</span>
        <span v-else>{{ $t('plugin.netdisk.upload.progress') }} {{ activeCount }}/{{ totalCount }}</span>
      </div>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :style="{ transform: expanded ? 'rotate(0deg)' : 'rotate(180deg)', transition: 'transform 0.2s' }"><polyline points="18 15 12 9 6 15"/></svg>
    </div>

    <!-- 上传列表 -->
    <div
      v-if="expanded"
      class="max-h-[280px] overflow-y-auto py-1.5"
    >
      <div
        v-for="task in queue"
        :key="task.id"
        class="px-3.5 py-2 border-b border-border"
      >
        <!-- 文件名 + 速度 + 操作 -->
        <div class="flex items-center gap-1.5 mb-1">
          <!-- 状态图标 -->
          <svg v-if="task.status === 'done'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          <svg v-else-if="task.status === 'error'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          <svg v-else-if="task.status === 'paused'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" :stroke="statusColor(task.status)" stroke-width="2.5"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>

          <!-- 文件名 -->
          <span class="flex-1 text-xs overflow-hidden text-ellipsis whitespace-nowrap" :title="task.filename">
            {{ task.filename }}
          </span>

          <!-- 速度 -->
          <span v-if="task.status === 'uploading'" class="text-[11px] text-slate-500 whitespace-nowrap">
            {{ fmtSpeed(task.speed) }}
          </span>

          <!-- 操作按钮 -->
          <div class="flex gap-1">
            <a-button
              v-if="task.status === 'uploading'"
              size="small"
              type="text"
              class="text-[11px] !px-1 !h-5"
              @click.stop="emit('pause', task.id)"
            >{{ $t('plugin.netdisk.upload.pause') }}</a-button>
            <a-button
              v-else-if="task.status === 'paused'"
              size="small"
              type="text"
              class="text-[11px] !px-1 !h-5 text-primary"
              @click.stop="emit('resume', task.id)"
            >{{ $t('plugin.netdisk.upload.resume') }}</a-button>
            <a-button
              v-if="task.status !== 'done'"
              size="small"
              type="text"
              danger
              class="text-[11px] !px-1 !h-5"
              @click.stop="emit('cancel', task.id)"
            >{{ $t('plugin.netdisk.upload.cancel') }}</a-button>
          </div>
        </div>

        <!-- 进度条 -->
        <a-progress
          v-if="task.status !== 'done'"
          :percent="task.progress"
          :status="progressStatus(task.status)"
          :show-info="false"
          size="small"
          class="!mb-0"
        />

        <!-- 错误信息 -->
        <div v-if="task.status === 'error' && task.errorMsg" class="text-[11px] text-red-500 mt-0.5">
          {{ task.errorMsg }}
        </div>
      </div>
    </div>
  </div>
</template>

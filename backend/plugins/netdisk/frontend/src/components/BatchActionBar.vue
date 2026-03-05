<script lang="ts" setup>
/**
 * N25: BatchActionBar — 多选后显示的批量操作浮动条
 * 显示已选数量 + 批量下载/移动/删除/取消选中
 */
interface Props {
  count: number;
}
interface Emits {
  (e: 'batchDownload'): void;
  (e: 'batchMove'): void;
  (e: 'batchDelete'): void;
  (e: 'clearSelection'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};
</script>

<template>
  <div
    v-if="count > 0"
    class="fixed bottom-[60px] left-1/2 -translate-x-1/2 z-[7000] flex items-center gap-2 py-2 px-4 bg-background border border-border rounded-3xl shadow-xl"
  >
    <span class="text-[13px] font-semibold text-foreground whitespace-nowrap">
      {{ $t('plugin.netdisk.action.selected').replace('{count}', String(count)) }}
    </span>

    <a-divider type="vertical" class="!mx-1" />

    <a-button size="small" @click="emit('batchDownload')">
      <template #icon>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      </template>
      {{ $t('plugin.netdisk.action.batchDownload') }}
    </a-button>

    <a-button size="small" @click="emit('batchMove')">
      <template #icon>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="5 9 2 12 5 15"/><line x1="2" y1="12" x2="22" y2="12"/></svg>
      </template>
      {{ $t('plugin.netdisk.action.batchMove') }}
    </a-button>

    <a-button size="small" danger @click="emit('batchDelete')">
      <template #icon>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M9 6V4h6v2"/></svg>
      </template>
      {{ $t('plugin.netdisk.action.batchDelete') }}
    </a-button>

    <a-divider type="vertical" class="!mx-1" />

    <a-button size="small" type="text" @click="emit('clearSelection')">
      {{ $t('plugin.netdisk.action.cancelSelect') }}
    </a-button>
  </div>
</template>

<script lang="ts" setup>
/**
 * N14d: 列表视图 — 紧凑行 (图标/名称/大小/修改时间/分享状态)
 */
import type { FileNode } from '../api/netdisk';
import FileIcon from './FileIcon.vue';

interface Props {
  nodes:       FileNode[];
  loading:     boolean;
  selectedIds: Set<number>;
}
interface Emits {
  (e: 'select',      id: number, multi: boolean): void;
  (e: 'dblclick',    node: FileNode): void;
  (e: 'contextmenu', event: MouseEvent, node: FileNode): void;
  (e: 'upload'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function fmtSize(bytes: number): string {
  if (!bytes) return '—';
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
</script>

<template>
  <!-- 加载中 -->
  <div v-if="loading" class="flex items-center justify-center py-16 px-4">
    <a-spin />
  </div>

  <!-- 空状态 -->
  <div v-else-if="nodes.length === 0" class="flex flex-col items-center justify-center py-16 px-4 gap-3">
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
    <p class="text-[15px] font-medium text-foreground m-0">{{ $t('plugin.netdisk.page.empty') }}</p>
    <p class="text-[13px] text-muted-foreground m-0">{{ $t('plugin.netdisk.page.emptyHint') }}</p>
    <a-button type="primary" @click="emit('upload')">
      <template #icon>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      </template>
      {{ $t('plugin.netdisk.action.upload') }}
    </a-button>
  </div>

  <!-- 列表 -->
  <div v-else class="flex flex-col gap-0.5 flex-1 overflow-y-auto py-2 px-4">
    <!-- 表头 -->
    <div class="grid grid-cols-[28px_1fr_90px_150px_36px_36px] items-center px-2 py-1 text-xs font-semibold text-muted-foreground border-b border-border mb-1">
      <div />
      <div>{{ $t('plugin.netdisk.label.name') }}</div>
      <div>{{ $t('plugin.netdisk.label.size') }}</div>
      <div>{{ $t('plugin.netdisk.label.modified') }}</div>
      <div class="flex justify-center">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      </div>
      <div />
    </div>

    <!-- 数据行 -->
    <div
      v-for="node in nodes"
      :key="node.id"
      class="grid grid-cols-[28px_1fr_90px_150px_36px_36px] items-center px-2 py-1.5 rounded-md cursor-pointer select-none transition-colors"
      :class="selectedIds.has(node.id) ? 'bg-primary/5 outline outline-2 outline-primary' : 'bg-transparent'"
      @click.stop="emit('select', node.id, $event.ctrlKey || $event.metaKey)"
      @dblclick="emit('dblclick', node)"
      @contextmenu.prevent="emit('contextmenu', $event, node)"
    >
      <div class="flex items-center justify-center">
        <FileIcon :node="node" :size="18" />
      </div>
      <div :title="node.name" class="text-[13px] overflow-hidden text-ellipsis whitespace-nowrap pr-2">{{ node.name }}</div>
      <div class="text-xs text-muted-foreground">{{ node.nodeType === 'file' ? fmtSize(node.sizeBytes) : '—' }}</div>
      <div class="text-xs text-muted-foreground">{{ fmtDate(node.updatedAt) }}</div>
      <div class="flex items-center justify-center">
      </div>
      <div class="flex items-center justify-center">
        <a-button size="small" type="text" class="!px-1 !h-[22px]" @click.stop="emit('contextmenu', $event, node)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
        </a-button>
      </div>
    </div>
  </div>
</template>

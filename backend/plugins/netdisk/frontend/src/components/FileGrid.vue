<script lang="ts" setup>
/**
 * N14c: 网格视图 — FolderCard + FileCard + EmptyState
 * 满足验收标准：
 * - 文件夹：彩色 SVG 图标 + 名称截断 + hover 高亮 + 「...」更多菜单
 * - 文件：按 MIME 彩色 SVG 图标 + 图片显示缩略图 + 文件名/大小
 * - 选中：左上角 checkbox + 蓝色边框高亮
 * - 空状态：SVG + 引导文案 + 上传按钮
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
  if (!bytes) return '';
  if (bytes < 1024)      return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function thumbnailUrl(node: FileNode): string | null {
  if (!node.mimeType?.startsWith('image/')) return null;
  return `/tenant/plugins/netdisk/api/nodes/${node.id}/thumbnail`;
}
</script>

<template>
  <!-- 加载中 -->
  <div v-if="loading" class="flex items-center justify-center gap-2 py-16 px-4 text-muted-foreground">
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

  <!-- 网格 -->
  <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-3 content-start p-4 flex-1 overflow-y-auto">
    <div
      v-for="node in nodes"
      :key="node.id"
      class="relative flex flex-col items-center pt-3 px-2 pb-2 border-2 rounded-lg cursor-pointer gap-1.5 transition-colors select-none"
      :class="selectedIds.has(node.id) ? 'border-primary bg-primary/5' : 'border-transparent bg-muted'"
      @click.stop="emit('select', node.id, $event.ctrlKey || $event.metaKey)"
      @dblclick="emit('dblclick', node)"
      @contextmenu.prevent="emit('contextmenu', $event, node)"
    >
      <!-- 选择框 -->
      <a-checkbox
        :checked="selectedIds.has(node.id)"
        class="absolute top-1.5 left-1.5"
        @click.stop="emit('select', node.id, true)"
      />

      <!-- 图标 / 缩略图 -->
      <div class="w-12 h-12 flex items-center justify-center mt-1">
        <img
          v-if="thumbnailUrl(node)"
          :src="thumbnailUrl(node)!"
          :alt="node.name"
          class="w-12 h-12 object-cover rounded-md"
          loading="lazy"
        />
        <FileIcon v-else :node="node" :size="44" />
      </div>

      <!-- 文件名 -->
      <span
        :title="node.name"
        class="text-xs text-center overflow-hidden line-clamp-2 w-full leading-snug break-all"
      >{{ node.name }}</span>

      <!-- 元信息 -->
      <span v-if="node.nodeType === 'file'" class="text-[11px] text-muted-foreground">{{ fmtSize(node.sizeBytes) }}</span>

      <!-- 更多按钮 -->
      <a-button
        size="small"
        type="text"
        class="absolute top-1 right-1 !px-1 !h-5 text-sm opacity-50"
        @click.stop="emit('contextmenu', $event, node)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
      </a-button>
    </div>
  </div>
</template>

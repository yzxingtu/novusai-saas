<script lang="ts" setup>
/**
 * 右键上下文菜单 — 文件/文件夹操作列表
 */
import type { FileNode } from '../api/netdisk';

interface Props {
  visible:  boolean;
  x:        number;
  y:        number;
  node:     FileNode | null;
}
interface Emits {
  (e: 'action', action: string, node: FileNode): void;
  (e: 'close'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function act(action: string) {
  if (props.node) emit('action', action, props.node);
  emit('close');
}
</script>

<template>
  <div
    v-if="visible && node"
    class="fixed z-[9000] min-w-[160px] rounded-md shadow-lg bg-background border border-border py-1"
    :style="{ top: `${y}px`, left: `${x}px` }"
    @click.stop
  >
    <div v-if="node.nodeType === 'file'" class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('download')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      {{ $t('plugin.netdisk.action.download') }}
    </div>
    <div v-if="node.nodeType === 'file'" class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('preview')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
      {{ $t('plugin.netdisk.action.preview') }}
    </div>
    <div class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('share')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
      {{ $t('plugin.netdisk.action.share') }}
    </div>
    <div class="h-px bg-border my-1" />
    <div class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('rename')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
      {{ $t('plugin.netdisk.action.rename') }}
    </div>
    <div class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('move')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/><polyline points="19 9 22 12 19 15"/><polyline points="9 19 12 22 15 19"/></svg>
      {{ $t('plugin.netdisk.action.move') }}
    </div>
    <div class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-foreground transition-colors hover:bg-accent" @click="act('copy')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      {{ $t('plugin.netdisk.action.copy') }}
    </div>
    <div class="h-px bg-border my-1" />
    <div class="flex cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 py-1.5 text-[13px] text-destructive transition-colors hover:bg-accent" @click="act('delete')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
      {{ $t('plugin.netdisk.action.delete') }}
    </div>
  </div>
</template>

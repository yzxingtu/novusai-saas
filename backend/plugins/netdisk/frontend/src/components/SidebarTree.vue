<script lang="ts" setup>
/**
 * N14b: 左侧文件夹目录树
 * 支持懒加载展开/折叠，点击进入目录，右键菜单，选中高亮
 */
import { ref, onMounted } from 'vue';
import { listNodesApi } from '../api/netdisk';
import type { FileNode } from '../api/netdisk';

interface Props {
  currentParentId: number | null;
}
interface Emits {
  (e: 'navigate', id: number | null, name: string): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

interface TreeNode {
  id: number | null;
  name: string;
  children: TreeNode[];
  loaded: boolean;
  expanded: boolean;
  loading: boolean;
}

const rootChildren = ref<TreeNode[]>([]);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

async function loadChildren(node: TreeNode) {
  if (node.loaded) { node.expanded = !node.expanded; return; }
  node.loading = true;
  try {
    const resp = await listNodesApi({ parent_id: node.id });
    const folders = (resp.data ?? []).filter((n: FileNode) => n.nodeType === 'folder');
    node.children = folders.map((f: FileNode) => ({
      id: f.id, name: f.name,
      children: [], loaded: false, expanded: false, loading: false,
    }));
    node.loaded   = true;
    node.expanded = true;
  } catch { /* ignore */ }
  finally { node.loading = false; }
}

function navigate(id: number | null, name: string) {
  emit('navigate', id, name);
}

function nodeClass(id: number | null) {
  return ['nd-tree-node', id === props.currentParentId && 'active'];
}

onMounted(async () => {
  const resp = await listNodesApi({ parent_id: null });
  const folders = (resp.data ?? []).filter((n: FileNode) => n.nodeType === 'folder');
  rootChildren.value = folders.map((f: FileNode) => ({
    id: f.id, name: f.name,
    children: [], loaded: false, expanded: false, loading: false,
  }));
});
</script>

<template>
  <nav class="w-[200px] shrink-0 border-r border-border flex flex-col overflow-y-auto py-2">
    <div class="px-4 pt-2.5 pb-1.5 text-xs font-bold tracking-wider text-muted-foreground uppercase">
      {{ $t('plugin.netdisk.page.title') }}
    </div>

    <!-- 根目录入口 -->
    <div
      class="flex items-center gap-2 py-1.5 px-4 cursor-pointer rounded-md mx-1.5 text-[13px]"
      :class="props.currentParentId === null ? 'bg-primary text-white font-semibold' : 'bg-transparent text-foreground font-normal'"
      @click="navigate(null, $t('plugin.netdisk.nav.root'))"
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" :stroke="props.currentParentId === null ? '#fff' : '#F59E0B'" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
      <span>{{ $t('plugin.netdisk.nav.root') }}</span>
    </div>

    <!-- 根级文件夹 -->
    <template v-for="node in rootChildren" :key="node.id">
      <div
        class="flex items-center gap-1.5 py-1 pr-4 pl-2 cursor-pointer rounded-md mx-1.5 text-[13px]"
      :class="props.currentParentId === node.id ? 'bg-primary text-white' : 'bg-transparent text-foreground'"
        @click="navigate(node.id, node.name)"
      >
        <!-- 展开/折叠按钮 -->
        <span
          class="w-4 h-4 flex items-center justify-center shrink-0 opacity-60"
          @click.stop="loadChildren(node)"
        >
          <svg v-if="node.loading" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          <svg v-else-if="node.expanded" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
          <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 6 15 12 9 18"/></svg>
        </span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" :stroke="props.currentParentId === node.id ? '#fff' : '#F59E0B'" stroke-width="2" class="shrink-0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <span :title="node.name" class="overflow-hidden text-ellipsis whitespace-nowrap">{{ node.name }}</span>
      </div>

      <!-- 子文件夹（第二层） -->
      <template v-if="node.expanded" v-for="child in node.children" :key="String(child.id)">
        <div
          class="flex items-center gap-1.5 py-1 pr-4 pl-7 cursor-pointer rounded-md mx-1.5 text-[13px]"
          :class="props.currentParentId === child.id ? 'bg-primary/10 text-primary' : 'bg-transparent text-foreground'"
          @click="navigate(child.id, child.name)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" class="shrink-0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span :title="child.name" class="overflow-hidden text-ellipsis whitespace-nowrap">{{ child.name }}</span>
        </div>
      </template>
    </template>

    <!-- 分隔线 -->
    <div class="h-px bg-border mx-3 my-2" />

    <!-- 回收站 -->
    <div
      class="flex items-center gap-2 py-1.5 px-4 cursor-pointer rounded-md mx-1.5 text-[13px]"
      :class="props.currentParentId === -1 ? 'bg-red-500/10 text-red-500' : 'bg-transparent text-muted-foreground'"
      @click="navigate(-1, $t('plugin.netdisk.nav.trash'))"
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M9 6V4h6v2"/></svg>
      <span>{{ $t('plugin.netdisk.nav.trash') }}</span>
    </div>
  </nav>
</template>


<script lang="ts" setup>
/**
 * N24: MoveModal — 目标目录选择器 Modal
 * 展示文件夹树，选择目标目录，不能选自身及子目录
 */
import { ref, watch } from 'vue';
import { listNodesApi, moveNodeApi, copyNodeApi } from '../api/netdisk';
import type { FileNode } from '../api/netdisk';

interface Props {
  visible:  boolean;
  nodeIds:  number[];
  action:   'move' | 'copy';
}
interface Emits {
  (e: 'close'): void;
  (e: 'done'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

interface FolderItem { id: number | null; name: string; depth: number; }

const MAX_DEPTH = 3;
const folders   = ref<FolderItem[]>([]);
const selected  = ref<number | null>(null);
const loading   = ref(false);
const submitting = ref(false);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

async function loadFolders(parentId: number | null = null, depth = 0) {
  if (depth >= MAX_DEPTH) return; // 限制最大展开深度，防止过深递归
  const resp = await listNodesApi({ parent_id: parentId });
  for (const node of (resp.data ?? []).filter((n: FileNode) => n.nodeType === 'folder')) {
    if (props.nodeIds.includes(node.id)) continue; // 不能选自身
    folders.value.push({ id: node.id, name: node.name, depth: depth + 1 });
    await loadFolders(node.id, depth + 1);
  }
}

watch(() => props.visible, async (v) => {
  if (v) {
    folders.value = [{ id: null, name: $t('plugin.netdisk.nav.root'), depth: 0 }];
    selected.value = null;
    await loadFolders();
  }
});

async function confirm() {
  if (selected.value === undefined) return;
  submitting.value = true;
  try {
    for (const id of props.nodeIds) {
      if (props.action === 'move') {
        await moveNodeApi(id, selected.value ?? null);
      } else {
        await copyNodeApi(id, selected.value ?? null);
      }
    }
    emit('done');
    emit('close');
  } catch { /* handle error */ }
  finally { submitting.value = false; }
}
</script>

<template>
  <a-modal
    :open="visible"
    :title="action === 'move' ? $t('plugin.netdisk.action.move') : $t('plugin.netdisk.action.copy')"
    :confirm-loading="submitting"
    :ok-disabled="selected === undefined"
    :width="420"
    @ok="confirm"
    @cancel="emit('close')"
  >
    <p class="text-[13px] text-muted-foreground mb-3">
      {{ $t('plugin.netdisk.modal.selectTarget').replace('{count}', String(nodeIds.length)) }}
    </p>

    <div class="max-h-[320px] overflow-y-auto border border-border rounded-md">
      <div
        v-for="folder in folders"
        :key="String(folder.id)"
        class="flex items-center gap-2 py-[7px] pr-3 cursor-pointer text-[13px] transition-colors border-l-[3px]"
        :class="selected === folder.id ? 'bg-primary/[0.08] border-l-primary' : 'bg-transparent border-l-transparent'"
        :style="{ paddingLeft: `${12 + folder.depth * 16}px` }"
        @click="selected = folder.id"
      >
        <svg v-if="folder.depth === 0" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <span>{{ folder.name }}</span>
      </div>
    </div>
  </a-modal>
</template>

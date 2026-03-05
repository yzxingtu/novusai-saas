<script lang="ts" setup>
/**
 * 企业网盘主页面 — 三栏布局：左侧目录树 + 中间内容区 + 底部状态栏
 * 禁止手写 loading/list/page/total + watch分页 + 手写删除确认
 * 状态全部通过 useNetDiskStore 管理
 */
import { onMounted, ref } from 'vue';
import { useNetDiskStore } from '../composables/useNetDiskStore';
import { useUploader } from '../composables/useUploader';
import type { FileNode } from '../api/netdisk';
import SidebarTree from '../components/SidebarTree.vue';
import FileToolbar from '../components/FileToolbar.vue';
import FileGrid from '../components/FileGrid.vue';
import FileList from '../components/FileList.vue';
import StatusBar from '../components/StatusBar.vue';
import ContextMenu from '../components/ContextMenu.vue';
import UploadQueueDrawer from '../components/UploadQueueDrawer.vue';
import BatchActionBar from '../components/BatchActionBar.vue';
import ShareModal from '../components/ShareModal.vue';
import MoveModal from '../components/MoveModal.vue';
import FilePreviewModal from '../components/FilePreviewModal.vue';

const {
  displayNodes, breadcrumbs, selectedIds, viewMode, quota,
  loading, currentParentId, uploadQueue,
  sortBy, sortOrder, searchQuery, selectedCount,
  loadDir, loadQuota, navigateTo, navigateUp,
  selectNode, selectAll, clearSelection,
  setViewMode, setSortBy, refreshDir,
} = useNetDiskStore();

const ctxMenuVisible = ref(false);
const ctxMenuX       = ref(0);
const ctxMenuY       = ref(0);
const ctxMenuNode    = ref<FileNode | null>(null);
const uploadDrop     = ref(false);

const newFolderModal   = ref(false);
const newFolderName    = ref('');
const newFolderSaving  = ref(false);
const deleteConfirm    = ref(false);
const deleteTarget     = ref<FileNode | null>(null);
const deleteLoading    = ref(false);

const shareVisible     = ref(false);
const shareNode        = ref<FileNode | null>(null);

const renameVisible    = ref(false);
const renameTarget     = ref<FileNode | null>(null);
const renameValue      = ref('');
const renameSaving     = ref(false);

const moveVisible      = ref(false);
const moveNodeIds      = ref<number[]>([]);
const moveAction       = ref<'move' | 'copy'>('move');

const previewVisible   = ref(false);
const previewNode      = ref<FileNode | null>(null);
const previewUrl       = ref('');

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

onMounted(async () => {
  await loadDir(null);
  await loadQuota();
});

function onDblClick(node: FileNode) {
  if (node.nodeType === 'folder') navigateTo(node.id, node.name);
}

function openContextMenu(e: MouseEvent, node: FileNode) {
  e.preventDefault();
  ctxMenuNode.value    = node;
  ctxMenuX.value       = e.clientX;
  ctxMenuY.value       = e.clientY;
  ctxMenuVisible.value = true;
}

function closeCtxMenu() { ctxMenuVisible.value = false; }

async function onCtxAction(action: string, node: FileNode) {
  closeCtxMenu();
  if (action === 'download') {
    const { getDownloadUrlApi } = await import('../api/netdisk');
    const r = await getDownloadUrlApi(node.id);
    window.open(r.data?.url, '_blank');
  } else if (action === 'delete') {
    deleteTarget.value  = node;
    deleteConfirm.value = true;
  } else if (action === 'share') {
    shareNode.value    = node;
    shareVisible.value = true;
  } else if (action === 'rename') {
    renameTarget.value  = node;
    renameValue.value   = node.name;
    renameVisible.value = true;
  } else if (action === 'move') {
    moveNodeIds.value = [node.id];
    moveAction.value  = 'move';
    moveVisible.value = true;
  } else if (action === 'copy') {
    moveNodeIds.value = [node.id];
    moveAction.value  = 'copy';
    moveVisible.value = true;
  } else if (action === 'preview') {
    previewNode.value = node;
    const { getDownloadUrlApi } = await import('../api/netdisk');
    const r = await getDownloadUrlApi(node.id);
    previewUrl.value     = r.data?.url ?? '';
    previewVisible.value = true;
  }
}

async function confirmRename() {
  if (!renameTarget.value || !renameValue.value.trim()) return;
  renameSaving.value = true;
  try {
    const { renameNodeApi } = await import('../api/netdisk');
    await renameNodeApi(renameTarget.value.id, renameValue.value.trim());
    renameVisible.value = false;
    renameTarget.value  = null;
    await refreshDir();
  } finally {
    renameSaving.value = false;
  }
}

async function onMoveDone() {
  clearSelection();
  await refreshDir();
}

function onBatchMove() {
  moveNodeIds.value = Array.from(selectedIds);
  moveAction.value  = 'move';
  moveVisible.value = true;
}

function onPreviewDownload() {
  if (previewUrl.value) {
    globalThis.open(previewUrl.value, '_blank');
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return;
  deleteLoading.value = true;
  try {
    const { deleteNodeApi } = await import('../api/netdisk');
    await deleteNodeApi(deleteTarget.value.id);
    deleteConfirm.value = false;
    deleteTarget.value  = null;
    await refreshDir();
  } finally {
    deleteLoading.value = false;
  }
}

function onNewFolder() {
  newFolderName.value  = '';
  newFolderModal.value = true;
}

async function createFolder() {
  if (!newFolderName.value.trim()) return;
  newFolderSaving.value = true;
  try {
    const { createFolderApi } = await import('../api/netdisk');
    await createFolderApi({ parent_id: currentParentId.value, name: newFolderName.value.trim() });
    newFolderModal.value = false;
    await refreshDir();
  } finally {
    newFolderSaving.value = false;
  }
}

// ── 上传 ──────────────────────────────────────────────────────
const fileInputRef = ref<HTMLInputElement | null>(null);
const { addFiles, pause, resume, cancel } = useUploader();

function onUploadClick() {
  fileInputRef.value?.click();
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) {
    addFiles(input.files, currentParentId.value);
    input.value = '';
  }
}

function onDragEnter(e: DragEvent) {
  if (e.dataTransfer?.types.includes('Files')) uploadDrop.value = true;
}
function onDragLeave(e: DragEvent) {
  if (!(e.currentTarget as HTMLElement)?.contains(e.relatedTarget as Node)) {
    uploadDrop.value = false;
  }
}
function onDrop(e: DragEvent) {
  e.preventDefault();
  uploadDrop.value = false;
  if (e.dataTransfer?.files?.length) {
    addFiles(e.dataTransfer.files, currentParentId.value);
  }
}

function setSearch(q: string) {
  searchQuery.value = q;
}

// ── 批量操作 ───────────────────────────────────────
const batchDeleteConfirm  = ref(false);
const batchDeleteLoading  = ref(false);

async function onBatchDownload() {
  const ids = Array.from(selectedIds);
  for (const id of ids) {
    const { getDownloadUrlApi } = await import('../api/netdisk');
    const r = await getDownloadUrlApi(id);
    if (r.data?.url) window.open(r.data.url, '_blank');
  }
}

async function confirmBatchDelete() {
  batchDeleteLoading.value = true;
  try {
    const { batchOpApi } = await import('../api/netdisk');
    await batchOpApi('delete', Array.from(selectedIds));
    clearSelection();
    batchDeleteConfirm.value = false;
    await refreshDir();
  } finally {
    batchDeleteLoading.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && e.key === 'a') { e.preventDefault(); selectAll(); }
  if (e.key === 'Escape')   clearSelection();
  if (e.key === 'Backspace') navigateUp();
}
</script>

<template>
  <!-- 拖拽上传浮层（pointer-events 开启以接收 drop/dragleave） -->
  <div
    v-if="uploadDrop"
    class="fixed inset-0 z-[9999] bg-indigo-500/15 flex flex-col items-center justify-center"
    @dragover.prevent
    @dragleave.self="() => { uploadDrop = false; }"
    @drop.prevent="onDrop"
  >
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5" class="mb-3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
    <p class="text-lg font-semibold text-indigo-500">{{ $t('plugin.netdisk.upload.dropText') }}</p>
  </div>

  <!-- 根容器：获取键盘焦点 + 拖拽监听 -->
  <div
    class="flex flex-col h-full bg-background outline-none relative"
    tabindex="0"
    @keydown="onKeydown"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @click="closeCtxMenu"
  >
    <!-- ── 主体三栏 ─── -->
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <!-- 左侧目录树 -->
      <SidebarTree
        :current-parent-id="currentParentId"
        @navigate="(id, name) => navigateTo(id, name)"
      />

      <!-- 中间内容区 -->
      <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
        <!-- 工具栏 + 面包屑 -->
        <FileToolbar
          :breadcrumbs="breadcrumbs"
          :view-mode="viewMode"
          :sort-by="sortBy"
          :sort-order="sortOrder"
          :search-query="searchQuery"
          @navigate="(id, name) => navigateTo(id, name)"
          @set-view-mode="setViewMode"
          @set-sort="(f, o) => setSortBy(f as 'name' | 'size_bytes' | 'updated_at', o)"
          @search="setSearch"
          @new-folder="onNewFolder"
          @upload="onUploadClick"
          @refresh="refreshDir"
        />

        <!-- 网格视图 -->
        <FileGrid
          v-if="viewMode === 'grid'"
          :nodes="displayNodes"
          :loading="loading"
          :selected-ids="selectedIds"
          @select="(id, multi) => selectNode(id, multi)"
          @dblclick="onDblClick"
          @contextmenu="openContextMenu"
          @upload="onUploadClick"
        />

        <!-- 列表视图 -->
        <FileList
          v-else
          :nodes="displayNodes"
          :loading="loading"
          :selected-ids="selectedIds"
          @select="(id, multi) => selectNode(id, multi)"
          @dblclick="onDblClick"
          @contextmenu="openContextMenu"
          @upload="onUploadClick"
        />
      </div>
    </div>

    <!-- 底部状态栏 -->
    <StatusBar
      :selected-count="selectedCount"
      :quota="quota"
    />
  </div>

  <!-- 隐藏文件选择 input -->
  <input
    ref="fileInputRef"
    type="file"
    multiple
    class="hidden"
    @change="onFileInputChange"
  />

  <!-- 批量操作浮动条 -->
  <BatchActionBar
    :count="selectedCount"
    @batch-download="onBatchDownload"
    @batch-move="onBatchMove"
    @batch-delete="batchDeleteConfirm = true"
    @clear-selection="clearSelection"
  />

  <!-- 批量删除确认弹窗 -->
  <a-modal
    v-model:open="batchDeleteConfirm"
    :title="$t('plugin.netdisk.action.batchDelete')"
    :confirm-loading="batchDeleteLoading"
    ok-type="danger"
    @ok="confirmBatchDelete"
    @cancel="batchDeleteConfirm = false"
  >
    <p>{{ $t('plugin.netdisk.action.deleteConfirm') }} {{ selectedCount }} {{ $t('plugin.netdisk.label.items') }}?</p>
  </a-modal>

  <!-- 上传队列抽屉 -->
  <UploadQueueDrawer
    :queue="uploadQueue"
    @pause="pause"
    @resume="resume"
    @cancel="cancel"
  />

  <!-- 右键菜单 -->
  <ContextMenu
    :visible="ctxMenuVisible"
    :x="ctxMenuX"
    :y="ctxMenuY"
    :node="ctxMenuNode"
    @action="onCtxAction"
    @close="closeCtxMenu"
  />

  <!-- 新建文件夹弹窗 -->
  <a-modal
    v-model:open="newFolderModal"
    :title="$t('plugin.netdisk.action.newFolder')"
    :confirm-loading="newFolderSaving"
    @ok="createFolder"
    @cancel="newFolderModal = false"
  >
    <a-input
      v-model:value="newFolderName"
      :placeholder="$t('plugin.netdisk.action.newFolderPrompt')"
      @press-enter="createFolder"
    />
  </a-modal>

  <!-- 删除确认弹窗 -->
  <a-modal
    v-model:open="deleteConfirm"
    :title="$t('plugin.netdisk.action.delete')"
    :confirm-loading="deleteLoading"
    ok-type="danger"
    @ok="confirmDelete"
    @cancel="deleteConfirm = false"
  >
    <p>{{ $t('plugin.netdisk.action.deleteConfirm') }} <strong>{{ deleteTarget?.name }}</strong>?</p>
  </a-modal>

  <!-- 重命名弹窗 -->
  <a-modal
    v-model:open="renameVisible"
    :title="$t('plugin.netdisk.action.rename')"
    :confirm-loading="renameSaving"
    @ok="confirmRename"
    @cancel="renameVisible = false"
  >
    <a-input
      v-model:value="renameValue"
      :placeholder="$t('plugin.netdisk.action.renamePrompt')"
      @press-enter="confirmRename"
    />
  </a-modal>

  <!-- 分享弹窗 -->
  <ShareModal
    :visible="shareVisible"
    :node="shareNode"
    @close="shareVisible = false"
  />

  <!-- 移动/复制弹窗 -->
  <MoveModal
    :visible="moveVisible"
    :node-ids="moveNodeIds"
    :action="moveAction"
    @close="moveVisible = false"
    @done="onMoveDone"
  />

  <!-- 文件预览弹窗 -->
  <FilePreviewModal
    :visible="previewVisible"
    :node="previewNode"
    :url="previewUrl"
    @close="previewVisible = false"
    @download="onPreviewDownload"
  />
</template>

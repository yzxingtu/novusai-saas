/**
 * 网盘状态管理 (Pinia-like reactive store via Vue 3 Composition API)
 * 插件内无法直接引入 Pinia，使用 Vue 3 reactive + ref
 */

import { ref, computed, reactive } from 'vue';
import type { FileNode, QuotaInfo } from '../api/netdisk';
import {
  listNodesApi,
  getQuotaApi,
  batchOpApi,
} from '../api/netdisk';

export interface BreadcrumbItem {
  id: number | null;
  name: string;
}

export interface UploadTask {
  id: string;
  filename: string;
  sizeBytes: number;
  progress: number;       // 0-100
  speed: number;          // bytes/s
  status: 'pending' | 'uploading' | 'paused' | 'done' | 'error';
  errorMsg?: string;
}

// ── 全局单例状态 ──────────────────────────────────────────────

const currentParentId = ref<number | null>(null);
const nodes           = ref<FileNode[]>([]);
const breadcrumbs     = ref<BreadcrumbItem[]>([{ id: null, name: 'plugin.netdisk.nav.root' }]);
const selectedIds     = reactive(new Set<number>());
const viewMode        = ref<'grid' | 'list'>(
  (localStorage.getItem('netdisk-view-mode') as 'grid' | 'list') || 'grid',
);
const sortBy    = ref<'name' | 'size_bytes' | 'updated_at'>('name');
const sortOrder = ref<'asc' | 'desc'>('asc');
const quota     = ref<QuotaInfo | null>(null);
const clipboard = ref<{ action: 'copy' | 'cut'; ids: number[] } | null>(null);
const loading   = ref(false);
const searchQuery   = ref('');
const searchResults = ref<FileNode[] | null>(null);
const uploadQueue   = ref<UploadTask[]>([]);

// ── Computed ──────────────────────────────────────────────────

const displayNodes = computed<FileNode[]>(() => {
  const source = searchResults.value !== null ? searchResults.value : nodes.value;
  return [...source].sort((a, b) => {
    // 文件夹优先
    if (a.nodeType !== b.nodeType) {
      return a.nodeType === 'folder' ? -1 : 1;
    }
    const field = sortBy.value;
    const aVal = (a as Record<string, unknown>)[field];
    const bVal = (b as Record<string, unknown>)[field];
    const cmp = String(aVal ?? '').localeCompare(String(bVal ?? ''), undefined, { numeric: true });
    return sortOrder.value === 'asc' ? cmp : -cmp;
  });
});

const selectedCount = computed(() => selectedIds.size);

const quotaPercent = computed(() => quota.value?.usedPercent ?? 0);

// ── Actions ───────────────────────────────────────────────────

async function loadDir(parentId: number | null = null) {
  loading.value = true;
  searchResults.value = null;
  searchQuery.value = '';
  try {
    const res = await listNodesApi({ parent_id: parentId });
    nodes.value = res.data ?? [];
    currentParentId.value = parentId;
    clearSelection();
  } catch (err) {
    console.error('[netdisk] loadDir error', err);
  } finally {
    loading.value = false;
  }
}

async function loadQuota() {
  try {
    const res = await getQuotaApi();
    quota.value = res.data ?? null;
  } catch (err) {
    console.warn('[netdisk] loadQuota error', err);
  }
}

function navigateTo(id: number | null, name: string) {
  const idx = breadcrumbs.value.findIndex(b => b.id === id);
  if (idx >= 0) {
    breadcrumbs.value = breadcrumbs.value.slice(0, idx + 1);
  } else {
    breadcrumbs.value.push({ id, name });
  }
  loadDir(id);
}

function navigateUp() {
  if (breadcrumbs.value.length <= 1) return;
  breadcrumbs.value.pop();
  const parent = breadcrumbs.value[breadcrumbs.value.length - 1];
  loadDir(parent?.id ?? null);
}

// ── 选择管理 ──────────────────────────────────────────────────

function selectNode(id: number, multiSelect = false) {
  if (multiSelect) {
    if (selectedIds.has(id)) {
      selectedIds.delete(id);
    } else {
      selectedIds.add(id);
    }
  } else {
    selectedIds.clear();
    selectedIds.add(id);
  }
}

function selectAll() {
  nodes.value.forEach(n => selectedIds.add(n.id));
}

function clearSelection() {
  selectedIds.clear();
}

// ── 剪贴板 ────────────────────────────────────────────────────

function copyToClipboard(ids: number[]) {
  clipboard.value = { action: 'copy', ids };
}

function cutToClipboard(ids: number[]) {
  clipboard.value = { action: 'cut', ids };
}

async function pasteClipboard(targetParentId: number | null) {
  if (!clipboard.value) return;
  const { action, ids } = clipboard.value;
  await batchOpApi(action === 'cut' ? 'move' : 'copy', ids, { new_parent_id: targetParentId });
  if (action === 'cut') clipboard.value = null;
  await loadDir(currentParentId.value);
}

// ── 视图模式 ──────────────────────────────────────────────────

function setViewMode(mode: 'grid' | 'list') {
  viewMode.value = mode;
  localStorage.setItem('netdisk-view-mode', mode);
}

function setSortBy(field: 'name' | 'size_bytes' | 'updated_at', order: 'asc' | 'desc' = 'asc') {
  sortBy.value    = field;
  sortOrder.value = order;
}

// ── 上传队列管理 ──────────────────────────────────────────────

function addUploadTask(task: UploadTask) {
  uploadQueue.value.push(task);
}

function updateUploadTask(id: string, patch: Partial<UploadTask>) {
  const task = uploadQueue.value.find(t => t.id === id);
  if (task) Object.assign(task, patch);
}

function removeUploadTask(id: string) {
  uploadQueue.value = uploadQueue.value.filter(t => t.id !== id);
}

// ── 节点操作后刷新 ────────────────────────────────────────────

async function refreshDir() {
  await loadDir(currentParentId.value);
  await loadQuota();
}

// ── 公开 store 接口 ───────────────────────────────────────────

export function useNetDiskStore() {
  return {
    // state
    currentParentId,
    nodes,
    breadcrumbs,
    selectedIds,
    viewMode,
    sortBy,
    sortOrder,
    quota,
    clipboard,
    loading,
    searchQuery,
    searchResults,
    uploadQueue,
    // computed
    displayNodes,
    selectedCount,
    quotaPercent,
    // actions
    loadDir,
    loadQuota,
    navigateTo,
    navigateUp,
    selectNode,
    selectAll,
    clearSelection,
    copyToClipboard,
    cutToClipboard,
    pasteClipboard,
    setViewMode,
    setSortBy,
    addUploadTask,
    updateUploadTask,
    removeUploadTask,
    refreshDir,
  };
}

<script lang="ts" setup>
/**
 * NovusDoc document list page — left sidebar (folders) + main content area (doc grid/list)
 * NovusDoc 文档列表页 — 左侧栏（文件夹）+ 主区域（文档网格/列表）
 * Reused for both tenant (/tenant/plugins/novusdoc) and admin (/admin/plugins/novusdoc)
 * 企业端与管理端共用（/tenant/plugins/novusdoc、/admin/plugins/novusdoc）
 */
import { computed, onMounted, ref, watch } from 'vue';
import type { DocItem, Folder } from '../types';
import { listDocs, listFolders, createDoc, deleteDoc, createFolder, deleteFolder, searchDocs } from '../api/novusdoc';
import {
  getNovusdocPermissionCodes,
  hasNovusdocAccess,
  resolveRouteAccessCodes,
} from '../permissions';

const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
  $t?: (k: string) => string;
  router?: {
    push: (to: string) => void;
    currentRoute?: { value?: { meta?: Record<string, unknown> } };
  };
} | undefined;

const $t = (key: string) => {
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

const docs = ref<DocItem[]>([]);
const folders = ref<Folder[]>([]);
const total = ref(0);
const page = ref(1);
const size = ref(20);
const loading = ref(false);
const activeFolderId = ref<number | null>(null);
const searchQuery = ref('');
const searchActive = ref(false);

const isAdmin = computed(() => location.pathname.includes('/admin/'));
const permissionScope = computed(() => (isAdmin.value ? 'admin' : 'tenant'));
const permissionCodes = computed(() =>
  getNovusdocPermissionCodes(permissionScope.value),
);
const routeAccessCodes = computed(() =>
  resolveRouteAccessCodes(
    shared?.router?.currentRoute?.value?.meta as
      | Record<string, unknown>
      | undefined,
    [permissionCodes.value.view],
  ),
);
const canView = computed(() => hasNovusdocAccess(routeAccessCodes.value));
const canCreate = computed(
  () => canView.value && hasNovusdocAccess(permissionCodes.value.create),
);
const canDelete = computed(
  () => canView.value && hasNovusdocAccess(permissionCodes.value.delete),
);

function clearListState() {
  docs.value = [];
  folders.value = [];
  total.value = 0;
  loading.value = false;
}

async function loadFolders() {
  if (!canView.value) {
    folders.value = [];
    return;
  }
  try {
    const res = await listFolders();
    folders.value = res.items;
  } catch {
    folders.value = [];
  }
}

async function loadDocs() {
  if (!canView.value) {
    clearListState();
    return;
  }
  loading.value = true;
  try {
    if (searchActive.value && searchQuery.value.trim()) {
      const res = await searchDocs(searchQuery.value.trim(), { page: page.value, size: size.value });
      docs.value = res.items;
      total.value = res.total;
    } else {
      const res = await listDocs({
        page: page.value,
        size: size.value,
        folder_id: activeFolderId.value,
      });
      docs.value = res.items;
      total.value = res.total;
    }
  } catch {
    docs.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

watch([page, activeFolderId], () => {
  if (!searchActive.value) loadDocs();
});

onMounted(async () => {
  if (canView.value) {
    await Promise.all([loadFolders(), loadDocs()]);
  } else {
    clearListState();
  }
});

watch(canView, (allowed) => {
  if (!allowed) {
    clearListState();
    return;
  }
  void Promise.all([loadFolders(), loadDocs()]);
});

function selectFolder(fid: number | null) {
  activeFolderId.value = fid;
  page.value = 1;
  searchActive.value = false;
  searchQuery.value = '';
}

function onSearch() {
  if (!canView.value) return;
  if (searchQuery.value.trim()) {
    searchActive.value = true;
    page.value = 1;
    loadDocs();
  } else {
    searchActive.value = false;
    loadDocs();
  }
}

function clearSearch() {
  if (!canView.value) return;
  searchQuery.value = '';
  searchActive.value = false;
  page.value = 1;
  loadDocs();
}

async function onNewDoc() {
  if (!canCreate.value) return;
  try {
    const res = await createDoc({
      title: $t('plugin.novusdoc.doc.untitled'),
      folder_id: activeFolderId.value,
      status: 'draft',
    });
    const doc = res.document;
    navigateToEditor(doc.id);
  } catch {
    // silently fail / 静默失败
  }
}

function navigateToEditor(docId: number) {
  const base = isAdmin.value ? '/admin/plugins/novusdoc' : '/tenant/plugins/novusdoc';
  const target = `${base}/editor/${docId}`;
  if (shared?.router) {
    shared.router.push(target);
  } else {
    window.location.href = target;
  }
}

// ── Folder management / 文件夹管理 ───────────────────────

const newFolderVisible = ref(false);
const newFolderName = ref('');
const newFolderSaving = ref(false);

async function confirmNewFolder() {
  if (!canCreate.value || !newFolderName.value.trim()) return;
  newFolderSaving.value = true;
  try {
    await createFolder({ name: newFolderName.value.trim(), parent_id: null });
    newFolderVisible.value = false;
    newFolderName.value = '';
    await loadFolders();
  } finally {
    newFolderSaving.value = false;
  }
}

// ── Delete / 删除 ─────────────────────────────────────────

const deleteConfirmVisible = ref(false);
const deleteTarget = ref<DocItem | null>(null);
const deleteLoading = ref(false);

function askDelete(doc: DocItem) {
  if (!canDelete.value) return;
  deleteTarget.value = doc;
  deleteConfirmVisible.value = true;
}

async function confirmDeleteDoc() {
  if (!canDelete.value || !deleteTarget.value) return;
  deleteLoading.value = true;
  try {
    await deleteDoc(deleteTarget.value.id);
    deleteConfirmVisible.value = false;
    deleteTarget.value = null;
    await loadDocs();
  } finally {
    deleteLoading.value = false;
  }
}

const deleteFolderConfirmVisible = ref(false);
const deleteFolderTarget = ref<Folder | null>(null);

function askDeleteFolder(f: Folder) {
  if (!canDelete.value) return;
  deleteFolderTarget.value = f;
  deleteFolderConfirmVisible.value = true;
}

async function confirmDeleteFolder() {
  if (!canDelete.value || !deleteFolderTarget.value) return;
  try {
    await deleteFolder(deleteFolderTarget.value.id);
    deleteFolderConfirmVisible.value = false;
    if (activeFolderId.value === deleteFolderTarget.value.id) {
      activeFolderId.value = null;
    }
    deleteFolderTarget.value = null;
    await loadFolders();
  } catch {
    // silently fail / 静默失败
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)));
</script>

<template>
  <div class="flex h-full bg-background text-foreground">
    <div
      v-if="!canView"
      data-testid="novusdoc-no-permission"
      class="flex flex-1 items-center justify-center text-sm text-muted-foreground"
    >
      {{ $t('common.noPermissions') }}
    </div>
    <template v-else>
    <!-- ── Left Sidebar: Folders ── -->
    <aside class="w-56 shrink-0 border-r border-border flex flex-col bg-card">
      <div class="px-4 py-3 flex items-center justify-between border-b border-border">
        <span class="text-sm font-semibold">{{ $t('plugin.novusdoc.folder.title') }}</span>
        <button
          v-if="canCreate"
          data-testid="novusdoc-new-folder"
          class="w-6 h-6 flex items-center justify-center rounded hover:bg-accent text-muted-foreground"
          :title="$t('plugin.novusdoc.folder.newFolder')"
          @click="newFolderVisible = true"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto py-1">
        <button
          class="w-full px-4 py-2 text-left text-sm flex items-center gap-2 transition-colors"
          :class="activeFolderId === null && !searchActive ? 'bg-accent text-accent-foreground font-medium' : 'hover:bg-accent/50 text-muted-foreground'"
          @click="selectFolder(null)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" /></svg>
          {{ $t('plugin.novusdoc.folder.allDocs') }}
        </button>
        <div
          v-for="f in folders"
          :key="f.id"
          role="button"
          tabindex="0"
          class="group w-full cursor-pointer px-4 py-2 text-left text-sm flex items-center gap-2 transition-colors"
          :class="activeFolderId === f.id ? 'bg-accent text-accent-foreground font-medium' : 'hover:bg-accent/50 text-muted-foreground'"
          @click="selectFolder(f.id)"
          @keydown.enter="selectFolder(f.id)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" /></svg>
          <span class="flex-1 truncate">{{ f.name }}</span>
          <button
            v-if="canDelete"
            class="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded text-muted-foreground hover:text-destructive"
            :title="$t('plugin.novusdoc.folder.delete')"
            @click.stop="askDeleteFolder(f)"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
          </button>
        </div>
      </nav>
    </aside>

    <!-- ── Main Area ── -->
    <main class="flex-1 min-w-0 flex flex-col overflow-hidden">
      <!-- Toolbar -->
      <header class="px-4 py-3 flex items-center gap-3 border-b border-border bg-card shrink-0">
        <!-- Search -->
        <div class="relative flex-1 max-w-sm">
          <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
          <input
            v-model="searchQuery"
            class="w-full pl-8 pr-8 py-1.5 text-sm rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            :placeholder="$t('plugin.novusdoc.search.placeholder')"
            @keyup.enter="onSearch"
          />
          <button
            v-if="searchQuery"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            @click="clearSearch"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>

        <div class="flex-1" />

        <!-- New document button -->
        <button
          v-if="canCreate"
          data-testid="novusdoc-new-doc"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          @click="onNewDoc"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          {{ $t('plugin.novusdoc.doc.newDoc') }}
        </button>
      </header>

      <!-- Document grid -->
      <div class="flex-1 overflow-y-auto p-4">
        <div v-if="loading" class="flex items-center justify-center h-32 text-muted-foreground text-sm">
          <svg class="animate-spin mr-2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
          {{ $t('common.loading') }}
        </div>

        <div v-else-if="docs.length === 0" class="flex flex-col items-center justify-center h-32 text-muted-foreground text-sm gap-2">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
          {{ searchActive ? $t('plugin.novusdoc.search.noResults') : $t('plugin.novusdoc.search.noResults') }}
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          <div
            v-for="doc in docs"
            :key="doc.id"
            class="group relative border border-border rounded-lg p-4 hover:shadow-md hover:border-primary/30 transition-all cursor-pointer bg-card"
            @click="navigateToEditor(doc.id)"
          >
            <!-- Pin indicator -->
            <div v-if="doc.is_pinned" class="absolute top-2 right-2 text-amber-500">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2z" /></svg>
            </div>

            <!-- Title -->
            <h3 class="text-sm font-medium truncate pr-6">{{ doc.title }}</h3>

            <!-- Meta row -->
            <div class="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
              <span
                class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium"
                :class="doc.status === 'published' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'"
              >
                {{ doc.status === 'published' ? $t('plugin.novusdoc.status.published') : $t('plugin.novusdoc.status.draft') }}
              </span>
              <span>{{ doc.word_count }} {{ $t('plugin.novusdoc.doc.wordCount') }}</span>
            </div>

            <!-- Date -->
            <p class="mt-1.5 text-xs text-muted-foreground/70">
              {{ formatDate(doc.updated_at) }}
            </p>

            <!-- Actions (hover) -->
            <div class="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
              <button
                v-if="canDelete"
                data-testid="novusdoc-delete-doc"
                class="w-7 h-7 flex items-center justify-center rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                :title="$t('plugin.novusdoc.doc.deleteDoc')"
                @click.stop="askDelete(doc)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="mt-4 flex items-center justify-center gap-2">
          <button
            :disabled="page <= 1"
            class="px-3 py-1 text-sm rounded border border-input hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
            @click="page--"
          >
            ‹
          </button>
          <span class="text-sm text-muted-foreground">{{ page }} / {{ totalPages }}</span>
          <button
            :disabled="page >= totalPages"
            class="px-3 py-1 text-sm rounded border border-input hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
            @click="page++"
          >
            ›
          </button>
        </div>
      </div>
    </main>

    <!-- ── New Folder Modal ── -->
    <teleport to="body">
      <div v-if="newFolderVisible" class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50" @click.self="newFolderVisible = false">
        <div class="bg-card rounded-lg shadow-lg p-6 w-80">
          <h3 class="text-base font-semibold mb-4">{{ $t('plugin.novusdoc.folder.newFolder') }}</h3>
          <input
            v-model="newFolderName"
            class="w-full px-3 py-2 text-sm rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            :placeholder="$t('plugin.novusdoc.folder.title')"
            @keyup.enter="confirmNewFolder"
          />
          <div class="mt-4 flex justify-end gap-2">
            <button class="px-3 py-1.5 text-sm rounded border border-input hover:bg-accent" @click="newFolderVisible = false">{{ $t('common.cancel') }}</button>
            <button
              class="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              :disabled="!newFolderName.trim() || newFolderSaving"
              @click="confirmNewFolder"
            >
              {{ newFolderSaving ? '...' : $t('common.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ── Delete Doc Confirm Modal ── -->
    <teleport to="body">
      <div v-if="deleteConfirmVisible" class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50" @click.self="deleteConfirmVisible = false">
        <div class="bg-card rounded-lg shadow-lg p-6 w-80">
          <h3 class="text-base font-semibold mb-2">{{ $t('plugin.novusdoc.doc.deleteDoc') }}</h3>
          <p class="text-sm text-muted-foreground mb-4">{{ $t('plugin.novusdoc.doc.deleteConfirm') }}</p>
          <div class="flex justify-end gap-2">
            <button class="px-3 py-1.5 text-sm rounded border border-input hover:bg-accent" @click="deleteConfirmVisible = false">{{ $t('common.cancel') }}</button>
            <button
              class="px-3 py-1.5 text-sm rounded bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
              :disabled="deleteLoading"
              @click="confirmDeleteDoc"
            >
              {{ deleteLoading ? '...' : $t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ── Delete Folder Confirm Modal ── -->
    <teleport to="body">
      <div v-if="deleteFolderConfirmVisible" class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50" @click.self="deleteFolderConfirmVisible = false">
        <div class="bg-card rounded-lg shadow-lg p-6 w-80">
          <h3 class="text-base font-semibold mb-2">{{ $t('plugin.novusdoc.folder.delete') }}</h3>
          <p class="text-sm text-muted-foreground mb-4">{{ $t('plugin.novusdoc.doc.deleteConfirm') }}</p>
          <div class="flex justify-end gap-2">
            <button class="px-3 py-1.5 text-sm rounded border border-input hover:bg-accent" @click="deleteFolderConfirmVisible = false">{{ $t('common.cancel') }}</button>
            <button
              class="px-3 py-1.5 text-sm rounded bg-destructive text-destructive-foreground hover:bg-destructive/90"
              @click="confirmDeleteFolder"
            >
              {{ $t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </teleport>
    </template>
  </div>
</template>

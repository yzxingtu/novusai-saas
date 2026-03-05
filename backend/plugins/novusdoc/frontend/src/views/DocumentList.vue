<script lang="ts" setup>
import { ref, computed, onMounted, watch } from 'vue';
import { Button, Input, Empty, Spin, Dropdown, Menu, Modal, Tag, Tooltip } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import { useRoute, useRouter } from 'vue-router';

import type { DocItem, FolderItem } from '../api/docs';
import {
  listDocsApi,
  createDocApi,
  deleteDocApi,
  listFoldersApi,
  createFolderApi,
  deleteFolderApi,
} from '../api/docs';

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const docs = ref<DocItem[]>([]);
const total = ref(0);
const page = ref(1);
const size = ref(20);
const searchQuery = ref('');
const activeFolderId = ref<number | null>(null);
const folders = ref<FolderItem[]>([]);
const folderTree = ref<FolderItem[]>([]);

function getRouteBase(): string {
  const path = route.path;
  if (path.startsWith('/admin')) return '/admin/plugins/novusdoc';
  return '/tenant/plugins/novusdoc';
}

function openDocEditor(docId: number) {
  router.push(`${getRouteBase()}/docs/${docId}`);
}

async function loadDocs() {
  loading.value = true;
  try {
    const params: Record<string, string> = {
      'page[number]': String(page.value),
      'page[size]': String(size.value),
      sort: '-updated_at',
    };
    if (activeFolderId.value !== null) {
      params['filter[folder_id][eq]'] = String(activeFolderId.value);
    }
    if (searchQuery.value.trim()) {
      params['filter[title][ilike]'] = searchQuery.value.trim();
    }
    const res = await listDocsApi(params) as unknown as Record<string, unknown>;
    docs.value = (res.items as DocItem[]) || [];
    total.value = (res.total as number) || 0;
  } catch {
    // handled by global interceptor
  } finally {
    loading.value = false;
  }
}

async function loadFolders() {
  try {
    const res = await listFoldersApi() as unknown as Record<string, unknown>;
    folders.value = (res.items as FolderItem[]) || [];
    folderTree.value = (res.tree as FolderItem[]) || [];
  } catch {
    // handled by global interceptor
  }
}

async function handleCreateDoc() {
  try {
    const res = await createDocApi({ title: '', status: 'draft' }) as unknown as DocItem;
    if (res?.id) {
      openDocEditor(res.id);
    }
  } catch {
    // handled by global interceptor
  }
}

async function handleDeleteDoc(doc: DocItem) {
  Modal.confirm({
    title: $t('plugin.novusdoc.doc.delete'),
    content: $t('plugin.novusdoc.doc.deleteConfirm'),
    okType: 'danger',
    async onOk() {
      await deleteDocApi(doc.id);
      await loadDocs();
    },
  });
}

const folderModalVisible = ref(false);
const newFolderName = ref('');

function handleCreateFolder() {
  newFolderName.value = '';
  folderModalVisible.value = true;
}

async function confirmCreateFolder() {
  if (!newFolderName.value.trim()) return;
  try {
    await createFolderApi({ name: newFolderName.value.trim() });
    folderModalVisible.value = false;
    await loadFolders();
  } catch {
    // handled by global interceptor
  }
}

function selectFolder(id: number | null) {
  activeFolderId.value = id;
  page.value = 1;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}

watch([activeFolderId, page], () => loadDocs());

onMounted(() => {
  loadDocs();
  loadFolders();
});
</script>

<template>
  <div class="flex h-full min-h-0 max-md:flex-col">
    <!-- Sidebar: Folder tree -->
    <aside class="flex w-[240px] min-w-[240px] flex-col border-r border-border bg-background py-4 max-lg:w-[200px] max-lg:min-w-[200px] max-md:w-full max-md:min-w-0 max-md:max-h-[140px] max-md:border-b max-md:border-r-0 max-md:py-2">
      <div class="flex items-center justify-between px-4 pb-3 pt-1">
        <span class="font-semibold text-sm text-foreground">
          <IconifyIcon icon="lucide:folder" class="mr-1 inline size-4" />
          {{ $t('plugin.novusdoc.folder.all') }}
        </span>
        <Tooltip :title="$t('plugin.novusdoc.folder.create')">
          <Button size="small" type="text" @click="handleCreateFolder">
            <IconifyIcon icon="lucide:folder-plus" class="size-4" />
          </Button>
        </Tooltip>
      </div>

      <div class="flex-1 overflow-y-auto px-2 max-md:flex max-md:gap-1 max-md:overflow-x-auto">
        <div
          class="nd-fitem flex cursor-pointer items-center rounded-md px-3 py-2 text-[13px] text-foreground transition-all hover:bg-accent max-md:shrink-0 max-md:whitespace-nowrap max-md:py-1.5"
          :class="{ 'bg-primary/10 !text-primary font-semibold': activeFolderId === null }"
          @click="selectFolder(null)"
        >
          <IconifyIcon icon="lucide:files" class="size-4 mr-2 text-muted-foreground" />
          <span>{{ $t('plugin.novusdoc.folder.all') }}</span>
        </div>

        <div
          v-for="folder in folderTree"
          :key="folder.id"
          class="nd-fitem flex cursor-pointer items-center rounded-md px-3 py-2 text-[13px] text-foreground transition-all hover:bg-accent max-md:shrink-0 max-md:whitespace-nowrap max-md:py-1.5"
          :class="{ 'bg-primary/10 !text-primary font-semibold': activeFolderId === folder.id }"
          @click="selectFolder(folder.id)"
        >
          <IconifyIcon icon="lucide:folder" class="size-4 mr-2 text-muted-foreground" />
          <span>{{ folder.name }}</span>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex flex-1 flex-col overflow-y-auto bg-background px-7 py-5 min-w-0 max-md:px-4 max-md:py-3">
      <!-- Toolbar -->
      <div class="mb-5 flex items-center justify-between gap-3 max-md:mb-3 max-md:flex-wrap max-md:gap-2">
        <Button type="primary" @click="handleCreateDoc">
          <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
          {{ $t('plugin.novusdoc.doc.create') }}
        </Button>

        <Input.Search
          v-model:value="searchQuery"
          :placeholder="$t('plugin.novusdoc.doc.search')"
          allow-clear
          style="width: 260px"
          @search="loadDocs"
        />
      </div>

      <!-- Document grid -->
      <Spin :spinning="loading">
        <div v-if="docs.length === 0 && !loading" class="flex justify-center py-20 opacity-80">
          <Empty :description="$t('plugin.novusdoc.doc.empty')">
            <Button type="primary" @click="handleCreateDoc">
              <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
              {{ $t('plugin.novusdoc.doc.create') }}
            </Button>
          </Empty>
        </div>

        <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4 max-lg:grid-cols-[repeat(auto-fill,minmax(220px,1fr))] max-lg:gap-3 max-md:grid-cols-1 max-md:gap-2.5">
          <div
            v-for="doc in docs"
            :key="doc.id"
            class="nd-dcard relative cursor-pointer rounded-[10px] border border-border bg-card p-[18px_20px] transition-all hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-md max-md:p-[14px_16px]"
            @click="openDocEditor(doc.id)"
          >
            <div class="flex items-start justify-between gap-2">
              <h3 class="m-0 line-clamp-2 text-sm font-semibold leading-normal text-foreground">
                {{ doc.title || $t('plugin.novusdoc.doc.untitled') }}
              </h3>
              <Dropdown>
                <template #overlay>
                  <Menu>
                    <Menu.Item key="star">
                      <IconifyIcon :icon="doc.is_starred ? 'lucide:star-off' : 'lucide:star'" class="mr-1 size-4" />
                      {{ doc.is_starred ? $t('plugin.novusdoc.doc.unstar') : $t('plugin.novusdoc.doc.star') }}
                    </Menu.Item>
                    <Menu.Divider />
                    <Menu.Item key="delete" danger @click.stop="handleDeleteDoc(doc)">
                      <IconifyIcon icon="lucide:trash-2" class="mr-1 size-4" />
                      {{ $t('plugin.novusdoc.doc.delete') }}
                    </Menu.Item>
                  </Menu>
                </template>
                <Button size="small" type="text" @click.stop>
                  <IconifyIcon icon="lucide:more-horizontal" class="size-4" />
                </Button>
              </Dropdown>
            </div>

            <div class="mt-3.5 flex justify-between border-t border-border/50 pt-3">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:file-text" class="size-3 text-muted-foreground" />
                <span class="text-muted-foreground text-xs">{{ doc.word_count }} {{ $t('plugin.novusdoc.doc.chars') }}</span>
              </span>
              <span class="text-muted-foreground text-xs">{{ formatDate(doc.updated_at) }}</span>
            </div>

            <div v-if="doc.is_starred" class="absolute right-2.5 top-2.5">
              <IconifyIcon icon="lucide:star" class="size-3.5 text-warning" />
            </div>
          </div>
        </div>
      </Spin>
    </main>

    <!-- Folder creation Modal -->
    <Modal
      v-model:open="folderModalVisible"
      :title="$t('plugin.novusdoc.folder.create')"
      :ok-text="$t('plugin.novusdoc.folder.create')"
      :cancel-text="$t('plugin.novusdoc.common.cancel')"
      @ok="confirmCreateFolder"
      :ok-button-props="{ disabled: !newFolderName.trim() }"
    >
      <Input
        v-model:value="newFolderName"
        :placeholder="$t('plugin.novusdoc.folder.namePrompt')"
        @pressEnter="confirmCreateFolder"
        autofocus
        class="mt-2"
      />
    </Modal>
  </div>
</template>

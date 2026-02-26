<script lang="ts" setup>
import { ref, computed, onMounted, watch } from 'vue';
import { Button, Input, Empty, Spin, Dropdown, Menu, Modal, Tag, Tooltip } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import { useRouter } from 'vue-router';

import type { DocItem, FolderItem } from '../api/docs';
import {
  listDocsApi,
  createDocApi,
  deleteDocApi,
  listFoldersApi,
  createFolderApi,
  deleteFolderApi,
} from '../api/docs';

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

function openDocEditor(docId: number) {
  router.push(`/tenant/plugins/novusdoc/docs/${docId}`);
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
  <div class="nd-doc-list-page">
    <!-- Sidebar: Folder tree -->
    <aside class="nd-sidebar">
      <div class="nd-sidebar-header">
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

      <div class="nd-folder-list">
        <div
          class="nd-folder-item"
          :class="{ 'nd-folder-active': activeFolderId === null }"
          @click="selectFolder(null)"
        >
          <IconifyIcon icon="lucide:files" class="size-4 mr-2 text-muted-foreground" />
          <span>{{ $t('plugin.novusdoc.folder.all') }}</span>
        </div>

        <div
          v-for="folder in folderTree"
          :key="folder.id"
          class="nd-folder-item"
          :class="{ 'nd-folder-active': activeFolderId === folder.id }"
          @click="selectFolder(folder.id)"
        >
          <IconifyIcon icon="lucide:folder" class="size-4 mr-2 text-muted-foreground" />
          <span>{{ folder.name }}</span>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="nd-main">
      <!-- Toolbar -->
      <div class="nd-toolbar-row">
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
        <div v-if="docs.length === 0 && !loading" class="nd-empty">
          <Empty :description="$t('plugin.novusdoc.doc.empty')">
            <Button type="primary" @click="handleCreateDoc">
              <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
              {{ $t('plugin.novusdoc.doc.create') }}
            </Button>
          </Empty>
        </div>

        <div v-else class="nd-doc-grid">
          <div
            v-for="doc in docs"
            :key="doc.id"
            class="nd-doc-card"
            @click="openDocEditor(doc.id)"
          >
            <div class="nd-doc-card-header">
              <h3 class="nd-doc-title">
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

            <div class="nd-doc-card-meta">
              <span class="nd-doc-meta-item">
                <IconifyIcon icon="lucide:file-text" class="size-3 text-muted-foreground" />
                <span class="text-muted-foreground text-xs">{{ doc.word_count }} {{ $t('plugin.novusdoc.doc.chars') }}</span>
              </span>
              <span class="text-muted-foreground text-xs">{{ formatDate(doc.updated_at) }}</span>
            </div>

            <div v-if="doc.is_starred" class="nd-doc-card-star">
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
      :cancel-text="$t('common.cancel')"
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

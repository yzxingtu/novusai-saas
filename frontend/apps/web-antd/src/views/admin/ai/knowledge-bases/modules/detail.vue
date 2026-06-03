<script lang="ts" setup>
/**
 * Admin knowledge base detail drawer
 * 管理端知识库详情抽屉
 *
 * Tab 1: Document management (list + upload + delete + retry + progress)
 * Tab 1: 文档管理（列表+上传+删除+重试+进度）
 * Tab 2: Search test / 检索测试
 */
import type {
  AdminKnowledgeDocumentItem,
  AdminSearchResultItem,
} from '#/api/admin/knowledge-bases';

import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  watch,
} from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { Tabs } from 'ant-design-vue';

import {
  batchImportAdminQAApi,
  createAdminQAPairApi,
  createAdminTextDocumentApi,
  deleteAdminDocumentApi,
  getAdminDocumentChunksApi,
  getAdminDocumentListApi,
  getAdminDocumentProgressApi,
  importAdminUrlApi,
  reindexAdminKnowledgeBaseApi,
  retryAdminDocumentApi,
  searchAdminKnowledgeBaseApi,
  uploadAdminDocumentApi,
} from '#/api/admin/knowledge-bases';
import {
  KnowledgeBaseChunkPreviewModal,
  KnowledgeBaseDocumentSection,
  KnowledgeBaseDocumentToolbar,
  KnowledgeBaseSearchSection,
} from '#/components/business/knowledge-base-detail';
import {
  useKnowledgeBaseChunkPreview,
  useKnowledgeBaseDocumentActions,
  useKnowledgeBaseDocumentFeed,
  useKnowledgeBaseSearch,
} from '#/composables/knowledge-base-detail';
import { $t } from '#/locales';
import { useSocketIOStore } from '#/store/shared/socketio';

const emit = defineEmits<{ success: [] }>();

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen) {
    isDrawerOpen.value = isOpen;
    if (isOpen) {
      const data = drawerApi.getData<{ id: number; name: string }>();
      if (data) {
        kbId.value = data.id;
        kbName.value = data.name;
        loadDocuments();
      }
    } else {
      stopWsListener();
    }
  },
});

// ========== Base state / 基础状态 ==========
const kbId = ref(0);
const kbName = ref('');
const isDrawerOpen = ref(false);
const activeTab = ref('documents');
const socketStore = useSocketIOStore();

const {
  docPage,
  docProgress,
  docTotal,
  documents,
  loadDocuments,
  loading,
  startWsListener,
  stopWsListener,
} = useKnowledgeBaseDocumentFeed<AdminKnowledgeDocumentItem>({
  kbId,
  listDocuments: getAdminDocumentListApi,
  getDocumentProgress: getAdminDocumentProgressApi,
  onTerminalStatus: () => {
    emit('success');
  },
  socketStore,
});

const {
  handleDeleteDoc,
  handleDocPickerSuccess,
  handleQABatchImport,
  handleQASubmit,
  handleReindex,
  handleRetryDoc,
  handleTextSubmit,
  handleUploadFile,
  handleUrlImport,
} = useKnowledgeBaseDocumentActions<AdminKnowledgeDocumentItem>({
  kbId,
  uploadDocument: uploadAdminDocumentApi,
  createTextDocument: createAdminTextDocumentApi,
  createQAPair: createAdminQAPairApi,
  qaBatchImport: batchImportAdminQAApi,
  urlImport: importAdminUrlApi,
  deleteTitleKey: 'admin.knowledgeBase.document.delete',
  deleteDocument: deleteAdminDocumentApi,
  retryDocument: retryAdminDocumentApi,
  reindex: reindexAdminKnowledgeBaseApi,
  reindexConfirmKey: 'admin.knowledgeBase.reindex.confirm',
  reindexStartedKey: 'admin.knowledgeBase.reindex.started',
  reindexTitleKey: 'admin.knowledgeBase.reindex.title',
  successMessageKey: 'admin.common.operationSuccess',
  onMutated: async () => {
    await loadDocuments();
    emit('success');
  },
});

onBeforeUnmount(stopWsListener);
onDeactivated(stopWsListener);
onActivated(() => {
  if (isDrawerOpen.value) {
    startWsListener();
  }
});

const {
  chunkPreviewVisible,
  chunkPreviewDoc,
  chunkList,
  chunkLoading,
  chunkPage,
  chunkTotal,
  loadChunks,
  openChunkPreview,
} = useKnowledgeBaseChunkPreview<
  AdminKnowledgeDocumentItem,
  {
    char_count: number;
    chunk_index: number;
    content: string;
    id: number;
  }
>({
  kbId,
  getChunks: getAdminDocumentChunksApi,
});

const {
  handleSearch,
  searchLoading,
  searchMode,
  searchQuery,
  searchResults,
  searchScoreThreshold,
  searchTopK,
} = useKnowledgeBaseSearch<AdminSearchResultItem>({
  kbId,
  search: searchAdminKnowledgeBaseApi,
});

const searchModeOptions = computed(() => [
  { label: $t('admin.knowledgeBase.searchMode.hybrid'), value: 'hybrid' },
  { label: $t('admin.knowledgeBase.searchMode.vector'), value: 'vector' },
  { label: $t('admin.knowledgeBase.searchMode.keyword'), value: 'keyword' },
]);

watch(activeTab, (tab) => {
  if (tab === 'documents') {
    loadDocuments();
  }
});
</script>

<template>
  <Drawer
    :title="`${$t('admin.knowledgeBase.detail')} - ${kbName}`"
    class="w-[960px]"
  >
    <Tabs v-model:active-key="activeTab">
      <!-- ==================== Document management / 文档管理 ==================== -->
      <Tabs.TabPane
        key="documents"
        :tab="$t('admin.knowledgeBase.document.title')"
      >
        <KnowledgeBaseDocumentToolbar
          i18n-prefix="admin.knowledgeBase"
          :on-upload-file="handleUploadFile"
          :on-text-submit="handleTextSubmit"
          :on-q-a-submit="handleQASubmit"
          :on-q-a-batch-import="handleQABatchImport"
          :on-url-import="handleUrlImport"
          :on-reindex="handleReindex"
          :on-success="handleDocPickerSuccess"
          reindex-access-code="ai_knowledge_base:update"
        />
        <KnowledgeBaseDocumentSection
          :documents="documents"
          :empty-text="$t('admin.knowledgeBase.emptyDocuments')"
          i18n-prefix="admin.knowledgeBase"
          :loading="loading"
          :progress-map="docProgress"
          :current-page="docPage"
          :total="docTotal"
          @delete="(doc) => handleDeleteDoc(doc as AdminKnowledgeDocumentItem)"
          @open-chunks="
            (doc) => openChunkPreview(doc as AdminKnowledgeDocumentItem)
          "
          @page-change="
            (page) => {
              docPage = page;
              loadDocuments();
            }
          "
          @retry="(doc) => handleRetryDoc(doc as AdminKnowledgeDocumentItem)"
        />
      </Tabs.TabPane>

      <!-- ==================== Search test / 检索测试 ==================== -->
      <Tabs.TabPane
        key="search"
        :tab="$t('admin.knowledgeBase.searchTest.title')"
      >
        <KnowledgeBaseSearchSection
          v-model:query="searchQuery"
          v-model:score-threshold="searchScoreThreshold"
          v-model:search-mode="searchMode"
          v-model:top-k="searchTopK"
          i18n-prefix="admin.knowledgeBase"
          :loading="searchLoading"
          :results="searchResults"
          :search-mode-options="searchModeOptions"
          @search="handleSearch"
        />
      </Tabs.TabPane>
    </Tabs>
    <KnowledgeBaseChunkPreviewModal
      v-model:open="chunkPreviewVisible"
      common-i18n-prefix="admin.common"
      :chunks="chunkList"
      :current-page="chunkPage"
      :file-name="chunkPreviewDoc?.file_name"
      i18n-prefix="admin.knowledgeBase"
      :loading="chunkLoading"
      :total="chunkTotal"
      @page-change="
        (page) => {
          chunkPage = page;
          loadChunks();
        }
      "
    />
  </Drawer>
</template>

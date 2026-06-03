<script lang="ts" setup>
/**
 * Knowledge base detail drawer
 * 知识库详情抽屉
 *
 * Tab 1: Document management (list + upload + delete + retry + progress)
 * Tab 1: 文档管理（列表+上传+删除+重试+进度）
 * Tab 2: Search test / 检索测试
 */
import type {
  KnowledgeDocumentItem,
  SearchResultItem,
} from '#/api/tenant/knowledge-bases';

import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  watch,
} from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { Tabs, Tag } from 'ant-design-vue';

import {
  batchImportQAApi,
  createQAPairApi,
  createTextDocumentApi,
  deleteDocumentApi,
  getDocumentChunksApi,
  getDocumentListApi,
  getDocumentProgressApi,
  importUrlApi,
  reindexKnowledgeBaseApi,
  retryDocumentApi,
  searchKnowledgeBaseApi,
  uploadDocumentApi,
} from '#/api/tenant/knowledge-bases';
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
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getSearchModeOptions, isTenantOwnedKnowledgeBase } from '../data';

const emit = defineEmits<{ success: [] }>();

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen) {
    isDrawerOpen.value = isOpen;
    if (isOpen) {
      const data = drawerApi.getData<{
        id: number;
        name: string;
        scope?: string;
        tenantId?: null | number;
      }>();
      if (data) {
        kbId.value = data.id;
        kbName.value = data.name;
        kbScope.value = data.scope || 'all_tenants';
        kbOwnerTenantId.value = data.tenantId ?? null;
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
const kbScope = ref('all_tenants');
const kbOwnerTenantId = ref<null | number>(null);
const isDrawerOpen = ref(false);
const isTenantOwned = computed(() =>
  isTenantOwnedKnowledgeBase(kbOwnerTenantId.value),
);
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
} = useKnowledgeBaseDocumentFeed<KnowledgeDocumentItem>({
  kbId,
  listDocuments: getDocumentListApi,
  getDocumentProgress: getDocumentProgressApi,
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
} = useKnowledgeBaseDocumentActions<KnowledgeDocumentItem>({
  kbId,
  uploadDocument: uploadDocumentApi,
  createTextDocument: createTextDocumentApi,
  createQAPair: createQAPairApi,
  qaBatchImport: batchImportQAApi,
  urlImport: importUrlApi,
  deleteTitleKey: 'tenant.knowledgeBase.document.delete',
  deleteDocument: deleteDocumentApi,
  retryDocument: retryDocumentApi,
  reindex: reindexKnowledgeBaseApi,
  reindexConfirmKey: 'tenant.knowledgeBase.reindex.confirm',
  reindexStartedKey: 'tenant.knowledgeBase.reindex.started',
  reindexTitleKey: 'tenant.knowledgeBase.reindex.title',
  successMessageKey: 'common.operationSuccess',
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
  KnowledgeDocumentItem,
  {
    char_count: number;
    chunk_index: number;
    content: string;
    id: number;
  }
>({
  kbId,
  getChunks: getDocumentChunksApi,
});

const {
  handleSearch,
  searchLoading,
  searchMode,
  searchQuery,
  searchResults,
  searchScoreThreshold,
  searchTopK,
} = useKnowledgeBaseSearch<SearchResultItem>({
  kbId,
  search: searchKnowledgeBaseApi,
});

const searchModeOptions = getSearchModeOptions();

watch(activeTab, (tab) => {
  if (tab === 'documents') {
    loadDocuments();
  }
});
</script>

<template>
  <Drawer
    :title="`${$t('tenant.knowledgeBase.detail')} - ${kbName}`"
    class="w-[960px]"
  >
    <!-- Scope readonly banner -->
    <div
      v-if="!isTenantOwned"
      class="mb-3 flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning"
    >
      <IconifyIcon icon="lucide:lock" class="size-3.5 shrink-0" />
      <span>{{ $t('tenant.knowledgeBase.readonlyHint') }}</span>
      <Tag :color="getScopeColor(kbScope)" class="ml-auto !text-[10px]">
        {{ getScopeText(kbScope) }}
      </Tag>
    </div>

    <Tabs v-model:active-key="activeTab">
      <!-- ==================== Document management / 文档管理 ==================== -->
      <Tabs.TabPane
        key="documents"
        :tab="$t('tenant.knowledgeBase.document.title')"
      >
        <KnowledgeBaseDocumentToolbar
          :can-manage="isTenantOwned"
          i18n-prefix="tenant.knowledgeBase"
          :on-upload-file="handleUploadFile"
          :on-text-submit="handleTextSubmit"
          :on-q-a-submit="handleQASubmit"
          :on-q-a-batch-import="handleQABatchImport"
          :on-url-import="handleUrlImport"
          :on-reindex="handleReindex"
          :on-success="handleDocPickerSuccess"
          reindex-access-code="knowledge_base:update"
        />
        <KnowledgeBaseDocumentSection
          :can-delete="isTenantOwned"
          :can-retry="isTenantOwned"
          :documents="documents"
          :empty-text="$t('tenant.knowledgeBase.searchTest.noResults')"
          i18n-prefix="tenant.knowledgeBase"
          :loading="loading"
          :progress-map="docProgress"
          :current-page="docPage"
          :total="docTotal"
          @delete="(doc) => handleDeleteDoc(doc as KnowledgeDocumentItem)"
          @open-chunks="(doc) => openChunkPreview(doc as KnowledgeDocumentItem)"
          @page-change="
            (page) => {
              docPage = page;
              loadDocuments();
            }
          "
          @retry="(doc) => handleRetryDoc(doc as KnowledgeDocumentItem)"
        />
      </Tabs.TabPane>

      <!-- ==================== Search test / 检索测试 ==================== -->
      <Tabs.TabPane
        key="search"
        :tab="$t('tenant.knowledgeBase.searchTest.title')"
      >
        <KnowledgeBaseSearchSection
          v-model:query="searchQuery"
          v-model:score-threshold="searchScoreThreshold"
          v-model:search-mode="searchMode"
          v-model:top-k="searchTopK"
          i18n-prefix="tenant.knowledgeBase"
          :loading="searchLoading"
          :results="searchResults"
          :search-mode-options="searchModeOptions"
          @search="handleSearch"
        />
      </Tabs.TabPane>
    </Tabs>
    <KnowledgeBaseChunkPreviewModal
      v-model:open="chunkPreviewVisible"
      common-i18n-prefix="tenant.common"
      :chunks="chunkList"
      :current-page="chunkPage"
      :file-name="chunkPreviewDoc?.file_name"
      i18n-prefix="tenant.knowledgeBase"
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

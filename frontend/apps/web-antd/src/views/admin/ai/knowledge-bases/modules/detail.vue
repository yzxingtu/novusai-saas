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
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  InputNumber,
  message,
  Modal,
  Pagination,
  Progress,
  Select,
  Spin,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

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
import { KnowledgeDocumentPicker } from '#/components/business/knowledge-document-picker';
import { $t } from '#/locales';
import { useSocketIOStore } from '#/store/shared/socketio';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

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
const loading = ref(false);

// ========== Document management / 文档管理 ==========
const documents = ref<AdminKnowledgeDocumentItem[]>([]);
const docTotal = ref(0);
const docPage = ref(1);
async function loadDocuments() {
  loading.value = true;
  try {
    const res = await getAdminDocumentListApi(kbId.value, {
      'page[number]': docPage.value,
      'page[size]': 20,
      sort: '-created_at',
    });
    documents.value = res.items;
    docTotal.value = res.total;
    startWsListener();
    fetchInitialProgress();
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    loading.value = false;
  }
}

// Document input callbacks (passed to KnowledgeDocumentPicker) / 文档录入回调（传给 KnowledgeDocumentPicker）
async function handleUploadFile(file: File) {
  await uploadAdminDocumentApi(kbId.value, file);
}

async function handleTextSubmit(data: { content: string; title: string }) {
  await createAdminTextDocumentApi(kbId.value, data);
}

async function handleQASubmit(data: { answer: string; question: string }) {
  await createAdminQAPairApi(kbId.value, data);
}

async function handleQABatchImport(file: File) {
  return await batchImportAdminQAApi(kbId.value, file);
}

async function handleUrlImport(urls: string[]) {
  return await importAdminUrlApi(kbId.value, urls);
}

function handleDocPickerSuccess() {
  loadDocuments();
  emit('success');
}

// Delete document / 删除文档
function handleDeleteDoc(doc: AdminKnowledgeDocumentItem) {
  Modal.confirm({
    title: $t('admin.knowledgeBase.document.delete'),
    content: doc.file_name,
    async onOk() {
      await deleteAdminDocumentApi(kbId.value, doc.id);
      message.success($t('admin.common.operationSuccess'));
      await loadDocuments();
      emit('success');
    },
  });
}

// Retry document / 重试文档
async function handleRetryDoc(doc: AdminKnowledgeDocumentItem) {
  try {
    await retryAdminDocumentApi(kbId.value, doc.id);
    message.success($t('admin.common.operationSuccess'));
    await loadDocuments();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

// Reindex / 重新向量化
function handleReindex() {
  Modal.confirm({
    title: $t('admin.knowledgeBase.reindex.title'),
    content: $t('admin.knowledgeBase.reindex.confirm'),
    async onOk() {
      const res = await reindexAdminKnowledgeBaseApi(kbId.value);
      message.success(
        `${$t('admin.knowledgeBase.reindex.started')} (${res.document_count})`,
      );
      await loadDocuments();
      emit('success');
    },
  });
}

// ========== WS real-time progress / WS 实时进度 ==========
interface DocProgressInfo {
  stage: string;
  progress: number;
  total_chunks: number;
  processed_chunks: number;
}
const docProgress = ref<Record<number, DocProgressInfo>>({});
const socketStore = useSocketIOStore();

function handleWsNotification(payload: unknown) {
  const msg = payload as Record<string, unknown>;
  if (msg?.type !== 'ai.kb_doc_progress') return;

  const d = msg.data as Record<string, unknown>;
  if (!d?.document_id) return;

  const docId = d.document_id as number;
  const kbIdFromWs = d.kb_id as number;

  // Only handle the currently opened knowledge base / 只处理当前打开的知识库
  if (kbIdFromWs && kbIdFromWs !== kbId.value) return;

  const prog: DocProgressInfo = {
    stage: (d.stage as string) || 'pending',
    progress: (d.progress as number) || 0,
    total_chunks: (d.total_chunks as number) || 0,
    processed_chunks: (d.processed_chunks as number) || 0,
  };

  docProgress.value[docId] = prog;

  // Update document status tag in real-time / 实时更新文档状态 Tag
  const found = documents.value.find((doc) => doc.id === docId);
  if (found && prog.stage && prog.stage !== found.status) {
    found.status = prog.stage;
  }

  // Refresh document list on completion or failure / 完成或失败时刷新文档列表
  if (['completed', 'error'].includes(prog.stage)) {
    loadDocuments();
    emit('success');
  }
}

function startWsListener() {
  if (!isDrawerOpen.value) return;
  socketStore.unregisterHandler('notification', handleWsNotification);
  socketStore.registerHandler('notification', handleWsNotification);
}

function stopWsListener() {
  socketStore.unregisterHandler('notification', handleWsNotification);
}

// Fetch initial progress for processing docs on drawer open (fallback: WS may not be connected) / 打开抽屉时一次性拉取处理中文档的进度（兜底：WS 可能未连接）
async function fetchInitialProgress() {
  const processingDocs = documents.value.filter(
    (d) => !['completed', 'error', 'pending'].includes(d.status),
  );
  for (const doc of processingDocs) {
    try {
      const prog = await getAdminDocumentProgressApi(kbId.value, doc.id);
      docProgress.value[doc.id] = prog;
      if (prog.stage && prog.stage !== doc.status) {
        doc.status = prog.stage;
      }
    } catch {
      // ignore / 忽略
    }
  }
}

onBeforeUnmount(stopWsListener);
onDeactivated(stopWsListener);
onActivated(() => {
  if (isDrawerOpen.value) {
    startWsListener();
  }
});

// ========== Document status helpers / 文档状态辅助 ==========
function getDocStatusText(status: string | undefined): string {
  if (!status) return '-';
  return $t(`admin.knowledgeBase.document.status.${status}`);
}

function getDocStatusColor(status: string | undefined): string {
  switch (status) {
    case 'chunking':
    case 'embedding':
    case 'parsing': {
      return 'processing';
    }
    case 'completed': {
      return 'success';
    }
    case 'error': {
      return 'error';
    }
    case 'pending': {
      return 'default';
    }
    default: {
      return 'default';
    }
  }
}

function getFileIcon(fileType: string): string {
  const t = (fileType || '').toLowerCase();
  if (t === 'pdf') return 'lucide:file-text';
  if (['doc', 'docx'].includes(t)) return 'lucide:file-type';
  if (['csv', 'xls', 'xlsx'].includes(t)) return 'lucide:sheet';
  if (['md', 'txt'].includes(t)) return 'lucide:file-code';
  if (t === 'url') return 'lucide:globe';
  if (t === 'qa') return 'lucide:message-circle-question';
  return 'lucide:file';
}

function getFileIconBg(fileType: string): string {
  const t = (fileType || '').toLowerCase();
  if (t === 'pdf') return 'bg-red-500/10';
  if (['doc', 'docx'].includes(t)) return 'bg-blue-500/10';
  if (['csv', 'xls', 'xlsx'].includes(t)) return 'bg-green-500/10';
  if (['md', 'txt'].includes(t)) return 'bg-amber-500/10';
  if (t === 'url') return 'bg-purple-500/10';
  if (t === 'qa') return 'bg-cyan-500/10';
  return 'bg-muted';
}

function getFileIconColor(fileType: string): string {
  const t = (fileType || '').toLowerCase();
  if (t === 'pdf') return 'text-red-500';
  if (['doc', 'docx'].includes(t)) return 'text-blue-500';
  if (['csv', 'xls', 'xlsx'].includes(t)) return 'text-green-500';
  if (['md', 'txt'].includes(t)) return 'text-amber-500';
  if (t === 'url') return 'text-purple-500';
  if (t === 'qa') return 'text-cyan-500';
  return 'text-muted-foreground';
}

// ========== Chunk preview / 分块预览 ==========
const chunkPreviewVisible = ref(false);
const chunkPreviewDoc = ref<AdminKnowledgeDocumentItem | null>(null);
const chunkList = ref<
  Array<{
    char_count: number;
    chunk_index: number;
    content: string;
    id: number;
  }>
>([]);
const chunkTotal = ref(0);
const chunkPage = ref(1);
const chunkLoading = ref(false);

async function openChunkPreview(doc: AdminKnowledgeDocumentItem) {
  chunkPreviewDoc.value = doc;
  chunkPage.value = 1;
  chunkPreviewVisible.value = true;
  await loadChunks();
}

async function loadChunks() {
  if (!chunkPreviewDoc.value) return;
  chunkLoading.value = true;
  try {
    const res = await getAdminDocumentChunksApi(
      kbId.value,
      chunkPreviewDoc.value.id,
      { page: chunkPage.value, page_size: 10 },
    );
    chunkList.value = res.chunks;
    chunkTotal.value = res.total;
  } catch {
    chunkList.value = [];
  } finally {
    chunkLoading.value = false;
  }
}

// ========== Search test / 检索测试 ==========
const searchQuery = ref('');
const searchLoading = ref(false);
const searchResults = ref<AdminSearchResultItem[]>([]);
const searchTopK = ref(5);
const searchScoreThreshold = ref(0.5);
const searchMode = ref('hybrid');
const searchModeOptions = computed(() => [
  { label: $t('admin.knowledgeBase.searchMode.hybrid'), value: 'hybrid' },
  { label: $t('admin.knowledgeBase.searchMode.vector'), value: 'vector' },
  { label: $t('admin.knowledgeBase.searchMode.keyword'), value: 'keyword' },
]);

async function handleSearch() {
  if (!searchQuery.value.trim()) return;
  searchLoading.value = true;
  try {
    searchResults.value = await searchAdminKnowledgeBaseApi(kbId.value, {
      query: searchQuery.value.trim(),
      top_k: searchTopK.value,
      score_threshold: searchScoreThreshold.value,
      search_mode: searchMode.value,
    });
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    searchLoading.value = false;
  }
}

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
        <!-- 操作栏 -->
        <div class="mb-4 flex items-center justify-between">
          <KnowledgeDocumentPicker
            :upload-fn="handleUploadFile"
            :text-fn="handleTextSubmit"
            :qa-fn="handleQASubmit"
            :qa-batch-fn="handleQABatchImport"
            :url-fn="handleUrlImport"
            @success="handleDocPickerSuccess"
          />
          <Button
            v-access:code="['ai_knowledge_base:update']"
            @click="handleReindex"
          >
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('admin.knowledgeBase.reindex.title') }}
          </Button>
        </div>

        <!-- 文档列表 -->
        <Spin :spinning="loading">
          <div
            v-if="documents.length === 0 && !loading"
            class="flex flex-col items-center justify-center py-16"
          >
            <div
              class="mb-3 flex size-14 items-center justify-center rounded-2xl bg-muted"
            >
              <IconifyIcon
                icon="lucide:file-text"
                class="size-7 text-muted-foreground"
              />
            </div>
            <p class="text-sm text-muted-foreground">
              {{ $t('admin.knowledgeBase.emptyDocuments') }}
            </p>
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="doc in documents"
              :key="doc.id"
              class="group flex items-center gap-4 rounded-lg border border-border/60 p-3.5 transition-colors hover:border-border hover:bg-accent/30"
            >
              <!-- File type icon -->
              <div
                class="flex size-10 shrink-0 items-center justify-center rounded-lg"
                :class="getFileIconBg(doc.file_type)"
              >
                <IconifyIcon
                  :icon="getFileIcon(doc.file_type)"
                  class="size-5"
                  :class="getFileIconColor(doc.file_type)"
                />
              </div>
              <!-- Document info -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="truncate text-sm font-medium text-foreground">{{
                    doc.file_name
                  }}</span>
                  <Tag
                    :color="getDocStatusColor(doc.status)"
                    class="shrink-0"
                    style="margin: 0"
                  >
                    {{ getDocStatusText(doc.status) }}
                  </Tag>
                </div>
                <div
                  class="mt-1 flex items-center gap-3 text-xs text-muted-foreground"
                >
                  <span class="inline-flex items-center gap-1">
                    <IconifyIcon icon="lucide:file" class="size-3" />
                    {{ (doc.file_type || '-').toUpperCase() }}
                  </span>
                  <span class="inline-flex items-center gap-1">
                    <IconifyIcon icon="lucide:hard-drive" class="size-3" />
                    {{ formatFileSize(doc.file_size) }}
                  </span>
                  <span class="inline-flex items-center gap-1">
                    <IconifyIcon icon="lucide:puzzle" class="size-3" />
                    {{ doc.chunk_count }}
                  </span>
                  <span class="inline-flex items-center gap-1">
                    <IconifyIcon icon="lucide:clock" class="size-3" />
                    {{ formatDate(doc.created_at) }}
                  </span>
                </div>
                <!-- Progress bar for processing docs -->
                <Progress
                  v-if="!['completed', 'error', 'pending'].includes(doc.status)"
                  :percent="docProgress[doc.id]?.progress ?? 0"
                  size="small"
                  :show-info="false"
                  :stroke-color="{
                    from: 'hsl(var(--primary))',
                    to: 'hsl(var(--success))',
                  }"
                  class="!mb-0 !mt-1.5 max-w-xs"
                />
                <!-- Error message -->
                <Tooltip
                  v-if="doc.error_message"
                  :title="doc.error_message"
                  :overlay-style="{ maxWidth: '400px' }"
                >
                  <span
                    class="mt-0.5 inline-block cursor-help truncate text-xs text-destructive"
                  >
                    {{ doc.error_message }}
                  </span>
                </Tooltip>
              </div>
              <!-- Action buttons -->
              <div
                class="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100"
              >
                <Tooltip
                  v-if="doc.status === 'completed'"
                  :title="$t('admin.knowledgeBase.document.viewChunks')"
                >
                  <Button
                    type="text"
                    size="small"
                    class="!size-8 !min-w-0 !p-0"
                    @click="openChunkPreview(doc)"
                  >
                    <IconifyIcon
                      icon="lucide:layers"
                      class="size-4 text-muted-foreground hover:text-primary"
                    />
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="doc.status === 'error'"
                  :title="$t('admin.knowledgeBase.document.retry')"
                >
                  <Button
                    type="text"
                    size="small"
                    class="!size-8 !min-w-0 !p-0"
                    @click="handleRetryDoc(doc)"
                  >
                    <IconifyIcon
                      icon="lucide:rotate-cw"
                      class="size-4 text-muted-foreground hover:text-warning"
                    />
                  </Button>
                </Tooltip>
                <Tooltip :title="$t('admin.knowledgeBase.document.delete')">
                  <Button
                    type="text"
                    size="small"
                    danger
                    class="!size-8 !min-w-0 !p-0"
                    @click="handleDeleteDoc(doc)"
                  >
                    <IconifyIcon icon="lucide:trash-2" class="size-4" />
                  </Button>
                </Tooltip>
              </div>
            </div>
          </div>
          <!-- Pagination -->
          <div v-if="docTotal > 20" class="mt-4 flex justify-end">
            <Pagination
              :current="docPage"
              :total="docTotal"
              :page-size="20"
              size="small"
              :show-size-changer="false"
              @change="
                (p: number) => {
                  docPage = p;
                  loadDocuments();
                }
              "
            />
          </div>
        </Spin>
      </Tabs.TabPane>

      <!-- ==================== Search test / 检索测试 ==================== -->
      <Tabs.TabPane
        key="search"
        :tab="$t('admin.knowledgeBase.searchTest.title')"
      >
        <!-- Search input -->
        <div class="mb-4">
          <Input
            v-model:value="searchQuery"
            :placeholder="$t('admin.knowledgeBase.searchTest.placeholder')"
            allow-clear
            @press-enter="handleSearch"
          >
            <template #prefix>
              <IconifyIcon
                icon="lucide:search"
                class="size-4 text-muted-foreground"
              />
            </template>
            <template #suffix>
              <Button
                type="primary"
                size="small"
                :loading="searchLoading"
                @click="handleSearch"
              >
                {{ $t('admin.knowledgeBase.searchTest.search') }}
              </Button>
            </template>
          </Input>
        </div>

        <!-- Search parameters -->
        <div
          class="mb-4 flex items-center gap-6 rounded-lg border border-border/60 bg-accent/20 px-4 py-3"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-muted-foreground">Top K</span>
            <InputNumber
              v-model:value="searchTopK"
              :min="1"
              :max="20"
              size="small"
              class="!w-[72px]"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-muted-foreground">
              {{ $t('admin.knowledgeBase.field.scoreThreshold') }}
            </span>
            <InputNumber
              v-model:value="searchScoreThreshold"
              :min="0"
              :max="1"
              :step="0.1"
              :precision="2"
              size="small"
              class="!w-20"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-muted-foreground">
              {{ $t('admin.knowledgeBase.field.searchMode') }}
            </span>
            <Select
              v-model:value="searchMode"
              size="small"
              class="!w-28"
              :options="searchModeOptions"
            />
          </div>
        </div>

        <!-- Search results -->
        <Spin :spinning="searchLoading">
          <Empty
            v-if="searchResults.length === 0 && !searchLoading"
            :description="$t('admin.knowledgeBase.searchTest.noResults')"
          />
          <div v-else class="space-y-3">
            <div
              v-for="(result, idx) in searchResults"
              :key="result.chunk_id"
              class="overflow-hidden rounded-lg border border-border/60 transition-colors hover:border-border"
            >
              <!-- Result header -->
              <div
                class="flex items-center justify-between border-b border-border/40 bg-accent/20 px-4 py-2"
              >
                <div class="flex items-center gap-2.5 text-xs">
                  <span
                    class="flex size-5 items-center justify-center rounded bg-primary/10 font-mono font-semibold text-primary"
                  >
                    {{ idx + 1 }}
                  </span>
                  <IconifyIcon
                    icon="lucide:file-text"
                    class="size-3.5 text-muted-foreground"
                  />
                  <span class="font-medium text-foreground">{{
                    result.document_name
                  }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <div class="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                    <div
                      class="h-full rounded-full bg-primary transition-all"
                      :style="{
                        width: `${Math.min(result.score * 100, 100)}%`,
                      }"
                    ></div>
                  </div>
                  <span class="font-mono text-xs font-medium text-primary">
                    {{ (result.score * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
              <!-- Result content -->
              <div class="px-4 py-3">
                <div
                  class="whitespace-pre-wrap text-sm leading-relaxed text-foreground"
                >
                  {{ result.content }}
                </div>
              </div>
            </div>
          </div>
        </Spin>
      </Tabs.TabPane>
    </Tabs>

    <!-- ==================== Chunk preview Modal / 分块预览 Modal ==================== -->
    <Modal
      v-model:open="chunkPreviewVisible"
      :title="`${$t('admin.knowledgeBase.document.viewChunks')} - ${chunkPreviewDoc?.file_name ?? ''}`"
      :footer="null"
      width="720px"
    >
      <Spin :spinning="chunkLoading">
        <div
          v-if="chunkList.length === 0 && !chunkLoading"
          class="flex flex-col items-center justify-center py-12"
        >
          <IconifyIcon
            icon="lucide:layers"
            class="mb-2 size-8 text-muted-foreground"
          />
          <p class="text-sm text-muted-foreground">
            {{ $t('admin.knowledgeBase.emptyChunks') }}
          </p>
        </div>
        <div v-else class="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
          <div
            v-for="chunk in chunkList"
            :key="chunk.id"
            class="rounded-lg border border-border/60 transition-colors hover:border-border"
          >
            <div
              class="flex items-center gap-2 border-b border-border/40 bg-accent/20 px-3 py-2 text-xs text-muted-foreground"
            >
              <span
                class="flex size-5 items-center justify-center rounded bg-primary/10 font-mono font-semibold text-primary"
              >
                {{ chunk.chunk_index }}
              </span>
              <span>{{ chunk.char_count }} chars</span>
            </div>
            <div
              class="max-h-40 overflow-y-auto whitespace-pre-wrap px-3 py-2.5 text-sm leading-relaxed text-foreground"
            >
              {{ chunk.content }}
            </div>
          </div>
        </div>
        <div
          v-if="chunkTotal > 10"
          class="mt-4 flex items-center justify-center gap-3 text-xs"
        >
          <Button
            v-if="chunkPage > 1"
            size="small"
            @click="
              chunkPage--;
              loadChunks();
            "
          >
            <template #icon>
              <IconifyIcon icon="lucide:chevron-left" class="size-3.5" />
            </template>
            {{ $t('admin.common.prev') }}
          </Button>
          <span
            class="rounded-md bg-accent/50 px-2.5 py-1 font-mono text-muted-foreground"
          >
            {{ chunkPage }} / {{ Math.ceil(chunkTotal / 10) }}
          </span>
          <Button
            v-if="chunkPage < Math.ceil(chunkTotal / 10)"
            size="small"
            @click="
              chunkPage++;
              loadChunks();
            "
          >
            {{ $t('admin.common.next') }}
            <template #icon>
              <IconifyIcon icon="lucide:chevron-right" class="size-3.5" />
            </template>
          </Button>
        </div>
      </Spin>
    </Modal>
  </Drawer>
</template>

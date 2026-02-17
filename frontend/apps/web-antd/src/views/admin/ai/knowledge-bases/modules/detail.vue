<script lang="ts" setup>
/**
 * 管理端知识库详情抽屉
 *
 * Tab 1: 文档管理（列表+上传+删除+重试+进度）
 * Tab 2: 检索测试
 */
import type {
  AdminKnowledgeDocumentItem,
  AdminSearchResultItem,
} from '#/api/admin/knowledge-bases';

import { computed, onUnmounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  Input,
  message,
  Modal,
  Progress,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import {
  deleteAdminDocumentApi,
  getAdminDocumentListApi,
  getAdminDocumentProgressApi,
  reindexAdminKnowledgeBaseApi,
  retryAdminDocumentApi,
  searchAdminKnowledgeBaseApi,
  uploadAdminDocumentApi,
} from '#/api/admin/knowledge-bases';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

const emit = defineEmits<{ success: [] }>();

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen) {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number; name: string }>();
      if (data) {
        kbId.value = data.id;
        kbName.value = data.name;
        loadDocuments();
      }
    } else {
      stopPolling();
    }
  },
});

// ========== 基础状态 ==========
const kbId = ref(0);
const kbName = ref('');
const activeTab = ref('documents');
const loading = ref(false);

// ========== 文档管理 ==========
const documents = ref<AdminKnowledgeDocumentItem[]>([]);
const docTotal = ref(0);
const docPage = ref(1);
const uploading = ref(false);

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
    startPollingForProcessing();
  } catch {
    // handled by global interceptor
  } finally {
    loading.value = false;
  }
}

const docColumns = computed(() => [
  {
    title: $t('admin.knowledgeBase.document.field.fileName'),
    dataIndex: 'file_name',
    key: 'file_name',
    ellipsis: true,
    width: 200,
  },
  {
    title: $t('admin.knowledgeBase.document.field.fileType'),
    dataIndex: 'file_type',
    key: 'file_type',
    width: 80,
    align: 'center' as const,
  },
  {
    title: $t('admin.knowledgeBase.document.field.fileSize'),
    dataIndex: 'file_size',
    key: 'file_size',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('admin.knowledgeBase.document.field.chunkCount'),
    dataIndex: 'chunk_count',
    key: 'chunk_count',
    width: 80,
    align: 'center' as const,
  },
  {
    title: $t('admin.knowledgeBase.document.field.status'),
    dataIndex: 'status',
    key: 'status',
    width: 120,
    align: 'center' as const,
  },
  {
    title: $t('admin.knowledgeBase.document.field.createdAt'),
    dataIndex: 'created_at',
    key: 'created_at',
    width: 170,
  },
  {
    title: $t('admin.common.operation'),
    key: 'action',
    width: 140,
    align: 'center' as const,
    fixed: 'right' as const,
  },
]);

// 上传文件
async function handleUpload(file: File) {
  uploading.value = true;
  try {
    await uploadAdminDocumentApi(kbId.value, file);
    message.success($t('admin.common.operationSuccess'));
    await loadDocuments();
    emit('success');
  } catch {
    // handled by global interceptor
  } finally {
    uploading.value = false;
  }
  return false;
}

// 删除文档
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

// 重试文档
async function handleRetryDoc(doc: AdminKnowledgeDocumentItem) {
  try {
    await retryAdminDocumentApi(kbId.value, doc.id);
    message.success($t('admin.common.operationSuccess'));
    await loadDocuments();
  } catch {
    // handled
  }
}

// 重新向量化
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

// ========== 轮询处理中文档的进度 ==========
let pollingTimer: ReturnType<typeof setInterval> | null = null;
const docProgress = ref<Record<number, number>>({});

function startPollingForProcessing() {
  stopPolling();
  const processingDocs = documents.value.filter(
    (d) => !['completed', 'error'].includes(d.status),
  );
  if (processingDocs.length === 0) return;

  pollingTimer = setInterval(async () => {
    let hasProcessing = false;
    for (const doc of processingDocs) {
      try {
        const prog = await getAdminDocumentProgressApi(kbId.value, doc.id);
        docProgress.value[doc.id] = prog.progress;
        if (!['completed', 'error'].includes(prog.stage)) {
          hasProcessing = true;
        }
      } catch {
        // ignore
      }
    }
    if (!hasProcessing) {
      stopPolling();
      await loadDocuments();
      emit('success');
    }
  }, 3000);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

onUnmounted(stopPolling);

// ========== 文档状态辅助 ==========
function getDocStatusText(status: string | undefined): string {
  if (!status) return '-';
  return $t(`admin.knowledgeBase.document.status.${status}`);
}

function getDocStatusColor(status: string | undefined): string {
  switch (status) {
    case 'completed': return 'success';
    case 'error': return 'error';
    case 'pending': return 'default';
    case 'parsing':
    case 'chunking':
    case 'embedding': return 'processing';
    default: return 'default';
  }
}

// ========== 检索测试 ==========
const searchQuery = ref('');
const searchLoading = ref(false);
const searchResults = ref<AdminSearchResultItem[]>([]);

async function handleSearch() {
  if (!searchQuery.value.trim()) return;
  searchLoading.value = true;
  try {
    searchResults.value = await searchAdminKnowledgeBaseApi(kbId.value, {
      query: searchQuery.value.trim(),
    });
  } catch {
    // handled
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
    class="w-[800px]"
  >
    <Tabs v-model:activeKey="activeTab">
      <!-- ========== 文档管理 Tab ========== -->
      <Tabs.TabPane key="documents" :tab="$t('admin.knowledgeBase.document.title')">
        <div class="mb-4 flex items-center justify-between">
          <Space>
            <Upload
              :before-upload="handleUpload"
              :show-upload-list="false"
              :multiple="true"
              accept=".pdf,.docx,.txt,.md,.csv"
            >
              <Button type="primary" :loading="uploading">
                <IconifyIcon icon="lucide:upload" class="mr-1 size-4" />
                {{ $t('admin.knowledgeBase.document.upload') }}
              </Button>
            </Upload>
            <Button @click="handleReindex">
              <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
              {{ $t('admin.knowledgeBase.reindex.title') }}
            </Button>
          </Space>
          <span class="text-muted-foreground">
            {{ $t('admin.knowledgeBase.document.uploadHint') }}
          </span>
        </div>

        <Table
          :columns="docColumns"
          :data-source="documents"
          :loading="loading"
          :pagination="{
            current: docPage,
            total: docTotal,
            pageSize: 20,
            onChange: (p: number) => { docPage = p; loadDocuments(); },
          }"
          :scroll="{ x: 800 }"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <!-- 文件大小 -->
            <template v-if="column.key === 'file_size'">
              {{ formatFileSize(record.file_size) }}
            </template>

            <!-- 状态（含进度条） -->
            <template v-else-if="column.key === 'status'">
              <div class="flex flex-col items-center gap-1">
                <Tag :color="getDocStatusColor(record.status)">
                  {{ getDocStatusText(record.status) }}
                </Tag>
                <Progress
                  v-if="!['completed', 'error'].includes(record.status)"
                  :percent="docProgress[record.id] ?? 0"
                  :show-info="false"
                  size="small"
                  class="w-16"
                />
                <Tooltip
                  v-if="record.error_message"
                  :title="record.error_message"
                >
                  <span class="cursor-help text-xs text-destructive">
                    {{ record.error_message?.slice(0, 30) }}...
                  </span>
                </Tooltip>
              </div>
            </template>

            <!-- 创建时间 -->
            <template v-else-if="column.key === 'created_at'">
              <span class="text-muted-foreground">
                {{ formatDate(record.created_at) }}
              </span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <Space>
                <Button
                  v-if="record.status === 'error'"
                  type="link"
                  size="small"
                  @click="handleRetryDoc(record as AdminKnowledgeDocumentItem)"
                >
                  {{ $t('admin.knowledgeBase.document.retry') }}
                </Button>
                <Button
                  type="link"
                  danger
                  size="small"
                  @click="handleDeleteDoc(record as AdminKnowledgeDocumentItem)"
                >
                  {{ $t('admin.knowledgeBase.document.delete') }}
                </Button>
              </Space>
            </template>
          </template>
        </Table>
      </Tabs.TabPane>

      <!-- ========== 检索测试 Tab ========== -->
      <Tabs.TabPane key="search" :tab="$t('admin.knowledgeBase.searchTest.title')">
        <div class="mb-4 flex gap-2">
          <Input
            v-model:value="searchQuery"
            :placeholder="$t('admin.knowledgeBase.searchTest.placeholder')"
            allow-clear
            @press-enter="handleSearch"
          />
          <Button
            type="primary"
            :loading="searchLoading"
            @click="handleSearch"
          >
            {{ $t('admin.knowledgeBase.searchTest.search') }}
          </Button>
        </div>

        <Spin :spinning="searchLoading">
          <Empty
            v-if="searchResults.length === 0 && !searchLoading"
            :description="$t('admin.knowledgeBase.searchTest.noResults')"
          />

          <div v-else class="flex flex-col gap-3">
            <Card
              v-for="(result, idx) in searchResults"
              :key="result.chunk_id"
              size="small"
              class="border-l-4"
              :style="{ borderLeftColor: `hsl(${210 - idx * 15}, 70%, 55%)` }"
            >
              <div class="mb-2 flex items-center justify-between">
                <Tag color="blue">
                  #{{ idx + 1 }}
                </Tag>
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {{ $t('admin.knowledgeBase.searchTest.score') }}:
                    {{ (result.score * 100).toFixed(1) }}%
                  </span>
                  <span>|</span>
                  <span>
                    {{ $t('admin.knowledgeBase.searchTest.source') }}:
                    {{ result.document_name }}
                  </span>
                </div>
              </div>
              <div class="whitespace-pre-wrap text-sm leading-relaxed">
                {{ result.content }}
              </div>
            </Card>
          </div>
        </Spin>
      </Tabs.TabPane>
    </Tabs>
  </Drawer>
</template>
